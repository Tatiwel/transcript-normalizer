"""Where a run's outputs go (D-015).

Everything the CLI produces lands under `runs/` in the current directory:
`runs/<input-stem>/` for one run's files, `runs/learned/` for the layer of
D-013. Nothing is ever written beside an input or into `fixtures/`.
"""

from __future__ import annotations

from pathlib import Path

RUNS_DIR = "runs"
LEARNED_DIR = "learned"

ANNOTATIONS_FILE = "annotations.json"
REPORT_FILE = "report.txt"
GOLD_DRAFT_FILE = "gold-draft.csv"


def runs_root() -> Path:
    return Path.cwd() / RUNS_DIR


def run_dir(input_path: str | Path, out: str | Path | None = None) -> Path:
    """`runs/<input-stem>/`, or `out` when the caller names a directory."""
    if out is not None:
        return Path(out)
    return runs_root() / Path(input_path).stem


def learned_file(pack_path: str | Path, override: str | Path | None = None) -> Path:
    """`runs/learned/<pack-name>.learned.yaml`, or `override` when given."""
    if override is not None:
        return Path(override)
    return runs_root() / LEARNED_DIR / f"{Path(pack_path).stem}.learned.yaml"
