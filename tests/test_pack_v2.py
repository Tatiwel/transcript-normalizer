"""Pack 0.2.x: what the second fixture taught packs/financas-ptbr.yaml."""

import csv
from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.core.standoff import KIND_ALIAS, RULE_UNIT
from transcript_normalizer.runs import BUNDLED_PACKS

ROOT = Path(__file__).resolve().parents[1]
PACK_V2 = BUNDLED_PACKS / "financas-ptbr.yaml"
FROZEN = sorted((ROOT / "fixtures").glob("*/pack.yaml"))
#: The third and fourth fixtures froze the curated pack as it was when each was added.
FROZEN_VERSIONS = {
    "R2Qgz8tFWVI": "0.1.0",
    "wxgFO_fyfXg": "0.1.0",
    "4wCtn8BWR4o": "0.2.3",
    "4tTmY8Buask": "0.2.4",
}


@pytest.fixture(scope="module")
def v2():
    return load_pack(PACK_V2, learned=Learned())


def annotate(pack, line):
    transcript = parse_caption(f"0:01 {line}")
    return transcript, resolve_overlaps(find_annotations(transcript, pack))


def applied(pack, line):
    _, found = annotate(pack, line)
    return [(a.original, a.term, a.rule, a.kind) for a in found if a.applied]


def test_versions(v2):
    assert v2.version == "0.3.2"
    assert {p.parent.name for p in FROZEN} == set(FROZEN_VERSIONS)
    for path in FROZEN:
        assert load_pack(path, learned=Learned()).version == FROZEN_VERSIONS[path.parent.name], path


def test_every_new_term_from_the_second_gold_is_in_the_pack(v2):
    with (ROOT / "fixtures" / "wxgFO_fyfXg" / "gold.csv").open(encoding="utf-8-sig") as fh:
        wanted = {r["term"] for r in csv.DictReader(fh) if r["status"] in ("conferido", "alias") and r["term"]}
    assert wanted <= {t.term for t in v2.terms}


def test_cpfe_is_the_ticker_not_a_misrecognition(v2):
    cpfl = next(t for t in v2.terms if t.term == "CPFL")
    assert "CPFE" in cpfl.aliases and "CPFE" not in cpfl.variants
    transcript, found = annotate(v2, "a CPFE pagou bem")
    assert applied(v2, "a CPFE pagou bem") == [("CPFE", "CPFL", "term:alias", KIND_ALIAS)]
    assert dict(render_lines(transcript, found))["0:01"] == "a CPFE pagou bem"


def test_spoken_ticker_is_an_alias_of_cemig(v2):
    assert applied(v2, "a CEMIG 4 caiu") == [("CEMIG 4", "CEMIG", "term:alias", KIND_ALIAS)]


def test_bit_after_a_number_is_bilhao(v2):
    found = applied(v2, "lucro de 31 bit no ano")
    assert found == [("31 bit", "bilhão", RULE_UNIT, "correction")]


def test_bit_on_its_own_stays_an_ebitda_variant(v2):
    assert applied(v2, "o bit da empresa") == [("bit", "EBITDA", "term:variant", "correction")]


def test_the_units_other_words_are_not_matched_on_their_own(v2):
    # `B` and `be` are bilhão only after a number, through the rule.
    assert applied(v2, "plano B e be") == []


def test_bilhoes_is_recognized_as_the_unit(v2):
    assert applied(v2, "44 bilhões de reais") == [("bilhões", "bilhão", "term:alias", KIND_ALIAS)]


@pytest.mark.parametrize(
    "path", [p for p in FROZEN if FROZEN_VERSIONS[p.parent.name] == "0.1.0"], ids=lambda p: p.parent.name
)
def test_a_frozen_pack_without_bilhao_keeps_the_rules_own_bi(path):
    """The fixture packs do not name the unit, so the rule's term is unchanged."""
    pack = load_pack(path, learned=Learned())
    assert pack.term_named("bi") is None
    found = applied(pack, "lucro de 31 bit no ano")
    assert ("31 bit", "bi", RULE_UNIT, "correction") in found


def test_the_plurals_of_preco_teto_are_curated_aliases_now(v2):
    """0.2.1: moved from the user's learned layer into the pack."""
    assert applied(v2, "os preços tetos subiram") == [("preços tetos", "preço teto", "term:alias", KIND_ALIAS)]
    assert applied(v2, "dois preços teto") == [("preços teto", "preço teto", "term:alias", KIND_ALIAS)]


def test_one_and_two_letter_misses_stayed_out(v2):
    """0.2.1: D-005 keeps R, TI, Ta, EB, rá and sem out of the variants."""
    variants = {v for t in v2.terms for v in t.variants}
    assert not {"R", "TI", "Ta", "EB", "rá", "sem"} & variants


def test_ordinary_words_are_not_variants(v2):
    """D-032: `tira`, `rápido` and `valorist` left the pack in 0.2.2."""
    variants = {t.term: set(t.variants) for t in v2.terms}
    assert "tira" not in variants["TIR"]
    assert "rápido" not in variants["RAP"]
    assert "valorist" not in variants["valuation"]
    assert applied(v2, "você tira esse custo, mais rápido") == []


def test_market_cap_is_a_term_with_its_other_names(v2):
    assert applied(v2, "o marketcap dela") == [("marketcap", "market cap", "term:alias", KIND_ALIAS)]
    assert applied(v2, "o valor de mercado dela") == [
        ("valor de mercado", "market cap", "term:alias", KIND_ALIAS)
    ]


def test_what_the_third_fixture_added(v2):
    """0.2.4, from 4wCtn8BWR4o. `preço alto` is two ordinary words (D-032)."""
    assert applied(v2, "a evitida caiu") == [("evitida", "EBITDA", "term:variant", "correction")]
    assert applied(v2, "o dividendio subiu") == [("dividendio", "dividend yield", "term:variant", "correction")]
    assert applied(v2, "a dívida alíquida") == [("dívida alíquida", "dívida líquida", "term:variant", "correction")]
    assert not v2.term_named("preço alvo").variants
    assert applied(v2, "o target price dela") == [("target price", "preço alvo", "term:alias", KIND_ALIAS)]
