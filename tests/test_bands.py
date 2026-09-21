"""D-011: the three confidence bands."""

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.matcher import APPLY_THRESHOLD, MARK_THRESHOLD

from .conftest import PACK


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


def annotate(pack, line):
    return find_annotations(parse_caption(f"0:01 {line}"), pack)


def test_thresholds_are_the_two_numbers_of_d011():
    assert (MARK_THRESHOLD, APPLY_THRESHOLD) == (60, 80)


def test_listed_variant_is_high(pack_without_semiga):
    hits = [a for a in annotate(pack_without_semiga, "olha a SEMIG hoje") if a.applied]
    assert [(a.original, a.term, a.rule, a.band) for a in hits] == [
        ("SEMIG", "CEMIG", "term:variant", "high")
    ]


def test_unlisted_near_miss_is_medium(pack_without_semiga):
    hits = [
        a
        for a in annotate(pack_without_semiga, 'Pô, semiga é horrível')
        if a.term == "CEMIG" and a.original == "semiga"
    ]
    assert len(hits) == 1
    a = hits[0]
    assert a.rule == "term:fuzzy"
    assert a.band == "medium"
    assert a.applied is True
    assert a.score >= APPLY_THRESHOLD


def test_a_65_score_match_is_low_and_not_applied(tmp_path):
    # Deliberately synthetic: two 20-character strings sharing a 13-character
    # subsequence score 200 * 13 / 40 = 65 exactly, which is inside D-011's
    # mark band. Nothing on the fixture lands on exactly 65.
    pack_file = tmp_path / "pack.yaml"
    pack_file.write_text(
        "version: test\nterms:\n  - term: custo de capikkkkkkk\n    class: teste\n", "utf-8"
    )
    pack = load_pack(pack_file)

    hits = annotate(pack, "o custo de capibbbbbbb subiu")
    assert len(hits) == 1
    a = hits[0]
    assert a.original == "custo de capibbbbbbb"
    assert a.score == 65
    assert a.rule == "term:fuzzy"
    assert a.band == "low"
    assert a.applied is False
