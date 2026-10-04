"""D-051: the interactive menu runs the same subcommands a script does."""

import io
from pathlib import Path

import pytest

from transcript_normalizer import cli, interactive
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.ingest import fetch
from transcript_normalizer.runs import CAPTION_FILE, NORMALIZED_FILE

from . import fetch_fakes
from .fetch_fakes import URL, VIDEO_ID, FakeYtDlp

MENU_VTT = Path(__file__).resolve().parent / "data" / "menu.vtt"


def menu(tmp_path, monkeypatch, capsys, lines, ytdlp=None):
    """Run `transcript-normalizer` with no arguments, as on a terminal."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_fakes, "VTT", MENU_VTT)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp or FakeYtDlp())
    monkeypatch.setattr(cli, "is_interactive", lambda: True)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in lines)))
    code = cli.main([])
    out = capsys.readouterr()
    return code, out.out + out.err, fake


def test_q_quits(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["q"])
    assert code == 0
    assert "1. Fetch a video or file" in out and "q. Quit" in out


def test_end_of_input_quits_too(tmp_path, monkeypatch, capsys):
    code, _, _ = menu(tmp_path, monkeypatch, capsys, [])
    assert code == 0


def test_fetch_then_normalize_then_review(tmp_path, monkeypatch, capsys):
    lines = [
        "1", URL,  # fetch: the platform caption
        "2", "1", "n",  # normalize run 1; not reviewing yet
        "3", "1", "y",  # review run 1: `Klabine -> Klabin`, confirmed
        "q",
    ]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    run = tmp_path / "runs" / VIDEO_ID
    assert (run / CAPTION_FILE).exists() and (run / NORMALIZED_FILE).exists()
    assert fake.downloads == [("--write-auto-subs", "pt")]
    assert "Klabine -> Klabin?" in out
    learned = load_learned(tmp_path / "packs" / "financas-ptbr.learned.yaml")
    assert [c.variant for c in learned.confirmed["Klabin"]] == ["Klabine"]
    assert out.count("q. Quit") == 4  # back to the menu after each action


def test_normalize_offers_the_review_straight_away(tmp_path, monkeypatch, capsys):
    lines = ["1", URL, "2", "1", "y", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "review pending now?" in out
    learned = load_learned(tmp_path / "packs" / "financas-ptbr.learned.yaml")
    assert [r.text for r in learned.rejected] == ["Klabine"]


def test_a_bad_url_is_an_error_in_the_menu(tmp_path, monkeypatch, capsys):
    code, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "not-a-url", "q"])
    assert code == 0
    assert "no such file, and not a url" in out
    assert "error: fetch did not finish (exit 1)" in out
    assert "Traceback" not in out
    assert out.count("q. Quit") == 2
    assert fake.calls == []


def test_no_caption_offers_local_speech_recognition(tmp_path, monkeypatch, capsys):
    lines = ["1", URL, "y", "q"]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines, FakeYtDlp(has_caption=False))
    assert "run with local speech recognition? [y/n]" in out
    assert fake.calls == ["metadata", "metadata", "audio"]
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_show_and_list_and_help(tmp_path, monkeypatch, capsys):
    lines = ["1", URL, "2", "1", "n", "4", "1", "5", "6", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert f"{NORMALIZED_FILE}, first 2 of 2 lines:" in out
    assert "Video sintetico de teste" in out  # the `list` line
    assert "docs/GUIDE.md" in out


def test_an_unexpected_error_is_shown_not_raised(tmp_path, monkeypatch, capsys):
    def broken(screen):
        raise RuntimeError("disk on fire")

    monkeypatch.setitem(interactive.ACTIONS, "5", broken)
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["5", "q"])
    assert code == 0 and "error: RuntimeError: disk on fire" in out


def test_without_a_terminal_no_arguments_is_the_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "is_interactive", lambda: False)
    with pytest.raises(SystemExit) as stop:
        cli.main([])
    assert stop.value.code == 2
    assert "usage: transcript-normalizer" in capsys.readouterr().err
