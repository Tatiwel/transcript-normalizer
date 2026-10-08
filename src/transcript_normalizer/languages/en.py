"""English (D-068): folding, plurals, the billion and million units, and the
sentence punctuation. No phonetic skeleton yet, so the phonetic source is off
for English packs (D-050)."""

from __future__ import annotations

import re
import unicodedata

from .base import UnitRule

CODE = "en"

# ------------------------------------------------------------------ normalize

_KEEP = re.compile(r"[^a-z0-9$ ]+")


def normalize(text: str) -> str:
    """Lowercase, accents stripped (`café` -> `cafe`), anything else a space."""
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _KEEP.sub(" ", s).strip()


# ------------------------------------------------------------------ inflections

#: D-031a, English: plural -> singular on normalized text: -ies -> -y,
#: -es, -s. A word in -ss (`class`) is not a plural.
_PLURALS = (("ies", "y"), ("es", ""), ("s", ""))


def inflections(word: str) -> set[str]:
    """The singulars a normalized single word may be the plural of."""
    if not word or " " in word or word.endswith("ss"):
        return set()
    bases = {word[: -len(plural)] + singular for plural, singular in _PLURALS if word.endswith(plural)}
    return {b for b in bases if len(b) > 1 and b != word}


# ------------------------------------------------------------------ unit rules

#: D-006, English: after a number, `bn` and `B` are billion, `mn` and `M`
#: million. The words each rule owns are the unit only after a number.
_BILLION_WORDS = ("bn", "B")
_MILLION_WORDS = ("mn", "M")

_UNIT_RULES = [
    UnitRule(
        re.compile(rf"(\d[\d.,]*)\s?({'|'.join(_BILLION_WORDS)})\b(?![\w])"),
        r"\1 billion", "billion", _BILLION_WORDS,
    ),
    UnitRule(
        re.compile(rf"(\d[\d.,]*)\s?({'|'.join(_MILLION_WORDS)})\b(?![\w])"),
        r"\1 million", "million", _MILLION_WORDS,
    ),
]


def unit_rules() -> list[UnitRule]:
    return list(_UNIT_RULES)


# ------------------------------------------------------------------ sentences

#: D-024, D-044: a comma inside a token (`1,500`) is a thousands separator.
sentence_boundaries: frozenset[str] = frozenset(".?!;,")

#: D-050: none yet.
skeleton = None

# ------------------------------------------------------------------ common words

#: D-032, D-066: ordinary words, which the pack editor warns about as variants.
common_words: frozenset[str] = frozenset("""
a about after again all also an and any are as at be because been before but by can
could did do does down each even for from get go going good got had has have he her
here him his how i if in into is it its just know like look make me more most my no
not now of off on one only or other our out over people right said say see she so some
take than that the their them then there these they thing think this those time to
two up us very was way we well were what when where which who why will with would yeah
year you your
""".split())
