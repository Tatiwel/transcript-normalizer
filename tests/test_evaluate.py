"""D-026: status records who wrote a gold row; one rule scores all of them."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.evaluate import evaluate

PACK = """\
language: pt-BR
version: test
terms:
  - term: CEMIG
    class: companhia
    variants: [SEMIG]
  - term: CPFL
    class: companhia
    aliases: [CPFE]
"""
CAPTION = "0:01 a SEMIG e a CPFE\n0:04 a SEMIG de novo\n"


@pytest.fixture
def scored(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(PACK, encoding="utf-8")
    transcript = parse_caption(CAPTION)
    pack = load_pack(path, learned=Learned())
    annotations = find_annotations(transcript, pack)
    return lambda gold: evaluate(transcript, annotations, gold, pack.normalize)


def row(ts, wrong, correct, term, status):
    return {"timestamp": ts, "wrong": wrong, "correct": correct, "term": term,
            "class": "companhia", "status": status}


@pytest.mark.parametrize("status", ["certo", "conferido"])
def test_certo_and_conferido_score_the_same(scored, status):
    result = scored([row("0:01", "SEMIG", "CEMIG", "CEMIG", status)])
    assert (len(result.hits), len(result.misses)) == (1, 0)


def test_a_correction_the_tool_does_not_make_is_a_miss(scored):
    result = scored([row("0:04", "de novo", "outra vez", "CEMIG", "conferido")])
    assert (len(result.hits), len(result.misses)) == (0, 1)


def test_an_alias_row_expects_an_alias_and_no_substitution(scored):
    result = scored([row("0:01", "CPFE", "CPFE", "CPFL", "alias")])
    assert len(result.aliases_recognized) == 1 and not result.aliases_substituted


def test_a_case_only_alias_row_is_still_an_alias(scored):
    """wxgFO_fyfXg writes `CPFe -> CPFE`: different strings, same name."""
    result = scored([row("0:01", "CPFE", "CPFe", "CPFL", "alias")])
    assert len(result.aliases_recognized) == 1


def test_a_case_or_accent_only_correction_is_out_of_scope(scored):
    """D-008, as for wxgFO_fyfXg 15:57 `Etaú -> ETAU`."""
    result = scored([row("0:01", "Semig", "SEMIG", "CEMIG", "conferido")])
    assert result.in_scope == []


def test_rows_with_no_term_are_out_of_scope(scored):
    assert scored([row("0:04", "de novo", "outra vez", "", "certo")]).in_scope == []
