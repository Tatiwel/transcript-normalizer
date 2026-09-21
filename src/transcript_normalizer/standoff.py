"""Stand-off annotations (D-004).

The transcript is never modified. A normalization is a separate layer of offsets
into the original text. Nothing in this package returns a corrected transcript.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

RULE_UNIT = "unit"


def term_rule(origin: str) -> str:
    """`variant` | `alias` | `fuzzy` -> the `rule` field of an annotation."""
    return f"term:{origin}"


@dataclass(frozen=True)
class Annotation:
    start: int
    end: int
    original: str
    replacement: str
    term: str
    rule: str  # "unit" | "term:variant" | "term:alias" | "term:fuzzy"
    score: int
    pack_version: str

    def to_dict(self) -> dict:
        return asdict(self)


def to_json(annotations: list[Annotation], indent: int = 2) -> str:
    return json.dumps([a.to_dict() for a in annotations], ensure_ascii=False, indent=indent)


def write_json(annotations: list[Annotation], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(to_json(annotations) + "\n", encoding="utf-8")
    return path
