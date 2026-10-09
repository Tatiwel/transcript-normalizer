"""D-011: the three confidence bands."""

import pytest
import yaml

from transcript_normalizer import load_pack
from transcript_normalizer.core.matcher import (
    APPLY_THRESHOLD,
    MARK_THRESHOLD,
    VARIANT_APPLY_THRESHOLD,
)
from transcript_normalizer.core.pack import Learned

from .conftest import PACK, annotate


@pytest.fixture
def pack_without_semiga(tmp_path):
    """The fixture pack with `semiga` dropped, so it has to be reached fuzzily."""
    data = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    for term in data["terms"]:
        if term["term"] == "CEMIG":
            term["variants"] = [v for v in term["variants"] if v != "semiga"]
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), "utf-8")
    return load_pack(path)


def test_thresholds_are_d011s_apply_and_d029s_mark():
    assert (MARK_THRESHOLD, APPLY_THRESHOLD) == (70, 80)


def test_listed_variant_is_high(pack_without_semiga):
    hits = [a for a in annotate(pack_without_semiga, "olha a SEMIG hoje") if a.applied]
    assert [(a.original, a.term, a.rule, a.band) for a in hits] == [
        ("SEMIG", "CEMIG", "term:variant", "high")
    ]


def test_unlisted_near_miss_of_a_variant_under_85_is_a_mark(pack_without_semiga):
    hits = [
        a
        for a in annotate(pack_without_semiga, 'Pô, semiga é horrível')
        if a.original == "semiga"
    ]
    assert len(hits) == 1
    a = hits[0]
    # Unlisted, so it is reached fuzzily. Since D-014 the nearest string is
    # `SEMigd`, which belongs to Cemig D; the band is what this test is about.
    # D-047: reached from a variant at 83, under 85, so a mark, not applied.
    assert a.term == "Cemig D"
    assert a.rule == "term:fuzzy"
    assert APPLY_THRESHOLD <= a.score < VARIANT_APPLY_THRESHOLD
    assert a.band == "low"
    assert a.applied is False


def synthetic(tmp_path, stem):
    # Deliberately synthetic: two 20-character strings, `stem` plus five or
    # seven letters the other one never uses, so the score is 200 * len(stem) / 40.
    pack_file = tmp_path / "pack.yaml"
    pad = "k" * (20 - len(stem))
    pack_file.write_text(
        f"language: pt-BR\nversion: test\nterms:\n  - term: {stem}{pad}\n    class: conceito\n", "utf-8"
    )
    return load_pack(pack_file, learned=Learned()), stem + "b" * (20 - len(stem))


def test_a_75_score_match_is_low_and_not_applied(tmp_path):
    """15 shared characters of 20: 75, inside the mark band of D-029."""
    pack, span = synthetic(tmp_path, "custo de capita")
    hits = annotate(pack, f"o {span} subiu")
    assert len(hits) == 1
    a = hits[0]
    assert a.original == span
    assert a.score == 75
    assert a.rule == "term:fuzzy"
    assert a.band == "low"
    assert a.applied is False


def test_a_65_score_match_is_below_the_mark_and_not_annotated(tmp_path):
    """13 shared characters of 20: 65, low band under D-011's 60, nothing under D-029."""
    pack, span = synthetic(tmp_path, "custo de capi")
    assert annotate(pack, f"o {span} subiu") == []


def tiny(tmp_path, terms):
    path = tmp_path / "tiny.yaml"
    path.write_text(yaml.safe_dump({"language": "pt-BR", "version": "test", "terms": terms}), "utf-8")
    return load_pack(path)


def test_the_same_score_applies_from_the_term_and_only_marks_from_a_variant(tmp_path):
    """D-047, measured: `Portizar` (a BR Partners variant) reached `aportar` at 80."""
    as_variant = tiny(tmp_path, [{"term": "BR Partners", "class": "companhia", "variants": ["Portizar"]}])
    as_term = tiny(tmp_path, [{"term": "Portizar", "class": "companhia"}])
    [mark] = [a for a in annotate(as_variant, "quero aportar mais") if a.original == "aportar"]
    [guess] = [a for a in annotate(as_term, "quero aportar mais") if a.original == "aportar"]
    assert mark.score == guess.score == 80
    assert (mark.band, guess.band) == ("low", "medium")


# D-047's other half: a variant's fuzzy score of 80-84 ranks as a mark when
# candidates compete for one span, so a candidate that reaches 80 or more on its
# own (here the canonical term) wins the span and applies. Deliberately synthetic:
# 25 letters, the term sharing 20 of them (80), the variant 21 (84).
SPAN = "abcdefghijklmnopqrstuvwxy"
TERM = "abcdefghijklmnopqrstzzzzz"
VARIANT = "abcdefghijklmnopqrstuzzzz"


def test_the_synthetic_scores_are_80_from_the_term_and_84_from_the_variant():
    from rapidfuzz import fuzz

    assert (fuzz.ratio(SPAN, TERM), fuzz.ratio(SPAN, VARIANT)) == (80, 84)


def test_the_term_at_80_beats_its_own_variant_at_84(tmp_path):
    pack = tiny(tmp_path, [{"term": TERM, "class": "conceito", "variants": [VARIANT]}])
    [a] = [a for a in annotate(pack, f"o {SPAN} subiu") if a.original == SPAN]
    assert (a.term, a.rule, a.score, a.band) == (TERM, "term:fuzzy", 80, "medium")


def test_another_term_at_80_beats_a_variant_at_84(tmp_path):
    pack = tiny(tmp_path, [
        {"term": TERM, "class": "conceito"},
        {"term": "Outro Termo", "class": "conceito", "variants": [VARIANT]},
    ])
    [a] = [a for a in annotate(pack, f"o {SPAN} subiu") if a.original == SPAN]
    assert (a.term, a.score, a.band) == (TERM, 80, "medium")
