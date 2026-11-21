"""D-091: no command writes over a run's legenda.txt unasked; D-092: passages
a transcription wrote twice; D-093: which moment of a line the timestamp is."""

import io
import shutil
import sys
import wave
from pathlib import Path

import pytest

from transcript_normalizer import caption_guard, cli
from transcript_normalizer.caption_guard import EXIT_CAPTION_EXISTS, REPLACED_PREFIX
from transcript_normalizer.cli import main
from transcript_normalizer.core.text import read_caption
from transcript_normalizer.ingest import fetch
from transcript_normalizer.ingest.header import Metadata, caption_header, file_header, speech_header
from transcript_normalizer.ingest.repeats import MIN_WORDS, REPEATS_FILE, find_repeats, header_lines
from transcript_normalizer.runs import ANNOTATIONS_FILE, CAPTION_FILE, META_FILE, NEEDS_REVIEW_DIR

from . import fetch_fakes
from .fetch_fakes import LINK, URL, VIDEO_ID, FakeYtDlp, Info, Segment

DATA = Path(__file__).resolve().parent / "data"


def run_of(tmp_path):
    return tmp_path / "runs" / VIDEO_ID


def fetch_url(tmp_path, monkeypatch, *extra, ytdlp=None):
    monkeypatch.chdir(tmp_path)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp or FakeYtDlp())
    return main(["fetch", URL, *extra]), fake


def replaced(run):
    return sorted(p for p in run.iterdir() if p.name.startswith(REPLACED_PREFIX))


# ------------------------------------------------------------------ fetch from a link


def test_fetching_the_same_link_again_uses_the_text_there(tmp_path, monkeypatch, capsys):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    caption = run_of(tmp_path) / CAPTION_FILE
    before = caption.read_bytes()
    capsys.readouterr()

    code, fake = fetch_url(tmp_path, monkeypatch, ytdlp=FakeYtDlp())
    assert code == 0
    assert fake.calls == ["metadata"]  # nothing downloaded
    assert caption.read_bytes() == before
    assert "already here, from the same source" in capsys.readouterr().out
    assert replaced(run_of(tmp_path)) == []


def test_another_source_is_refused_before_anything_is_downloaded(tmp_path, monkeypatch, capsys):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    caption = run_of(tmp_path) / CAPTION_FILE
    before = caption.read_bytes()
    capsys.readouterr()

    code, fake = fetch_url(tmp_path, monkeypatch, "--whisper", ytdlp=FakeYtDlp())
    assert code == EXIT_CAPTION_EXISTS
    assert fake.calls == ["metadata"]
    assert caption.read_bytes() == before
    err = capsys.readouterr().err
    assert "already there, and was not replaced" in err
    assert "you asked for a local transcription" in err
    assert "--out <folder>" in err and "--replace-caption" in err


@pytest.mark.parametrize("first, second, reason", [
    (["--whisper"], ["--whisper", "--model", "small"], "you asked for the model small"),
    (["--whisper"], ["--caption-only"], "you asked for the platform's caption"),
    (["--track", "pt"], ["--track", "en"], "you asked for the track en"),
])
def test_what_pins_the_text_down_is_part_of_its_source(tmp_path, monkeypatch, capsys, first, second, reason):
    platform = dict(automatic=("pt", "en"))
    assert fetch_url(tmp_path, monkeypatch, *first, ytdlp=FakeYtDlp(**platform))[0] == 0
    capsys.readouterr()
    code, _ = fetch_url(tmp_path, monkeypatch, *second, ytdlp=FakeYtDlp(**platform))
    assert code == EXIT_CAPTION_EXISTS
    assert reason in capsys.readouterr().err


def test_another_video_in_the_same_out_folder_is_refused(tmp_path, monkeypatch, capsys):
    assert fetch_url(tmp_path, monkeypatch, "--out", "here")[0] == 0
    other = "https://www.youtube.com/watch?v=zzzzzzzzzzz"
    fake = FakeYtDlp(url=other, video_id="zzzzzzzzzzz")
    fetch_fakes.install(monkeypatch, fetch, fake)
    capsys.readouterr()
    assert main(["fetch", other, "--out", "here"]) == EXIT_CAPTION_EXISTS
    assert "not of this link" in capsys.readouterr().err


def test_replacing_keeps_the_old_text_and_what_was_made_from_it(tmp_path, monkeypatch, capsys):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    run = run_of(tmp_path)
    old = (run / CAPTION_FILE).read_bytes()
    (run / ANNOTATIONS_FILE).write_text("[]", encoding="utf-8")  # as normalize leaves it
    (run / NEEDS_REVIEW_DIR).mkdir()
    (run / NEEDS_REVIEW_DIR / "pending.txt").write_text("x\n", encoding="utf-8")

    code, fake = fetch_url(tmp_path, monkeypatch, "--whisper", "--replace-caption", ytdlp=FakeYtDlp())
    assert code == 0 and fake.calls == ["metadata", "audio"]
    [kept] = replaced(run)
    assert (kept / CAPTION_FILE).read_bytes() == old
    assert sorted(p.name for p in kept.iterdir()) == sorted(
        [CAPTION_FILE, META_FILE, ANNOTATIONS_FILE, NEEDS_REVIEW_DIR])
    assert read_caption(run / CAPTION_FILE).header[0].startswith(caption_guard.SPEECH_FIRST)
    assert not (run / ANNOTATIONS_FILE).exists()  # it belonged to the old text
    assert "the earlier text, kept there" in capsys.readouterr().out


def test_a_replacement_that_fails_puts_the_old_text_back(tmp_path, monkeypatch, capsys):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    run = run_of(tmp_path)
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}

    code, _ = fetch_url(tmp_path, monkeypatch, "--whisper", "--replace-caption", ytdlp=FakeYtDlp(audio=["fail"]))
    assert code == 1
    assert {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    assert replaced(run) == []
    assert "are back as they were" in capsys.readouterr().out


def test_two_replacements_in_the_same_second_never_share_a_folder(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    from datetime import datetime

    now = datetime(2026, 11, 21, 12, 0, 0)
    (run / CAPTION_FILE).write_text("a\n", encoding="utf-8")
    first = caption_guard.archive(run, now)
    (run / CAPTION_FILE).write_text("b\n", encoding="utf-8")
    second = caption_guard.archive(run, now)
    assert first.name == "replaced-2026-11-21T12-00-00" and second.name == "replaced-2026-11-21T12-00-00-2"
    assert caption_guard.archive(run, now) is None  # nothing left to move


# ------------------------------------------------------------------ fetch of a local file


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "media" / "aula.wav"
    path.parent.mkdir()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\0\0" * 1600)
    return path


def fetch_file(tmp_path, monkeypatch, *argv):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    return main(["fetch", *argv])


def test_a_local_file_transcribed_again_is_used_or_refused(tmp_path, monkeypatch, capsys, wav):
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0
    caption = tmp_path / "runs" / "aula" / CAPTION_FILE
    before = caption.read_bytes()
    calls = []
    monkeypatch.setattr(fetch, "transcribe", lambda *a, **k: calls.append(a) or ("0:01 outro texto", 1.0))

    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0  # same file, same model
    assert fetch_file(tmp_path, monkeypatch, str(wav), "--model", "large-v3") == EXIT_CAPTION_EXISTS
    assert calls == [] and caption.read_bytes() == before
    assert "you asked for the model large-v3" in capsys.readouterr().err

    assert fetch_file(tmp_path, monkeypatch, str(wav), "--model", "large-v3", "--replace-caption") == 0
    [kept] = replaced(caption.parent)
    assert (kept / CAPTION_FILE).read_bytes() == before
    assert "outro texto" in caption.read_text(encoding="utf-8")


# ------------------------------------------------------------------ normalize of a .vtt or .srt


def normalize(tmp_path, monkeypatch, *argv):
    monkeypatch.chdir(tmp_path)
    return main(["normalize", *argv, "--force"])


def test_the_same_subtitle_again_is_used_as_it_is(tmp_path, monkeypatch, capsys):
    vtt = tmp_path / "aula.vtt"
    shutil.copy(DATA / "rolling.vtt", vtt)
    assert normalize(tmp_path, monkeypatch, str(vtt)) == 0
    caption = tmp_path / "runs" / "aula" / CAPTION_FILE
    caption.write_text(caption.read_text(encoding="utf-8").replace("# Convertido em: ", "# Convertido em: x"),
                       encoding="utf-8")  # another day's header: the lines are what count
    before = caption.read_bytes()
    assert normalize(tmp_path, monkeypatch, str(vtt)) == 0
    assert caption.read_bytes() == before
    assert replaced(caption.parent) == []


def test_another_subtitle_with_the_same_name_is_refused_then_replaced(tmp_path, monkeypatch, capsys):
    vtt = tmp_path / "aula.vtt"
    shutil.copy(DATA / "rolling.vtt", vtt)
    assert normalize(tmp_path, monkeypatch, str(vtt)) == 0
    caption = tmp_path / "runs" / "aula" / CAPTION_FILE
    before = caption.read_bytes()

    other = tmp_path / "other" / "aula.vtt"
    other.parent.mkdir()
    shutil.copy(DATA / "menu.vtt", other)
    capsys.readouterr()
    assert normalize(tmp_path, monkeypatch, str(other)) == EXIT_CAPTION_EXISTS
    assert caption.read_bytes() == before
    assert "its lines differ from aula.vtt's" in capsys.readouterr().err

    assert normalize(tmp_path, monkeypatch, str(other), "--replace-caption") == 0
    [kept] = replaced(caption.parent)
    assert (kept / CAPTION_FILE).read_bytes() == before
    assert (kept / ANNOTATIONS_FILE).exists()  # the first normalize's, moved with it


def test_a_subtitle_kept_in_a_run_folder_belongs_to_that_run(tmp_path, monkeypatch):
    code, _ = fetch_url(tmp_path, monkeypatch, "--keep-raw")
    assert code == 0
    run = run_of(tmp_path)
    [kept_vtt] = run.glob("*.vtt")
    before = (run / CAPTION_FILE).read_bytes()
    assert normalize(tmp_path, monkeypatch, str(kept_vtt)) == 0
    assert (run / CAPTION_FILE).read_bytes() == before  # the same lines, under fetch's header
    assert (run / ANNOTATIONS_FILE).exists()
    assert not (tmp_path / "runs" / kept_vtt.stem).exists()


# ------------------------------------------------------------------ the menu


def menu(tmp_path, monkeypatch, capsys, lines, ytdlp=None):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_fakes, "VTT", DATA / "menu.vtt")
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp or FakeYtDlp())
    monkeypatch.setattr(cli, "is_interactive", lambda: True)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in lines)))
    code = cli.main([])
    out = capsys.readouterr()
    return code, out.out + out.err, fake


def test_the_menu_asks_before_replacing_and_keeps_by_default(tmp_path, monkeypatch, capsys):
    # The caption, then the same link transcribed: asked, Enter keeps the caption.
    lines = [*LINK, "n", "1", "1", URL, "2", "", "n", "q"]
    _, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert "The run folder already has a text. What now?" in out
    assert "audio" not in fake.calls
    assert read_caption(run_of(tmp_path) / CAPTION_FILE).header[0].startswith(caption_guard.CAPTION_FIRST)
    assert "Next: normalize this run now?" in out.split("What now?")[1]


def test_the_menu_replaces_when_asked(tmp_path, monkeypatch, capsys):
    lines = [*LINK, "n", "1", "1", URL, "2", "2", "n", "q"]
    _, out, fake = menu(tmp_path, monkeypatch, capsys, lines)
    assert fake.calls.count("audio") == 1
    run = run_of(tmp_path)
    assert read_caption(run / CAPTION_FILE).header[0].startswith(caption_guard.SPEECH_FIRST)
    [kept] = replaced(run)
    assert read_caption(kept / CAPTION_FILE).header[0].startswith(caption_guard.CAPTION_FIRST)


# ------------------------------------------------------------------ D-092: passages written twice


def body(*lines):
    return "\n".join(f"{stamp} {text}" for stamp, text in lines)


PASSAGE = ("se eu posso retirar zero vírgula seis se eu tenho que tirar zero vírgula cinco "
           "isso daria mais uma aula de três horas")


def test_a_long_passage_written_again_within_a_minute_is_found():
    [found] = find_repeats(body(
        ("1:00", "Inclusive outro ponto é sobre o percentual da retirada."),
        ("1:06", PASSAGE + "."),
        ("1:20", "Que é modos de aposentadoria."),
        ("1:29", "Porque " + PASSAGE.upper() + ","),
        ("1:40", "Mas isso é papo pra outra hora."),
    ))
    assert (found.start, found.end, found.source_start, found.source_end) == ("1:29", "1:29", "1:06", "1:06")
    assert found.words == len(PASSAGE.split())
    assert found.text == "1:29 Porque " + PASSAGE.upper() + ","  # as written, never changed


def test_a_short_repetition_or_an_old_one_is_what_a_speaker_does():
    words = PASSAGE.split()
    short = " ".join(words[: MIN_WORDS - 1])
    assert find_repeats(body(("1:00", short), ("1:10", short))) == []
    assert find_repeats(body(("1:00", PASSAGE), ("2:01", PASSAGE))) == []
    assert len(find_repeats(body(("1:00", PASSAGE), ("2:00", PASSAGE)))) == 1


def repeating_whisper(model, out=None):
    class Whisper:
        def transcribe(self, audio, **options):
            return iter([
                Segment(66.0, 70.0, PASSAGE),
                Segment(89.0, 93.0, "porque " + PASSAGE),
                Segment(95.0, 96.0, "beleza"),
            ]), Info(duration=100.0)

    return Whisper()


def test_fetch_says_so_and_lists_it_for_review(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    monkeypatch.setattr(fetch, "load_whisper", repeating_whisper)
    assert main(["fetch", URL, "--whisper"]) == 0
    run = run_of(tmp_path)
    assert "1 passage(s) came out twice, at 1:29" in capsys.readouterr().out
    report = (run / NEEDS_REVIEW_DIR / REPEATS_FILE).read_text(encoding="utf-8")
    assert "1:29  repeats 1:06" in report and "  1:29 porque " + PASSAGE in report
    header = read_caption(run / CAPTION_FILE).header
    assert "# Trecho repetido: 1. Ouca o audio antes de citar estes trechos:" in header
    assert any(line.startswith("#   1:29 repete 1:06") for line in header)
    assert [line.text for line in read_caption(run / CAPTION_FILE).lines][1] == "porque " + PASSAGE


def test_no_passage_written_twice_is_said_too_without_a_promise(tmp_path, monkeypatch):
    assert fetch_url(tmp_path, monkeypatch, "--whisper")[0] == 0
    run = run_of(tmp_path)
    assert not (run / NEEDS_REVIEW_DIR).exists()
    assert header_lines([])[0] in read_caption(run / CAPTION_FILE).header
    assert "nao garante que nada faltou" in header_lines([])[0]


def test_a_platform_caption_is_not_searched(tmp_path, monkeypatch):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    assert not any(line.startswith("# Trecho repetido") for line in
                   read_caption(run_of(tmp_path) / CAPTION_FILE).header)


# ------------------------------------------------------------------ D-093: which moment


def test_each_header_says_which_moment_its_timestamps_are():
    meta = Metadata(id="x", title="t")
    assert "do FIM do trecho" in caption_header(meta, URL, "automatica", "pt")
    assert "do FIM do trecho" in file_header("a.vtt", "a")
    speech = speech_header(meta, URL, "pt", "medium")
    assert "do INICIO do trecho" in speech and "FIM" not in speech


# ------------------------------------------------------------------ review of PR #5


def test_another_language_is_another_source(tmp_path, monkeypatch, capsys):
    platform = dict(automatic=("pt", "en"))
    assert fetch_url(tmp_path, monkeypatch, ytdlp=FakeYtDlp(**platform))[0] == 0
    capsys.readouterr()
    assert fetch_url(tmp_path, monkeypatch, "--lang", "pt-BR", ytdlp=FakeYtDlp(**platform))[0] == 0
    code, fake = fetch_url(tmp_path, monkeypatch, "--lang", "en", ytdlp=FakeYtDlp(**platform))
    assert code == EXIT_CAPTION_EXISTS and fake.calls == ["metadata"]
    assert "in 'pt', and you asked for 'en'" in capsys.readouterr().err


def test_an_interrupted_replacement_puts_the_old_text_back(tmp_path, monkeypatch):
    assert fetch_url(tmp_path, monkeypatch)[0] == 0
    run = run_of(tmp_path)
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}

    def interrupted(*args, **kwargs):
        (run / "audio.m4a").write_bytes(b"partial")
        raise KeyboardInterrupt

    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    monkeypatch.setattr(fetch, "step_speech", interrupted)
    with pytest.raises(KeyboardInterrupt):
        main(["fetch", URL, "--whisper", "--replace-caption"])
    assert {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()} == before
    assert replaced(run) == []


def test_a_text_written_while_transcribing_a_file_is_not_written_over(tmp_path, monkeypatch, capsys, wav):
    run = tmp_path / "runs" / "aula"

    def meanwhile(*args, **kwargs):  # another run of the same file finished first, with another model
        run.mkdir(parents=True, exist_ok=True)
        (run / CAPTION_FILE).write_text(
            speech_header(Metadata(id="aula", title="aula"), "", "pt", "small", file_name="aula.wav") + "0:01 a\n",
            encoding="utf-8",
        )
        return "0:01 b", 1.0

    monkeypatch.setattr(fetch, "transcribe", meanwhile)
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == EXIT_CAPTION_EXISTS
    assert "0:01 a" in (run / CAPTION_FILE).read_text(encoding="utf-8")
    assert "you asked for the model medium" in capsys.readouterr().err


def test_two_earlier_stretches_are_named_apart():
    first = " ".join(f"um{i}" for i in range(10))
    second = " ".join(f"dois{i}" for i in range(10))
    [found] = find_repeats(body(("1:00", first + " coisa dita no meio"), ("1:10", second), ("1:30", f"{first} {second}")))
    assert found.sources == (("1:00", "1:00"), ("1:10", "1:10"))
    assert header_lines([found])[1].startswith("#   1:30 repete 1:00 e 1:10 (20 palavras)")


def test_a_refrain_that_overlaps_itself_is_not_a_passage_written_twice():
    assert find_repeats(body(("0:01", "alpha beta gamma delta epsilon zeta " * 4))) == []


# ------------------------------------------------------------------ D-099: a local file's fingerprint


def other_wav(tmp_path, folder):
    path = tmp_path / folder / "aula.wav"
    path.parent.mkdir()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\1\0" * 1600)
    return path


def test_the_header_names_the_file_s_content(tmp_path, monkeypatch, wav):
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0
    existing = caption_guard.read_existing(tmp_path / "runs" / "aula")
    assert existing.fingerprint == caption_guard.fingerprint(wav)
    assert existing.fingerprint.startswith("sha256 ") and existing.fingerprint.endswith(f", {wav.stat().st_size} bytes")
    assert f"# Impressao digital: {existing.fingerprint}" in existing.header


def test_another_file_with_the_same_name_is_refused(tmp_path, monkeypatch, capsys, wav):
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0
    caption = tmp_path / "runs" / "aula" / CAPTION_FILE
    before = caption.read_bytes()
    calls = []
    monkeypatch.setattr(fetch, "transcribe", lambda *a, **k: calls.append(a) or ("0:01 outra aula", 1.0))
    other = other_wav(tmp_path, "outro-curso")

    assert fetch_file(tmp_path, monkeypatch, str(other)) == EXIT_CAPTION_EXISTS
    assert calls == [] and caption.read_bytes() == before
    assert "aula.wav has other content" in capsys.readouterr().err

    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0  # the first file is still the same
    assert calls == []


def test_the_same_content_under_another_folder_is_the_same_file(tmp_path, monkeypatch, wav):
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 0
    copy = tmp_path / "copia" / "aula.wav"
    copy.parent.mkdir()
    shutil.copy(wav, copy)
    monkeypatch.setattr(fetch, "transcribe", lambda *a, **k: pytest.fail("transcribed again"))
    assert fetch_file(tmp_path, monkeypatch, str(copy)) == 0


def test_a_text_without_a_fingerprint_is_compared_by_name_as_before(tmp_path, monkeypatch, capsys, wav):
    run = tmp_path / "runs" / "aula"
    run.mkdir(parents=True)
    (run / CAPTION_FILE).write_text(  # as 0.8.2 wrote it
        speech_header(Metadata(id="aula", title="aula"), "", "pt", "medium", file_name="aula.wav") + "0:01 a\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(fetch, "transcribe", lambda *a, **k: pytest.fail("transcribed again"))
    assert fetch_file(tmp_path, monkeypatch, str(other_wav(tmp_path, "outro-curso"))) == 0
    assert caption_guard.read_existing(run).fingerprint == ""


def test_a_file_changed_while_transcribed_is_not_written(tmp_path, monkeypatch, capsys, wav):
    def rewrite(*args, **kwargs):
        wav.write_bytes(wav.read_bytes() + b"\0\0")
        return "0:01 b", 1.0

    monkeypatch.setattr(fetch, "transcribe", rewrite)
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 1
    assert "changed while it was being transcribed" in capsys.readouterr().err
    assert not (tmp_path / "runs" / "aula" / CAPTION_FILE).exists()


def test_a_file_that_cannot_be_read_is_said(tmp_path, monkeypatch, capsys, wav):
    def unreadable(path):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(caption_guard, "fingerprint", unreadable)
    assert fetch_file(tmp_path, monkeypatch, str(wav)) == 1
    assert f"could not read {wav}" in capsys.readouterr().err
