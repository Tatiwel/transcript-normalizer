"""The generic language module: used only with --allow-generic (D-033).

Case and accent folding, the common sentence punctuation, and nothing else: no
inflections and no unit rules. Letters of any script survive normalization.
"""

from __future__ import annotations

import re
import unicodedata

from .base import UnitRule

CODE = "generic"

_NOT_WORD = re.compile(r"[^\w$]+")

sentence_boundaries: frozenset[str] = frozenset(".?!;")

#: D-050: no phonetic source without a language that defines one.
skeleton = None


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _NOT_WORD.sub(" ", s).strip()


def inflections(word: str) -> set[str]:
    return set()


def unit_rules() -> list[UnitRule]:
    return []
