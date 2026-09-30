"""Where things live on disk (D-015, D-016, D-017, D-022, D-023).

Everything the CLI produces lands under `runs/` in the current directory, one
directory per input. Domain packs and the learned layer that belongs to them
live under `packs/`, the user's own knowledge directory. Nothing is ever
written beside an input or into `fixtures/`.
"""

from __future__ import annotations

import re
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


def runs_root() -> Path:
    return Path.cwd() / RUNS_DIR


def packs_root() -> Path:
    return Path.cwd() / PACKS_DIR


#: The packs that ship inside the package. The repo's `packs/` links to them.
BUNDLED_PACKS = Path(__file__).resolve().parent / "packs"


def default_pack() -> Path:
    """The pack `--pack` falls back to (D-017).

    `packs/<default>` in the current directory when there is one, so a pack the
    user edits wins; otherwise the copy that ships in the package, so the
    default still resolves after `pip install`, from any directory.
    """
    local = packs_root() / DEFAULT_PACK
    return local if local.exists() else BUNDLED_PACKS / DEFAULT_PACK


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
