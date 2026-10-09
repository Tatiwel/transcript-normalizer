"""D-030: "the term is already spelled out here" means as whole words."""

from transcript_normalizer import find_annotations, parse_caption, resolve_overlaps


def applied(pack, line):
    found = find_annotations(parse_caption(f"0:01 {line}"), pack)
    return [(a.original, a.term, a.rule) for a in found if a.applied]


def test_deck_is_a_variant_of_dec_not_dec_spelled_out(v2):
    assert ("deck", "DEC", "term:variant") in applied(v2, "o índice deck subiu")


def test_enterprise_valuey_is_a_variant_not_the_term_spelled_out(v2):
    assert ("Enterprise Valuey", "Enterprise Value", "term:variant") in applied(
        v2, "o Enterprise Valuey dela"
    )


def test_the_term_spelled_out_is_still_left_alone(v2):
    """Not corrected; since D-041, recognized.

    D-049: the longer window `o Enterprise Value` is a proposal again (fuzzy,
    94), and loses its span to the name itself (100) in overlap resolution.
    """
    found = resolve_overlaps(find_annotations(parse_caption("0:01 o DEC e o Enterprise Value"), v2))
    assert [(a.original, a.term, a.rule) for a in found if a.applied] == [
        ("DEC", "DEC", "term:exact"),
        ("Enterprise Value", "Enterprise Value", "term:exact"),
    ]


def test_a_plural_of_the_term_is_not_corrected_to_it(v2):
    """D-031 closes D-030's regression: the plural is the term spelled out."""
    found = [a for a in applied(v2, "pagou dividendos") if a[1] == "dividendo"]
    assert found == [("dividendos", "dividendo", "term:alias")]
