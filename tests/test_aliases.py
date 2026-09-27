"""D-020: an alias names the term; a correction replaces the words."""

import io
import json

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.cli import main, report
from transcript_normalizer.core.pack import Learned, load_learned
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.core.standoff import KIND_ALIAS, KIND_CORRECTION
from transcript_normalizer.runs import ANNOTATIONS_FILE, NORMALIZED_FILE, learned_file

PACK = """\
version: test
terms:
  - term: CPFL
    class: companhia
    aliases: [CPFE]
  - term: preço teto
    class: indicador
    variants: [presteto]
"""
CAPTION = """\
# URL: https://youtu.be/aliasesTest
0:01 a CPFE subiu e o presteto também
0:04 os preços tetos de novo
"""


@pytest.fixture
def pack_path(tmp_path):
    path = tmp_path / "test.yaml"
    path.write_text(PACK, encoding="utf-8")
    return path


def annotate(pack):
    transcript = parse_caption(CAPTION)
    return transcript, resolve_overlaps(find_annotations(transcript, pack))


def by_original(annotations):
    return {a.original: a for a in annotations if a.applied}


def test_a_pack_alias_is_recognized_and_a_variant_is_corrected(pack_path):
    _, annotations = annotate(load_pack(pack_path, learned=Learned()))
    found = by_original(annotations)

    alias = found["CPFE"]
    assert (alias.kind, alias.rule, alias.band, alias.term) == (
        KIND_ALIAS, "term:alias", "high", "CPFL"
    )
    assert alias.replacement == "CPFE"  # nothing to replace it with

    correction = found["presteto"]
    assert (correction.kind, correction.rule, correction.replacement) == (
        KIND_CORRECTION, "term:variant", "preço teto"
    )


def test_normalized_text_substitutes_corrections_only(pack_path):
    transcript, annotations = annotate(load_pack(pack_path, learned=Learned()))
    rendered = dict(render_lines(transcript, annotations))
    assert rendered["0:01"] == "a CPFE subiu e o preço teto também"


def test_annotations_json_carries_the_kind(tmp_path, monkeypatch, pack_path):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    caption.write_text(CAPTION, encoding="utf-8")
    assert main([str(caption), "--pack", str(pack_path)]) == 0

    out = tmp_path / "runs" / "aliasesTest"
    records = json.loads((out / ANNOTATIONS_FILE).read_text(encoding="utf-8"))
    kinds = {r["original"]: r["kind"] for r in records if r["applied"]}
    assert kinds["CPFE"] == KIND_ALIAS
    assert kinds["presteto"] == KIND_CORRECTION
    assert "CPFE" in (out / NORMALIZED_FILE).read_text(encoding="utf-8")


def test_the_report_lists_aliases_as_recognized_not_changed(pack_path):
    _, annotations = annotate(load_pack(pack_path, learned=Learned()))
    text = report(annotations)
    section = text[text.index("recognized (not changed):") :]
    assert "CPFE (1 occurrence) -> CPFL" in section
    # An alias is not listed among the terms that were corrected.
    corrected = text[: text.index("recognized (not changed):")]
    assert "CPFE" not in corrected


def test_inflection_is_an_alias_once_learned(pack_path):
    """`preços tetos` is the plural of the term, not a misrecognition of it."""
    learned = Learned().alias("preço teto", "preços tetos")
    transcript, annotations = annotate(load_pack(pack_path, learned=learned))

    plural = by_original(annotations)["preços tetos"]
    assert (plural.kind, plural.band, plural.term) == (KIND_ALIAS, "high", "preço teto")
    assert dict(render_lines(transcript, annotations))["0:04"] == "os preços tetos de novo"


def test_without_it_the_plural_is_only_a_fuzzy_correction(pack_path):
    _, annotations = annotate(load_pack(pack_path, learned=Learned()))
    plural = by_original(annotations)["preços tetos"]
    assert (plural.kind, plural.rule, plural.band) == (KIND_CORRECTION, "term:fuzzy", "medium")


def test_answering_l_records_an_alias_that_the_next_run_recognizes(
    tmp_path, monkeypatch, pack_path
):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    caption.write_text(CAPTION, encoding="utf-8")

    # The only medium-band proposal is `preços tetos`; say it is an alias.
    monkeypatch.setattr("sys.stdin", io.StringIO("l\n"))
    assert main([str(caption), "--pack", str(pack_path), "--confirm"]) == 0

    learned = load_learned(learned_file(pack_path))
    assert [(t, a.alias) for t, entries in learned.aliases.items() for a in entries] == [
        ("preço teto", "preços tetos")
    ]
    assert not learned.confirmed and not learned.rejected

    _, annotations = annotate(load_pack(pack_path))  # reads the learned file back
    assert by_original(annotations)["preços tetos"].kind == KIND_ALIAS


def test_a_text_is_either_a_variant_or_an_alias_of_a_term(tmp_path):
    learned = Learned().confirm("preço teto", "preços teto")
    learned = learned.alias("preço teto", "preços teto")
    assert not learned.confirmed
    assert [a.alias for a in learned.aliases["preço teto"]] == ["preços teto"]

    learned = learned.confirm("preço teto", "preços teto")
    assert not learned.aliases
    assert [c.variant for c in learned.confirmed["preço teto"]] == ["preços teto"]


def test_the_learned_aliases_section_round_trips(tmp_path):
    path = tmp_path / "x.learned.yaml"
    path.write_text(
        Learned()
        .alias("preço teto", "preços tetos", decided="2026-09-21")
        .confirm("preço teto", "preç teto", decided="2026-09-21")
        .to_yaml(),
        encoding="utf-8",
    )
    back = load_learned(path)
    assert [(a.alias, a.decided) for a in back.aliases["preço teto"]] == [
        ("preços tetos", "2026-09-21")
    ]
    assert [c.variant for c in back.confirmed["preço teto"]] == ["preç teto"]
