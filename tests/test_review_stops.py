"""D-072 to D-075: the review one form at a time, "only in this video", dubbed
caption tracks, and no decision numbers in what the program says.

Driven through the plain prompts, as a test always is (no terminal).
"""

import io
import json
import re
import shutil
from pathlib import Path

import pytest

from transcript_normalizer import cli, contribute, review
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.ingest import fetch
from transcript_normalizer.ingest.header import Metadata
from transcript_normalizer.runs import ANNOTATIONS_FILE, BUNDLED_PACKS, CAPTION_FILE, NORMALIZED_FILE

from .fetch_fakes import FakeYtDlp
from .test_interactive import LINK, menu

DATA = Path(__file__).resolve().parent / "data"
#: In review.vtt, three forms of Klabin wait for an answer, in this order:
#: Klabine (0:04), Klabim (0:07), Clabine (0:10).
TIMELINE = ["Klabine", "Klabim", "Clabine"]
YES, LOCAL, ALIAS, NO, LATER = "1", "2", "3", "4", "5"
PACK = BUNDLED_PACKS / "financas-ptbr.yaml"


def reviewed(tmp_path, monkeypatch, answers, caption=None, *extra):
    """`normalize <caption> --review`, fed `answers` (then end of input)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{a}\n" for a in answers)))
    code = cli.main(["normalize", str(caption or DATA / "review.vtt"), "--review", "--quiet", *extra])
    return code


def layer(tmp_path):
    return load_learned(tmp_path / "packs" / "financas-ptbr.learned.yaml")


def run_of(tmp_path, name="review"):
    return tmp_path / "runs" / name


def asked(out):
    return re.findall(r"^Is «(.+?)» Klabin\?$", out, re.M)


# ------------------------------------------------------------------ Enter, No, the summary


def test_enter_on_every_stop_writes_nothing(tmp_path, monkeypatch, capsys):
    assert reviewed(tmp_path, monkeypatch, ["", "", ""]) == 0
    out = capsys.readouterr().out
    assert asked(out) == TIMELINE
    assert "left for later: 3" in out
    assert "Save these answers?" not in out  # nothing to save, nothing asked
    assert not (tmp_path / "packs" / "financas-ptbr.learned.yaml").exists()
    assert not review.local_path(run_of(tmp_path)).exists()
    assert "3 variant(s) still pending" in out


@pytest.mark.parametrize("answer", [YES, LOCAL, ALIAS, NO, LATER])
def test_no_is_the_only_way_to_a_rejection(tmp_path, monkeypatch, answer):
    reviewed(tmp_path, monkeypatch, [answer, "", "", "y"])
    rejected = [(r.text, r.term) for r in layer(tmp_path).rejected]
    assert rejected == ([("Klabine", "Klabin")] if answer == NO else [])


def test_the_summary_comes_before_anything_is_written(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, [YES, LOCAL, "", NO, "y"])  # "": keep it local (D-086)
    out = capsys.readouterr().out
    summary = out.split("Summary")[1]
    assert "will remember: Klabine → Klabin" in summary
    assert "rejected: Clabine is not Klabin" in summary
    assert "only in this video: Klabim → Klabin" in summary
    assert "left for later: 0" in summary
    assert "Save these answers? [Y/n]" in summary
    learned = layer(tmp_path)
    assert [c.variant for c in learned.confirmed["Klabin"]] == ["Klabine"]
    assert review.read_local(run_of(tmp_path)) == [("Klabin", "Klabim")]


def test_no_to_the_summary_discards_every_answer(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, [YES, LOCAL, "", NO, "n"])
    out = capsys.readouterr().out
    assert "nothing saved: the 3 answer(s) of this review were discarded." in out
    assert not (tmp_path / "packs" / "financas-ptbr.learned.yaml").exists()
    assert not review.local_path(run_of(tmp_path)).exists()
    pending = (run_of(tmp_path) / "needs-review" / "pending.txt").read_text(encoding="utf-8")
    assert all(f in pending for f in TIMELINE)


def test_back_ends_the_stops_and_still_asks_before_saving(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, [YES, "b", "y"])
    out = capsys.readouterr().out
    assert asked(out) == ["Klabine", "Klabim"]
    assert "left for later: 2" in out
    assert [c.variant for c in layer(tmp_path).confirmed["Klabin"]] == ["Klabine"]


# ------------------------------------------------------------------ the order and the repeats


def test_stops_follow_the_timeline_and_a_form_is_asked_once(tmp_path, monkeypatch, capsys):
    # Klabine said three times, Clabine before it once more: each is one stop,
    # at its first occurrence, and lists where else it is said.
    caption = tmp_path / "repeat.vtt"
    cues = ["a Clabine pagou dividendos", "hoje a Klabine caiu", "e a Klabim subiu", "a Klabine de novo",
            "o EBITDA da Taesa melhorou", "a Klabine outra vez"]
    caption.write_text("WEBVTT\n\n" + "".join(
        f"00:00:{2 * i + 1:02d}.000 --> 00:00:{2 * i + 3:02d}.000\n{text}\n\n" for i, text in enumerate(cues)
    ), encoding="utf-8")
    reviewed(tmp_path, monkeypatch, [NO, YES, "", "y"], caption)
    out = capsys.readouterr().out
    assert asked(out) == ["Clabine", "Klabine", "Klabim"]
    stop = out.split("Is «Clabine» Klabin?")[1].split("Is «Klabine»")[0]
    assert re.search(r"also at \d:\d\d, \d:\d\d", stop)  # Klabine's two later places
    # The later occurrences took the answer: one confirmation, no question left for it.
    pending = (run_of(tmp_path, "repeat") / "needs-review" / "pending.txt").read_text(encoding="utf-8")
    assert "Klabine" not in pending and "Klabim" in pending


def test_a_form_taken_as_one_term_is_not_asked_for_another():
    a = lambda term, start: review.Annotation(start, start + 4, "Taes", term, term, "term:fuzzy", "medium", 85, "1")  # noqa: E731
    stops = review.stops([a("Taesa", 10), a("Tesla", 30), a("Taesa", 50)])
    assert [(s.term, s.form, len(s.found)) for s in stops] == [("Taesa", "Taes", 2), ("Tesla", "Taes", 1)]


# ------------------------------------------------------------------ context and the link


def test_a_stop_shows_the_lines_around_the_form(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, ["", "", ""])
    out = capsys.readouterr().out
    second = out.split("2 of 3")[1].split("Is «Klabim»")[0]
    assert "    0:04  hoje a Klabine caiu bastante" in second
    assert "  » 0:07  e a «Klabim» subiu depois" in second
    assert "    0:10  a Clabine pagou dividendos" in second
    assert "watch:" not in second  # a converted file has no URL: the time only


@pytest.mark.parametrize("url, link", [
    ("https://www.youtube.com/watch?v=4tTmY8Buask", "https://youtu.be/4tTmY8Buask?t=125"),
    ("https://youtu.be/4tTmY8Buask?si=x", "https://youtu.be/4tTmY8Buask?t=125"),
    ("https://www.youtube.com/shorts/4tTmY8Buask", "https://youtu.be/4tTmY8Buask?t=125"),
    ("https://vimeo.com/123456", "https://vimeo.com/123456 at 2:05"),
    ("", ""),
])
def test_the_link_to_that_moment(url, link):
    assert review.video_link(url, "2:05") == link


def test_a_youtube_run_links_each_stop(tmp_path, monkeypatch, capsys):
    caption = tmp_path / "legenda.txt"
    monkeypatch.chdir(tmp_path)
    converted = cli.convert_subtitle(DATA / "review.vtt", tmp_path / "conv")
    caption.write_text("# URL: https://www.youtube.com/watch?v=4tTmY8Buask\n" + converted.read_text(encoding="utf-8"),
                       encoding="utf-8")
    reviewed(tmp_path, monkeypatch, ["", "", ""], caption)
    out = capsys.readouterr().out
    assert "  watch: https://youtu.be/4tTmY8Buask?t=7" in out.split("2 of 3")[1]


# ------------------------------------------------------------------ only in this video (D-073)


def test_only_in_this_video_applies_on_renormalize_and_is_never_learned(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, [LOCAL, "", "", "", "y"])
    run = run_of(tmp_path)
    assert review.read_local(run) == [("Klabin", "Klabine")]
    assert layer(tmp_path).is_empty()
    # Normalized again, the run's own decision applies, as a stand-off annotation.
    assert cli.main(["normalize", str(run / CAPTION_FILE), "--quiet"]) == 0
    found = json.loads((run / ANNOTATIONS_FILE).read_text(encoding="utf-8"))
    local = [a for a in found if a["rule"] == review.RULE_LOCAL]
    assert [(a["original"], a["replacement"], a["band"], a["applied"]) for a in local] == [
        ("Klabine", "Klabin", "high", True)
    ]
    assert "hoje a Klabin caiu" in (run / NORMALIZED_FILE).read_text(encoding="utf-8")
    # Decided: no longer asked in this run.
    assert "Klabine" not in (run / "needs-review" / "pending.txt").read_text(encoding="utf-8")
    # Another run, the same words: still a question there, and nothing local.
    other = tmp_path / "other.vtt"
    shutil.copy(DATA / "review.vtt", other)
    cli.main(["normalize", str(other), "--quiet"])
    assert "Klabine" in (run_of(tmp_path, "other") / "needs-review" / "pending.txt").read_text(encoding="utf-8")
    others = json.loads((run_of(tmp_path, "other") / ANNOTATIONS_FILE).read_text(encoding="utf-8"))
    assert not any(a["rule"] == review.RULE_LOCAL for a in others)
    # Nothing to contribute: no learned layer was written, and a proposal reads only it.
    assert not (tmp_path / "packs" / "financas-ptbr.learned.yaml").exists()
    (tmp_path / "packs").mkdir(exist_ok=True)
    shutil.copy(PACK, tmp_path / "packs" / "financas-ptbr.yaml")
    assert contribute.items(tmp_path / "packs" / "financas-ptbr.yaml") == []
    assert not any("Klabine" in p.read_text(encoding="utf-8") for p in (tmp_path / "packs").rglob("*.yaml")
                   if p.name != "financas-ptbr.yaml")


def test_confirm_takes_o_for_only_in_this_video(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO("o\nn\ns\n"))
    cli.main(["normalize", str(DATA / "review.vtt"), "--confirm", "--quiet"])
    out = capsys.readouterr().out
    assert "[y]es / [o]nly in this video / [n]o" in out
    assert len(review.read_local(run_of(tmp_path))) == 1
    assert all(t == "Klabin" for t, _ in review.read_local(run_of(tmp_path)))
    assert not layer(tmp_path).confirmed


# ------------------------------------------------------------------ the menu


def test_the_menu_reviews_one_stop_at_a_time(tmp_path, monkeypatch, capsys):
    # fetch, normalize with financas-ptbr, review now: Yes, then Enter twice
    # (later), save; no contribution, no folder.
    lines = [*LINK, "", "1", "", YES, "", "", "", "", "", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    assert asked(out) == TIMELINE
    assert "will remember: Klabine → Klabin" in out and "left for later: 2" in out
    assert "  watch: https://youtu.be/" in out
    learned = load_learned(tmp_path / "packs" / "financas-ptbr.learned.yaml")
    assert [c.variant for c in learned.confirmed["Klabin"]] == ["Klabine"] and not learned.rejected


# ------------------------------------------------------------------ dubbed tracks (D-074)


#: What yt-dlp reported for 4tTmY8Buask, a Portuguese video YouTube dubbed.
DUBBED = Metadata(
    id="4tTmY8Buask",
    language="pt",
    manual_captions=("en",),
    automatic_captions=("de", "en", "en-US-orig", "es", "es-US-orig", "fr", "pt", "pt-orig"),
)


def test_the_video_s_own_language_is_the_original_and_comes_first():
    listed, translations = fetch.tracks(DUBBED)
    assert [(t.code, t.name) for t in listed] == [
        ("pt-orig", "Portuguese, original audio (automatic)"),
        ("en", "English (written by the channel)"),  # D-081: manual before automatic
        ("en-US-orig", "English (en-US), dubbed audio (automatic)"),
        ("es-US-orig", "Spanish (es-US), dubbed audio (automatic)"),
    ]
    assert all(t.translated for t in translations)
    assert fetch.choose_language(DUBBED, "pt") == ("pt-orig", fetch.AUTOMATIC_ORIGINAL)
    # A dub is not what --lang en takes first: the channel's own English is.
    assert fetch.choose_language(DUBBED, "en") == ("en", fetch.MANUAL)
    assert fetch.track_named(DUBBED, "es-US-orig").source == fetch.AUTOMATIC_DUBBED


def test_without_a_language_every_orig_track_is_original_as_before():
    plain = Metadata(automatic_captions=("en-US-orig", "pt", "pt-orig"))
    listed, _ = fetch.tracks(plain)
    assert [t.source for t in listed] == [fetch.AUTOMATIC_ORIGINAL] * 2


def test_the_menu_defaults_to_the_original_and_list_says_dubbed(tmp_path, monkeypatch, capsys):
    from transcript_normalizer import interactive

    listed, _ = fetch.tracks(DUBBED)
    assert interactive.default_track(DUBBED, listed) == "pt-orig"

    class Dubbed(FakeYtDlp):
        def info(self):
            return {**super().info(), "language": "pt", "subtitles": {"en": [{}]},
                    "automatic_captions": {c: [{}] for c in DUBBED.automatic_captions}}

    from . import fetch_fakes

    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, Dubbed())
    assert cli.main(["fetch", "--list", fetch_fakes.URL]) == 0
    out = capsys.readouterr().out
    assert "original: pt-orig" in out and "dubbed: en-US-orig, es-US-orig" in out


# ------------------------------------------------------------------ no decision numbers (D-075)


def test_no_decision_number_in_help_or_any_command_help(capsys):
    assert cli.main(["help"]) == 0
    for argv in (["fetch"], ["normalize"], ["list"], ["pack"], ["pack", "merge"], ["pack", "create"],
                 ["pack", "propose"], ["pack", "copy"], ["pack", "add-term"]):
        with pytest.raises(SystemExit):
            cli.main([*argv, "--help"])
    assert "D-0" not in capsys.readouterr().out


def test_no_decision_number_in_the_menu(tmp_path, monkeypatch, capsys):
    lines = [*LINK, "", "1", "", YES, "", "", "", "", "", "6", "1", "b", "7", "1", "", "8", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    assert "D-0" not in out


def test_no_decision_number_in_any_message_string():
    """Every string in the program but docstrings and the comment block written
    into a new pack file (a file comment, like the code's own)."""
    import ast

    source = Path(cli.__file__).parent
    found = []
    for path in source.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
                    and re.search(r"D-0\d\d", node.value) and not node.value.endswith(".\n")):
                found.append(f"{path.name}:{node.lineno}")
    assert found == []


# ------------------------------------------------------------------ after the summary (D-077)


def test_only_local_answers_neither_announce_the_layer_nor_offer_to_contribute(tmp_path, monkeypatch, capsys):
    # fetch, normalize, review now: only in this video, later, later; save;
    # no term noticed; no folder.
    lines = [*LINK, "", "1", "", LOCAL, "", "", "", "", "", "", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    assert "only in this video: Klabine → Klabin" in out
    assert "learned layer written" not in out
    assert "Contribute what you taught the tool?" not in out
    after = out.split("Save these answers?")[1]
    assert after.count("Add a term you noticed?") == 1 and after.count("Open the folder?") == 1
    assert after.index("Add a term you noticed?") < after.index("Open the folder?")


def test_one_confirmed_form_announces_the_layer_and_offers_to_contribute(tmp_path, monkeypatch, capsys):
    # ... yes, later, later; save; no contribution; no term; no folder.
    lines = [*LINK, "", "1", "", YES, "", "", "", "", "", "", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines, vtt="review.vtt")
    after = out.split("Save these answers?")[1]
    asked_in_order = [after.index(q) for q in (
        "learned layer written to", "Contribute what you taught the tool?",
        "Add a term you noticed?", "Open the folder?")]
    assert asked_in_order == sorted(asked_in_order)
    assert all(after.count(q) == 1 for q in ("Contribute what you taught the tool?",
                                             "Add a term you noticed?", "Open the folder?"))


def test_an_earlier_review_s_entries_do_not_make_this_one_offer_to_contribute(tmp_path, monkeypatch, capsys):
    menu(tmp_path, monkeypatch, capsys, [*LINK, "", "1", "", YES, "", "", "", "", "", "", "q"], vtt="review.vtt")
    # The same run reviewed again from the menu (one pack: not asked), only
    # later answers this time; no term, no folder.
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["3", "1", "", "", "", "", "q"], vtt="review.vtt")
    assert "left for later: 2" in out
    assert "Contribute what you taught the tool?" not in out and "learned layer written" not in out
