"""Brazilian Portuguese (D-033). Everything the core used to know about pt-BR."""

from __future__ import annotations

import re
import unicodedata

from .base import UnitRule, fold_numbers

CODE = "pt-BR"

# ------------------------------------------------------------------ normalize

_KEEP = re.compile(r"[^a-z0-9$ ]+")


#: D-084: the words for 2 to 20, folded, and their digits. 1 is left out: `um`
#: and `uma` are articles far more often than numbers.
NUMBER_WORDS = {
    "dois": "2", "duas": "2", "tres": "3", "quatro": "4", "cinco": "5", "seis": "6",
    "sete": "7", "oito": "8", "nove": "9", "dez": "10", "onze": "11", "doze": "12",
    "treze": "13", "catorze": "14", "quatorze": "14", "quinze": "15", "dezesseis": "16",
    "dezasseis": "16", "dezessete": "17", "dezassete": "17", "dezoito": "18",
    "dezenove": "19", "dezanove": "19", "vinte": "20",
}


def normalize(text: str) -> str:
    """Lowercase, accents stripped, anything else flattened to a space; then
    D-084's number words as digits."""
    s = unicodedata.normalize("NFD", unicodedata.normalize("NFC", text).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return fold_numbers(_KEEP.sub(" ", s).strip(), NUMBER_WORDS, common_words)


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

#: D-024; D-044 adds the comma. A comma inside a token (`11,5`) is a decimal separator.
sentence_boundaries: frozenset[str] = frozenset(".?!;,")


# ------------------------------------------------------------------ skeleton

_CONSONANT = "bcdfghjklmnpqrstvwxz"


def skeleton(text: str) -> str:
    """D-050: a pt-BR consonant skeleton, for the phonetic source.

    Folded as `normalize` folds, spaces dropped (`BR Portness` sounds like
    `brportness`). Then s/c/ç -> s, g/j -> j, and l or u before a consonant ->
    `w` (vocalized; a letter of its own so the vowel pass keeps it). The vowels
    go and doubled letters collapse: what is left is what a recognizer rarely
    gets wrong in a name, and the vowels it often does.
    """
    s = normalize(text).replace(" ", "")
    s = re.sub(rf"[lu](?=[{_CONSONANT}])", "w", s)
    s = re.sub(r"[sc]", "s", s)
    s = re.sub(r"[gj]", "j", s)
    s = re.sub(r"[aeiouy]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


# ------------------------------------------------------------------ common words

#: D-032, D-066: ordinary words, normalized; the pack editor warns when a
#: variant is made of these only (`esse amigo`, `me caiu`).
common_words: frozenset[str] = frozenset("""
a ao aos aquela aquele aquilo as ate bem cada como com da das de dela dele depois
do dos e ela ele eles em entao entre era essa esse esta estava este eu foi for ha
isso isto ja la lhe mais mas me mesmo meu minha muito na nao nas nem no nos nossa
nosso num numa o os ou para pela pelo pode por porque pra quando que quem se sem
ser seu sua so sobre tambem tem ter tipo tudo um uma umas uns vai voce
amigo caiu cair coisa dia diz faz fazer gente hoje tira rapido divide trio oxe
""".split())
