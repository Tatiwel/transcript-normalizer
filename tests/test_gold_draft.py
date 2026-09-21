"""`--gold-draft`: the applied annotations as the starting point for a new gold file."""

import csv
import shutil

from transcript_normalizer import find_annotations, load_pack, read_caption, resolve_overlaps
from transcript_normalizer.cli import DRAFT_STATUS, GOLD_COLUMNS, main
from transcript_normalizer.core.standoff import applied
from transcript_normalizer.runs import GOLD_DRAFT_FILE, run_dir

from .conftest import CAPTION, GOLD, PACK


def read_rows(path, encoding="utf-8-sig"):
    with open(path, encoding=encoding, newline="") as fh:
        return list(csv.DictReader(fh))


def run(tmp_path, monkeypatch, *extra):
    """A run in its own directory, so runs/ lands in tmp_path."""
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert main([str(caption), "--pack", str(PACK), *extra]) == 0
    return caption, run_dir(caption)


def test_draft_has_the_columns_and_status_of_a_gold_file(tmp_path, monkeypatch):
    _, out = run(tmp_path, monkeypatch, "--gold-draft")

    rows = read_rows(out / GOLD_DRAFT_FILE)
    assert list(rows[0].keys()) == list(GOLD_COLUMNS)
    assert list(rows[0].keys()) == list(read_rows(GOLD)[0].keys())
    assert {r["status"] for r in rows} == {DRAFT_STATUS}


def test_draft_holds_exactly_the_applied_annotations(tmp_path, monkeypatch):
    caption, out = run(tmp_path, monkeypatch, "--gold-draft")

    transcript = read_caption(caption)
    pack = load_pack(PACK)
    expected = applied(resolve_overlaps(find_annotations(transcript, pack)))
    rows = read_rows(out / GOLD_DRAFT_FILE)
    assert len(rows) == len(expected)

    klass = {t.term: (t.klass or "") for t in pack.terms}
    for row, a in zip(rows, sorted(expected, key=lambda a: (a.start, a.end))):
        assert row["timestamp"] == transcript.locate(a.start)[1]
        assert row["wrong"] == " ".join(a.original.split())
        assert row["correct"] == a.replacement
        assert row["term"] == a.term
        assert row["class"] == ("unidade" if a.rule == "unit" else klass.get(a.term, ""))


def test_draft_carries_the_cross_line_and_unit_rows(tmp_path, monkeypatch):
    _, out = run(tmp_path, monkeypatch, "--gold-draft")

    rows = read_rows(out / GOLD_DRAFT_FILE)
    # D-007's cross-line hit is credited to the line it starts on.
    assert {"timestamp": "24:48", "wrong": "ser MIG", "correct": "CEMIG",
            "term": "CEMIG", "class": "companhia", "status": "draft"} in rows
    # D-006's unit rows use the gold file's own class for units.
    assert [r for r in rows if r["class"] == "unidade"]


def test_no_draft_is_written_without_the_flag(tmp_path, monkeypatch):
    _, out = run(tmp_path, monkeypatch)
    assert not (out / GOLD_DRAFT_FILE).exists()
    assert not list(tmp_path.rglob("*.csv"))
