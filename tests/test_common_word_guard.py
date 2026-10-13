"""D-083: a fuzzy window with an ordinary word the term does not have is not
a garble of the term."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines

PACK = """\
language: pt-BR
version: 0.0.1
classes: [equipamento, conceito]
terms:
  - term: impressora 3D
    class: equipamento
    aliases: [impressora 3D que]
  - term: BR Partners
    class: organizacao
  - term: fluxo de caixa
    class: conceito
  - term: caixa que fala
    class: conceito
    variants: [caixa que falha]
"""


@pytest.fixture
def pack(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text(PACK, encoding="utf-8")
    return load_pack(path, learned=Learned())


def run(pack, line):
    transcript = parse_caption(f"0:01 {line}")
    found = resolve_overlaps(find_annotations(transcript, pack))
    return [(a.original, a.term, a.rule) for a in found], dict(render_lines(transcript, found))["0:01"]


def test_marco_s_case_an_ordinary_word_not_in_the_term_is_rejected(pack):
    """`que` is ordinary and not a word of `impressora 3D`: the text stays."""
    found, line = run(pack, "comprei uma impressora que imprime peças")
    assert found == []
    assert line == "comprei uma impressora que imprime peças"


def test_no_ordinary_word_is_still_matched(pack):
    found, line = run(pack, "o banco BR Portness subiu")
    assert found == [("BR Portness", "BR Partners", "term:fuzzy")]
    assert line == "o banco BR Partners subiu"


def test_an_ordinary_word_of_the_term_is_allowed(pack):
    """`de` is ordinary, but `fluxo de caixa` has it."""
    found, line = run(pack, "o fluxo de caixo da empresa")
    assert found == [("fluxo de caixo", "fluxo de caixa", "term:fuzzy")]
    assert line == "o fluxo de caixa da empresa"


def test_exact_and_alias_forms_are_not_guarded(pack):
    """Only fuzzy guesses: a listed variant and an alias with `que` still match."""
    found, line = run(pack, "a caixa que falha e a impressora 3D que veio")
    assert ("caixa que falha", "caixa que fala", "term:variant") in found
    assert ("impressora 3D que", "impressora 3D", "term:alias") in found
    assert line == "a caixa que fala e a impressora 3D que veio"
