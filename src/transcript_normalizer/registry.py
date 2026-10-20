"""The packs repository (D-055): `pack list`, `pack install`, `pack update`.

Domain content lives in its own repository, one directory per pack, with an
`index.json` that names every pack, its version and the sha256 of its file.
This module reads that index and installs packs into the user's `packs/`, where
`--pack`, the menu and `default_pack` already look (D-017, D-054). urllib only:
no new dependency, and a `file://` index works the same, which is what the
tests use. The packs that ship inside the program (financas-ptbr, D-043) are
included, not installed (D-088): `pack install` copies one into packs/ as it
would a download, offline, with the same record, so `pack update` and `pack
merge` treat it the same.

An entry may name the oldest engine that understands its pack, `min_engine`
(D-087): an older engine lists it with the reason and never installs it. A
name may have several entries, one per version: this engine takes the newest
it can use. Engines up to 0.6.5 keep the last entry of a name and ignore
`min_engine`, so the index lists the newest first and the one for them last.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import engine
from .runs import included_packs, installed_packs, packs_root

INDEX_URL = "https://raw.githubusercontent.com/Tatiwel/transcript-normalizer-packs/main/index.json"
#: Moves the index: a fork, a mirror, or a `file://` index in the tests.
INDEX_ENV = "TRANSCRIPT_NORMALIZER_PACKS_INDEX"
REPOSITORY = "https://github.com/Tatiwel/transcript-normalizer-packs"

#: What `pack install` wrote, so `pack update` can tell a pack edited by hand.
INSTALLED_FILE = "installed.json"

TIMEOUT_SECONDS = 20
#: A pack name is a file name in packs/, so nothing that could leave it.
NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FIELDS = ("name", "version", "language", "description", "path", "sha256")
#: D-087: fields an entry may leave out, and their value when it does.
OPTIONAL = {"min_engine": ""}
#: Where a newer engine is had, for the message that one is needed.
RELEASES = "https://github.com/Tatiwel/transcript-normalizer/releases"


class RegistryError(Exception):
    """The index or a pack could not be had, or is not what it should be."""


@dataclass(frozen=True)
class Entry:
    """One pack in the index."""

    name: str
    version: str
    language: str
    description: str
    path: str  # relative to the index
    sha256: str
    min_engine: str = ""  # D-087: the oldest engine that understands the pack
    #: D-087: a newer version of the pack, in the index, that this engine cannot use.
    held: Entry | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_raw(cls, raw: dict) -> "Entry":
        """One entry of index.json (or of the menu's cache of it)."""
        optional = {f: str(raw[f]) for f in OPTIONAL if raw.get(f) not in (None, "")}
        return cls(**{f: str(raw[f]) for f in FIELDS}, **optional)

    def too_new(self) -> bool:
        """Whether its pack needs a newer engine than this one."""
        return engine.too_old_for(self.min_engine)

    def needs(self) -> str:
        return engine.needs(self.name, self.version, self.min_engine)

    @property
    def blocked(self) -> Entry | None:
        """The version of this pack this engine cannot have: itself, or a newer one."""
        return self if self.too_new() else self.held

    def raw(self) -> list[dict]:
        """As index.json writes it, with the held-back version after it (for the cache)."""
        out = {f: getattr(self, f) for f in FIELDS}
        out.update({f: getattr(self, f) for f in OPTIONAL if getattr(self, f)})
        return [out] + (self.held.raw() if self.held is not None else [])


def choose(entries: list[Entry]) -> dict[str, Entry]:
    """By name, the newest version this engine can use, with the newest it
    cannot as `held`; when it can use none, the newest (D-087). Between two
    entries of the same version the later wins, as it always did."""
    by_name: dict[str, list[tuple[int, Entry]]] = {}
    for i, e in enumerate(entries):
        by_name.setdefault(e.name, []).append((i, e))

    def newest(found: list[tuple[int, Entry]]) -> Entry | None:
        return max(found, key=lambda x: (engine.numbers(x[1].version), x[0]))[1] if found else None

    out = {}
    for name, found in by_name.items():
        usable = [x for x in found if not x[1].too_new()]
        best = newest(usable) or newest(found)
        held = newest([x for x in found if x[1].too_new()
                       and engine.numbers(x[1].version) > engine.numbers(best.version)])
        out[name] = replace(best, held=held) if held is not None else best
    return out


def index_url(override: str | None = None) -> str:
    return override or os.environ.get(INDEX_ENV) or INDEX_URL


def fetch(url: str, timeout: float = TIMEOUT_SECONDS) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "transcript-normalizer"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise RegistryError(f"{url}: HTTP {error.code}") from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        raise RegistryError(f"could not reach {url}: {reason}") from None


def read_index(url: str, timeout: float = TIMEOUT_SECONDS) -> dict[str, Entry]:
    """Every pack the index names, by name."""
    try:
        data = json.loads(fetch(url, timeout).decode("utf-8"))
        entries = [Entry.from_raw(raw) for raw in data["packs"]]
    except (ValueError, KeyError, TypeError) as error:
        raise RegistryError(f"{url} is not a packs index: {error}") from None
    bad = [e.name for e in entries if not NAME.match(e.name)]
    if bad:
        raise RegistryError(f"{url}: not a pack name: {', '.join(bad)}")
    return choose(entries)


def installable(entries: dict[str, Entry]) -> dict[str, Entry]:
    """The entries this engine can use: none whose min_engine is newer (D-087)."""
    return {name: e for name, e in entries.items() if not e.too_new()}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(entry: Entry, url: str) -> bytes:
    """The pack's file, checked against the index's sha256."""
    data = fetch(urllib.parse.urljoin(url, entry.path))
    if sha256(data) != entry.sha256.lower():
        raise RegistryError(
            f"{entry.name} {entry.version}: the download does not match the index's sha256; "
            "nothing was written"
        )
    return data


# ------------------------------------------------------------------ packs/


def pack_path(name: str, root: Path | None = None) -> Path:
    return (root or packs_root()) / f"{name}.yaml"


def installed(root: Path | None = None) -> dict[str, dict]:
    """packs/installed.json: name -> {version, sha256} of what install wrote."""
    path = (root or packs_root()) / INSTALLED_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def edited(name: str, root: Path | None = None) -> bool:
    """Whether packs/<name>.yaml is there and is not the file install wrote."""
    path = pack_path(name, root)
    if not path.exists():
        return False
    record = installed(root).get(name)
    return record is None or sha256(path.read_bytes()) != record.get("sha256")


def write_atomic(path: Path, data: bytes) -> None:
    """Atomically, as the learned layer is written (D-037)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write_installed(record: dict[str, dict], root: Path | None = None) -> None:
    write_atomic((root or packs_root()) / INSTALLED_FILE, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode())


def write_pack(name: str, version: str, data: bytes, root: Path | None = None) -> Path:
    """packs/<name>.yaml and its record in installed.json: what `pack update`
    compares, and what tells a pack edited by hand."""
    target = pack_path(name, root)
    write_atomic(target, data)
    record = installed(root)
    record[name] = {"version": version, "sha256": sha256(data)}
    write_installed(record, root)
    return target


def install(entry: Entry, url: str, root: Path | None = None) -> Path:
    if entry.too_new():  # D-087: every way in comes through here
        raise RegistryError(f"{entry.needs()}; nothing was written")
    return write_pack(entry.name, entry.version, download(entry, url), root)


# ------------------------------------------------------------------ included (D-088)

#: D-088: where a pack there to install comes from, and how every list marks it.
FROM_INCLUDED, FROM_REPOSITORY = "included", "repository"
MARKS = {FROM_INCLUDED: "(included, not installed)", FROM_REPOSITORY: "(from the packs repository)"}


def pack_info(path: Path) -> tuple[str, str, str]:
    """A pack file's version, language and one-line description ("?" when unreadable)."""
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        data = {}
    description = data.get("description") or ""
    if isinstance(description, dict):  # the field templates' {en, pt-BR} (D-065)
        description = description.get("en") or next(iter(description.values()), "")
    return str(data.get("version") or "?"), str(data.get("language") or "?"), str(description)


def install_included(name: str, root: Path | None = None) -> Path:
    """D-088: the included pack, copied into packs/ as `pack install` writes a download."""
    path = included_packs()[name]
    return write_pack(name, pack_info(path)[0], path.read_bytes(), root)


def newer(available: str, have: str) -> bool:
    return engine.numbers(available) > engine.numbers(have)


@dataclass(frozen=True)
class Available:
    """D-088: a pack there to install, not installed."""

    name: str
    version: str  # the one `pack install` would install
    language: str
    description: str
    origin: str  # FROM_INCLUDED | FROM_REPOSITORY: its mark
    entry: Entry | None  # the repository's, when installing downloads it

    @property
    def mark(self) -> str:
        return MARKS[self.origin]

    def install_argv(self) -> list[str]:
        """The command that installs it; an included pack without the
        repository when the repository has nothing newer."""
        return ["pack", "install", self.name] + (["--included"] if self.entry is None else [])


def from_repository(entry: Entry | None, version: str) -> Entry | None:
    """The repository's entry when this engine can use it and it is newer than `version`."""
    return entry if entry is not None and not entry.too_new() and newer(entry.version, version) else None


def available(index: dict[str, Entry] | None) -> list[Available]:
    """D-088: what can be installed and is not: the included packs first, then
    the repository's (none when `index` is None: it was not reached). A pack
    in both is listed once, as included, with the newer of the two versions.
    A repository pack this engine cannot use is listed; its entry says why."""
    have = installed_packs()
    out = []
    for name, path in included_packs().items():
        if name in have:
            continue
        version, language, description = pack_info(path)
        entry = (index or {}).get(name)
        upgrade = from_repository(entry, version)
        if entry is not None:
            description = entry.description or description
        out.append(Available(name, upgrade.version if upgrade else version, language, description, FROM_INCLUDED, upgrade))
    for name, entry in (index or {}).items():
        if name in have or name in included_packs():
            continue
        out.append(Available(name, entry.version, entry.language, entry.description, FROM_REPOSITORY, entry))
    return out


# ------------------------------------------------------------------ commands


def installed_mark(name: str) -> str:
    """D-088: how `pack list` marks an installed pack: from `pack install`, or yours."""
    return "installed" if name in installed() and not edited(name) else "installed (yours)"


def held_line(entry: Entry) -> str:
    """D-087: what the index has of this pack that this engine cannot use."""
    if entry.too_new():
        return f"{entry.needs()}; it cannot be installed with this version"
    return f"{entry.held.needs()}; {entry.version} is the newest for this version"


def run_list(args) -> int:
    """D-088: the installed packs, then the included ones not installed, then
    the repository's not installed, each with its mark."""
    if args.installed:  # D-064: what this machine has, not the repository
        from .packfiles import run_installed

        return run_installed(args)
    url = index_url(args.index)
    try:
        entries, problem = read_index(url), None
    except RegistryError as error:
        entries, problem = None, error
    rows = []
    for name, path in installed_packs().items():
        version, language, description = pack_info(path)
        entry = (entries or {}).get(name)
        mark = installed_mark(name)
        upgrade = from_repository(entry, version) if mark == "installed" else None
        if upgrade is not None:
            mark += f", ↑ {upgrade.version}"
        rows.append((name, version, language, mark, (entry.description if entry else "") or description))
    for a in available(entries):
        too_new = a.entry is not None and a.entry.too_new()
        rows.append((a.name, a.version, a.language,
                     a.mark + (f", needs {a.entry.min_engine}+" if too_new else ""), a.description))
    if not rows:
        print(f"no packs: none installed, none included, and the index at {url} lists none")
    widths = [max(len(row[i]) for row in rows) for i in range(4)] if rows else []
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)) + "  " + row[4])
    if problem is not None:
        print(f"\n(the packs repository was not reached, so its packs are not listed: {problem})")
    held = [e for e in (entries or {}).values() if e.blocked is not None]
    if held:
        print()
        for e in held:
            print(held_line(e))
        print(f"newer versions of transcript-normalizer: {RELEASES}")
    if any(r[3].startswith("↑") or ", ↑" in r[3] for r in rows):
        print("\n↑: the packs repository has a newer version; `transcript-normalizer pack update` installs it")
    print(f"\n`transcript-normalizer pack install <name>` puts one in {packs_root()}{os.sep}")
    return 0


def run_install(args) -> int:
    """From the repository; an included pack (D-088) from the program itself,
    unless the repository has a newer version this engine can use."""
    name = args.name
    included = included_packs().get(name)
    if args.included and included is None:
        print(f"no pack called {name} is included in this program; `pack list` shows them", file=sys.stderr)
        return 1
    url = index_url(args.index)
    entry = None
    try:
        if included is not None:
            if not args.included:  # offline, or slow: the included one, without waiting long
                from .packfiles import INDEX_WAIT_SECONDS, index_within

                entry = from_repository((index_within(INDEX_WAIT_SECONDS, args.index) or {}).get(name),
                                        pack_info(included)[0])
        else:
            entry = read_index(url).get(name)
            if entry is None:
                print(f"no pack called {name} in the index; `pack list` shows them", file=sys.stderr)
                return 1
            if entry.too_new():
                print(entry.needs(), file=sys.stderr)
                print(f"nothing was installed; newer versions of transcript-normalizer: {RELEASES}", file=sys.stderr)
                return 1
        version = entry.version if entry is not None else pack_info(included)[0]
        target = pack_path(name)
        if edited(name) and not args.force:
            print(
                f"{target} is there and is not a file pack install wrote; "
                "pass --force to replace it",
                file=sys.stderr,
            )
            return 1
        record = installed().get(name)
        if record and record.get("version") == version and target.exists() and not args.force:
            print(f"{name} {version} is already installed in {target}")
            return 0
        if entry is not None:
            install(entry, url)
        else:
            install_included(name)
    except RegistryError as error:
        print(error, file=sys.stderr)
        return 1
    how = "sha256 checked" if entry is not None else "included in the program"
    print(f"installed {name} {version} in {target} ({how})")
    if entry is not None and entry.held is not None:
        print(f"({held_line(entry)})")
    return 0


def offer_merges(entries: dict | None) -> None:
    """D-069: a copy of the user's is never replaced; when its upstream is
    newer, say so, and on a terminal ask whether to merge."""
    from . import cli, merge, prompts

    for offer in merge.offers(index=entries or {}):
        print(offer.line())
        if cli.is_interactive() and prompts.confirm("Merge?", default=False):
            cli.main(["pack", "merge", offer.name])
        else:
            print(f"  `transcript-normalizer pack merge {offer.name}` merges it, asking about each conflict")


def run_update(args) -> int:
    """Newer versions from the repository, and (D-088) from the packs included
    in the program, which need no connection."""
    url = index_url(args.index)
    names = sorted(installed())
    code = 0
    try:
        entries = read_index(url)
    except RegistryError as error:
        if not names:
            offer_merges(None)
            print("no packs installed with `pack install`; nothing to update")
            return 0
        print(f"could not read the packs index: {error}", file=sys.stderr)
        if not set(names) & set(included_packs()):
            return 1
        entries, code = None, 1
    offer_merges(entries)
    if not names:
        print("no packs installed with `pack install`; nothing to update")
        return code
    held = False
    for name in names:
        entry, current = (entries or {}).get(name), installed()[name].get("version")
        included = included_packs().get(name)
        mine = pack_info(included)[0] if included is not None else None
        if entries is None and included is None:
            continue  # not checked: said above
        upgrade = from_repository(entry, current)
        if mine is not None and newer(mine, current) and (upgrade is None or not newer(upgrade.version, mine)):
            upgrade = None  # D-088: the included one, no download
        else:
            mine = None
        blocked = entry.blocked if entry is not None else None
        if entry is None and included is None:
            print(f"{name}: no longer in the index; left as it is")
        elif edited(name):
            print(f"{name}: {pack_path(name)} was edited here; left as it is (pack install --force replaces it)")
        elif mine is not None:
            install_included(name)
            print(f"{name}: {current} → {mine} (included in the program)")
        elif upgrade is not None:
            try:
                install(upgrade, url)
            except RegistryError as error:
                print(f"{name}: {error}", file=sys.stderr)
                code = 1
                continue
            print(f"{name}: {current} → {upgrade.version}")
            if upgrade.held is not None:
                print(f"  ({held_line(upgrade)})")
                held = True
        elif blocked is not None and newer(blocked.version, current):
            if entry.too_new():
                print(f"{name}: {entry.needs()}; {current} is kept")
            else:
                print(f"{name}: {current} is the latest for this version; {blocked.needs()}")
            held = True
        else:
            print(f"{name}: {current} is the latest")
    if held:
        print(f"newer versions of transcript-normalizer: {RELEASES}")
    return code


def add_arguments(parser) -> None:
    """`pack list | install | update` (and `propose`, D-056, and `create`,
    `import`, `remove`, D-065, added by the CLI)."""
    commands = parser.add_subparsers(dest="pack_command", required=True, metavar="ACTION")

    def with_index(sub):
        sub.add_argument(
            "--index", metavar="URL", help=f"the packs index. default: ${INDEX_ENV}, else {INDEX_URL}"
        )
        return sub

    listing = with_index(commands.add_parser(
        "list", help="the packs installed, then those included in the program and in the packs repository"))
    listing.add_argument(
        "--installed", action="store_true",
        help="only the packs installed in packs/, with their source, terms and size",
    )
    listing.set_defaults(run=run_list)

    installing = with_index(commands.add_parser(
        "install", help="put a pack in packs/: from the packs repository, or one included in the program"))
    installing.add_argument("name", help="the pack's name, as `pack list` shows it")
    installing.add_argument(
        "--included", action="store_true",
        help="the copy included in the program, without reading the packs repository (offline)",
    )
    installing.add_argument(
        "--force", action="store_true", help="replace packs/<name>.yaml even if it was edited here"
    )
    installing.set_defaults(run=run_install)

    updating = with_index(commands.add_parser("update", help="install newer versions of installed packs"))
    updating.set_defaults(run=run_update)
    return commands
