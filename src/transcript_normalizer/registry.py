"""The packs repository (D-055): `pack list`, `pack install`, `pack update`.

Domain content lives in its own repository, one directory per pack, with an
`index.json` that names every pack, its version and the sha256 of its file.
This module reads that index and installs packs into the user's `packs/`, where
`--pack`, the menu and `default_pack` already look (D-017, D-054). urllib only:
no new dependency, and a `file://` index works the same, which is what the
tests use. The bundled financas-ptbr stays the offline default (D-043).
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
from dataclasses import dataclass
from pathlib import Path

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
        entries = [Entry(**{f: str(raw[f]) for f in FIELDS}) for raw in data["packs"]]
    except (ValueError, KeyError, TypeError) as error:
        raise RegistryError(f"{url} is not a packs index: {error}") from None
    bad = [e.name for e in entries if not NAME.match(e.name)]
    if bad:
        raise RegistryError(f"{url}: not a pack name: {', '.join(bad)}")
    return {e.name: e for e in entries}


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
    rows = [(e.name, e.version, e.language, status(e.name), e.description) for e in entries.values()]
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)) + "  " + row[4])
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
    return 0


def run_update(args) -> int:
    url = index_url(args.index)
    names = sorted(installed())
    if not names:
        print("no packs installed with `pack install`; nothing to update")
        return 0
    try:
        entries = read_index(url)
    except RegistryError as error:
        print(f"could not read the packs index: {error}", file=sys.stderr)
        return 1
    code = 0
    for name in names:
        entry, current = entries.get(name), installed()[name].get("version")
        if entry is None:
            print(f"{name}: no longer in the index; left as it is")
        elif edited(name):
            print(f"{name}: {pack_path(name)} was edited here; left as it is (pack install --force replaces it)")
        elif entry.version == current:
            print(f"{name}: {current} is the latest")
        else:
            try:
                install(entry, url)
            except RegistryError as error:
                print(f"{name}: {error}", file=sys.stderr)
                code = 1
                continue
            print(f"{name}: {current} → {entry.version}")
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
