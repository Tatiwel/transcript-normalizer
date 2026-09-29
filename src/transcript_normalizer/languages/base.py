"""The protocol a language module implements (D-033).

A language module is a plain Python module that provides:

- `normalize(text) -> str`: the form text is compared in. Case and accent
  folding, and whatever the language needs flattened.
- `inflections(word) -> set[str]`: the base forms a normalized single word may
  be an inflection of (D-031a). `set()` when it is not inflected.
- `unit_rules() -> list[UnitRule]`: the deterministic unit layer (D-006).
- `sentence_boundaries`: the punctuation a word n-gram never runs across (D-024).

The core calls these and nothing else; it holds no rule of any language.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Protocol, runtime_checkable


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

    def normalize(self, text: str) -> str: ...

    def inflections(self, word: str) -> set[str]: ...

    def unit_rules(self) -> list[UnitRule]: ...
