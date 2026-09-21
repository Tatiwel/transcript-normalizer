"""Matching a domain pack against a transcript (D-001, D-003, D-005, D-006, D-007).

This is a port of `experiments/exp2_units_and_threshold.py`, which is the reference
behaviour, with one deliberate difference: matching runs over the whole joined text
instead of line by line (D-007).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .pack import Pack, fold
from .rules import find_unit_hits
from .standoff import RULE_UNIT, Annotation, term_rule
from .text import Transcript

#: D-011, apply band. D-005 calls the same number the fuzzy threshold.
APPLY_THRESHOLD = 80

#: D-005: fuzzy similarity needs 6+ characters on both sides and similar lengths.
MIN_FUZZY_LEN = 6
MAX_LEN_DIFF = 2

#: Word n-grams the matcher considers.
NGRAM_SIZES = (1, 2, 3)

_TOKEN = re.compile(r"[\wÀ-ÿ$%,.]+")
_WORDY = re.compile(r"\w")
_EDGE = ".,"


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    """Word tokens with their offsets in `text`, as exp2 split them."""
    tokens: list[Token] = []
    for m in _TOKEN.finditer(text):
        raw, start, end = m.group(0), m.start(), m.end()
        if not _WORDY.search(raw):
            continue
        while raw and raw[0] in _EDGE:
            raw, start = raw[1:], start + 1
        while raw and raw[-1] in _EDGE:
            raw, end = raw[:-1], end - 1
        if raw:
            tokens.append(Token(raw, start, end))
    return tokens


def _score(span: str, candidate: str) -> int:
    """D-005: fuzzy only for long, similarly sized strings; otherwise exact equality."""
    if (
        len(span) >= MIN_FUZZY_LEN
        and len(candidate) >= MIN_FUZZY_LEN
        and abs(len(span) - len(candidate)) <= MAX_LEN_DIFF
    ):
        return fuzz.ratio(span, candidate)
    return 100 if span == candidate else 0


def find_annotations(
    transcript: Transcript, pack: Pack, threshold: int = APPLY_THRESHOLD
) -> list[Annotation]:
    """Every stand-off annotation the pack proposes for the transcript.

    Overlapping proposals are all returned; `resolve_overlaps` picks between them.
    """
    text = transcript.text
    annotations: list[Annotation] = []

    # D-006: the unit layer runs before the dictionary.
    for hit in find_unit_hits(text):
        annotations.append(
            Annotation(
                start=hit.start,
                end=hit.end,
                original=hit.original,
                replacement=hit.replacement,
                term=hit.term,
                rule=RULE_UNIT,
                score=100,
                pack_version=pack.version,
            )
        )

    origins = {}
    for c in pack.candidates:
        origins.setdefault((c.term, c.folded), c.origin)
    folded_term = {t.term: fold(t.term) for t in pack.terms}
    folded_aliases = {t.term: tuple(fold(a) for a in t.aliases) for t in pack.terms}

    tokens = tokenize(text)
    for n in NGRAM_SIZES:
        for i in range(len(tokens) - n + 1):
            window = tokens[i : i + n]
            span = " ".join(t.text for t in window)
            folded_span = fold(span)
            if len(folded_span) < 2:
                continue
            score, term, candidate = max(
                (
                    (_score(folded_span, c.folded), c.term, c.folded)
                    for c in pack.candidates
                ),
                default=(0, None, None),
            )
            if score < threshold:
                continue
            # The term (or one of its aliases) is already spelled out here: nothing to correct.
            if folded_term[term] in folded_span:
                continue
            if any(a in folded_span for a in folded_aliases[term]):
                continue
            origin = origins[(term, candidate)]
            rule = term_rule(origin if folded_span == candidate else "fuzzy")
            annotations.append(
                Annotation(
                    start=window[0].start,
                    end=window[-1].end,
                    original=text[window[0].start : window[-1].end],
                    replacement=term,
                    term=term,
                    rule=rule,
                    score=int(score),
                    pack_version=pack.version,
                )
            )
    return annotations


def resolve_overlaps(annotations: list[Annotation]) -> list[Annotation]:
    """Keep one annotation per stretch of text: best score first, then longest span."""
    ordered = sorted(
        annotations, key=lambda a: (-a.score, -(a.end - a.start), a.start, a.rule)
    )
    kept: list[Annotation] = []
    for a in ordered:
        if any(a.start < k.end and k.start < a.end for k in kept):
            continue
        kept.append(a)
    return sorted(kept, key=lambda a: (a.start, a.end))
