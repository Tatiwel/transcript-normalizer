"""D-025: fuzzy runs against the term and curated pack variants; aliases and
learned variants match exactly."""

from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines

ROOT = Path(__file__).resolve().parents[1]
PACK_V2 = ROOT / "packs" / "financas-ptbr.yaml"
MILHOES = "0:01 o lucro foi de 300 milhões no trimestre"


@pytest.fixture(scope="module")
def v2():
    return load_pack(PACK_V2, learned=Learned())


def as_bilhao(pack, caption):
    return [a for a in find_annotations(parse_caption(caption), pack) if a.term == "bilhão"]


def test_milhoes_is_never_applied_or_rendered_as_bilhao(v2):
    """wxgFO_fyfXg: the alias `bilhões` reached `milhões` at 85.7, medium band."""
    found = as_bilhao(v2, MILHOES)
    assert not [a for a in found if a.applied]

    transcript = parse_caption(MILHOES)
    rendered = dict(render_lines(transcript, resolve_overlaps(find_annotations(transcript, v2))))
    assert rendered["0:01"] == "o lucro foi de 300 milhões no trimestre"


@pytest.mark.xfail(
    strict=True,
    reason="D-025 keeps fuzzy against the canonical term: `milhões` still scores "
    "61.5 against `bilhão` and is marked in the low band (not applied)",
)
def test_milhoes_is_never_annotated_as_bilhao(v2):
    assert as_bilhao(v2, MILHOES) == []


@pytest.mark.xfail(
    strict=True,
    reason="D-025 keeps fuzzy against the canonical term: `milhão` scores 83 "
    "against `bilhão`, medium band, and is applied (3x on wxgFO_fyfXg)",
)
def test_milhao_is_never_rewritten_as_bilhao(v2):
    assert not [a for a in as_bilhao(v2, "0:01 foi 1 milhão só") if a.applied]


def test_an_alias_still_matches_exactly(v2):
    found = [a for a in find_annotations(parse_caption("0:01 a CPFE pagou"), v2) if a.applied]
    assert [(a.original, a.term, a.kind) for a in found] == [("CPFE", "CPFL", "alias")]


PACK = """\
version: test
terms:
  - term: XPTO Corp
    class: companhia
    aliases: [zeta prime]
    variants: [gama delta]
"""


@pytest.fixture
def tiny(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(PACK, encoding="utf-8")
    return path


def terms(pack, line):
    return [(a.original, a.rule) for a in find_annotations(parse_caption(f"0:01 {line}"), pack)]


def test_a_near_miss_of_an_alias_is_not_proposed(tiny):
    pack = load_pack(tiny, learned=Learned())
    assert terms(pack, "a zeta prime chegou") == [("zeta prime", "term:alias")]
    assert terms(pack, "a zeta primes chegou") == []  # would be ~95 fuzzy


def test_a_near_miss_of_a_pack_variant_still_is(tiny):
    """Curated variants are what fuzzy is for: finding misrecognitions."""
    pack = load_pack(tiny, learned=Learned())
    assert ("gama deltas", "term:fuzzy") in terms(pack, "o gama deltas")


def test_a_learned_variant_matches_exactly_and_no_further(tiny):
    """Closes the cascade: a confirmation no longer widens fuzzy reach."""
    pack = load_pack(tiny, learned=Learned().confirm("XPTO Corp", "omega sigma"))
    assert terms(pack, "o omega sigma caiu") == [("omega sigma", "term:variant")]
    assert terms(pack, "o omega sigmas caiu") == []
