"""D-051, D-053: the interactive menu, driven through the plain prompts.

Every action runs a subcommand through `cli.main`; the questions go through
`prompts`, which in a test (no terminal) is the numbered and lettered text.
"""

import importlib.machinery
import io
import re
import sys
import types
from pathlib import Path

import pytest

from transcript_normalizer import cli, interactive, prompts
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.ingest import fetch
from transcript_normalizer.prompts import Option
from transcript_normalizer.runs import CAPTION_FILE, NORMALIZED_FILE

from . import fetch_fakes
from .fetch_fakes import URL, VIDEO_ID, FakeYtDlp

DATA = Path(__file__).resolve().parent / "data"
SECTIONS = ("USAGE", "COMMANDS", "MENU", "WHAT HAPPENS", "THE REVIEW LOOP", "EXAMPLES", "LEARN MORE")
ANSI = re.compile(r"\x1b\[")


def menu(tmp_path, monkeypatch, capsys, lines, ytdlp=None, vtt="menu.vtt"):
    """`transcript-normalizer` with no arguments, as on a terminal, fed `lines`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_fakes, "VTT", DATA / vtt)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp or FakeYtDlp())
    monkeypatch.setattr(cli, "is_interactive", lambda: True)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in lines)))
    code = cli.main([])
    out = capsys.readouterr()
    return code, out.out + out.err, fake


def learned(tmp_path):
    return load_learned(tmp_path / "packs" / "financas-ptbr.learned.yaml")


def lines_of(out):
    return [line.removeprefix("> ") for line in out.splitlines()]


# ------------------------------------------------------------------ the menu


def test_first_screen(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["q"])
    assert code == 0
    first = out.splitlines()
    assert first[0].startswith("transcript-normalizer ")
    assert first[1] == f"Working in: {tmp_path}"
    assert first[2] == "Typical flow: 1 fetch → 2 normalize → 3 review"
    assert first[3].startswith("Keyboard: ")
    assert "What would you like to do?" in out
    assert "   1. Fetch a video or file   download a caption, or transcribe audio locally" in out
    assert "   6. Help                    what each action does and its command" in out
    assert "   q. Quit" in out
    assert not ANSI.search(out)  # no colour without a terminal


@pytest.mark.parametrize("lines", [[], [""]], ids=["end of input", "empty input"])
def test_empty_input_or_end_of_input_at_the_menu_quits(tmp_path, monkeypatch, capsys, lines):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0


def test_a_key_not_on_the_menu_is_asked_again(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["9", "q"])
    assert code == 0 and "'9' is not one of 1, 2, 3, 4, 5, 6, q" in out


def test_question_mark_explains_each_option_and_asks_again(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["?", "q"])
    assert "  Normalize a run: fix domain terms in a fetched caption" in out
    assert out.count("What would you like to do?") == 1  # the same question, not a new menu


def test_actions_are_separated_by_a_rule(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["5", "q"])
    rules = [line for line in out.splitlines() if line and set(line) == {"─"}]
    assert len(rules) == 1  # before the second menu, not the first


def test_help_has_the_sections(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["6", "q"])
    assert all(header in lines_of(out) for header in SECTIONS)
    assert "`transcript-normalizer runs/<id>/legenda.txt --review`" in out


def test_an_unexpected_error_is_shown_not_raised(tmp_path, monkeypatch, capsys):
    def broken():
        raise RuntimeError("disk on fire")

    monkeypatch.setitem(interactive.ACTIONS, "5", broken)
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["5", "q"])
    assert code == 0 and "error: RuntimeError: disk on fire" in out
    assert "Traceback" not in out


# ------------------------------------------------------------------ fetch, normalize, review


def test_fetch_then_normalize_then_review_chained(tmp_path, monkeypatch, capsys):
    lines = [
        "1", URL,  # fetch: the platform caption
        "",  # Next: normalize this run now? [Y/n] -> yes
        "1",  # What is this video about? -> financas-ptbr
        "",  # Next: review the 1 uncertain one(s) now? [Y/n] -> yes
        "a",  # Klabine is the recognizer mishearing Klabin
        "-",  # ... and not the speaker's own word
        "",  # Open the folder? [y/N] -> no
        "q",
    ]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    run = tmp_path / "runs" / VIDEO_ID
    assert (run / CAPTION_FILE).exists() and (run / NORMALIZED_FILE).exists()
    assert fake.downloads == [("--write-auto-subs", "pt")]
    # The summary, not the full report.
    assert "corrected 1  (SEMIG → CEMIG)" in out
    assert "to confirm 1  (the tool was unsure; your answer is remembered)" in out
    assert f"result: {run / NORMALIZED_FILE}" in out
    assert "terms:" not in out
    assert "The result is usable as it is" in out
    assert 'Which of these are the recognizer mishearing "Klabin"?' in out
    assert [c.variant for c in learned(tmp_path).confirmed["Klabin"]] == ["Klabine"]
    assert "nothing left pending." in out


def test_declining_the_next_steps_returns_to_the_menu(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", URL, "n", "q"])
    assert code == 0
    assert not (tmp_path / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()
    assert out.count("What would you like to do?") == 2


def test_empty_input_goes_back_from_any_question(tmp_path, monkeypatch, capsys):
    # fetch: empty URL; normalize: no run picked; review: no run picked.
    lines = ["1", "", "1", URL, "n", "2", "", "3", "", "q"]
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    assert "Normalize which run?" in out and "Review which run?" in out
    assert out.count("What would you like to do?") == 5
    assert "error" not in out


def test_a_run_is_picked_from_a_list_with_its_date_and_title(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", URL, "n", "4", "1", "q"])
    assert f"   1. {VIDEO_ID}   2026-08-25  Video sintetico de teste" in out
    assert "not normalized yet (2)." in out.split("Show which run?")[1]


def test_review_writes_confirmed_rejected_and_aliases(tmp_path, monkeypatch, capsys):
    lines = [
        "1", URL, "", "1",  # fetch, then normalize with financas-ptbr
        "",  # review now
        "a b",  # two of the three forms are the term ...
        "b",  # ... and the second of those is the speaker's own word
        "",  # Open the folder? [y/N] -> no
        "q",
    ]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    rows = dict(re.findall(r"^  ([abc])\. \[ \] (\S+)", out, re.M))
    assert set(rows) == {"a", "b", "c"}
    layer = learned(tmp_path)
    assert [c.variant for c in layer.confirmed["Klabin"]] == [rows["a"]]
    assert [a.alias for a in layer.aliases["Klabin"]] == [rows["b"]]
    assert [(r.text, r.term) for r in layer.rejected] == [(rows["c"], "Klabin")]
    # One example line per form, the form marked.
    assert re.search(rf"  a\. \[ \] {rows['a']} .*1 occurrence · \d:\d\d  .*«{rows['a']}»", out)


def test_esc_or_empty_on_a_term_leaves_it_pending(tmp_path, monkeypatch, capsys):
    lines = ["1", URL, "", "1", "", "", "", "q"]  # fetch, normalize, review, empty on the term, no folder
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    assert learned(tmp_path).is_empty()
    assert "3 variant(s) still pending" in out


def test_no_caption_offers_local_speech_recognition(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: [])
    lines = ["1", URL, "y", "n", "q"]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines, FakeYtDlp(has_caption=False))
    assert "Transcribe the audio on this computer instead?" in out
    assert fake.calls == ["metadata", "metadata", "audio"]
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_a_bad_url_is_an_error_in_the_menu(tmp_path, monkeypatch, capsys):
    code, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "not-a-url", "q"])
    assert code == 0
    assert "no such file, and not a url" in out
    assert "error: fetch did not finish (exit 1)" in out
    assert fake.calls == []


def test_show_wraps_long_lines_with_a_margin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "30")
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", URL, "", "1", "n", "", "4", "1", "q"])
    shown = out.split("normalized.txt, first")[1].split("─")[0]
    body = [line for line in shown.splitlines()[1:] if line.strip()]
    assert body and all(line.startswith("  ") and len(line) <= 30 for line in body)


# ------------------------------------------------------------------ the lite build


def test_the_lite_build_says_so_instead_of_offering_speech_recognition(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("TRANSCRIPT_NORMALIZER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", URL, "q"], FakeYtDlp(has_caption=False))
    assert fetch.LITE_BUILD in out
    assert "Transcribe the audio" not in out
    assert "audio" not in fake.calls


def test_the_lite_build_message_on_the_command_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("TRANSCRIPT_NORMALIZER_HOME", str(tmp_path / "home"))
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp(has_caption=False))
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: ["faster-whisper"] if "faster_whisper" in modules else [])
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)
    assert cli.main(["fetch", URL]) == 1
    assert fetch.LITE_BUILD in capsys.readouterr().err


# ------------------------------------------------------------------ command line


@pytest.mark.parametrize("argv", [["help"], ["--help"], ["-h"]])
def test_help_and_top_level_help_are_the_same_text(argv, monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "80")
    assert cli.main(argv) == 0
    out = capsys.readouterr().out
    assert [line for line in out.splitlines() if line and not line.startswith(" ")] == list(SECTIONS)
    assert max(len(line) for line in out.splitlines()) <= 80


def test_a_command_s_own_help_is_still_argparse(capsys):
    with pytest.raises(SystemExit) as stop:
        cli.main(["fetch", "--help"])
    assert stop.value.code == 0
    assert "--caption-only" in capsys.readouterr().out


def test_without_a_terminal_no_arguments_is_the_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(cli, "is_interactive", lambda: False)
    with pytest.raises(SystemExit) as stop:
        cli.main([])
    assert stop.value.code == 2
    assert "usage: transcript-normalizer" in capsys.readouterr().err


def test_review_and_confirm_cannot_be_combined(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as stop:
        cli.main(["normalize", str(DATA / "rolling.legenda.txt"), "--review", "--confirm"])
    assert stop.value.code == 2


# ------------------------------------------------------------------ questionary


class FakeQuestion:
    def __init__(self, answer, record, kind, kwargs):
        self.answer = answer
        record.append((kind, kwargs))

    def unsafe_ask(self):
        return self.answer


@pytest.fixture
def fake_questionary(monkeypatch):
    """A stand-in questionary module whose questions answer from a script."""
    module = types.ModuleType("questionary")
    module.__spec__ = importlib.machinery.ModuleSpec("questionary", None)
    module.answers, module.asked = [], []

    class Choice:
        def __init__(self, title, value=None, checked=False, **_):
            self.title, self.value, self.checked = title, value, checked

    module.Choice = Choice
    for kind in ("select", "checkbox", "confirm", "text"):
        setattr(module, kind, lambda title, *, _kind=kind, **kw: FakeQuestion(
            module.answers.pop(0), module.asked, _kind, {"title": title, **kw}
        ))
    monkeypatch.setitem(sys.modules, "questionary", module)
    monkeypatch.setattr(prompts, "interactive_terminal", lambda: True)
    return module


def test_select_goes_through_questionary_when_it_is_there(fake_questionary):
    options = [Option("Fetch", "download", value="1"), Option("Quit", value="q")]
    fake_questionary.answers = [1, prompts._BACK]
    assert prompts.select("What?", options) == "q"
    assert prompts.select("What?", options) is None  # Esc goes back
    kind, asked = fake_questionary.asked[0]
    assert kind == "select" and [c.value for c in asked["choices"]] == [0, 1]
    assert "esc back" in asked["instruction"]


def test_multi_select_and_confirm_go_through_questionary(fake_questionary):
    options = [Option("Klabine"), Option("Klabim"), Option("Clabine")]
    fake_questionary.answers = [[0, 2], True]
    assert prompts.multi_select("Which?", options, preselected={"Klabim"}) == ["Klabine", "Clabine"]
    assert prompts.confirm("Next?") is True
    (kind, asked), (kind2, _) = fake_questionary.asked
    assert kind == "checkbox" and [c.checked for c in asked["choices"]] == [False, True, False]
    assert "space select" in asked["instruction"]
    assert kind2 == "confirm"
