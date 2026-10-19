"""The packs repository (D-055): `pack list`, `pack install`, `pack update`.

Domain content lives in its own repository, one directory per pack, with an
`index.json` that names every pack, its version and the sha256 of its file.
This module reads that index and installs packs into the user's `packs/`, where
`--pack`, the menu and `default_pack` already look (D-017, D-054). urllib only:
no new dependency, and a `file://` index works the same, which is what the
tests use. The bundled financas-ptbr stays the offline default (D-043).

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
from .runs import BUNDLED_PACKS, packs_root

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


def install(entry: Entry, url: str, root: Path | None = None) -> Path:
    if entry.too_new():  # D-087: every way in comes through here
        raise RegistryError(f"{entry.needs()}; nothing was written")
    data = download(entry, url)
    target = pack_path(entry.name, root)
    write_atomic(target, data)
    record = installed(root)
    record[entry.name] = {"version": entry.version, "sha256": entry.sha256.lower()}
    write_installed(record, root)
    return target


# ------------------------------------------------------------------ commands


def status(name: str) -> str:
    """What this machine has of a pack: installed, bundled, or nothing."""
    record = installed().get(name)
    if pack_path(name).exists():
        if record and not edited(name):
            return f"installed {record['version']}"
        return "in packs/ (yours)"
    if (BUNDLED_PACKS / f"{name}.yaml").exists():
        return "bundled"
    return ""


def held_line(entry: Entry) -> str:
    """D-087: what the index has of this pack that this engine cannot use."""
    if entry.too_new():
        return f"{entry.needs()}; it cannot be installed with this version"
    return f"{entry.held.needs()}; {entry.version} is the newest for this version"


def run_list(args) -> int:
    if args.installed:  # D-064: what this machine has, not the repository
        from .packfiles import run_installed

        return run_installed(args)
    url = index_url(args.index)
    try:
        entries = read_index(url)
    except RegistryError as error:
        print(f"could not read the packs index: {error}", file=sys.stderr)
        return 1
    if not entries:
        print(f"the index at {url} lists no packs")
        return 0
    rows = [
        (e.name, e.version, e.language,
         ", ".join(filter(None, [status(e.name), f"needs {e.min_engine}+" if e.too_new() else ""])),
         e.description)
        for e in entries.values()
    ]
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)) + "  " + row[4])
    held = [e for e in entries.values() if e.blocked is not None]
    if held:
        print()
        for e in held:
            print(held_line(e))
        print(f"newer versions of transcript-normalizer: {RELEASES}")
    print(f"\n`transcript-normalizer pack install <name>` puts one in {packs_root()}{os.sep}")
    return 0


def run_install(args) -> int:
    url = index_url(args.index)
    try:
        entries = read_index(url)
        entry = entries.get(args.name)
        if entry is None:
            print(f"no pack called {args.name} in the index; `pack list` shows them", file=sys.stderr)
            return 1
        if entry.too_new():
            print(entry.needs(), file=sys.stderr)
            print(f"nothing was installed; newer versions of transcript-normalizer: {RELEASES}", file=sys.stderr)
            return 1
        target = pack_path(entry.name)
        if edited(entry.name) and not args.force:
            print(
                f"{target} is there and is not a file pack install wrote; "
                "pass --force to replace it",
                file=sys.stderr,
            )
            return 1
        record = installed().get(entry.name)
        if record and record.get("version") == entry.version and target.exists() and not args.force:
            print(f"{entry.name} {entry.version} is already installed in {target}")
            return 0
        install(entry, url)
    except RegistryError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"installed {entry.name} {entry.version} in {target} (sha256 checked)")
    if entry.held is not None:
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
    url = index_url(args.index)
    names = sorted(installed())
    try:
        entries = read_index(url)
    except RegistryError as error:
        if not names:
            offer_merges(None)
            print("no packs installed with `pack install`; nothing to update")
            return 0
        print(f"could not read the packs index: {error}", file=sys.stderr)
        return 1
    offer_merges(entries)
    if not names:
        print("no packs installed with `pack install`; nothing to update")
        return 0
    code, held = 0, False
    for name in names:
        entry, current = entries.get(name), installed()[name].get("version")
        if entry is None:
            print(f"{name}: no longer in the index; left as it is")
        elif edited(name):
            print(f"{name}: {pack_path(name)} was edited here; left as it is (pack install --force replaces it)")
        elif entry.version == current:
            if entry.held is not None:
                print(f"{name}: {current} is the latest for this version; {entry.held.needs()}")
                held = True
            else:
                print(f"{name}: {current} is the latest")
        elif entry.too_new():
            print(f"{name}: {entry.needs()}; {current} is kept")
            held = True
        else:
            try:
                install(entry, url)
            except RegistryError as error:
                print(f"{name}: {error}", file=sys.stderr)
                code = 1
                continue
            print(f"{name}: {current} → {entry.version}")
            if entry.held is not None:
                print(f"  ({held_line(entry)})")
                held = True
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

    listing = with_index(commands.add_parser("list", help="the packs in the packs repository"))
    listing.add_argument(
        "--installed", action="store_true",
        help="the packs on this machine instead: bundled, from the repository, and yours",
    )
    listing.set_defaults(run=run_list)

    installing = with_index(commands.add_parser("install", help="download a pack into packs/"))
    installing.add_argument("name", help="the pack's name, as `pack list` shows it")
    installing.add_argument(
        "--force", action="store_true", help="replace packs/<name>.yaml even if it was edited here"
    )
    installing.set_defaults(run=run_install)

    updating = with_index(commands.add_parser("update", help="install newer versions of installed packs"))
    updating.set_defaults(run=run_update)
    return commands
