"""The packs on this machine (D-064, D-065): `pack list --installed`,
`pack create`, `pack import`, `pack remove`.

registry.py talks to the packs repository; this module works on packs/ and
the field templates that ship in the package. Every check a pack gets here is
`load_pack`'s own, so a file this accepts is a file normalize accepts.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from . import languages, registry
from .core.pack import Learned, load_pack
from .runs import BUNDLED_PACKS, installed_packs, learned_file, packs_root

#: The field templates (D-065): a pack with no terms, per field.
TEMPLATES = Path(__file__).resolve().parent / "templates"

#: D-065: `pack list --installed` waits this long for the index, then shows
#: the table without repository updates (the column stays when there is a
#: copy to mark, D-069).
INDEX_WAIT_SECONDS = 3

#: A language code as packs write it: pt-BR, en, es-419.
LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")

BUNDLED, REPOSITORY, MINE = "bundled", "repository", "mine"


class PackFileError(Exception):
    """A pack file that load_pack refuses, said with its path."""


# ------------------------------------------------------------------ templates


@dataclass(frozen=True)
class Template:
    field: str
    classes: tuple[str, ...]
    description: dict[str, str]  # en and pt-BR, one line each
    path: Path
    phonetic_classes: tuple[str, ...] = ()  # D-068; empty: the default


#: The order the menu lists them in; a template not named here comes after,
#: and geral is always last.
ORDER = (
    "financas", "medicina", "direito", "tecnologia", "engenharia",
    "educacao-ciencias", "esportes", "politica-governo", "agro", "geral",
)


def templates() -> dict[str, Template]:
    """Every field template, by field, in ORDER."""
    rank = {field: i for i, field in enumerate(ORDER)}
    found = {}
    key = lambda p: (p.stem == "geral", rank.get(p.stem, len(ORDER)), p.stem)  # noqa: E731
    for path in sorted(TEMPLATES.glob("*.yaml"), key=key):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        found[path.stem] = Template(
            path.stem, tuple(data["classes"]), dict(data["description"]), path,
            tuple(data.get("phonetic_classes") or ()),
        )
    return found


# ------------------------------------------------------------------ checks


def check(path: Path) -> object:
    """The pack at `path` as normalize would load it, or PackFileError.

    A language with no module is allowed here (it matches with the generic
    one, `--allow-generic`); a missing `language:` line is not.
    """
    try:
        return load_pack(path, learned=Learned(), allow_generic=True)
    except languages.LanguageNotFound as error:
        raise PackFileError(str(error)) from None
    except yaml.YAMLError as error:
        raise PackFileError(f"{path} is not YAML: {error}") from None
    except ValueError as error:  # an unlisted class, a bad `classes:` (D-064)
        raise PackFileError(str(error)) from None
    except (KeyError, TypeError, AttributeError) as error:
        raise PackFileError(f"{path} is not a pack (see CONTRIBUTING.md, section 2): {error!r}") from None


def pack_name_problem(name: str) -> str:
    """Why `name` cannot be a pack in packs/, or ""."""
    if name.endswith(".learned"):
        return f"{name!r} is a learned layer's name, not a pack's"
    if not registry.NAME.match(name):
        return f"{name!r}: a pack name is lowercase letters, digits and hyphens, e.g. medicina-ptbr"
    return ""


def bundled_path(name: str) -> Path:
    return BUNDLED_PACKS / f"{name}.yaml"


# ------------------------------------------------------------------ installed


@dataclass(frozen=True)
class Row:
    name: str
    version: str
    language: str
    terms: str
    size_kb: str
    source: str
    path: Path


def source_of(name: str, path: Path) -> str:
    """bundled, repository (as `pack install` wrote it) or mine."""
    if path.parent == BUNDLED_PACKS:
        return BUNDLED
    return MINE if registry.edited(name) or name not in registry.installed() else REPOSITORY


def rows() -> list[Row]:
    out = []
    for name, path in installed_packs().items():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            data = {}
        out.append(Row(
            name=name,
            version=str(data.get("version") or "?"),
            language=str(data.get("language") or "?"),
            terms=str(len(data.get("terms") or ())) if data else "?",
            size_kb=f"{path.stat().st_size / 1024:.1f}",
            source=source_of(name, path),
            path=path,
        ))
    return out


def index_within(seconds: float, url: str | None = None) -> dict | None:
    """The repository index, or None when it is not had within `seconds`.

    In a thread, since urllib's timeout does not cover a name lookup; a
    thread still waiting is left behind (a daemon) and its answer dropped.
    """
    result: dict = {}

    def read():
        try:
            result["index"] = registry.read_index(registry.index_url(url), timeout=seconds)
        except registry.RegistryError:
            pass

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(seconds)
    return result.get("index")


#: D-069, amended: the menu's background check keeps the index this long, in
#: packs/ under the data directory, so a portable install keeps it inside.
INDEX_CACHE_FILE = ".index-cache.json"
INDEX_CACHE_SECONDS = 24 * 60 * 60


def index_cache() -> Path:
    return packs_root() / INDEX_CACHE_FILE


def cached_index(
    url: str | None = None, now: float | None = None, cache: Path | None = None
) -> dict | None:
    """The index as cached under a day ago from the same url, or None."""
    url = registry.index_url(url)
    try:
        data = json.loads((cache or index_cache()).read_text(encoding="utf-8"))
        age = (time.time() if now is None else now) - float(data["fetched_at"])
        if data["url"] != url or not 0 <= age < INDEX_CACHE_SECONDS:
            return None
        return {e["name"]: registry.Entry(**{f: str(e[f]) for f in registry.FIELDS}) for e in data["packs"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def index_cached_within(
    seconds: float, url: str | None = None, cache: Path | None = None
) -> dict | None:
    """The cached index when it is fresh; otherwise `index_within`, cached on success."""
    url = registry.index_url(url)
    cache = cache or index_cache()
    index = cached_index(url, cache=cache)
    if index is not None:
        return index
    index = index_within(seconds, url)
    if index is not None:
        try:
            cache.write_text(json.dumps({
                "url": url, "fetched_at": time.time(), "packs": [asdict(e) for e in index.values()],
            }), encoding="utf-8")
        except OSError:
            pass  # a cache that cannot be written is only a slower next start
    return index


def _version(text: str) -> tuple[int, ...] | None:
    parts = text.split(".")
    return tuple(int(p) for p in parts) if all(p.isdigit() for p in parts) else None


def newer(available: str, have: str) -> bool:
    """Whether `available` is a later version than `have` (numbers only)."""
    a, h = _version(available), _version(have)
    return a is not None and h is not None and a > h


def run_installed(args) -> int:
    table = rows()
    index = index_within(INDEX_WAIT_SECONDS, args.index)
    header = ["name", "version", "language", "terms", "size (KB)", "source"]
    lines = [[r.name, r.version, r.language, r.terms, r.size_kb, r.source] for r in table]
    marked = merges = False
    from .merge import copies, offer_for

    copied = copies()
    if index is not None or copied:
        header.append("update")
        for line, r in zip(lines, table):
            if r.name in copied:  # D-069: a copy is merged, never replaced
                offer = offer_for(r.name, copied[r.name][0], copied[r.name][1], index)
                line.append(f"↑ merge available ({offer.upstream.version})" if offer else "")
                merges |= offer is not None
                continue
            entry = (index or {}).get(r.name)
            update = r.source != MINE and entry is not None and newer(entry.version, r.version)
            line.append(f"↑ update ({entry.version})" if update else "")
            marked |= update
    widths = [max(len(cell) for cell in column) for column in zip(header, *lines, strict=True)]
    for line in (header, *lines):
        print("  ".join(cell.rjust(w) if i in (3, 4) else cell.ljust(w)
                        for i, (cell, w) in enumerate(zip(line, widths, strict=True))).rstrip())
    print()
    if index is None:
        print("(the packs repository was not reached, so its updates are not shown)")
    if marked:
        print("↑ update: the packs repository has a newer version; `transcript-normalizer pack install <name>` gets it")
    if merges:
        print("↑ merge available: upstream is newer than your copy's base; `transcript-normalizer pack merge <name>` merges it, asking about each conflict")
    print(f"your packs: {packs_root()}{os.sep}")
    return 0


# ------------------------------------------------------------------ create


def run_create(args) -> int:
    known = templates()
    template = known.get(args.template)
    if template is None:
        print(f"no template called {args.template!r}; there are: {', '.join(known)}", file=sys.stderr)
        return 1
    problem = pack_name_problem(args.name)
    if not problem and bundled_path(args.name).exists():
        problem = f"{args.name} is the name of a bundled pack; pick another"
    if not problem and not LANGUAGE.match(args.lang):
        problem = f"{args.lang!r}: a language code, e.g. pt-BR or en"
    if problem:
        print(problem, file=sys.stderr)
        return 1
    target = registry.pack_path(args.name)
    if target.exists():
        print(f"{target} is already there; `pack remove {args.name}` first, or pick another name", file=sys.stderr)
        return 1

    registry.write_atomic(target, created_text(template, args.name, args.lang).encode("utf-8"))
    check(target)
    print(f"created {target}")
    print(f"  {template.field}: classes {', '.join(template.classes)}; no terms yet")
    note_language(args.lang)
    return 0


def created_text(template: Template, name: str, lang: str) -> str:
    """The new pack: the template's fields, with its name and language."""
    quoted = json.dumps  # a JSON string is a YAML string
    return "".join([
        f"# {name}: made from the {template.field} template (D-065).\n",
        "# Add terms under `terms:`; CONTRIBUTING.md, section 2, says how.\n",
        "# pessoa, organizacao, sigla and unidade are allowed in every pack (D-064).\n",
        f"name: {name}\n",
        f"field: {template.field}\n",
        "description:\n",
        *(f"  {code}: {quoted(line, ensure_ascii=False)}\n" for code, line in template.description.items()),
        f"language: {lang}\n",
        "version: 0.1.0\n",
        f"classes: [{', '.join(template.classes)}]\n",
        *([f"phonetic_classes: [{', '.join(template.phonetic_classes)}]\n"] if template.phonetic_classes else []),
        "terms: []\n",
    ])


def note_language(code: str) -> None:
    try:
        languages.for_code(code)
    except languages.LanguageNotFound:
        print(
            f"  no language module for {code}: it is matched with the generic one, no "
            "inflections and no unit rules (the menu does this; a command needs --allow-generic, D-033)"
        )


# ------------------------------------------------------------------ import


def run_import(args) -> int:
    source = Path(args.file).expanduser()
    if not source.is_file():
        print(f"no file at {source}", file=sys.stderr)
        return 1
    name = source.stem
    problem = pack_name_problem(name)
    if problem:
        print(f"{problem}; rename the file to <name>.yaml", file=sys.stderr)
        return 1
    try:
        pack = check(source)
    except PackFileError as error:
        print(f"not imported: {error}", file=sys.stderr)
        return 1
    target = registry.pack_path(name)
    if target.exists() and not args.force:
        print(f"{target} is already there; pass --force to replace it", file=sys.stderr)
        return 1
    registry.write_atomic(target, source.read_bytes())
    print(f"imported {name} into {target}: {len(pack.terms)} terms, language {pack.language_code}")
    if bundled_path(name).exists():
        print(f"  it is used instead of the bundled {name} (D-017); `pack remove {name}` undoes that")
    note_language(pack.language_code)
    return 0


# ------------------------------------------------------------------ remove


def run_remove(args) -> int:
    name = args.name
    target = registry.pack_path(name)
    if pack_name_problem(name) or not target.is_file():
        if bundled_path(name).exists():
            print(f"{name} is bundled with the program and cannot be removed", file=sys.stderr)
        else:
            print(f"no pack called {name} in {packs_root()}{os.sep}", file=sys.stderr)
        return 1
    target.unlink()
    record = registry.installed()
    if record.pop(name, None) is not None:
        registry.write_installed(record)
    print(f"removed {target}")
    if bundled_path(name).exists():
        print(f"  the bundled {name} is used again")
    learned = learned_file(target)
    if learned.exists():
        print(f"  kept {learned}: what your reviews taught; delete it by hand to forget it")
    return 0


# ------------------------------------------------------------------ arguments


def add_arguments(commands) -> None:
    """`pack create | import | remove` beside registry's list, install, update."""
    creating = commands.add_parser(
        "create", help="a new pack in packs/, with no terms, from a field template (D-065)"
    )
    creating.add_argument("--template", required=True, metavar="FIELD", help=f"one of: {', '.join(templates())}")
    creating.add_argument("--name", required=True, help="the pack's name, e.g. medicina-ptbr")
    creating.add_argument("--lang", required=True, metavar="CODE", help="its language, e.g. pt-BR")
    creating.set_defaults(run=run_create)

    importing = commands.add_parser("import", help="check a pack file and copy it into packs/")
    importing.add_argument("file", help="a pack .yaml; its file name is the pack's name")
    importing.add_argument("--force", action="store_true", help="replace a pack of the same name in packs/")
    importing.set_defaults(run=run_import)

    removing = commands.add_parser("remove", help="delete a pack from packs/ (never a bundled one)")
    removing.add_argument("name", help="the pack's name, as `pack list --installed` shows it")
    removing.set_defaults(run=run_remove)
