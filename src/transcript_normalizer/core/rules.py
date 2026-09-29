"""The unit layer (D-006): a deterministic regex pass that runs before the dictionary.

The rules themselves belong to a language (D-033); this module only applies
them. Rules apply in order, and a match overlapping one accepted from an earlier
rule is dropped, so a longer pattern listed first wins over what it contains.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..languages.base import UnitRule


@dataclass(frozen=True)
class UnitHit:
    start: int
    end: int
    original: str
    replacement: str
    term: str


def find_unit_hits(text: str, rules: list[UnitRule]) -> list[UnitHit]:
    hits: list[UnitHit] = []
    taken: list[tuple[int, int]] = []
    for rule in rules:
        for m in rule.pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            hits.append(UnitHit(m.start(), m.end(), m.group(0), m.expand(rule.replacement), rule.term))
            taken.append((m.start(), m.end()))
    return hits
