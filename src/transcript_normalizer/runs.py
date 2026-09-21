"""Where a run's outputs go (D-015).

Everything the CLI produces lands under `runs/` in the current directory:
`runs/<input-stem>/` for one run's files, `runs/learned/` for the layer of
D-013. Nothing is ever written beside an input or into `fixtures/`.
"""

from __future__ import annotations

from pathlib import Path

RUNS_DIR = "runs"
LEARNED_DIR = "learned"

#: The run's own record. Machine-readable first, then the printed report.
ANNOTATIONS_FILE = "annotations.json"
REPORT_FILE = "report.txt"

#: Rendered views over the stand-off layer (D-016).
NORMALIZED_FILE = "normalized.txt"
#: Reserved for when diarization exists; nothing writes it yet.
NORMALIZED_SPEAKERS_FILE = "normalized.speakers.txt"

#: Everything that needs a person goes in one place.
REVIEW_DIR = "review"
GOLD_DRAFT_FILE = "gold-draft.csv"
TO_CONFIRM_FILE = "to-confirm.txt"


def runs_root() -> Path:
    return Path.cwd() / RUNS_DIR


def run_dir(input_path: str | Path, out: str | Path | None = None) -> Path:
    """`runs/<input-stem>/`, or `out` when the caller names a directory."""
    if out is not None:
        return Path(out)
    return runs_root() / Path(input_path).stem


def review_dir(out_dir: str | Path) -> Path:
    """`<run>/review/`: the files that need a person to look at them (D-016)."""
    return Path(out_dir) / REVIEW_DIR


def learned_file(pack_path: str | Path, override: str | Path | None = None) -> Path:
    """`runs/learned/<pack-name>.learned.yaml`, or `override` when given."""
    if override is not None:
        return Path(override)
    return runs_root() / LEARNED_DIR / f"{Path(pack_path).stem}.learned.yaml"
