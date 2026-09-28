"""Matching a domain pack against a transcript (D-001, D-003, D-005, D-006, D-007).

This is a port of `experiments/exp2_units_and_threshold.py`, which is the reference
behaviour, with one deliberate difference: matching runs over the whole joined text
instead of line by line (D-007).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from rapidfuzz import fuzz

from .pack import SOURCE_LEARNED, Candidate, Pack, fold
from .rules import RULE_TOKENS, find_unit_hits
from .standoff import (
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    KIND_ALIAS,
    RULE_UNIT,
    Annotation,
    term_rule,
)
from .text import Transcript

# D-011's two thresholds live here and nowhere else. Apply at or above 80 (which
# is also D-005's fuzzy threshold); between 70 and 80, mark but do not apply.
# D-029 raised the mark threshold from D-011's initial 60.
APPLY_THRESHOLD = 80
MARK_THRESHOLD = 70

#: D-005: fuzzy similarity needs 6+ characters on both sides and similar lengths.
MIN_FUZZY_LEN = 6
MAX_LEN_DIFF = 2

#: Word n-grams the matcher considers.
NGRAM_SIZES = (1, 2, 3)

_TOKEN = re.compile(r"[\wÀ-ÿ$%,.]+")
_WORDY = re.compile(r"\w")
_EDGE = ".,"

#: D-024: strong punctuation. A word n-gram never runs across one. A `.` inside
#: a token (`6.7`) is a decimal point, not an end of sentence.
STRONG_PUNCTUATION = ".?!;"


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    #: Strong punctuation stands between this token and the next (D-024).
    closes_sentence: bool = False


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

    # D-024: look at what separates each token from the next. A `.` stripped
    # off a token's edge above lands here, which is exactly the sentence end.
    marked = []
    for i, token in enumerate(tokens):
        following = tokens[i + 1].start if i + 1 < len(tokens) else len(text)
        gap = text[token.end : following]
        marked.append(replace(token, closes_sentence=any(c in STRONG_PUNCTUATION for c in gap)))
    return marked


def band_for(rule: str, score: float) -> str:
    """D-011: which confidence band a proposal falls in."""
    if rule != term_rule("fuzzy"):
        return BAND_HIGH  # a unit rule, a listed variant or an alias
    return BAND_MEDIUM if score >= APPLY_THRESHOLD else BAND_LOW


#: D-028: the class whose terms never enter fuzzy matching.
UNIT_CLASS = "unidade"


def exact_elsewhere(folded_span: str, term: str, exact_forms: dict[str, set[str]]) -> bool:
    """Whether some run of the span's words is exactly a form of a term other than `term`."""
    words = folded_span.split()
    for size in range(1, len(words) + 1):
        for start in range(len(words) - size + 1):
            if exact_forms.get(" ".join(words[start : start + size]), {term}) - {term}:
                return True
    return False


def contains_words(span: str, part: str) -> bool:
    """Whether folded `part` occurs in folded `span` as whole words (D-027, D-030)."""
    return f" {' '.join(part.split())} " in f" {' '.join(span.split())} "


def fuzzy_allowed(candidate: Candidate, unit_terms: frozenset[str] = frozenset()) -> bool:
    """D-025: fuzzy runs against the canonical term and curated pack variants only.

    Aliases are legitimate spellings, not misrecognitions, and learned variants
    are unreviewed; both match by exact normalized equality. Otherwise the alias
    `bilhões` reaches `milhões`, and every confirmation widens fuzzy reach.

    D-028: nothing of a `unidade` term is fuzzy, not even its canonical name.
    `milhão` and `bilhão` are both real words one letter apart, and no threshold
    separates them; units are matched by the rules of D-006 and exactly.
    """
    return (
        candidate.origin != "alias"
        and candidate.source != SOURCE_LEARNED
        and candidate.term not in unit_terms
    )


def _score(span: str, candidate: str, fuzzy: bool = True) -> int:
    """D-005: fuzzy only for long, similarly sized strings; otherwise exact equality."""
    if (
        fuzzy
        and len(span) >= MIN_FUZZY_LEN
        and len(candidate) >= MIN_FUZZY_LEN
        and abs(len(span) - len(candidate)) <= MAX_LEN_DIFF
    ):
        return fuzz.ratio(span, candidate)
    return 100 if span == candidate else 0


def find_annotations(
    transcript: Transcript, pack: Pack, threshold: int = MARK_THRESHOLD
) -> list[Annotation]:
    """Every stand-off annotation the pack proposes for the transcript.

    The search runs down to D-011's mark threshold, so low-band proposals are
    returned too; `Annotation.applied` says which ones count. Overlapping
    proposals are all returned; `resolve_overlaps` picks between them.
    """
    text = transcript.text
    annotations: list[Annotation] = []

    # D-006: the unit layer runs before the dictionary. Its output belongs to the
    # pack term that names the unit, when the pack has one (`bi` -> `bilhão`),
    # and that term's rule-owned words are not matched on their own below.
    owned: set[tuple[str, str]] = set()
    for rule_term, tokens in RULE_TOKENS.items():
        unit = pack.term_named(rule_term)
        if unit is not None:
            owned |= {(unit.term, fold(token)) for token in tokens}

    for hit in find_unit_hits(text):
        unit = pack.term_named(hit.term)
        term = unit.term if unit is not None else hit.term
        if pack.is_rejected(fold(hit.original), term):
            continue
        annotations.append(
            Annotation(
                start=hit.start,
                end=hit.end,
                original=hit.original,
                replacement=hit.replacement,
                term=term,
                rule=RULE_UNIT,
                band=BAND_HIGH,
                score=100,
                pack_version=pack.version,
            )
        )

    origins = {}
    for c in pack.candidates:
        origins.setdefault((c.term, c.folded), c.origin)
    folded_term = {t.term: fold(t.term) for t in pack.terms}
    # Every other name the term is spelled out by: curated and learned aliases,
    # and (D-031) the plurals of the term and of those aliases.
    folded_aliases: dict[str, list[str]] = {t.term: [] for t in pack.terms}
    for c in pack.candidates:
        if c.origin == "alias":
            folded_aliases[c.term].append(c.folded)

    candidates = [
        c
        for c in pack.candidates
        if not (c.origin == "variant" and (c.term, c.folded) in owned)
    ]

    unit_terms = frozenset(t.term for t in pack.terms if t.klass == UNIT_CLASS)
    scored = [(c, fuzzy_allowed(c, unit_terms)) for c in candidates]

    # D-031 (b): folded text -> the terms it is an exact form of.
    exact_forms: dict[str, set[str]] = {}
    for c in candidates:
        exact_forms.setdefault(" ".join(c.folded.split()), set()).add(c.term)

    tokens = tokenize(text)
    for n in NGRAM_SIZES:
        for i in range(len(tokens) - n + 1):
            window = tokens[i : i + n]
            if any(t.closes_sentence for t in window[:-1]):
                continue  # D-024: `Warn Buffet. Tem` is two sentences, not one term
            span = " ".join(t.text for t in window)
            folded_span = fold(span)
            if len(folded_span) < 2:
                continue
            score, term, candidate = max(
                (
                    (_score(folded_span, c.folded, fuzzy), c.term, c.folded)
                    for c, fuzzy in scored
                ),
                default=(0, None, None),
            )
            if score < threshold:
                continue
            # D-013: a pair the user has turned down is never proposed again.
            if pack.is_rejected(folded_span, term):
                continue
            origin = origins[(term, candidate)]
            original = text[window[0].start : window[-1].end]

            # D-020: exactly another name of the term. Recognized, never substituted.
            if origin == "alias" and folded_span == candidate:
                annotations.append(
                    Annotation(
                        start=window[0].start,
                        end=window[-1].end,
                        original=original,
                        replacement=original,
                        term=term,
                        rule=term_rule("alias"),
                        band=BAND_HIGH,
                        score=int(score),
                        pack_version=pack.version,
                        kind=KIND_ALIAS,
                    )
                )
                continue

            # The term (or one of its aliases) is already spelled out here: nothing to
            # correct. D-030: as whole words, so `deck` is not `dec` spelled out.
            if contains_words(folded_span, folded_term[term]):
                continue
            if any(contains_words(folded_span, a) for a in folded_aliases[term]):
                continue
            rule = term_rule(origin if folded_span == candidate else "fuzzy")
            # D-031 (b): a span holding an exact form of another term is not a
            # fuzzy guess at this one (`dividendos e` is not dividend yield).
            if rule == term_rule("fuzzy") and exact_elsewhere(folded_span, term, exact_forms):
                continue
            annotations.append(
                Annotation(
                    start=window[0].start,
                    end=window[-1].end,
                    original=original,
                    replacement=term,
                    term=term,
                    rule=rule,
                    band=band_for(rule, score),
                    score=int(score),
                    pack_version=pack.version,
                )
            )
    return annotations


def resolve_overlaps(annotations: list[Annotation]) -> list[Annotation]:
    """Keep one annotation per stretch of text.

    Applied bands win over low marks, then the best score, then the longest span.
    """
    ordered = sorted(
        annotations,
        key=lambda a: (not a.applied, -a.score, -(a.end - a.start), a.start, a.rule),
    )
    kept: list[Annotation] = []
    for a in ordered:
        if any(a.start < k.end and k.start < a.end for k in kept):
            continue
        kept.append(a)
    return sorted(kept, key=lambda a: (a.start, a.end))
