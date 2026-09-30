"""Matching a domain pack against a transcript (D-001, D-003, D-005, D-006, D-007).

This is a port of `experiments/exp2_units_and_threshold.py`, which is the reference
behaviour, with one deliberate difference: matching runs over the whole joined text
instead of line by line (D-007).

Nothing here knows a language (D-033). Normalization, inflection, unit rules and
sentence punctuation all come from the pack's language module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from rapidfuzz import fuzz

from .pack import SOURCE_LEARNED, Candidate, Pack
from .rules import find_unit_hits
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



@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    #: Strong punctuation stands between this token and the next (D-024).
    closes_sentence: bool = False


def tokenize(text: str, boundaries: frozenset[str] | str) -> list[Token]:
    """Word tokens with their offsets in `text`, as exp2 split them.

    `boundaries` is the language's sentence punctuation (D-024): each token
    followed by one is marked, and no n-gram runs across the mark. A `.` inside
    a token (`6.7`) is a decimal point, not an end of sentence.
    """
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
        marked.append(replace(token, closes_sentence=any(c in boundaries for c in gap)))
    return marked


def band_for(rule: str, score: float) -> str:
    """D-011: which confidence band a proposal falls in."""
    if rule != term_rule("fuzzy"):
        return BAND_HIGH  # a unit rule, a listed variant or an alias
    return BAND_MEDIUM if score >= APPLY_THRESHOLD else BAND_LOW


#: D-028: the class whose terms never enter fuzzy matching.
UNIT_CLASS = "unidade"


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
    language = pack.language
    norm = language.normalize
    rules = language.unit_rules()

    # D-006: the unit layer runs before the dictionary. Its output belongs to the
    # pack term that names the unit, when the pack has one (`bi` -> `bilhão`),
    # and that term's rule-owned words are not matched on their own below.
    owned: set[tuple[str, str]] = set()
    for rule in rules:
        unit = pack.term_named(rule.term)
        if unit is not None:
            owned |= {(unit.term, norm(word)) for word in rule.owns}

    for hit in find_unit_hits(text, rules):
        unit = pack.term_named(hit.term)
        term = unit.term if unit is not None else hit.term
        if pack.is_rejected(norm(hit.original), term):
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
    folded_term = {t.term: norm(t.term) for t in pack.terms}
    # Every other name the term is spelled out by: curated and learned aliases.
    folded_aliases: dict[str, list[str]] = {t.term: [] for t in pack.terms}
    for c in pack.candidates:
        if c.origin == "alias":
            folded_aliases[c.term].append(c.folded)

    # D-031a: a word whose base form (per the language) is a single-word term or
    # alias is that term spelled out. An explicit entry of any term wins, and
    # among bases the earliest candidate of the pack does.
    explicit = {c.folded for c in pack.candidates}
    base_owner: dict[str, tuple[int, str]] = {}
    for index, c in enumerate(pack.candidates):
        if c.origin in ("term", "alias") and " " not in c.folded:
            base_owner.setdefault(c.folded, (index, c.term))

    def inflection_of(word: str) -> str | None:
        """The term a normalized word is an inflection of, if any."""
        if word in explicit:
            return None
        owners = [base_owner[b] for b in language.inflections(word) if b in base_owner]
        return min(owners)[1] if owners else None

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

    # D-040: the same, for the term's own names only (canonical and aliases).
    name_forms: dict[str, set[str]] = {}
    for c in candidates:
        if c.origin in ("term", "alias"):
            name_forms.setdefault(" ".join(c.folded.split()), set()).add(c.term)

    def exact_terms(run: str) -> set[str]:
        """The terms a run of words is exactly a form of, inflections included."""
        found = set(exact_forms.get(run, ()))
        if " " not in run:
            owner = inflection_of(run)
            if owner is not None:
                found.add(owner)
        return found

    def spelled_out(folded_span: str, term: str) -> bool:
        """The term, an alias or (D-031a) an inflection of either, as whole words."""
        if contains_words(folded_span, folded_term[term]):
            return True
        if any(contains_words(folded_span, a) for a in folded_aliases[term]):
            return True
        return any(inflection_of(word) == term for word in folded_span.split())

    tokens = tokenize(text, language.sentence_boundaries)

    def windows():
        for n in NGRAM_SIZES:
            for i in range(len(tokens) - n + 1):
                window = tokens[i : i + n]
                if any(t.closes_sentence for t in window[:-1]):
                    continue  # D-024: `Warn Buffet. Tem` is two sentences, not one term
                yield i, window, norm(" ".join(t.text for t in window))

    # D-034: every stretch of text that is exactly a form of some term, found
    # before any fuzzy guess, as the terms each token takes part in. Whether that
    # stretch produces an annotation does not matter: `market cap` spelled out
    # produces none, and still rules `market` out as a guess at market share.
    exact_at: list[set[str]] = [set() for _ in tokens]
    for i, window, folded_span in windows():
        terms = exact_terms(" ".join(folded_span.split()))
        if terms:
            for k in range(i, i + len(window)):
                exact_at[k] |= terms

    # D-040: every stretch of text that is exactly a term or an alias, as
    # (first token, past the last, terms). A shorter correction of another term
    # overlapping it is not a correction: `Dividend` in `Dividend Yield`.
    exact_names: list[tuple[int, int, set[str]]] = []
    for i, window, folded_span in windows():
        run = " ".join(folded_span.split())
        names = set(name_forms.get(run, ()))
        if " " not in run and (owner := inflection_of(run)) is not None:
            names.add(owner)
        if names:
            exact_names.append((i, i + len(window), names))

    def inside_a_longer_name(i: int, j: int, term: str) -> bool:
        return any(
            s < j and i < e and e - s > j - i and names - {term}
            for s, e, names in exact_names
        )

    for i, window, folded_span in windows():
        if len(folded_span) < 2:
            continue

        # D-031a: an inflected single word is its term spelled out: an alias.
        owner = inflection_of(folded_span) if " " not in folded_span else None
        if owner is not None:
            if not pack.is_rejected(folded_span, owner):
                original = text[window[0].start : window[-1].end]
                annotations.append(
                    Annotation(
                        start=window[0].start,
                        end=window[-1].end,
                        original=original,
                        replacement=original,
                        term=owner,
                        rule=term_rule("alias"),
                        band=BAND_HIGH,
                        score=100,
                        pack_version=pack.version,
                        kind=KIND_ALIAS,
                    )
                )
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
        if spelled_out(folded_span, term):
            continue
        rule = term_rule(origin if folded_span == candidate else "fuzzy")
        # D-031 (b), as D-034 amends it: a fuzzy span that overlaps, either
        # way, an exact form of another term is not a guess at this one
        # (`dividendos e` is not dividend yield; `market` in `market cap` is
        # not market share).
        if rule == term_rule("fuzzy") and any(
            exact_at[k] - {term} for k in range(i, i + len(window))
        ):
            continue
        # D-040: D-034 for exact corrections too, when the name is longer.
        if inside_a_longer_name(i, i + len(window), term):
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
