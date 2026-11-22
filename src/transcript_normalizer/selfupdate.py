"""D-104: `tn update` says what a newer release brings; `tn upgrade` installs it.

The latest release is the one GitHub marks latest: a tag that went through the
release workflow (CI on three systems, then the build), never a draft or a
prerelease. `update` only reads: the version installed, the latest one, and the
CHANGELOG sections between them. `upgrade` installs the latest one the way this
copy was installed:

- in a project that lists the tool as a dependency (its `.venv` beside a
  `pyproject.toml` that names it): `uv add --project <dir> "<spec>"`, which
  moves the project's pin and its uv.lock to the new tag in one step, keeping
  the extras the project asked for;
- as a uv tool: `uv tool install --force "<spec>"`;
- anywhere else with pip: `<python> -m pip install --upgrade "<spec>"`;
- the executable cannot replace itself: it says where to download the new one;
- a checkout of this repository is updated with git, and says so.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import registry
from .engine import version as installed_version

REPOSITORY = "Tatiwel/transcript-normalizer"
GIT_URL = f"https://github.com/{REPOSITORY}"
RELEASES_URL = f"{GIT_URL}/releases"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
CHANGELOG_URL = "https://raw.githubusercontent.com/" + REPOSITORY + "/{tag}/CHANGELOG.md"

FROZEN, PROJECT, UV_TOOL, PIP, CHECKOUT = "executable", "project", "uv tool", "pip", "checkout"

_HEADING = re.compile(r"^## (\d+(?:\.\d+)*)\s*$", re.M)
#: A requirement's name and extras, as PEP 508 writes them before anything else.
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?")
NAME = "transcript-normalizer"
#: Each extra carries the one before it (pyproject.toml): the largest installed is the one asked for.
EXTRAS = (("ingest", "faster_whisper"), ("captions", "yt_dlp"), ("menu", "questionary"))
#: What uv writes in a tool's environment, saying how it was asked for.
RECEIPT = "uv-receipt.toml"


def parse(text: str) -> tuple[int, ...]:
    """`0.8.6` or `v0.8.6` as (0, 8, 6); () for anything else."""
    text = text.strip().removeprefix("v")
    try:
        return tuple(int(part) for part in text.split("."))
    except ValueError:
        return ()


def latest_tag() -> str:
    """The tag of the release GitHub marks latest. Raises registry.RegistryError offline."""
    try:
        tag = json.loads(registry.fetch(LATEST_URL).decode("utf-8"))["tag_name"]
    except (ValueError, KeyError, TypeError) as error:
        raise registry.RegistryError(f"{LATEST_URL}: not a release ({error})") from None
    if not parse(tag):
        raise registry.RegistryError(f"{LATEST_URL}: the latest release is tagged {tag!r}")
    return tag


def changes(changelog: str, since: str, until: str) -> str:
    """The CHANGELOG sections after `since`, up to and including `until`, newest first."""
    low, high = parse(since), parse(until)
    out = []
    marks = list(_HEADING.finditer(changelog))
    for i, mark in enumerate(marks):
        if low < parse(mark.group(1)) <= high:
            end = marks[i + 1].start() if i + 1 < len(marks) else len(changelog)
            out.append(changelog[mark.start():end].strip())
    return "\n\n".join(out)


@dataclass(frozen=True)
class Install:
    kind: str
    where: Path | None = None  # the project's folder, or the checkout's
    extras: str = ""  # `[ingest]`, as asked for
    group: str = ""  # the dependency group that declares it in a project; "" for the project's own


def normalized(name: str) -> str:
    """PEP 503: `Transcript_Normalizer` and `transcript.normalizer` are the same name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement(text: str) -> str | None:
    """The extras (`[ingest]`, or "") when `text` asks for this package; None for another."""
    found = _NAME.match(text) if isinstance(text, str) else None
    if found is None or normalized(found.group(1)) != NAME:
        return None
    return found.group(2) or ""


def declared(pyproject: dict) -> tuple[str, str] | None:
    """(extras, group) where a project's pyproject.toml asks for this package; None when it does not."""
    for entry in pyproject.get("project", {}).get("dependencies", []):
        if (extras := requirement(entry)) is not None:
            return extras, ""
    for group, entries in pyproject.get("dependency-groups", {}).items():
        for entry in entries:
            if (extras := requirement(entry)) is not None:
                return extras, group
    return None


def _extras_installed() -> str:
    """The largest extra whose own package is installed beside this copy."""
    for extra, module in EXTRAS:
        if importlib.util.find_spec(module) is not None:
            return f"[{extra}]"
    return ""


def _extras_of_receipt(receipt: dict) -> str:
    for entry in receipt.get("tool", {}).get("requirements", []):
        if isinstance(entry, dict) and normalized(str(entry.get("name", ""))) == NAME:
            extras = entry.get("extras") or []
            return f"[{','.join(extras)}]" if extras else ""
    return _extras_installed()


def _toml(path: Path) -> dict | None:
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None


def install_kind(prefix: Path | None = None) -> Install:
    """How this copy was installed, from where its Python environment is."""
    if getattr(sys, "frozen", False):
        return Install(FROZEN)
    prefix = Path(prefix or sys.prefix)
    receipt = _toml(prefix / RECEIPT)
    if receipt is not None:  # uv wrote it: a uv tool, wherever UV_TOOL_DIR put it
        return Install(UV_TOOL, extras=_extras_of_receipt(receipt))
    folder = prefix.parent
    project = _toml(folder / "pyproject.toml")
    if project is not None:
        if normalized(str(project.get("project", {}).get("name", ""))) == NAME:
            return Install(CHECKOUT, folder)
        found = declared(project)
        if found is not None:
            return Install(PROJECT, folder, found[0], found[1])
    return Install(PIP, extras=_extras_installed())


def spec(tag: str, extras: str) -> str:
    return f"transcript-normalizer{extras} @ git+{GIT_URL}@{tag}"


def command(install: Install, tag: str) -> list[str] | None:
    """What installs `tag` the way this copy was installed; None when nothing can."""
    wanted = spec(tag, install.extras)
    if install.kind == PROJECT:
        group = [] if not install.group else ["--dev"] if install.group == "dev" else ["--group", install.group]
        return ["uv", "add", "--project", str(install.where), *group, wanted]
    if install.kind == UV_TOOL:
        return ["uv", "tool", "install", "--force", wanted]
    if install.kind == PIP:
        return [sys.executable, "-m", "pip", "install", "--upgrade", wanted]
    return None


def shown(argv: list[str]) -> str:
    return " ".join(f'"{a}"' if " " in a else a for a in argv)


def _versions() -> tuple[str, str] | None:
    current = installed_version()
    try:
        tag = latest_tag()
    except registry.RegistryError as error:
        print(f"could not check for a newer version: {error}", file=sys.stderr)
        return None
    return current or "unknown", tag


def run_update(args: argparse.Namespace) -> int:
    found = _versions()
    if found is None:
        return 1
    current, tag = found
    print(f"installed: {current}")
    print(f"latest:    {tag.removeprefix('v')}")
    if parse(current) and parse(current) >= parse(tag):
        print("up to date")
        return 0
    try:
        text = registry.fetch(CHANGELOG_URL.format(tag=tag)).decode("utf-8")
        what = changes(text, current, tag)
    except registry.RegistryError as error:
        what = f"(the changelog could not be read: {error})"
    if what:
        print()
        print(what)
    print()
    print("`tn upgrade` installs it.")
    return 0


def run_upgrade(args: argparse.Namespace) -> int:
    found = _versions()
    if found is None:
        return 1
    current, tag = found
    if parse(current) and parse(current) >= parse(tag):
        print(f"{current} is the latest version; nothing to do")
        return 0
    install = install_kind()
    print(f"{current} → {tag.removeprefix('v')} ({install.kind})")
    if install.kind == FROZEN:
        print(f"This program cannot replace itself. Download {tag} for your system from {RELEASES_URL}")
        return 1
    if install.kind == CHECKOUT:
        print(f"This is a checkout of the repository, in {install.where}: `git pull`, then `uv sync`.")
        return 1
    argv = command(install, tag)
    if argv[0] == "uv" and shutil.which("uv") is None:
        print(f"uv is not installed. Install it (https://docs.astral.sh/uv/), then run:\n  {shown(argv)}",
              file=sys.stderr)
        return 1
    print(f"running: {shown(argv)}")
    code = subprocess.run(argv).returncode
    if code != 0:
        print(f"it did not finish (exit {code}); run it by hand:\n  {shown(argv)}", file=sys.stderr)
        return code
    print(f"done: {tag.removeprefix('v')} is installed; `tn --version` shows it")
    return 0


def add_arguments(commands) -> None:
    update = commands.add_parser(
        "update",
        help="check for a newer version: installed and latest, and what changed between them",
        description="D-104: read only. The installed version, the latest release, and the "
        "CHANGELOG sections between them.",
    )
    update.set_defaults(run=run_update)
    upgrade = commands.add_parser(
        "upgrade",
        help="install the latest version, the way this copy was installed",
        description="D-104: in a project, moves its pin and uv.lock to the latest tag (uv add); "
        "as a uv tool or with pip, reinstalls; the executable says where to download.",
    )
    upgrade.set_defaults(run=run_upgrade)
