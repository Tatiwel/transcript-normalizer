"""Where things live on disk (D-015, D-016, D-017).

Everything the CLI produces lands under `runs/` in the current directory, one
directory per input. Domain packs and the learned layer that belongs to them
live under `packs/`, the user's own knowledge directory. Nothing is ever
written beside an input or into `fixtures/`.
"""

from __future__ import annotations

from pathlib import Path

RUNS_DIR = "runs"

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

#: Everything that needs a person goes in one place.
REVIEW_DIR = "review"
GOLD_DRAFT_FILE = "gold-draft.csv"
TO_CONFIRM_FILE = "to-confirm.txt"


def runs_root() -> Path:
    return Path.cwd() / RUNS_DIR


def packs_root() -> Path:
    return Path.cwd() / PACKS_DIR


def default_pack() -> Path:
    """The pack `--pack` falls back to (D-017)."""
    return packs_root() / DEFAULT_PACK


def run_dir(input_path: str | Path, out: str | Path | None = None) -> Path:
    """`runs/<input-stem>/`, or `out` when the caller names a directory."""
    if out is not None:
        return Path(out)
    return runs_root() / Path(input_path).stem


def review_dir(out_dir: str | Path) -> Path:
    """`<run>/review/`: the files that need a person to look at them (D-016)."""
    return Path(out_dir) / REVIEW_DIR


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
