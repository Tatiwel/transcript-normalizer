"""D-024: word n-grams do not cross strong punctuation (. ? ! ;)."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.core.matcher import tokenize
from transcript_normalizer.languages import pt_br
from transcript_normalizer.core.pack import Learned

PACK = """\
language: pt-BR
version: test
terms:
  - term: Warren Buffett
    class: pessoa
    variants: [Warn Buffet]
  - term: preço teto
    class: indicador
    variants: [preço delet]
"""


@pytest.fixture
def tiny_pack(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(PACK, encoding="utf-8")
    return load_pack(path, learned=Learned())


def closes(text):
    return [t.text for t in tokenize(text, pt_br.sentence_boundaries) if t.closes_sentence]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Warn Buffet. Tem gente", ["Buffet"]),
        ("e agora? Bom; certo! sim", ["agora", "Bom", "certo"]),
        ("vale 6.7 B hoje", []),  # a decimal point is not an end of sentence
        ("sim, não, talvez", []),  # a comma is not strong punctuation
        ("fim.", ["fim"]),
    ],
)
def test_strong_punctuation_closes_a_sentence(text, expected):
    assert closes(text) == expected


def test_the_reported_case_is_no_longer_one_span(tiny_pack):
    """wxgFO_fyfXg 36:41: `Warn Buffet. Tem` was proposed as Warren Buffett."""
    found = find_annotations(parse_caption("0:01 braço direito do Warn Buffet. Tem gente"), tiny_pack)
    originals = {a.original for a in found}
    assert "Warn Buffet" in originals
    assert not [o for o in originals if "." in o]


def test_nothing_spans_a_question_mark_either(tiny_pack):
    found = find_annotations(parse_caption("0:01 qual o preço? Delet isso"), tiny_pack)
    assert not [a for a in found if "?" in a.original]


def test_a_caption_break_is_not_a_sentence_break():
    """D-007 still holds: `ser` / `MIG` across two caption lines is one span."""
    tokens = tokenize("tem que ser MIG, não é", pt_br.sentence_boundaries)
    assert not [t for t in tokens if t.closes_sentence]


def test_the_unit_rule_is_a_regex_and_does_not_care(tiny_pack):
    found = find_annotations(parse_caption("0:01 lucro de 6.7 B. Então"), tiny_pack)
    assert [(a.original, a.rule) for a in found if a.rule == "unit"] == [("6.7 B", "unit")]


def test_on_the_first_fixture_preco_entao_is_gone(annotations):
    """R2Qgz8tFWVI 1:12 `preço. Então` -> preço teto was a false positive."""
    assert not [a for a in annotations if a.original == "preço. Então"]
