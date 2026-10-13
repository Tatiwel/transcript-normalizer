"""D-084: number words 2-20 fold to digits for matching only."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.languages import en, pt_br


@pytest.mark.parametrize(
    "text, folded",
    [
        ("nove", "9"),
        ("onze", "11"),
        ("dois", "2"),
        ("duas", "2"),
        ("três", "3"),
        ("Dezenove", "19"),
        ("vinte", "20"),
        ("BOVA onze", "bova11"),  # a ticker as it is written
        ("de onze", "de 11"),  # an ordinary word does not join
        ("dez onze", "10 11"),  # nor does another number
        ("um", "um"),
        ("uma", "uma"),
        ("um dia", "um dia"),
        ("vinte e um", "20 e um"),
        ("novembro", "novembro"),
        ("a, onze", "a  11"),  # the spacing is kept
    ],
)
def test_pt_br(text, folded):
    assert pt_br.normalize(text) == folded


@pytest.mark.parametrize(
    "text, folded",
    [
        ("nine", "9"),
        ("eleven", "11"),
        ("Twenty", "20"),
        ("the one", "the one"),
        ("one", "one"),
        ("of nine", "of 9"),
        ("ninety", "ninety"),
    ],
)
def test_en(text, folded):
    assert en.normalize(text) == folded


PACK = """\
language: pt-BR
version: 0.0.1
classes: [ativo]
terms:
  - term: BOVA11
    class: ativo
"""


@pytest.fixture
def pack(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text(PACK, encoding="utf-8")
    return load_pack(path, learned=Learned())


def run(pack, line):
    transcript = parse_caption(f"0:01 {line}")
    found = resolve_overlaps(find_annotations(transcript, pack))
    return found, dict(render_lines(transcript, found))["0:01"]


def test_bova_onze_is_bova11_and_the_text_stays(pack):
    found, line = run(pack, "comprei BOVA onze ontem")
    assert [(a.original, a.term) for a in found] == [("BOVA onze", "BOVA11")]
    assert line == "comprei BOVA onze ontem"


def test_um_is_not_a_number(pack):
    found, _ = run(pack, "comprei BOVA um ontem")
    assert found == []
