"""D-015: user outputs live in runs/<id>/, never beside the input."""

import shutil

from transcript_normalizer.cli import main
from transcript_normalizer.runs import (
    ANNOTATIONS_FILE,
    GOLD_DRAFT_FILE,
    REPORT_FILE,
    run_dir,
)

from .conftest import CAPTION, PACK


def staged(tmp_path):
    caption = tmp_path / "input" / "legenda.txt"
    caption.parent.mkdir()
    shutil.copy(CAPTION, caption)
    return caption


def test_outputs_go_to_runs_and_not_beside_the_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = staged(tmp_path)

    assert main([str(caption), "--pack", str(PACK), "--gold-draft"]) == 0

    out = run_dir(caption)
    assert out == tmp_path / "runs" / "legenda"
    assert sorted(p.name for p in out.iterdir()) == [
        ANNOTATIONS_FILE,
        GOLD_DRAFT_FILE,
        REPORT_FILE,
    ]
    # Nothing landed next to the caption.
    assert [p.name for p in caption.parent.iterdir()] == ["legenda.txt"]


def test_out_overrides_the_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = staged(tmp_path)
    elsewhere = tmp_path / "somewhere" / "deep"

    assert main([str(caption), "--pack", str(PACK), "--out", str(elsewhere)]) == 0

    assert (elsewhere / ANNOTATIONS_FILE).exists()
    assert not (tmp_path / "runs").exists()


def test_report_file_is_what_was_printed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    caption = staged(tmp_path)
    main([str(caption), "--pack", str(PACK)])

    printed = capsys.readouterr().out
    assert (run_dir(caption) / REPORT_FILE).read_text(encoding="utf-8") == printed
