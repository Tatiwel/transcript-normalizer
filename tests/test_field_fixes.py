"""0.4.2: fixes from field use. Missing files, typed paths, the folder, one summary."""

import shutil
from pathlib import Path

from transcript_normalizer import cli, interactive
from transcript_normalizer.runs import CAPTION_FILE, NORMALIZED_FILE

from . import fetch_fakes
from .fetch_fakes import LINK
from .test_interactive import DATA, menu

SRT = """1
00:00:01,000 --> 00:00:04,000
hoje a Klabine caiu bastante

2
00:00:04,000 --> 00:00:07,000
e a SEMIG pagou dividendos
"""


# ------------------------------------------------------------------ missing files


def test_normalize_on_a_missing_file_says_run_fetch_first(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["normalize", "runs/nope/legenda.txt"]) == 1
    err = capsys.readouterr().err
    assert err == f"no caption at {Path('runs/nope/legenda.txt')}; run fetch first\n"  # backslashes on Windows


def test_any_file_not_found_is_a_message_not_a_traceback(monkeypatch, capsys):
    def missing(args):
        raise FileNotFoundError(2, "No such file or directory", "/nowhere/x.yaml")

    monkeypatch.setattr(cli, "run_list", missing)
    assert cli.main(["list"]) == 1
    assert capsys.readouterr().err == "no file at /nowhere/x.yaml\n"


# ------------------------------------------------------------------ subtitles on the command line


def test_normalize_converts_a_srt_into_runs_stem(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "aula.srt").write_text(SRT, encoding="utf-8")
    assert cli.main(["normalize", "aula.srt", "--force"]) == 0
    run = tmp_path / "runs" / "aula"
    caption = (run / CAPTION_FILE).read_text(encoding="utf-8")
    assert "# Arquivo: aula.srt" in caption and "0:04 hoje a Klabine caiu bastante" in caption
    assert "SEMIG" not in (run / NORMALIZED_FILE).read_text(encoding="utf-8")
    assert not (run / "aula.srt").exists()  # the subtitle stays where it was


# ------------------------------------------------------------------ the menu


def test_normalize_takes_a_typed_vtt_path(tmp_path, monkeypatch, capsys):
    shutil.copy(DATA / "menu.vtt", tmp_path / "palestra.vtt")
    lines = ["2", str(tmp_path / "palestra.vtt"), "1", "n", "", "q"]  # no runs yet: straight to the path
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    run = tmp_path / "runs" / "palestra"
    assert (run / CAPTION_FILE).exists() and (run / NORMALIZED_FILE).exists()
    assert "corrected 1  (SEMIG → CEMIG)" in out


def test_normalize_offers_a_file_beside_the_runs(tmp_path, monkeypatch, capsys):
    caption = tmp_path / "entrevista.txt"
    caption.write_text(
        "0:01 hoje a Klabine caiu\n0:04 e a SEMIG pagou dividendos\n0:07 o EBITDA da Taesa\n", encoding="utf-8"
    )
    lines = [*LINK, "n", "2", "f", str(caption), "1", "n", "", "q"]
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "  f. A file…" in out
    assert (tmp_path / "runs" / "entrevista" / NORMALIZED_FILE).exists()


def test_a_typed_path_that_does_not_exist_is_an_error(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["2", str(tmp_path / "x.vtt"), "q"])
    assert code == 0 and f"error: no file at {tmp_path / 'x.vtt'}" in out


def test_normalize_then_review_prints_the_counters_once(tmp_path, monkeypatch, capsys):
    lines = [*LINK, "", "1", "", "a", "-", "", "", "q"]  # no contribution, no folder
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert out.count("corrected 1  (SEMIG → CEMIG)") == 1


def test_open_the_folder_falls_back_to_printing_the_path(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(interactive, "open_folder", lambda path: False)
    lines = [*LINK, "", "1", "n", "n", "y", "q"]  # no review, no term, open
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "Open the folder? [y/N]" in out
    assert f"the folder: {tmp_path / 'runs' / fetch_fakes.VIDEO_ID}" in out


def test_open_the_folder_opens_it(tmp_path, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(interactive, "open_folder", lambda path: opened.append(path) or True)
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "1", "n", "n", "y", "q"])
    assert opened == [tmp_path / "runs" / fetch_fakes.VIDEO_ID]
