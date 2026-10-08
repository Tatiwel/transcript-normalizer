"""Editing a pack (D-066): `pack copy`, `add-term`, `edit-term`, `remove-term`,
`show` and `export`.

Only a pack of the user's own (`mine`, D-065) is edited; a bundled pack or
one from the repository is read-only, and `pack copy` makes it the user's.
Every write is checked as normalize loads the pack (D-064, D-068) before it
replaces the file, the forms it adds are checked against D-005 (no variant
under 3 letters) and D-032 (a warning for an ordinary word), and each saved
change bumps the pack's patch version.

A pack is YAML. The comment block at the top of the file is kept; comments
inside it are not, because the file is written again from its data.
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

import yaml

from . import languages, packfiles, registry
from .core.pack import pack_classes
from .runs import base_dir, installed_packs

#: D-005: a variant this short matches too much, even by exact equality.
MIN_VARIANT_LETTERS = 3
#: `pack show`: terms per page.
PAGE_SIZE = 20
#: The keys a written pack starts with, in this order; the rest follow.
KEY_ORDER = ("name", "field", "description", "language", "version", "classes", "phonetic_classes")


class EditError(Exception):
    """A change refused, with the reason; nothing was written."""


# ------------------------------------------------------------------ the file


class _Dumper(yaml.SafeDumper):
    """Lists of scalars in flow style (`variants: [a, b]`), and the terms
    indented under `terms:`, as packs are written by hand."""

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _list(dumper, items):
    flow = all(not isinstance(i, (list, dict)) for i in items)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=flow)


_Dumper.add_representer(list, _list)


def header(text: str) -> str:
    """The comment block at the top of a pack: kept when it is written again."""
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith("#") or not line.strip():
            lines.append(line)
        else:
            break
    return "".join(lines)


def ordered(data: dict) -> dict:
    first = {k: data[k] for k in KEY_ORDER if k in data}
    rest = {k: v for k, v in data.items() if k not in first and k not in ("terms", "unit_rules")}
    tail = {k: data[k] for k in ("terms", "unit_rules") if k in data}
    return {**first, **rest, **tail}


def dump(head: str, data: dict) -> str:
    body = yaml.dump(ordered(data), Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=math.inf)
    return head + body


def bump(version) -> str:
    """The next patch version: 0.1.0 -> 0.1.1; anything else starts at 0.1.0."""
    parts = str(version or "").split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"
    return "0.1.0"


# ------------------------------------------------------------------ which pack


def own_pack(name: str) -> Path:
    """packs/<name>.yaml, if it is the user's to edit; else EditError."""
    path = installed_packs().get(name)
    if path is None:
        raise EditError(f"no pack called {name}; `pack list --installed` shows them")
    source = packfiles.source_of(name, path)
    if source != packfiles.MINE:
        raise EditError(
            f"{name} is a {source} pack, read-only; `transcript-normalizer pack copy {name}` "
            "makes it your own to edit"
        )
    return path


def language_of(data: dict):
    try:
        return languages.for_code(str(data.get("language") or ""), allow_generic=True)
    except languages.LanguageNotFound:
        return languages.generic


# ------------------------------------------------------------------ forms


def variant_problem(form: str, language) -> str:
    """D-005: why `form` cannot be a variant, or ""."""
    letters = language.normalize(form).replace(" ", "")
    if len(letters) < MIN_VARIANT_LETTERS:
        return (
            f"variant {form!r} refused: under {MIN_VARIANT_LETTERS} letters, it would match "
            "too many words even by exact equality (D-005)"
        )
    return ""


def variant_warning(form: str, language) -> str:
    """D-032: a warning when every word of `form` is an ordinary word."""
    common = getattr(language, "common_words", frozenset())
    words = language.normalize(form).split()
    if words and all(w in common for w in words):
        return (
            f"warning: {form!r} is made of ordinary words; as a variant it is corrected wherever "
            "it appears, also where it means something else (D-032)"
        )
    return ""


SINGULAR = {"aliases": "alias", "variants": "variant"}


def forms_of(term: dict) -> list[str]:
    return [term["term"], *(term.get("aliases") or []), *(term.get("variants") or [])]


def find_term(data: dict, name: str, language, by_alias: bool = False) -> dict | None:
    """The term called `name` (or, with `by_alias`, having it as an alias)."""
    target = language.normalize(name)
    for term in data.get("terms") or []:
        names = [term["term"], *((term.get("aliases") or []) if by_alias else [])]
        if any(language.normalize(str(n)) == target for n in names):
            return term
    return None


def owner_of(data: dict, form: str, language) -> dict | None:
    target = language.normalize(form)
    for term in data.get("terms") or []:
        if any(language.normalize(str(f)) == target for f in forms_of(term)):
            return term
    return None


def add_forms(data: dict, term: dict, aliases, variants, language) -> list[str]:
    """Add aliases and variants to `term`; what was done, line by line. A form
    already in this term is skipped; one in another term is an EditError."""
    said = []
    for kind, forms in (("aliases", aliases), ("variants", variants)):
        for form in forms or ():
            form = form.strip()
            if not form:
                continue
            if kind == "variants":
                problem = variant_problem(form, language)
                if problem:
                    raise EditError(problem)
            owner = owner_of(data, form, language)
            if owner is term:
                said.append(f"  {form!r} is already a form of {term['term']}; skipped")
                continue
            if owner is not None:
                raise EditError(f"{form!r} is already a form of {owner['term']}; one form, one term")
            term.setdefault(kind, []).append(form)
            said.append(f"  + {SINGULAR[kind]:8s} {form} -> {term['term']}")
            if kind == "variants":
                warning = variant_warning(form, language)
                if warning:
                    said.append(f"  {warning}")
    return said


# ------------------------------------------------------------------ saving


def save(path: Path, head: str, data: dict) -> str:
    """Check the changed pack as normalize loads it, then write it with the
    next patch version. Returns that version."""
    data["version"] = bump(data.get("version"))
    text = dump(head, data)
    trial = path.with_name(f".{path.stem}.check.yaml")
    try:
        trial.write_text(text, encoding="utf-8")
        packfiles.check(trial)
    except packfiles.PackFileError as error:
        raise EditError(str(error).replace(str(trial), str(path))) from None
    finally:
        trial.unlink(missing_ok=True)
    registry.write_atomic(path, text.encode("utf-8"))
    return data["version"]


def read(path: Path) -> tuple[str, dict]:
    text = path.read_text(encoding="utf-8")
    return header(text), yaml.safe_load(text) or {}


def edit(args, change) -> int:
    """Read the user's pack, apply `change(data, language) -> lines`, save."""
    try:
        path = own_pack(args.pack)
        head, data = read(path)
        data.setdefault("terms", [])
        lines = change(data, language_of(data))
        version = save(path, head, data)
    except EditError as error:
        print(f"nothing saved: {error}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    print(f"saved {path} ({args.pack} {version})")
    return 0


def check_class(data: dict, klass: str | None) -> None:
    """D-064: `klass` is one the pack allows (its own, or a common one)."""
    if klass is None:
        return
    allowed = pack_classes(data, Path("pack"))
    if klass not in allowed:
        raise EditError(f"class {klass!r} is not one of this pack's classes ({', '.join(allowed)}) (D-064)")


# ------------------------------------------------------------------ commands


def run_copy(args) -> int:
    """Make a bundled or repository pack the user's own, under the same name."""
    path = installed_packs().get(args.name)
    if path is None:
        print(f"no pack called {args.name}", file=sys.stderr)
        return 1
    source = packfiles.source_of(args.name, path)
    target = registry.pack_path(args.name)
    if source == packfiles.MINE:
        print(f"{args.name} is already yours: {path}")
        return 0
    if source == packfiles.BUNDLED:
        registry.write_atomic(target, path.read_bytes())
        print(f"copied the bundled {args.name} to {target}; that copy is used from now on (D-017)")
    else:  # from the repository: stop tracking it, so pack update leaves it alone
        record = registry.installed()
        record.pop(args.name, None)
        registry.write_installed(record)
        print(f"{target} is yours now; `pack update` no longer replaces it")
    return 0


def run_add_term(args) -> int:
    def change(data, language):
        check_class(data, args.klass)
        existing = find_term(data, args.term, language, by_alias=True)
        if existing is not None:
            if args.klass and existing.get("class") and existing["class"] != args.klass:
                raise EditError(
                    f"{existing['term']} is already in the pack as {existing['class']}; "
                    "`pack edit-term --class` changes its class"
                )
            return [f"{existing['term']} is in the pack; adding to it:",
                    *add_forms(data, existing, args.alias, args.variant, language)]
        owner = owner_of(data, args.term, language)
        if owner is not None:
            raise EditError(f"{args.term!r} is already a variant of {owner['term']}")
        term = {"term": args.term.strip()}
        if args.klass:
            term["class"] = args.klass
        data["terms"].append(term)
        return [f"+ term     {term['term']}" + (f" ({args.klass})" if args.klass else ""),
                *add_forms(data, term, args.alias, args.variant, language)]

    return edit(args, change)


def run_edit_term(args) -> int:
    def change(data, language):
        term = find_term(data, args.term, language)
        if term is None:
            raise EditError(f"no term called {args.term!r} in {args.pack}")
        lines = []
        if args.rename:
            other = owner_of(data, args.rename, language)
            if other is not None and other is not term:
                raise EditError(f"{args.rename!r} is already a form of {other['term']}")
            lines.append(f"  term     {term['term']} -> {args.rename}")
            term["term"] = args.rename.strip()
        if args.klass:
            check_class(data, args.klass)
            lines.append(f"  class    {term.get('class') or '-'} -> {args.klass}")
            term["class"] = args.klass
        for kind, forms in (("aliases", args.remove_alias), ("variants", args.remove_variant)):
            for form in forms or ():
                kept = [f for f in term.get(kind) or [] if language.normalize(f) != language.normalize(form)]
                if len(kept) == len(term.get(kind) or []):
                    raise EditError(f"{form!r} is not one of {term['term']}'s {kind}")
                term[kind] = kept
                lines.append(f"  - {SINGULAR[kind]:8s} {form}")
        lines += add_forms(data, term, args.add_alias, args.add_variant, language)
        if not lines:
            raise EditError("nothing to change; see `pack edit-term --help`")
        return [f"{term['term']}:", *lines]

    return edit(args, change)


def run_remove_term(args) -> int:
    def change(data, language):
        term = find_term(data, args.term, language)
        if term is None:
            raise EditError(f"no term called {args.term!r} in {args.pack}")
        data["terms"].remove(term)
        return [f"- term     {term['term']}"]

    return edit(args, change)


def term_line(term: dict) -> str:
    parts = [term["term"], f"({term['class']})" if term.get("class") else ""]
    if term.get("aliases"):
        parts.append(f"aliases: {', '.join(map(str, term['aliases']))}")
    if term.get("variants"):
        parts.append(f"variants: {', '.join(map(str, term['variants']))}")
    return "  ".join(p for p in parts if p)


def run_show(args) -> int:
    path = installed_packs().get(args.pack)
    if path is None:
        print(f"no pack called {args.pack}", file=sys.stderr)
        return 1
    _, data = read(path)
    language = language_of(data)
    terms = data.get("terms") or []
    if args.search:
        needle = language.normalize(args.search)
        terms = [t for t in terms if any(needle in language.normalize(str(f)) for f in forms_of(t))]
    total = len(terms)
    if args.page:
        start = (args.page - 1) * PAGE_SIZE
        terms = terms[start : start + PAGE_SIZE]
    else:
        start = 0
    what = f"matching {args.search!r}" if args.search else "terms"
    if not total:
        print(f"{args.pack}: no {what}")
        return 0
    print(f"{args.pack}: {total} {what}" + (f", {start + 1}-{start + len(terms)}" if args.page else ""))
    for term in terms:
        print(f"  {term_line(term)}")
    return 0


def export_target(name: str, version: str, to: str | None) -> Path:
    file_name = f"{name}-{version}.yaml"
    if to is None:
        return base_dir() / file_name
    target = Path(to).expanduser()
    return target if target.suffix.lower() in (".yaml", ".yml") else target / file_name


def run_export(args) -> int:
    path = installed_packs().get(args.name)
    if path is None:
        print(f"no pack called {args.name}", file=sys.stderr)
        return 1
    _, data = read(path)
    version = str(data.get("version") or "0.0.0")
    target = export_target(args.name, version, args.to)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)
    print(f"exported {args.name} {version} to {target}")
    return 0


# ------------------------------------------------------------------ arguments


def add_arguments(commands) -> None:
    copying = commands.add_parser("copy", help="make a bundled or repository pack your own, to edit (D-066)")
    copying.add_argument("name")
    copying.set_defaults(run=run_copy)

    adding = commands.add_parser("add-term", help="add a term, or forms to a term, in one of your packs")
    adding.add_argument("pack")
    adding.add_argument("term", help="the canonical form, as it should be written")
    adding.add_argument("--class", dest="klass", metavar="CLASS", help="one of the pack's classes")
    adding.add_argument("--alias", action="append", metavar="FORM", help="another correct name; repeatable")
    adding.add_argument("--variant", action="append", metavar="FORM", help="a mishearing; repeatable")
    adding.set_defaults(run=run_add_term)

    editing = commands.add_parser("edit-term", help="change a term of one of your packs")
    editing.add_argument("pack")
    editing.add_argument("term")
    editing.add_argument("--rename", metavar="TERM")
    editing.add_argument("--class", dest="klass", metavar="CLASS")
    for flag in ("add-alias", "add-variant", "remove-alias", "remove-variant"):
        editing.add_argument(f"--{flag}", action="append", metavar="FORM", help="repeatable")
    editing.set_defaults(run=run_edit_term)

    removing = commands.add_parser("remove-term", help="remove a term from one of your packs")
    removing.add_argument("pack")
    removing.add_argument("term")
    removing.set_defaults(run=run_remove_term)

    showing = commands.add_parser("show", help="a pack's terms, with their forms")
    showing.add_argument("pack")
    showing.add_argument("--search", metavar="TEXT", help="only terms with a form containing TEXT")
    showing.add_argument("--page", type=int, default=0, metavar="N", help=f"page N, {PAGE_SIZE} terms each")
    showing.set_defaults(run=run_show)

    exporting = commands.add_parser("export", help="write a pack to <name>-<version>.yaml")
    exporting.add_argument("name")
    exporting.add_argument("--to", metavar="PATH", help="a folder or a .yaml file. default: the data folder")
    exporting.set_defaults(run=run_export)

