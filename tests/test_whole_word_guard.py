"""D-030: "the term is already spelled out here" means as whole words."""

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned

from .conftest import PACK_V2


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


TETOS = "calcular aqui os preços tetos, perceba"


def test_a_window_covered_by_its_own_name_is_no_guess_before_resolution(v2):
    """D-049: `preços` inside `preços tetos` (the term, inflected) is no guess at
    preço teto, even before overlap resolution."""
    raw = find_annotations(parse_caption(f"0:01 {TETOS}"), v2)
    assert [a for a in raw if a.original == "preços" and a.term == "preço teto"] == []


def test_the_guard_holds_when_the_name_is_itself_rejected():
    """Why D-049 is not left to overlap resolution: a rejection by containment
    (D-027) of `tetos -> preço teto` removes the annotation of the alias `preços
    tetos`, and without the guard `preços` comes back as a mark on preço teto
    (fuzzy, 76) in annotations.json. Measured on wxgFO_fyfXg with the bundled
    pack: three such marks."""
    pack = load_pack(PACK_V2, learned=Learned().reject("tetos", "preço teto"))
    found = resolve_overlaps(find_annotations(parse_caption(f"0:01 {TETOS}"), pack))
    assert [a for a in found if a.term == "preço teto"] == []
