"""The protocol a language module implements (D-033).

A language module is a plain Python module that provides:

- `normalize(text) -> str`: the form text is compared in. Case and accent
  folding, and whatever the language needs flattened.
- `inflections(word) -> set[str]`: the base forms a normalized single word may
  be an inflection of (D-031a). `set()` when it is not inflected.
- `unit_rules() -> list[UnitRule]`: the deterministic unit layer (D-006).
- `sentence_boundaries`: the punctuation a word n-gram never runs across (D-024).
- `NUMBER_WORDS` (optional): number words and their digits, which
  `fold_numbers` folds inside `normalize` (D-084).
- `skeleton`: a function `text -> str` that keeps what a name sounds like and
  drops what a recognizer gets wrong (D-050), or `None`, which turns the
  phonetic source off for the language.

The core calls these and nothing else; it holds no rule of any language.
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple, Protocol, runtime_checkable


class UnitRule(NamedTuple):
    """One unit rule: `pattern` matched over the text, rewritten by `replacement`.

    `replacement` is a `re.Match.expand` template (`r"\\1 bi"`). `term` is the
    rule's own name for the unit; a pack term that names it, by its name or an
    alias, takes the annotation (`bi` -> `bilhão`). `owns` lists words that only
    this rule may match for that pack term: after a number they are the unit,
    anywhere else they are left to the dictionary. Rules apply in order, and a
    match that overlaps one accepted from an earlier rule is dropped.
    """

    pattern: re.Pattern
    replacement: str
    term: str
    owns: tuple[str, ...] = ()


@runtime_checkable
class Language(Protocol):
    sentence_boundaries: frozenset[str]
    skeleton: Callable[[str], str] | None

    def normalize(self, text: str) -> str: ...

    def inflections(self, word: str) -> set[str]: ...

    def unit_rules(self) -> list[UnitRule]: ...


_PIECES = re.compile(r"\S+|\s+")


def fold_numbers(folded: str, words: dict[str, str], common: frozenset[str] = frozenset()) -> str:
    """D-084: each number word of normalized text as its digits, for matching
    only; the text is never rewritten from this. The spacing is kept as it was.

    A number word one space after a word that ends in a letter, is not itself a
    number word and is not an ordinary word, joins it, as a ticker is written:
    `bova onze` -> `bova11`, while `de onze` -> `de 11`.
    """
    out: list[str] = []
    for piece in _PIECES.findall(folded):
        digits = words.get(piece)
        if digits is None:
            out.append(piece)
            continue
        before = out[-2] if len(out) >= 2 and out[-1] == " " else ""
        if before and before[-1].isalpha() and before not in words and before not in common:
            out[-2:] = [before + digits]
        else:
            out.append(digits)
    return "".join(out)
