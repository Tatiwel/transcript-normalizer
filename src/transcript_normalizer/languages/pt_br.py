"""Brazilian Portuguese (D-033). Everything the core used to know about pt-BR."""

from __future__ import annotations

import re
import unicodedata

from .base import UnitRule

CODE = "pt-BR"

# ------------------------------------------------------------------ normalize

_KEEP = re.compile(r"[^a-z0-9$ ]+")


def normalize(text: str) -> str:
    """Lowercase, accents stripped, anything else flattened to a space."""
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _KEEP.sub(" ", s).strip()


# ------------------------------------------------------------------ inflections

#: D-031a, pt-BR: plural -> singular, on normalized (accent-free) text.
#: -s, -es, -ão -> -ões, -al -> -ais, -el -> -eis.
_PLURALS = (("oes", "ao"), ("ais", "al"), ("eis", "el"), ("es", ""), ("s", ""))


def inflections(word: str) -> set[str]:
    """The singulars a normalized single word may be the plural of."""
    if not word or " " in word:
        return set()
    bases = {word[: -len(plural)] + singular for plural, singular in _PLURALS if word.endswith(plural)}
    return {b for b in bases if b and b != word}


# ------------------------------------------------------------------ unit rules

#: D-006. The words `number + unit` owns: after a number they are `bi`.
_BI_WORDS = ("B", "bit", "be")
_BI = "|".join(_BI_WORDS)

_UNIT_RULES = [
    # `number + number + (B | bit | be)`: the stray repeated digit of `6.7 7 B`.
    UnitRule(re.compile(rf"(\d[\d.,]*)\s+(\d)\s+({_BI})\b"), r"\1 bi", "bi", _BI_WORDS),
    # `number + (B | bit | be)` -> `number bi`.
    UnitRule(re.compile(rf"(\d[\d.,]*)\s+({_BI})\b(?![\w])"), r"\1 bi", "bi", _BI_WORDS),
    # `bilhões deais` -> `bilhões de reais`.
    UnitRule(re.compile(r"(bilh[oõ]es|milh[oõ]es)\s+deais\b"), r"\1 de reais", "reais"),
]


def unit_rules() -> list[UnitRule]:
    return list(_UNIT_RULES)


# ------------------------------------------------------------------ sentences

#: D-024.
sentence_boundaries: frozenset[str] = frozenset(".?!;")
