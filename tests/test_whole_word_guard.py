"""D-030: "the term is already spelled out here" means as whole words."""

from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.core.matcher import contains_words
from transcript_normalizer.core.pack import Learned

PACK_V2 = Path(__file__).resolve().parents[1] / "packs" / "financas-ptbr.yaml"


@pytest.fixture(scope="module")
def v2():
    return load_pack(PACK_V2, learned=Learned())


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
    assert [a for a in applied(v2, "o DEC e o Enterprise Value") if a[1] in ("DEC", "Enterprise Value")] == []


@pytest.mark.parametrize(
    "span, part, expected",
    [
        ("dec", "dec", True),
        ("o dec subiu", "dec", True),
        ("deck", "dec", False),
        ("enterprise valuey", "enterprise value", False),
        ("o enterprise value dela", "enterprise value", True),
        ("preco  entao", "preco entao", True),  # fold can leave a double space
    ],
)
def test_containment_is_by_whole_words(span, part, expected):
    assert contains_words(span, part) is expected


def test_a_plural_of_the_term_is_not_corrected_to_it(v2):
    """D-031 closes D-030's regression: the plural is the term spelled out."""
    found = [a for a in applied(v2, "pagou dividendos") if a[1] == "dividendo"]
    assert found == [("dividendos", "dividendo", "term:alias")]
