"""D-005: short strings match by exact equality only."""

from transcript_normalizer import find_annotations, parse_caption


def annotate(pack, line):
    return find_annotations(parse_caption(f"0:01 {line}"), pack)


def applied_terms(pack, line):
    """What the run would actually correct. D-011's low band is a mark, not a match."""
    return [a.term for a in annotate(pack, line) if a.applied]


def test_tri_does_not_match_divida(pack):
    # `tri` is 3 characters, so fuzzy similarity never applies to it.
    assert "tri" not in [a.term for a in annotate(pack, "a dívida da companhia")]
    # `dívida` only ever reaches `dividendo` as a low mark, never as a correction.
    assert applied_terms(pack, "a dívida da companhia") == []


def test_end_does_not_match_ainda(pack):
    # `End` is a listed variant of Engie, but it is too short to match fuzzily.
    assert annotate(pack, "ele ainda não falou") == []


def test_ward_matches_word_only_as_a_listed_variant(pack):
    hits = [a for a in annotate(pack, "abri o Word ontem") if a.term == "Ward"]
    assert [(a.original, a.rule, a.band, a.score) for a in hits] == [
        ("Word", "term:variant", "high", 100)
    ]

    # Nothing else of that length reaches Ward: only the listed variant does.
    assert annotate(pack, "abri o Ford ontem") == []
