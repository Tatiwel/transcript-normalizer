"""`transcript-normalizer pack propose` (D-056): give back what the review taught;
`pack propose --whole <name>` (D-067): propose a whole pack.

The learned layer (D-013) is personal and never merged into a pack by the tool.
This reads it, keeps what the pack does not already have, shows it (term, form
and decision; never the transcript), and on a yes writes it to
`contributions/<pack>-<date>.yaml` and opens a prefilled issue on the packs
repository (D-055), where the pack's maintainers decide. Nothing is sent by the
tool itself: the issue is the user's to submit.
"""

from __future__ import annotations

import sys
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

from .core.pack import Learned, load_learned, load_pack
from .runs import base_dir, default_pack, installed_packs, learned_file
from .registry import REPOSITORY

CONTRIBUTIONS_DIR = "contributions"
ISSUE_URL = f"{REPOSITORY}/issues/new"
#: Browsers and GitHub turn away much longer links; past this the file is attached by hand.
MAX_URL = 8000

VARIANT, ALIAS, REJECTED = "variant", "alias", "rejected"


@dataclass(frozen=True)
class Item:
    term: str
    form: str
    decision: str  # variant | alias | rejected
    decided: str  # ISO date

    def line(self) -> str:
        if self.decision == REJECTED:
            return f"  - rejected  {self.form}  (not {self.term})"
        return f"  + {self.decision:8s}  {self.form} -> {self.term}"


def items(pack_path: Path, learned: Learned | None = None) -> list[Item]:
    """What the learned layer has that the pack does not, in the layer's order."""
    pack = load_pack(pack_path, learned=Learned())
    learned = learned if learned is not None else load_learned(learned_file(pack_path))
    known = {
        t.term: {pack.normalize(s) for s in (t.term, *t.aliases, *t.variants)} for t in pack.terms
    }
    out = [
        Item(term, c.variant, VARIANT, c.decided)
        for term, confirmations in learned.confirmed.items()
        for c in confirmations
        if pack.normalize(c.variant) not in known.get(term, ())
    ]
    out += [
        Item(term, a.alias, ALIAS, a.decided)
        for term, entries in learned.aliases.items()
        for a in entries
        if pack.normalize(a.alias) not in known.get(term, ())
    ]
    out += [Item(r.term, r.text, REJECTED, r.decided) for r in learned.rejected]
    return out


def contribution_yaml(name: str, version: str, found: list[Item], today: str) -> str:
    from .helptext import version as engine_version

    data = {
        "pack": name,
        "pack_version": version,
        "engine": engine_version(),
        "date": today,
        "entries": [
            {"term": i.term, "form": i.form, "decision": i.decision, "decided": i.decided} for i in found
        ],
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def issue_url(name: str, path: Path, text: str, count: int) -> str:
    title = f"{name}: {count} entr{'y' if count == 1 else 'ies'} from a review"
    intro = (
        f"Proposed with `transcript-normalizer pack propose`: what one user's reviews taught the "
        f"tool about **{name}**, beyond the pack. Term, form and decision only; no transcript.\n\n"
        "`variant`: the recognizer's mishearing of the term. `alias`: the term, said that way. "
        "`rejected`: not the term.\n\n"
    )
    for body in (f"{intro}```yaml\n{text}```\n", f"{intro}The file is too long for a link: attach `{path.name}`.\n"):
        url = f"{ISSUE_URL}?{urllib.parse.urlencode({'title': title, 'body': body})}"
        if len(url) <= MAX_URL:
            return url
    return url


def resolve(name: str | None) -> Path | None:
    if name is None:
        return default_pack()
    return installed_packs().get(Path(name).stem)


def open_issue(url: str) -> None:
    opened = False
    try:
        opened = webbrowser.open(url)
    except Exception:  # no browser here is a fallback, not a failure
        opened = False
    if opened:
        print("a prefilled issue is open in your browser; check it and submit it there.")
    else:
        print(f"open this link to submit it as an issue:\n{url}")


# ------------------------------------------------------------------ a whole pack (D-067)

#: How many terms the summary shows.
EXAMPLES = 5


def pack_summary(name: str, data: dict) -> list[str]:
    """What the user sees before a whole pack is proposed: field, classes,
    number of terms and five examples."""
    from .packedit import term_line

    terms = data.get("terms") or []
    description = data.get("description")
    if isinstance(description, dict):
        description = description.get("en") or next(iter(description.values()), "")
    lines = [
        f"  pack      {name} {data.get('version') or '?'} ({data.get('language') or '?'})",
        f"  field     {data.get('field') or '(not recorded)'}" + (f": {description}" if description else ""),
        f"  classes   {', '.join(data.get('classes') or ['(the eight of D-021)'])}",
        f"  terms     {len(terms)}",
    ]
    lines += [f"    {term_line(t)}" for t in terms[:EXAMPLES]]
    if len(terms) > EXAMPLES:
        lines.append(f"    … and {len(terms) - EXAMPLES} more")
    return lines


def whole_issue_url(title: str, path: Path, text: str, summary: list[str]) -> str:
    intro = (
        f"Proposed with `transcript-normalizer pack propose --whole`: the whole pack, as one "
        "user has it. The pack file only; no transcript.\n\n```\n" + "\n".join(summary) + "\n```\n\n"
    )
    for body in (
        f"{intro}<details><summary>{path.name}</summary>\n\n```yaml\n{text}```\n\n</details>\n",
        f"{intro}The pack is too long for a link: attach `{path.name}` (written to {path}).\n",
    ):
        url = f"{ISSUE_URL}?{urllib.parse.urlencode({'title': title, 'body': body})}"
        if len(url) <= MAX_URL:
            return url
    return url


def known_to_repository(name: str, path: Path) -> bool:
    """Whether the packs repository has a pack of this name: from its index
    when it answers within a few seconds, else from where the pack came from."""
    from .packfiles import INDEX_WAIT_SECONDS, MINE, index_within, source_of

    index = index_within(INDEX_WAIT_SECONDS)
    if index is not None:
        return name in index
    return source_of(name, path) != MINE


# ------------------------------------------------------------------ a copy's diff (D-069)


def diff_against_base(base: dict, mine: dict) -> dict:
    """What a copy changed since its base: new terms, added forms, removals, class changes."""
    from .packedit import language_of

    n = language_of(mine).normalize
    B = {n(str(t["term"])): t for t in base.get("terms") or []}
    M = {n(str(t["term"])): t for t in mine.get("terms") or []}
    out = {"new_terms": [], "added": [], "removed": [], "class_changed": []}
    for k, m in M.items():
        b = B.get(k)
        if b is None:
            out["new_terms"].append(m)
            continue
        for kind, key in (("alias", "aliases"), ("variant", "variants")):
            had = {n(str(x)) for x in b.get(key) or []}
            has = {n(str(x)) for x in m.get(key) or []}
            out["added"] += [{"term": m["term"], kind: x} for x in m.get(key) or [] if n(str(x)) not in had]
            out["removed"] += [{"term": m["term"], kind: x} for x in b.get(key) or [] if n(str(x)) not in has]
        if b.get("class") != m.get("class"):
            out["class_changed"].append({"term": m["term"], "from": b.get("class"), "to": m.get("class")})
    out["removed"] += [{"term": b["term"]} for k, b in B.items() if k not in M]
    return {k: v for k, v in out.items() if v}


def diff_lines(diff: dict) -> list[str]:
    from .packedit import term_line

    lines = [f"  + term     {term_line(t)}" for t in diff.get("new_terms", [])]
    for item in diff.get("added", []):
        kind = "alias" if "alias" in item else "variant"
        lines.append(f"  + {kind:8s} {item[kind]} -> {item['term']}")
    for item in diff.get("removed", []):
        kind = "alias" if "alias" in item else "variant" if "variant" in item else ""
        lines.append(f"  - {kind:8s} {item[kind]}  (of {item['term']})" if kind else f"  - term     {item['term']}")
    for item in diff.get("class_changed", []):
        lines.append(f"  ~ class    {item['term']}: {item['from']} -> {item['to']}")
    return lines


def run_propose_diff(name: str, path: Path, data: dict, base: dict, base_ref: tuple[str, str]) -> int:
    """D-069: a copy with a base proposes what it changed, never the whole file."""
    import getpass

    from . import prompts
    from .helptext import version as engine_version

    diff = diff_against_base(base, data)
    if not diff:
        print(f"nothing to contribute: {name} is as its base {base_ref[0]}@{base_ref[1]}")
        return 0
    additions = len(diff.get("new_terms", [])) + len(diff.get("added", []))
    removals = len(diff.get("removed", []))
    user = getpass.getuser()
    title = f"{name}: {additions} addition{'' if additions == 1 else 's'}" + (
        f", {removals} removal{'' if removals == 1 else 's'}" if removals else "") + f" from {user}"
    print(f'What would be proposed to the packs repository, as "{title}":')
    print(f"  the changes in your copy since {base_ref[0]}@{base_ref[1]}:")
    for line in diff_lines(diff):
        print(line)
    print("Only these changes are sent, never the whole file and never a transcript.")
    if not prompts.confirm("Propose these changes?", default=False):
        print("nothing written.")
        return 0
    version = str(data.get("version") or "0.0.0")
    text = yaml.safe_dump({"pack": name, "based_on": f"{base_ref[0]}@{base_ref[1]}", "pack_version": version,
                           "engine": engine_version(), "date": date.today().isoformat(), **diff},
                          allow_unicode=True, sort_keys=False)
    target = base_dir() / CONTRIBUTIONS_DIR / f"{name}-{version}-diff.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"written to {target}")
    intro = (f"Proposed with `transcript-normalizer pack propose --whole`: what one user's copy of **{name}** "
             f"changed since {base_ref[1]}. The changes only; no transcript.\n\n")
    url = ""
    for body in (f"{intro}```yaml\n{text}```\n", f"{intro}Too long for a link: attach `{target.name}`.\n"):
        url = f"{ISSUE_URL}?{urllib.parse.urlencode({'title': title, 'body': body})}"
        if len(url) <= MAX_URL:
            break
    open_issue(url)
    return 0


def run_propose_whole(name: str) -> int:
    from . import prompts
    from .merge import base_path, based_on

    path = installed_packs().get(name)
    if path is None:
        print(f"no pack called {name}; installed: {', '.join(installed_packs())}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    base_ref = based_on(data)
    if base_ref and base_path(*base_ref).exists():
        base = yaml.safe_load(base_path(*base_ref).read_text(encoding="utf-8")) or {}
        return run_propose_diff(name, path, data, base, base_ref)
    version = str(data.get("version") or "0.0.0")
    summary = pack_summary(name, data)
    title = f"{'Update' if known_to_repository(name, path) else 'New pack'}: {name}"
    print(f"What would be proposed to the packs repository, as \"{title}\":")
    for line in summary:
        print(line)
    print(f"The whole file is sent, as it is in {path}; never a transcript.")
    if not prompts.confirm("Propose this pack?", default=False):
        print("nothing written.")
        return 0
    target = base_dir() / CONTRIBUTIONS_DIR / f"{name}-{version}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"written to {target}")
    open_issue(whole_issue_url(title, target, text, summary))
    return 0


def run_propose(args) -> int:
    from . import prompts

    if args.whole:
        return run_propose_whole(args.whole)
    pack_path = resolve(args.pack)
    if pack_path is None:
        print(
            f"no pack called {args.pack}; installed: {', '.join(installed_packs())}",
            file=sys.stderr,
        )
        return 1
    name = pack_path.stem
    layer = learned_file(pack_path)
    found = items(pack_path)
    if not found:
        print(f"nothing to contribute: {layer} has nothing the pack {name} does not already have")
        return 0

    version = load_pack(pack_path, learned=Learned()).version
    print(f"What would be contributed to {name} {version} ({len(found)}), from {layer}:")
    for item in found:
        print(item.line())
    print("Only these lines are sent: the term, the form and your decision, never the transcript.")
    if not prompts.confirm("Contribute these?", default=False):
        print("nothing written.")
        return 0

    today = date.today().isoformat()
    text = contribution_yaml(name, version, found, today)
    path = base_dir() / CONTRIBUTIONS_DIR / f"{name}-{today}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"written to {path}")

    open_issue(issue_url(name, path, text, len(found)))
    return 0


def add_arguments(commands) -> None:
    proposing = commands.add_parser(
        "propose",
        help="contribute what your reviews taught the tool to the packs repository (D-056)",
        description=__doc__.split("\n\n")[1],
    )
    proposing.add_argument("--pack", metavar="NAME", help="the pack. default: the default pack")
    proposing.add_argument(
        "--whole", metavar="NAME",
        help="propose the whole pack instead, as a new pack or an update (D-067)",
    )
    proposing.set_defaults(run=run_propose)
