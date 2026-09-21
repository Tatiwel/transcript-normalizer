"""Domain-term normalization for ASR transcripts and auto-captions."""

from .matcher import find_annotations, resolve_overlaps
from .pack import Pack, load_pack
from .standoff import Annotation, to_json, write_json
from .text import Transcript, parse_caption, read_caption

__all__ = [
    "Annotation",
    "Pack",
    "Transcript",
    "find_annotations",
    "load_pack",
    "parse_caption",
    "read_caption",
    "resolve_overlaps",
    "to_json",
    "write_json",
]
