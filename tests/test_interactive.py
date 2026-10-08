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

from transcript_normalizer import cli, interactive, prompts, runs
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.ingest import fetch
from transcript_normalizer.prompts import Option
from transcript_normalizer.runs import CAPTION_FILE, NORMALIZED_FILE

from . import fetch_fakes
from .fetch_fakes import LINK, URL, VIDEO_ID, FakeYtDlp

DATA = Path(__file__).resolve().parent / "data"
SECTIONS = ("USAGE", "COMMANDS", "MENU", "WHAT HAPPENS", "THE REVIEW LOOP", "EXAMPLES", "LEARN MORE")
ANSI = re.compile(r"\x1b\[")


#: fetch's own check for an extra, before the fakes replace it.
REAL_MISSING_EXTRA = fetch.missing_extra


def menu(tmp_path, monkeypatch, capsys, lines, ytdlp=None, vtt="menu.vtt", whisper=True):
    """`transcript-normalizer` with no arguments, as on a terminal, fed `lines`.

    `whisper=False`: faster-whisper cannot be imported, and fetch finds that out
    the way it does outside the tests.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_fakes, "VTT", DATA / vtt)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp or FakeYtDlp())
    if not whisper:
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        monkeypatch.setattr(fetch, "missing_extra", REAL_MISSING_EXTRA)
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
    assert first[1] in ("captions + local transcription", "captions only")
    assert first[2] == f"Working in: {tmp_path}"
    assert first[3] == "Typical flow: 1 fetch → 2 normalize → 3 review"
    assert first[4].startswith("Keyboard: ")
    assert "What would you like to do?" in out
    assert "   1. Fetch a video or file   download a caption, or transcribe audio locally" in out
    assert "   6. Help                    what each action does and its command" in out
    assert "   7. Settings                where to save your files, the pack offered first" in out
    assert "   q. Quit" in out
    assert "Back" not in out  # the menu has Quit instead
    assert not ANSI.search(out)  # no colour without a terminal


@pytest.mark.parametrize("lines", [[], [""]], ids=["end of input", "empty input"])
def test_empty_input_or_end_of_input_at_the_menu_quits(tmp_path, monkeypatch, capsys, lines):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0


def test_a_key_not_on_the_menu_is_asked_again(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["9", "q"])
    assert code == 0 and "'9' is not one of 1, 2, 3, 4, 5, 6, 7, q" in out


def test_question_mark_explains_each_option_and_asks_again(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "200")
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["?", "q"])
    # The help entries (help's MENU section), not the one-line descriptions again.
    entry = next(a for a in interactive.ITEMS if a.key == "2")
    assert f"  {entry.label}" in out and entry.help in out
    assert f"`{entry.command}`" in out
    assert "  Quit" in out and "leave the menu" in out
    assert out.count("What would you like to do?") == 1  # the same question, not a new menu


def test_actions_are_separated_by_a_rule(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["5", "q"])
    rules = [line for line in out.splitlines() if line and set(line) == {"-"}]
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
        *LINK,  # fetch: the platform caption
        "",  # Next: normalize this run now? [Y/n] -> yes
        "1",  # What is this video about? -> financas-ptbr
        "",  # Next: review the 1 uncertain one(s) now? [Y/n] -> yes
        "a",  # Klabine is the recognizer mishearing Klabin
        "-",  # ... and not the speaker's own word
        "",  # Contribute what you taught the tool? [y/N] -> no
        "",  # Open the folder? [y/N] -> no
        "q",
    ]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    run = tmp_path / "runs" / VIDEO_ID
    assert (run / CAPTION_FILE).exists() and (run / NORMALIZED_FILE).exists()
    assert fake.downloads == [("writeautomaticsub", "pt")]
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
    code, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "n", "q"])
    assert code == 0
    assert not (tmp_path / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()
    assert out.count("What would you like to do?") == 2


def test_empty_input_goes_back_from_any_question(tmp_path, monkeypatch, capsys):
    # fetch: empty URL; normalize: no run picked; review: no run picked.
    lines = ["1", "", *LINK, "n", "2", "", "3", "", "q"]
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    assert "Normalize which run?" in out and "Review which run?" in out
    assert out.count("What would you like to do?") == 5
    assert "error" not in out


def test_a_run_is_picked_from_a_list_with_its_date_and_title(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "n", "4", "1", "q"])
    assert f"   1. {VIDEO_ID}   2026-08-25  Video sintetico de teste" in out
    assert "not normalized yet." in out.split("Show which run?")[1]
    assert "(2)" not in out


def test_review_writes_confirmed_rejected_and_aliases(tmp_path, monkeypatch, capsys):
    lines = [
        *LINK, "", "1",  # fetch, then normalize with financas-ptbr
        "",  # review now
        "a b",  # two of the three forms are the term ...
        "b",  # ... and the second of those is the speaker's own word
        "",  # Contribute what you taught the tool? [y/N] -> no
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
    lines = [*LINK, "", "1", "", "", "", "q"]  # fetch, normalize, review, empty on the term, no folder
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    assert learned(tmp_path).is_empty()
    assert "3 variant(s) still pending" in out


def test_no_caption_offers_local_speech_recognition(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: [])
    lines = ["1", "1", URL, "y", "n", "q"]
    code, out, fake = menu(tmp_path, monkeypatch, capsys, lines, FakeYtDlp(has_caption=False))
    assert "Transcribe the audio on this computer instead?" in out
    assert fake.calls == ["metadata", "metadata", "audio"]
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_a_bad_url_is_an_error_in_the_menu(tmp_path, monkeypatch, capsys):
    code, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", "not-a-url", "q"])
    assert code == 0
    assert "no such file, and not a url" in out
    assert "error: fetch did not finish" in out and "exit" not in out
    assert fake.calls == []


def test_show_wraps_long_lines_with_a_margin(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COLUMNS", "30")
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "1", "n", "", "4", "1", "q"])
    shown = out.split("normalized.txt, first")[1].split("-" * 30)[0]
    body = [line for line in shown.splitlines()[1:] if line.strip()]
    assert body and all(line.startswith("  ") and len(line) <= 30 for line in body)


# ------------------------------------------------------------------ the lite build


def test_the_lite_build_says_so_instead_of_offering_speech_recognition(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("TRANSCRIPT_NORMALIZER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "q"], FakeYtDlp(has_caption=False))
    # D-057, D-062: the reason first, then the lite notice, because step 2 was needed.
    reason = fetch.NO_CAPTION
    assert reason in out and fetch.LITE_BUILD in out
    assert out.index(reason) < out.index(fetch.LITE_BUILD)
    assert "Transcribe the audio" not in out
    assert "audio" not in fake.calls


def test_the_lite_notice_never_hides_a_step_1_error(tmp_path, monkeypatch, capsys):
    """D-057: a failure to read the video is not a lite-build problem."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("TRANSCRIPT_NORMALIZER_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)

    class Unreachable(FakeYtDlp):
        def info(self):
            raise fetch_fakes.DownloadError("ERROR: [youtube] abcdefghijk: Video unavailable")

    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "q"], Unreachable())
    assert "could not read the video: reading the video failed: ERROR: [youtube] abcdefghijk: Video unavailable" in out
    assert fetch.LITE_BUILD not in out


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
    fake_questionary.answers = [1, prompts._BACK, 2]
    assert prompts.select("What?", options) == "q"
    assert prompts.select("What?", options) is None  # Esc goes back
    assert prompts.select("What?", options) is None  # so does the Back option
    kind, asked = fake_questionary.asked[0]
    assert kind == "select" and [c.value for c in asked["choices"]] == [0, 1, 2]
    assert asked["choices"][-1].title.strip() == "← Back"
    assert "esc back" in asked["instruction"] and asked["pointer"] == "»"


def test_multi_select_and_confirm_go_through_questionary(fake_questionary):
    options = [Option("Klabine"), Option("Klabim"), Option("Clabine")]
    fake_questionary.answers = [[0, 2], True]
    assert prompts.multi_select("Which?", options, preselected={"Klabim"}) == ["Klabine", "Clabine"]
    assert prompts.confirm("Next?") is True
    (kind, asked), (kind2, _) = fake_questionary.asked
    assert kind == "checkbox" and [c.checked for c in asked["choices"]] == [False, True, False]
    assert "space select" in asked["instruction"]
    assert kind2 == "confirm"


def test_question_mark_in_real_questionary_explains_then_asks_again(monkeypatch, capsys):
    """The `?` key reaches our binding through prompt_toolkit, not just the fake."""
    questionary = pytest.importorskip("questionary")
    import functools

    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    monkeypatch.setenv("COLUMNS", "120")
    monkeypatch.setattr(prompts, "interactive_terminal", lambda: True)
    with create_pipe_input() as keys:
        monkeypatch.setattr(questionary, "select", functools.partial(questionary.select, input=keys, output=DummyOutput()))
        options = interactive.menu_options()
        keys.send_text("?")  # explain
        keys.send_text("\x1b[A\r")  # then: up (to Quit, the last), enter
        assert prompts.select("What would you like to do?", options, back=False) == "q"
        keys.send_text("\x1b")  # Esc goes back
        assert prompts.select("What would you like to do?", options, back=False) is None
    out = capsys.readouterr().out
    assert "`transcript-normalizer fetch <url|file> [--track <code>]`" in out and "leave the menu" in out


def test_a_chosen_option_is_echoed_by_its_label_only(monkeypatch):
    """D-063: the list shows each description; the answer line, the label."""
    questionary = pytest.importorskip("questionary")
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    asked = []

    def select(*args, **kwargs):
        question = real(*args, input=keys, output=DummyOutput(), **kwargs)
        asked.append(question)
        return question

    real = questionary.select
    monkeypatch.setattr(prompts, "interactive_terminal", lambda: True)
    monkeypatch.setattr(questionary, "select", select)
    options = [Option("Fetch", "a video or a file", value="f"), Option("Quit", value="q")]
    with create_pipe_input() as keys:
        choices = []
        monkeypatch.setattr(prompts._Questionary, "_choices", staticmethod(
            lambda o, p=(), make=prompts._Questionary._choices: choices.extend(make(o, p)) or choices
        ))
        keys.send_text("\r")
        assert prompts.select("What?", options) == "f"
    assert asked and "a video or a file" in choices[0].line  # the list
    assert choices[0].title == "Fetch"  # the answer line


# ------------------------------------------------------------------ 0.5.0: Back, Settings, structure (D-061)


def fetched(lines):
    """Fetch the fake video, decline normalizing, then `lines`, then quit."""
    return [*LINK, "n", *lines, "q"]


def nothing_written(tmp_path):
    run = tmp_path / "runs" / VIDEO_ID
    return not (run / NORMALIZED_FILE).exists() and learned(tmp_path).is_empty()


def test_back_from_a_run_list_returns_to_the_menu(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, fetched(["2", "b", "4", "b"]))
    assert code == 0
    assert "   b. <- Back" in out.split("Normalize which run?")[1]
    assert out.count("What would you like to do?") == 4
    assert nothing_written(tmp_path) and "error" not in out


def test_back_from_the_pack_question_returns_to_the_run_list_then_the_menu(tmp_path, monkeypatch, capsys):
    # From the fetch chain, Back at the pack question is the menu; from
    # "Normalize a run", it is the run list, and Back there is the menu.
    lines = [*LINK, "", "b", "2", "1", "b", "b", "q"]
    code, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert code == 0
    assert out.count("What is this video about?") == 2
    assert out.count("Normalize which run?") == 2
    assert out.count("What would you like to do?") == 3
    assert nothing_written(tmp_path)


def test_back_from_the_review_returns_to_the_menu(tmp_path, monkeypatch, capsys):
    code, out, _ = menu(tmp_path, monkeypatch, capsys, fetched(["3", "b"]))
    assert code == 0
    assert "Review which run?" in out and out.count("What would you like to do?") == 3
    assert nothing_written(tmp_path)


def test_review_with_nothing_pending_says_so_and_does_not_offer_the_folder(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, fetched(["3", "1"]))
    assert interactive.NOTHING_TO_REVIEW in out
    assert "Open the folder?" not in out and "Review against which pack?" not in out


def test_review_on_a_run_whose_pack_did_not_fit_says_nothing_to_review(tmp_path, monkeypatch, capsys):
    lines = [*LINK, "", "1", "3", "1", "q"]  # fetch, normalize (unfit), review
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="rolling.vtt")
    after = out.split("Review which run?")[1]
    assert interactive.NOTHING_TO_REVIEW in after and "Open the folder?" not in after


def test_stages_and_text_fields_are_marked(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "1", "", "", "7", "b", "q"])
    lines = out.splitlines()
    for label in ("* Fetch", "* Settings"):
        at = lines.index(label)
        assert set(lines[at - 1]) == {"-"}  # a rule above each stage label
    assert "-- paste below --" in lines
    assert "(empty or Esc: back)" in out


def test_settings_writes_the_folder_and_the_menu_uses_it(tmp_path, monkeypatch, capsys, isolated_settings):
    chosen = tmp_path / "my files"
    # Settings -> Where to save -> Choose another folder (no dialog here: typed).
    code, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "1", "1", str(chosen), "b", "q"])
    assert code == 0
    assert "no folder dialog here; type the path instead" in out
    assert "-- type a path --" in out
    assert f"Saved. Your files go in {chosen}" in out
    assert runs.read_config() == {"data_dir": str(chosen)}
    assert runs.base_dir() == chosen and (chosen / "runs").is_dir() and (chosen / "packs").is_dir()
    # The next start says where, and a fetch writes there.
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "n", "q"])
    assert f"Your files: {chosen}" in out.splitlines()
    assert (chosen / "runs" / VIDEO_ID / CAPTION_FILE).exists()
    assert not (tmp_path / "runs").exists()


def test_settings_can_go_back_to_the_default(tmp_path, monkeypatch, capsys):
    runs.write_config({"data_dir": str(tmp_path / "elsewhere"), "pack": "financas-ptbr"})
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "1", "2", "b", "q"])
    assert "chosen in Settings" in out
    assert runs.read_config() == {"pack": "financas-ptbr"}
    assert runs.base_dir() == tmp_path


def test_the_pack_offered_first_is_saved(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "2", "1", "b", "q"])
    assert "Saved. Offered first: financas-ptbr" in out
    assert runs.read_config() == {"pack": "financas-ptbr"}


def test_the_config_file_round_trips_any_path(isolated_settings):
    odd = 'C:\\Users\\Zoë\\My "files"'
    runs.write_config({"data_dir": odd, "gone": None})
    assert runs.read_config() == {"data_dir": odd}
    assert isolated_settings.read_text(encoding="utf-8").startswith("data_dir = ")
    isolated_settings.write_text("not toml [", encoding="utf-8")
    assert runs.read_config() == {} and runs.configured_dir() is None


def test_the_variable_wins_over_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runs.write_config({"data_dir": str(tmp_path / "chosen")})
    assert runs.base_dir() == tmp_path / "chosen"
    monkeypatch.setenv(runs.DATA_DIR_ENV, str(tmp_path / "scripted"))
    assert runs.base_dir() == tmp_path / "scripted"


def fake_tkinter(monkeypatch, chosen):
    """A stand-in tkinter whose folder dialog answers `chosen`."""
    tk = types.ModuleType("tkinter")
    tk.TclError = type("TclError", (Exception,), {})
    tk.calls = []

    class Tk:
        def withdraw(self):
            tk.calls.append("withdraw")

        def attributes(self, *args):
            pass

        def destroy(self):
            tk.calls.append("destroy")

    dialog = types.ModuleType("tkinter.filedialog")
    dialog.askdirectory = lambda **kwargs: tk.calls.append(("askdirectory", kwargs)) or chosen
    dialog.askopenfilename = lambda **kwargs: tk.calls.append(("askopenfilename", kwargs)) or chosen
    tk.Tk, tk.filedialog = Tk, dialog
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", dialog)
    return tk


def test_the_folder_dialog_is_used_and_its_answer_stored(tmp_path, monkeypatch, capsys):
    chosen = tmp_path / "picked"
    tk = fake_tkinter(monkeypatch, str(chosen))
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "1", "1", "b", "q"])
    (_, asked), = [c for c in tk.calls if isinstance(c, tuple)]
    assert asked["initialdir"] == str(tmp_path) and asked["title"] == "Where to save your files"
    assert tk.calls[-1] == "destroy"
    assert "type a path" not in out
    assert runs.read_config() == {"data_dir": str(chosen)}


def test_cancelling_the_folder_dialog_changes_nothing(tmp_path, monkeypatch, capsys):
    fake_tkinter(monkeypatch, "")
    menu(tmp_path, monkeypatch, capsys, ["7", "1", "1", "b", "q"])
    assert runs.read_config() == {}


@pytest.mark.parametrize("frozen,whisper,line", [
    (False, True, "captions + local transcription"),
    (False, False, "captions only"),
    (True, True, "full build: captions and local transcription"),
    (True, False, "lite build: platform captions only (no local transcription)"),
])
def test_the_first_screen_says_what_this_build_does(tmp_path, monkeypatch, capsys, frozen, whisper, line):
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv(runs.DATA_DIR_ENV, str(tmp_path / "home"))
    module = types.ModuleType("faster_whisper")
    module.__spec__ = importlib.machinery.ModuleSpec("faster_whisper", None)
    monkeypatch.setitem(sys.modules, "faster_whisper", module if whisper else None)
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["q"])
    assert out.splitlines()[1] == line


# ------------------------------------------------------------------ 0.5.2: the fetch flow (D-062)


def test_where_is_it_offers_a_link_or_a_file(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "b", "q"])
    asked = out.split("Where is it?")[1].split("What would you like to do?")[0]
    assert "   1. A link (YouTube and others)" in asked
    assert "   2. A file on this computer" in asked
    assert "   b. <- Back" in asked
    assert out.count("What would you like to do?") == 2


def test_a_media_file_from_the_dialog_is_transcribed(tmp_path, monkeypatch, capsys):
    media = tmp_path / "aula.mp3"
    media.write_bytes(b"\0" * 16)
    tk = fake_tkinter(monkeypatch, str(media))
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "2", "n", "q"])
    (_, asked), = [c for c in tk.calls if isinstance(c, tuple)]
    assert asked["filetypes"][0] == (  # D-063: the default filter
        "All supported (audio, video, captions)",
        "*.mp3 *.m4a *.wav *.ogg *.opus *.mp4 *.mkv *.webm *.mov *.txt *.srt *.vtt",
    )
    assert asked["filetypes"][1] == ("Audio or video", "*.mp3 *.m4a *.wav *.ogg *.opus *.mp4 *.mkv *.webm *.mov")
    assert asked["filetypes"][2] == ("Captions", "*.txt *.srt *.vtt")
    assert asked["filetypes"][3] == ("All files", "*")
    assert "step 2: local speech recognition" in out
    assert (tmp_path / "runs" / "aula" / CAPTION_FILE).exists()
    assert fake.calls == []  # a file: nothing asked of the platform
    assert "Next: normalize this run now?" in out


def test_a_caption_file_skips_transcription_and_goes_to_normalizing(tmp_path, monkeypatch, capsys):
    caption = tmp_path / "aula.vtt"
    caption.write_bytes((DATA / "menu.vtt").read_bytes())
    fake_tkinter(monkeypatch, str(caption))
    # Fetch, a file, then: the pack, no review, no folder.
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "2", "1", "n", "", "q"])
    fetched = out.split("Where is it?")[1].split("What would you like to do?")[0]
    assert "step 2" not in fetched and "transcrib" not in fetched
    assert "Next: normalize this run now?" not in out  # straight there
    assert "What is this video about?" in out
    run = tmp_path / "runs" / "aula"
    assert (run / CAPTION_FILE).exists() and (run / NORMALIZED_FILE).exists()
    assert fake.calls == []


def test_without_a_file_dialog_the_path_is_typed(tmp_path, monkeypatch, capsys):
    caption = tmp_path / "aula.vtt"
    caption.write_bytes((DATA / "menu.vtt").read_bytes())
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "2", str(caption), "1", "n", "", "q"])
    assert "no file dialog here; type the path instead" in out and "-- type a path --" in out
    assert (tmp_path / "runs" / "aula" / NORMALIZED_FILE).exists()


def test_cancelling_the_file_dialog_goes_back_to_where_is_it(tmp_path, monkeypatch, capsys):
    fake_tkinter(monkeypatch, "")
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "2", "b", "q"])
    assert out.count("Where is it?") == 2 and "error" not in out


@pytest.mark.parametrize("code,name", [
    ("pt", "Portuguese"), ("pt-BR", "Portuguese (pt-BR)"), ("zh-Hans", "Chinese (zh-Hans)"), ("xx", "xx"),
])
def test_language_names(code, name):
    assert fetch.language_name(code) == name


def test_the_track_list_names_the_tracks_and_takes_the_original_by_default(tmp_path, monkeypatch, capsys):
    platform = FakeYtDlp(automatic=("en", "pt", "pt-orig"))
    _, out, fake = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "n", "q"], platform)
    listed = out.split("Which caption?")[1].split("> ")[0]
    assert "   1. Portuguese, original audio (automatic)" in listed
    assert (
        "   2. Other languages (automatic translations)…   2 language(s) (translations are rate-limited more often)"
        in listed
    )
    assert "enter alone: Portuguese, original audio (automatic)" in listed
    assert "pt-orig" not in listed  # names, not codes
    assert fake.downloads == [("writeautomaticsub", "pt-orig")]  # enter: today's choice (D-045)


def test_a_translation_is_picked_from_its_own_list(tmp_path, monkeypatch, capsys):
    platform = FakeYtDlp(automatic=("en", "pt", "pt-orig"))
    _, out, fake = menu(tmp_path, monkeypatch, capsys, [*LINK, "2", "1", "n", "q"], platform)
    listed = out.split("Which language?")[1].split("> ")[0]
    assert "   1. English (automatic translation)      (translations are rate-limited more often)" in listed
    assert "   2. Portuguese (automatic translation)   (translations are rate-limited more often)" in listed
    assert fake.downloads == [("writeautomaticsub", "en")]


def test_manual_tracks_come_after_the_original(tmp_path, monkeypatch, capsys):
    platform = FakeYtDlp(manual=("pt",), automatic=("en", "pt-orig"))
    _, out, fake = menu(tmp_path, monkeypatch, capsys, [*LINK, "2", "n", "q"], platform)
    listed = out.split("Which caption?")[1].split("> ")[0]
    assert listed.index("Portuguese, original audio (automatic)") < listed.index("Portuguese (written by the channel)")
    assert fake.downloads == [("writesubtitles", "pt")]


def test_a_video_with_one_track_names_it_without_asking(tmp_path, monkeypatch, capsys):
    _, out, fake = menu(tmp_path, monkeypatch, capsys, [*LINK, "n", "q"])
    assert "Which caption?" not in out and "caption: Portuguese (automatic)" in out
    assert fake.downloads == [("writeautomaticsub", "pt")]


def test_full_build_can_transcribe_instead_of_the_caption(tmp_path, monkeypatch, capsys):
    lines = ["1", "1", URL, "2", "n", "q"]  # the second option: transcribe
    _, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert "Use the platform's caption, or transcribe the audio on this computer?" in out
    assert fake.downloads == [] and "audio" in fake.calls
    assert "step 2: local speech recognition" in out


@pytest.mark.parametrize("frozen,reason", [(True, "full build only"), (False, "needs the ingest extra")])
def test_without_whisper_transcription_is_shown_but_disabled(tmp_path, monkeypatch, capsys, frozen, reason):
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setenv(runs.DATA_DIR_ENV, str(tmp_path / "home"))
    lines = ["1", "1", URL, "2", "", "n", "q"]  # 2 is refused; enter takes the caption
    _, out, fake = menu(tmp_path, monkeypatch, capsys, lines, whisper=False)
    assert f"   -. Transcribe the audio on this computer   ({reason})" in out
    assert "'2' is not one of 1, b" in out
    assert fake.downloads == [("writeautomaticsub", "pt")] and "audio" not in fake.calls


def test_track_on_the_command_line_takes_that_exact_track(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, FakeYtDlp(automatic=("en", "pt-orig")))
    assert cli.main(["fetch", URL, "--track", "en"]) == 0
    assert fake.downloads == [("writeautomaticsub", "en")]
    assert cli.main(["fetch", URL, "--track", "fr", "--caption-only"]) == 1
    assert "there is no caption track 'fr' for this video" in capsys.readouterr().err
    assert cli.main(["fetch", URL]) == 0  # --lang's choice, as before
    assert fake.downloads[-1] == ("writeautomaticsub", "pt-orig")


def test_settings_hint_is_printed_once(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "2", "1", "b", "q"])
    assert out.count("saved in your user settings, for every run of the menu") == 1
    assert out.count("What would you like to change?") == 2


def test_a_fresh_frozen_start_reads_the_saved_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    chosen = tmp_path / "chosen"
    runs.write_config({"data_dir": str(chosen)})
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["q"])
    assert f"Your files: {chosen}" in out.splitlines()
