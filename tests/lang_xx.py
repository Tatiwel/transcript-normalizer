"""A fake language module for `xx`, following D-033's protocol.

The template for a real one. Each piece is deliberately unlike pt-BR, so a test
can tell the module's behaviour from the core's: plurals end in `-ix`, the unit
is `number + zk`, and `|` ends a sentence.
"""

import re

from transcript_normalizer.languages import generic
from transcript_normalizer.languages.base import UnitRule

CODE = "xx"

sentence_boundaries = frozenset("|")

skeleton = None  # D-050: optional; None turns the phonetic source off


def normalize(text):
    return generic.normalize(text)


def inflections(word):
    return {word[:-2]} if word.endswith("ix") and len(word) > 2 else set()


def unit_rules():
    return [UnitRule(re.compile(r"(\d+)\s+zk\b"), r"\1 zorkon", "zorkon")]
