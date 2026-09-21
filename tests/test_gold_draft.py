"""`--gold-draft`: the applied annotations as the starting point for a new gold file."""

import csv
import shutil

from transcript_normalizer import find_annotations, load_pack, read_caption
from transcript_normalizer.cli import DRAFT_STATUS, GOLD_COLUMNS, main
from transcript_normalizer.standoff import applied

from .conftest import CAPTION, GOLD, PACK


def read_rows(path, encoding="utf-8-sig"):
    with open(path, encoding=encoding, newline="") as fh:
        return list(csv.DictReader(fh))


def test_draft_has_the_columns_and_status_of_a_gold_file(tmp_path):
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    draft = tmp_path / "draft.csv"

    assert main([str(caption), "--pack", str(PACK), "--gold-draft", str(draft)]) == 0

    rows = read_rows(draft)
    assert list(rows[0].keys()) == list(GOLD_COLUMNS)
    assert list(rows[0].keys()) == list(read_rows(GOLD)[0].keys())
    assert {r["status"] for r in rows} == {DRAFT_STATUS}


def test_draft_holds_exactly_the_applied_annotations(tmp_path):
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    draft = tmp_path / "draft.csv"
    main([str(caption), "--pack", str(PACK), "--gold-draft", str(draft)])

    transcript = read_caption(caption)
    pack = load_pack(PACK)
    from transcript_normalizer import resolve_overlaps

    expected = applied(resolve_overlaps(find_annotations(transcript, pack)))
    rows = read_rows(draft)
    assert len(rows) == len(expected)

    klass = {t.term: (t.klass or "") for t in pack.terms}
    for row, a in zip(rows, sorted(expected, key=lambda a: (a.start, a.end))):
        assert row["timestamp"] == transcript.locate(a.start)[1]
        assert row["wrong"] == " ".join(a.original.split())
        assert row["correct"] == a.replacement
        assert row["term"] == a.term
        assert row["class"] == ("unidade" if a.rule == "unit" else klass.get(a.term, ""))


def test_draft_carries_the_cross_line_and_unit_rows(tmp_path):
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    draft = tmp_path / "draft.csv"
    main([str(caption), "--pack", str(PACK), "--gold-draft", str(draft)])

    rows = read_rows(draft)
    # D-007's cross-line hit is credited to the line it starts on.
    assert {"timestamp": "24:48", "wrong": "ser MIG", "correct": "CEMIG",
            "term": "CEMIG", "class": "companhia", "status": "draft"} in rows
    # D-006's unit rows use the gold file's own class for units.
    assert [r for r in rows if r["class"] == "unidade"]


def test_no_draft_is_written_without_the_flag(tmp_path):
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    main([str(caption), "--pack", str(PACK)])
    assert not list(tmp_path.glob("*.csv"))
