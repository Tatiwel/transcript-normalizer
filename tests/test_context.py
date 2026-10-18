"""D-086: a form that declares a `context` matches only where its context terms appear."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.standoff import BAND_ASK, BAND_HIGH

PACK = """\
language: pt-BR
version: test
classes: [indicador, conceito, ferramenta]
terms:
  - term: OPEX
    class: indicador
    variants: [Ox]
    context: {Ox: [CAPEX]}
    unless_near: {Ox: [pecuária]}
  - term: CAPEX
    class: indicador
  - term: pecuária
    class: conceito
  - term: Claude
    class: ferramenta
    variants: [cloud]
    context: {cloud: [agente]}
  - term: agente
    class: conceito
"""


@pytest.fixture
def pack_file(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text(PACK, encoding="utf-8")
    return path


def found(pack_file, caption, learned=None):
    pack = load_pack(pack_file, learned=learned or Learned())
    transcript = parse_caption(caption)
    return [(transcript.locate(a.start)[1], a.original, a.term, a.band)
            for a in resolve_overlaps(find_annotations(transcript, pack))]


def ox(result):
    return [(ts, band) for ts, original, term, band in result if original == "Ox"]


def test_no_context_nothing(pack_file):
    assert ox(found(pack_file, "0:01 o Ox da empresa subiu\n0:30 o Ox caiu\n")) == []


def test_one_mention_asks(pack_file):
    caption = "0:01 o CAPEX subiu\n3:00 o Ox da empresa subiu\n6:00 e o Ox caiu\n"
    assert ox(found(pack_file, caption)) == [("3:00", BAND_ASK), ("6:00", BAND_ASK)]


def test_two_mentions_apply(pack_file):
    caption = "0:01 o CAPEX subiu\n1:00 o capex caiu\n3:00 o Ox da empresa subiu\n"
    assert ox(found(pack_file, caption)) == [("3:00", BAND_HIGH)]


def test_unless_near_within_90_seconds_asks(pack_file):
    caption = (
        "0:01 o CAPEX subiu\n0:20 o CAPEX caiu\n"
        "5:00 o Ox da empresa subiu\n6:00 falando de pecuária\n"  # 60 s apart: asked
        "9:00 o Ox caiu de novo\n"  # 180 s after pecuária: applied
    )
    assert ox(found(pack_file, caption)) == [("5:00", BAND_ASK), ("9:00", BAND_HIGH)]


def test_without_timestamps_nearness_is_200_tokens(pack_file):
    filler = " ".join(["palavra"] * 250)
    caption = f"a o CAPEX subiu e o CAPEX caiu\nb o Ox subiu pecuária\nc {filler} o Ox caiu\n"
    assert [band for _, band in ox(found(pack_file, caption))] == [BAND_ASK, BAND_HIGH]


def test_context_through_a_learned_variant_of_the_context_term(pack_file):
    caption = "0:01 o kapex subiu\n1:00 o kapex caiu\n3:00 o Ox da empresa subiu\n"
    assert ox(found(pack_file, caption)) == []
    learned = Learned().confirm("CAPEX", "kapex")
    assert ox(found(pack_file, caption, learned)) == [("3:00", BAND_HIGH)]


def test_context_is_never_found_by_similarity(pack_file):
    """`a gente` is close to `agente`, and must not stand for it."""
    caption = "0:01 a gente usa o cloud\n0:30 a gente gosta do cloud\n1:00 o cloud é bom\n"
    result = found(pack_file, caption)
    assert [r for r in result if r[1] == "cloud"] == []
    caption = "0:01 o agente usa o cloud\n0:30 outro agente no cloud\n"
    assert [(o, t, b) for _, o, t, b in found(pack_file, caption) if o == "cloud"] == [
        ("cloud", "Claude", BAND_HIGH), ("cloud", "Claude", BAND_HIGH),
    ]


def test_a_form_without_context_is_unchanged(pack_file):
    """CAPEX itself declares nothing: it matches with no other term around."""
    assert [(o, t, b) for _, o, t, b in found(pack_file, "0:01 o CAPEX subiu\n")] == [
        ("CAPEX", "CAPEX", BAND_HIGH)
    ]


def test_a_canonical_name_that_is_an_ordinary_word(tmp_path):
    """`Vale` the company, `vale` the verb: the name itself declares the context."""
    path = tmp_path / "vale.yaml"
    path.write_text(
        "language: pt-BR\nversion: test\nclasses: [companhia, conceito]\nterms:\n"
        "  - term: Vale\n    class: companhia\n    context: {Vale: [minério de ferro]}\n"
        "  - term: minério de ferro\n    class: conceito\n",
        encoding="utf-8",
    )
    assert [o for _, o, t, _ in found(path, "0:01 vale a pena ver\n") if t == "Vale"] == []
    caption = "0:01 o minério de ferro subiu\n0:10 o minério de ferro caiu\n0:20 a Vale lucrou\n"
    assert [(o, b) for _, o, t, b in found(path, caption) if t == "Vale"] == [("Vale", BAND_HIGH)]


# ------------------------------------------------------------------ the mixed caption

DATA = __import__("pathlib").Path(__file__).resolve().parent / "data"


def cloud(caption):
    pack = load_pack(DATA / "context-ia.yaml", learned=Learned())
    transcript = parse_caption(caption)
    found = resolve_overlaps(find_annotations(transcript, pack))
    return [(transcript.locate(a.start)[1], a.band, a.applied) for a in found if a.original == "cloud"]


def test_the_mixed_caption_occurrence_by_occurrence():
    """Half a video on Claude, half on cloud infrastructure, one sentence with both.

    Anthropic appears three times, so `cloud` is Claude where nothing says
    otherwise; within 90 seconds of AWS or Kubernetes it is only asked."""
    assert cloud((DATA / "context-mixed.txt").read_text(encoding="utf-8")) == [
        ("0:20", BAND_HIGH, True),
        ("1:10", BAND_HIGH, True),
        ("2:20", BAND_HIGH, True),  # 100 s before the AWS at 4:00
        ("4:00", BAND_ASK, False),  # the sentence with both
        ("6:50", BAND_ASK, False),
        ("7:30", BAND_ASK, False),
    ]


def test_the_infrastructure_half_alone_proposes_nothing():
    lines = (DATA / "context-mixed.txt").read_text(encoding="utf-8").splitlines()
    assert cloud("\n".join(lines[5:]) + "\n") == []
