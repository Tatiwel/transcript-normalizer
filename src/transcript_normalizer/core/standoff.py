"""Stand-off annotations (D-004), the confidence bands of D-011 and the kinds of D-020.

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
#: D-060: a proposal that is asked about and never applied until the user
#: confirms it (the phonetic source). Not rendered, counted as pending.
BAND_ASK = "ask"

APPLIED_BANDS = (BAND_HIGH, BAND_MEDIUM)
#: What the confirmation loop and needs-review/pending.txt ask about.
QUESTION_BANDS = (BAND_MEDIUM, BAND_ASK)

#: D-020's two kinds. A correction replaces its span in normalized.txt; an alias
#: names the term the speaker meant and leaves the words as they were said.
KIND_CORRECTION = "correction"
KIND_ALIAS = "alias"


def term_rule(origin: str) -> str:
    """`variant` | `alias` | `exact` | `fuzzy` -> the `rule` field of an annotation."""
    return f"term:{origin}"


@dataclass(frozen=True)
class Annotation:
    start: int
    end: int
    original: str
    replacement: str
    term: str
    rule: str  # "unit" | "term:variant" | "term:alias" | "term:exact" | "term:fuzzy" | "term:phonetic"
    band: str  # "high" | "medium" | "low"
    score: int
    pack_version: str
    kind: str = KIND_CORRECTION  # "correction" | "alias"

    @property
    def is_correction(self) -> bool:
        return self.kind == KIND_CORRECTION

    @property
    def is_alias(self) -> bool:
        return self.kind == KIND_ALIAS

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
            "kind": self.kind,
            "band": self.band,
            "score": self.score,
            "applied": self.applied,
            "pack_version": self.pack_version,
        }


def applied(annotations: list[Annotation]) -> list[Annotation]:
    return [a for a in annotations if a.applied]


def corrections(annotations: list[Annotation]) -> list[Annotation]:
    return [a for a in annotations if a.is_correction]


def aliases(annotations: list[Annotation]) -> list[Annotation]:
    return [a for a in annotations if a.is_alias]


def in_band(annotations: list[Annotation], band: str | tuple[str, ...]) -> list[Annotation]:
    bands = (band,) if isinstance(band, str) else band
    return [a for a in annotations if a.band in bands]


def to_json(annotations: list[Annotation], indent: int = 2) -> str:
    return json.dumps([a.to_dict() for a in annotations], ensure_ascii=False, indent=indent)


def write_json(annotations: list[Annotation], path: str | Path) -> Path:
    path = Path(path)
    path.write_text(to_json(annotations) + "\n", encoding="utf-8")
    return path
