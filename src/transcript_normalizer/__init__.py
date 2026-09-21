"""Domain-term normalization for ASR transcripts and auto-captions."""

from .core.matcher import band_for, find_annotations, resolve_overlaps
from .core.pack import Learned, Pack, load_learned, load_pack, save_learned
from .runs import learned_file, run_dir, runs_root
from .core.standoff import Annotation, applied, in_band, to_json, write_json
from .core.text import Transcript, parse_caption, read_caption

__all__ = [
    "Annotation",
    "Learned",
    "Pack",
    "Transcript",
    "applied",
    "band_for",
    "find_annotations",
    "in_band",
    "learned_file",
    "load_learned",
    "load_pack",
    "parse_caption",
    "read_caption",
    "resolve_overlaps",
    "run_dir",
    "runs_root",
    "save_learned",
    "to_json",
    "write_json",
]
