"""Unit rules (D-006): a deterministic regex layer that runs before the dictionary."""

from __future__ import annotations

import re
from dataclasses import dataclass

#: `number + number + (B | bit | be)` -- the stray repeated digit of `6.7 7 B`.
RE_UNIT_STRAY_DIGIT = re.compile(r"(\d[\d.,]*)\s+(\d)\s+(B|bit|be)\b")

#: `number + (B | bit | be)` -> `number bi`.
RE_UNIT = re.compile(r"(\d[\d.,]*)\s+(B|bit|be)\b(?![\w])")

#: `bilhões deais` -> `bilhões de reais`.
RE_REAIS = re.compile(r"(bilh[oõ]es|milh[oõ]es)\s+deais\b")


@dataclass(frozen=True)
class UnitHit:
    start: int
    end: int
    original: str
    replacement: str
    term: str


def find_unit_hits(text: str) -> list[UnitHit]:
    """Apply the unit rules to `text`. Longer patterns win over the ones they contain."""
    hits: list[UnitHit] = []
    taken: list[tuple[int, int]] = []

    for m in RE_UNIT_STRAY_DIGIT.finditer(text):
        hits.append(UnitHit(m.start(), m.end(), m.group(0), f"{m.group(1)} bi", "bi"))
        taken.append((m.start(), m.end()))

    for m in RE_UNIT.finditer(text):
        if any(m.start() < e and s < m.end() for s, e in taken):
            continue
        hits.append(UnitHit(m.start(), m.end(), m.group(0), f"{m.group(1)} bi", "bi"))

    for m in RE_REAIS.finditer(text):
        hits.append(
            UnitHit(m.start(), m.end(), m.group(0), f"{m.group(1)} de reais", "reais")
        )

    return hits
