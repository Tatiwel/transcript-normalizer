"""Stand-off annotations (D-004) and the confidence bands of D-011.

The transcript is never modified. A normalization is a separate layer of offsets
into the original text. Nothing in this package returns a corrected transcript.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

RULE_UNIT = "unit"

#: D-011's three bands. Only high and medium are applied; low is a passive mark.
BAND_HIGH = "high"
BAND_MEDIUM = "medium"
BAND_LOW = "low"

APPLIED_BANDS = (BAND_HIGH, BAND_MEDIUM)


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
    band: str  # "high" | "medium" | "low"
    score: int
    pack_version: str

    @property
    def applied(self) -> bool:
        """D-011: high and medium are applied; low is marked and left alone."""
        return self.band in APPLIED_BANDS

    def to_dict(self) -> dict:
        return {
            "start": self.start,
            "end": self.end,
            "original": self.original,
            "replacement": self.replacement,
            "term": self.term,
            "rule": self.rule,
            "band": self.band,
            "score": self.score,
            "applied": self.applied,
            "pack_version": self.pack_version,
        }


def applied(annotations: list[Annotation]) -> list[Annotation]:
    return [a for a in annotations if a.applied]


def in_band(annotations: list[Annotation], band: str) -> list[Annotation]:
    return [a for a in annotations if a.band == band]


def to_json(annotations: list[Annotation], indent: int = 2) -> str:
    return json.dumps([a.to_dict() for a in annotations], ensure_ascii=False, indent=indent)


def write_json(annotations: list[Annotation], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(to_json(annotations) + "\n", encoding="utf-8")
    return path
