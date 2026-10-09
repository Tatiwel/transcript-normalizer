"""Where things live on disk (D-015, D-016, D-017, D-022, D-023).

Everything the CLI produces lands under `runs/`, one directory per input, and
domain packs and the learned layer that belongs to them live under `packs/`,
the user's own knowledge directory. Both sit in `base_dir()`: the current
directory, or the folder D-061 and D-070 choose (see there). Nothing is ever
written beside an input or into `fixtures/`.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

RUNS_DIR = "runs"

#: A platform video id, and the url shapes it turns up in (D-018).
VIDEO_ID = r"[A-Za-z0-9_-]{11}"
_URL_PATTERNS = tuple(
    re.compile(pattern + r"(?![A-Za-z0-9_-])")
    for pattern in (
        rf"youtu\.be/({VIDEO_ID})",
        rf"[?&]v=({VIDEO_ID})",
        rf"/(?:shorts|embed|live|v)/({VIDEO_ID})",
    )
)

#: D-017: the user's packs, and the learned layer beside each of them.
PACKS_DIR = "packs"
DEFAULT_PACK = "financas-ptbr.yaml"

#: The run's own record. Machine-readable first, then the printed report.
ANNOTATIONS_FILE = "annotations.json"
REPORT_FILE = "report.txt"

#: Rendered views over the stand-off layer (D-016).
NORMALIZED_FILE = "normalized.txt"
#: Reserved for when diarization exists; nothing writes it yet.
NORMALIZED_SPEAKERS_FILE = "normalized.speakers.txt"

#: D-023: everything that needs a person goes in one place.
NEEDS_REVIEW_DIR = "needs-review"
CORRECTIONS_FILE = "corrections.csv"  # was review/gold-draft.csv
PENDING_FILE = "pending.txt"  # was review/to-confirm.txt

#: D-022: what `fetch` knows about the video, beside its caption.
META_FILE = "meta.yaml"
CAPTION_FILE = "legenda.txt"


#: D-052: the standalone executable keeps the user's files here, under the
#: platform's documents directory; this variable moves it (tests, portable use).
APP_NAME = "transcript-normalizer"
DATA_DIR_ENV = "TRANSCRIPT_NORMALIZER_HOME"


def is_frozen() -> bool:
    """Running as the PyInstaller executable, not as an installed package."""
    return bool(getattr(sys, "frozen", False))


#: D-070: this file beside the program makes it portable.
PORTABLE_FILE = "portable.txt"
#: Inside the program's folder, where a portable program keeps everything.
PORTABLE_DATA = "data"


def program_dir() -> Path:
    """The folder of the executable (frozen), or of the script that was run."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(sys.argv[0] or ".").resolve().parent


def portable_dir() -> Path | None:
    """D-070: `<program folder>/data` when `portable.txt` is beside the program."""
    folder = program_dir()
    return folder / PORTABLE_DATA if (folder / PORTABLE_FILE).is_file() else None


def portable_models() -> Path | None:
    """D-070: where a portable program keeps the speech model (HF_HOME)."""
    base = portable_dir()
    return base / "models" if base else None


def portable_cache() -> Path | None:
    """D-070: yt-dlp's cache, and the working directory it runs in."""
    base = portable_dir()
    return base / "cache" if base else None


def apply_portable_environment() -> None:
    """D-070: the speech model goes inside the portable folder. Called once,
    before anything imports huggingface_hub."""
    models = portable_models()
    if models is not None:
        os.environ["HF_HOME"] = str(models)


def data_dir() -> Path:
    """D-052: `~/Documents/transcript-normalizer/`, or the platform's equivalent;
    `<program folder>/data` for a portable program (D-070)."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()
    portable = portable_dir()
    if portable is not None:
        return portable
    import platformdirs

    return Path(platformdirs.user_documents_dir()) / APP_NAME


#: D-061: the user's settings, written by the menu's Settings screen.
CONFIG_FILE = "config.toml"


def config_file() -> Path:
    """`config.toml` in the platform's user configuration directory, or in the
    portable folder (D-070)."""
    portable = portable_dir()
    if portable is not None:
        return portable / CONFIG_FILE
    import platformdirs

    return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False)) / CONFIG_FILE


def read_config() -> dict:
    """The settings, or {} when there is no file or it cannot be read."""
    import tomllib

    try:
        return tomllib.loads(config_file().read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}


def write_config(settings: dict) -> Path:
    """Write `settings` (string values only); a None value removes its key."""
    import json

    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    # A JSON string is a valid TOML basic string: the same escapes.
    lines = [f"{key} = {json.dumps(str(value), ensure_ascii=False)}"
             for key, value in settings.items() if value is not None]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def configured_dir() -> Path | None:
    """D-061: the folder chosen in Settings (`data_dir` in config.toml), if any."""
    chosen = read_config().get("data_dir")
    return Path(chosen).expanduser() if isinstance(chosen, str) and chosen.strip() else None


def base_dir() -> Path:
    """Where runs/ and packs/ live.

    In order (D-061): TRANSCRIPT_NORMALIZER_HOME, for scripts; the portable
    folder (D-070); the folder chosen in Settings; then the current directory,
    as always (D-015, D-017), except in
    the executable: double-clicked, its current directory is wherever the system
    chose, so it uses the documents directory instead (D-052). A folder other
    than the current directory is created with both folders on first use.
    """
    if os.environ.get(DATA_DIR_ENV):
        base = data_dir()
    elif (portable := portable_dir()) is not None:
        base = portable
    elif (chosen := configured_dir()) is not None:
        base = chosen
    elif not is_frozen():
        return Path.cwd()
    else:
        base = data_dir()
    for folder in (RUNS_DIR, PACKS_DIR):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def runs_root() -> Path:
    return base_dir() / RUNS_DIR


def packs_root() -> Path:
    return base_dir() / PACKS_DIR


#: The packs that ship inside the package (D-043).
BUNDLED_PACKS = Path(__file__).resolve().parent / "packs"


def default_pack() -> Path:
    """The pack `--pack` falls back to (D-017).

    `packs/<default>` under `base_dir()` when there is one, so a pack the
    user edits wins; otherwise the copy that ships in the package, so the
    default still resolves after `pip install`, from any directory.
    """
    local = packs_root() / DEFAULT_PACK
    return local if local.exists() else BUNDLED_PACKS / DEFAULT_PACK


def installed_packs() -> dict[str, Path]:
    """Every pack there is to choose from, by name (D-054, D-055).

    The bundled packs, then the `.yaml` files in packs/ (installed with `pack
    install` or written by the user), which win over a bundled one of the
    same name, as in `default_pack`. Learned layers and a merge's pending
    conflicts (D-069) are not packs.
    """
    found = {p.stem: p for p in sorted(BUNDLED_PACKS.glob("*.yaml"))}
    root = packs_root()
    if root.is_dir():
        found.update(
            (p.stem, p) for p in sorted(root.glob("*.yaml"))
            if not p.name.endswith((".learned.yaml", ".merge-pending.yaml"))
        )
    return found


def video_id_from_url(url: str) -> str:
    """The video id in a url, or `""` when there is no recognizable one."""
    for pattern in _URL_PATTERNS:
        match = pattern.search(url or "")
        if match:
            return match.group(1)
    return ""


def run_dir_containing(path: str | Path) -> Path | None:
    """The `runs/<id>/` a path already lives in, if it lives in one."""
    root = runs_root()
    try:
        relative = Path(path).resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    if len(relative.parts) < 2:  # directly in runs/, so there is no <id>
        return None
    return root / relative.parts[0]


def run_dir(
    input_path: str | Path, out: str | Path | None = None, url: str = ""
) -> Path:
    """Where this run writes (D-018).

    `out` wins. Otherwise: a caption already inside `runs/<id>/` keeps that
    directory, a caption whose header declares a url with a recognizable video
    id gets `runs/<id>/`, and anything else falls back to the input's stem.

    The stem alone is not enough because `fetch` names every caption
    `legenda.txt`, so every video would normalize into `runs/legenda/`.
    """
    if out is not None:
        return Path(out)

    inside = run_dir_containing(input_path)
    if inside is not None:
        return inside

    video_id = video_id_from_url(url)
    if video_id:
        return runs_root() / video_id

    return runs_root() / Path(input_path).stem


def needs_review_dir(out_dir: str | Path) -> Path:
    """`<run>/needs-review/`: the files that need a person to look at them (D-023)."""
    return Path(out_dir) / NEEDS_REVIEW_DIR


def learned_file(pack_path: str | Path, override: str | Path | None = None) -> Path:
    """`packs/<pack-name>.learned.yaml`, or `override` when given.

    D-017 moves this out of `runs/learned/`, where D-015 had put it: what the
    user confirms belongs with the pack it is about, not with a disposable run.
    It stays out of `fixtures/` even when the pack is a fixture copy, because
    the location is fixed rather than taken from the pack's own directory.
    """
    if override is not None:
        return Path(override)
    return packs_root() / f"{Path(pack_path).stem}.learned.yaml"
