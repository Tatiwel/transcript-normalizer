"""D-103: a timestamp from 1 hour on is written as a video player shows it,
`1:14:14`, not `74:14`; every reader takes both; `restamp` rewrites an old text."""

import shutil

import pytest

from transcript_normalizer import caption_guard, restamp, stamps
from transcript_normalizer.cli import main
from transcript_normalizer.ingest import clips
from transcript_normalizer.ingest.fetch import segment_line
from transcript_normalizer.ingest.repeats import REPEATS_FILE, find_repeats
from transcript_normalizer.ingest.subtitles import cues_to_lines
from transcript_normalizer.runs import CAPTION_FILE, META_FILE, NEEDS_REVIEW_DIR

from .fetch_fakes import Segment
from .test_caption_guard import DATA, PASSAGE, body, normalize, replaced

# ------------------------------------------------------------------ writing and reading


@pytest.mark.parametrize("seconds, written", [
    (0, "0:00"), (59.9, "0:59"), (2669, "44:29"), (3599, "59:59"),
    (3600, "1:00:00"), (4454, "1:14:14"), (9685.4, "2:41:25"), (36000, "10:00:00"),
])
def test_a_moment_is_written_as_a_player_shows_it(seconds, written):
    assert stamps.clock(seconds) == written
    assert stamps.seconds(written) == int(seconds)


@pytest.mark.parametrize("stamp, value", [
    ("74:14", 4454), ("1:14:14", 4454), ("0:05", 5), ("44:29", 2669),
    ("abc", None), ("1:2", None), ("1:14:1", None), ("", None),
])
def test_both_ways_are_read(stamp, value):
    assert stamps.seconds(stamp) == value


def test_the_old_way_is_rewritten_and_the_new_one_kept():
    assert stamps.rewrite("74:14") == "1:14:14"
    assert stamps.rewrite("1:14:14") == "1:14:14"
    assert stamps.rewrite("44:29") == "44:29"
    assert stamps.rewrite_line("74:14 às 10:30 e 74:00") == "1:14:14 às 10:30 e 74:00"  # only the leading one
    assert stamps.rewrite_line("# 74:14 a header") == "# 74:14 a header"
    assert stamps.same_lines(["74:14 a", "0:05 b"], ["1:14:14 a", "0:05 b"])
    assert not stamps.same_lines(["74:14 a"], ["1:14:15 a"])


def test_every_writer_uses_the_new_way():
    assert segment_line(Segment(4454.7, 4458.0, " Inclusive ")) == "1:14:14 Inclusive"
    assert segment_line(Segment(10.0, 12.0, "a"), offset=4444) == "1:14:14 a"  # a stretch, timed from the file's start
    assert cues_to_lines([(4450.0, 4454.2, ["uma linha"])]) == "1:14:14 uma linha"
    assert clips.stamp(4454) == "1:14:14"


def test_a_passage_after_one_hour_is_found_and_named_the_new_way():
    [found] = find_repeats(body(
        ("1:14:00", "Inclusive outro ponto é sobre o percentual da retirada."),
        ("1:14:06", PASSAGE + "."),
        ("1:14:20", "Que é modos de aposentadoria."),
        ("1:14:29", "Porque " + PASSAGE.upper() + ","),
    ))
    assert (found.start, found.source_start) == ("1:14:29", "1:14:06")
    assert clips.window(found) == (4446 - 15 + 0, 4469 + 10)
    assert clips.file_name(found) == "1-14-29.txt"


def test_a_text_of_the_old_way_is_found_too_across_the_hour():
    [found] = find_repeats(body(
        ("59:50", PASSAGE + "."),
        ("60:10", "Porque " + PASSAGE + ","),
    ))
    assert (found.start, found.source_start) == ("60:10", "59:50")


def test_a_subtitle_converted_the_old_way_is_the_same_subtitle(tmp_path, monkeypatch):
    srt = tmp_path / "aula.srt"
    srt.write_text("1\n01:14:10,000 --> 01:14:14,200\numa linha depois de uma hora\n\n", encoding="utf-8")
    assert normalize(tmp_path, monkeypatch, str(srt)) == 0
    caption = tmp_path / "runs" / "aula" / CAPTION_FILE
    assert "1:14:14 uma linha depois de uma hora" in caption.read_text(encoding="utf-8")
    caption.write_text(caption.read_text(encoding="utf-8").replace("1:14:14 ", "74:14 "), encoding="utf-8")
    before = caption.read_bytes()  # as 0.8.5 wrote it
    assert normalize(tmp_path, monkeypatch, str(srt)) == 0  # not exit 4: the same lines
    assert caption.read_bytes() == before and replaced(caption.parent) == []


# ------------------------------------------------------------------ restamp

HEADER = """\
# Transcricao por reconhecimento de fala local, material bruto
#
# Modelo: faster-whisper medium, idioma pt, vad_filter ativo
# Arquivo: aula1.mp4
# Impressao digital: sha256 50e3, 1551926294 bytes
# Transcrito em: 2026-11-22
#
# Cada linha comeca com o timestamp mm:ss do INICIO do trecho: o
# instante em que a fala comeca.
#
# Trecho repetido: 2. Ouca o audio antes de usar estes trechos:
#   44:29 a 44:33 repete 44:06 e 44:24 a 44:29 (24 palavras); a fala real ali pode ter se perdido.
#   74:29 a 74:33 repete 74:06 (15 palavras); a fala real ali pode ter se perdido.
"""
OLD_BODY = "44:29 antes da hora\n59:59 quase\n60:00 uma hora\n74:14 às 10:30 e 74:00 ditos assim\n161:25 fim\n"
NEW_BODY = "44:29 antes da hora\n59:59 quase\n1:00:00 uma hora\n1:14:14 às 10:30 e 74:00 ditos assim\n2:41:25 fim\n"
REPEATS = """\
Passages the local transcription wrote twice.

74:29 to 74:33  repeats 74:06  (15 words)
  74:29 porque às 10:30 aqui
"""
CLIP = """\
The stretch 73:51 to 74:43, transcribed again on its own.
legenda.txt wrote 74:29 to 74:33 twice: it repeats 74:06 (15 words), and what was said there may be lost.

File: aula1.mp4, sha256 50e3, 1551926294 bytes
73:51 o que foi dito
74:30 às 10:30
"""


@pytest.fixture
def old_run(tmp_path):
    run = tmp_path / "runs" / "aula1"
    stretches = run / NEEDS_REVIEW_DIR / clips.CLIPS_DIR
    stretches.mkdir(parents=True)
    (run / CAPTION_FILE).write_text(HEADER + OLD_BODY, encoding="utf-8")
    (run / META_FILE).write_text("id: aula1\n", encoding="utf-8")
    (run / NEEDS_REVIEW_DIR / REPEATS_FILE).write_text(REPEATS, encoding="utf-8")
    (stretches / "74-29.txt").write_text(CLIP, encoding="utf-8")
    (stretches / "74-29-2.txt").write_text(CLIP, encoding="utf-8")
    (stretches / "44-29.txt").write_text("The stretch 43:51 to 44:43, transcribed again on its own.\n",
                                         encoding="utf-8")
    return run


def test_restamp_rewrites_the_times_and_no_word(old_run, capsys):
    before = caption_guard.read_existing(old_run)
    assert main(["restamp", str(old_run)]) == 0
    text = (old_run / CAPTION_FILE).read_text(encoding="utf-8")
    assert text.endswith(NEW_BODY)
    assert "#   44:29 a 44:33 repete 44:06 e 44:24 a 44:29 (24 palavras)" in text
    assert "#   1:14:29 a 1:14:33 repete 1:14:06 (15 palavras)" in text
    assert "# Impressao digital: sha256 50e3, 1551926294 bytes" in text
    assert ("# Cada linha comeca com o timestamp do INICIO do trecho: o\n"
            "# instante em que a fala comeca.\n"
            "# Antes de 1 hora, m:ss (44:29); depois, h:mm:ss (1:14:14).\n#\n") in text
    after = caption_guard.read_existing(old_run)
    assert (after.kind, after.model, after.lang, after.file_name, after.fingerprint) == (
        before.kind, before.model, before.lang, before.file_name, before.fingerprint)  # D-091 sees the same source
    assert (old_run / META_FILE).read_text(encoding="utf-8") == "id: aula1\n"

    review = old_run / NEEDS_REVIEW_DIR
    assert (review / REPEATS_FILE).read_text(encoding="utf-8") == REPEATS.replace(
        "74:29 to 74:33  repeats 74:06", "1:14:29 to 1:14:33  repeats 1:14:06").replace(
        "  74:29 porque às 10:30", "  1:14:29 porque às 10:30")
    stretches = review / clips.CLIPS_DIR
    assert sorted(p.name for p in stretches.iterdir()) == ["1-14-29-2.txt", "1-14-29.txt", "44-29.txt"]
    clip = (stretches / "1-14-29.txt").read_text(encoding="utf-8")
    assert clip.startswith("The stretch 1:13:51 to 1:14:43, transcribed")
    assert "legenda.txt wrote 1:14:29 to 1:14:33 twice: it repeats 1:14:06 (15 words)" in clip
    assert "1:13:51 o que foi dito\n1:14:30 às 10:30\n" in clip

    [kept] = replaced(old_run)
    assert (kept / CAPTION_FILE).read_text(encoding="utf-8") == HEADER + OLD_BODY
    assert (kept / NEEDS_REVIEW_DIR / clips.CLIPS_DIR / "74-29.txt").read_text(encoding="utf-8") == CLIP
    out = capsys.readouterr().out
    assert "3 line(s) rewritten" in out  # 60:00, 74:14, 161:25


def test_restamp_twice_does_nothing_the_second_time(old_run, capsys):
    assert main(["restamp", str(old_run / CAPTION_FILE)]) == 0
    capsys.readouterr()
    assert main(["restamp", str(old_run)]) == 0
    assert "nothing to do" in capsys.readouterr().out
    assert len(replaced(old_run)) == 1


def test_what_normalize_made_waits_to_be_made_again(old_run, capsys):
    (old_run / "normalized.txt").write_text("74:14  normalized\n", encoding="utf-8")
    (old_run / NEEDS_REVIEW_DIR / "pending.txt").write_text("74:14 x\n", encoding="utf-8")
    assert main(["restamp", str(old_run)]) == 0
    assert not (old_run / "normalized.txt").exists()
    assert not (old_run / NEEDS_REVIEW_DIR / "pending.txt").exists()
    out = capsys.readouterr().out
    assert "normalize again" in out and "normalized.txt" in out


def test_a_restamp_that_fails_leaves_the_run_as_it_was(old_run, monkeypatch):
    files = {p.relative_to(old_run): p.read_bytes() for p in old_run.rglob("*") if p.is_file()}

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(restamp.shutil, "copy2", broken)
    with pytest.raises(OSError):
        main(["restamp", str(old_run)])
    assert {p.relative_to(old_run): p.read_bytes() for p in old_run.rglob("*") if p.is_file()} == files


def test_restamp_needs_a_run(tmp_path, capsys):
    assert main(["restamp", str(tmp_path)]) == 1
    assert "is not there" in capsys.readouterr().err
    other = tmp_path / "notes.txt"
    other.write_text("74:14 a\n", encoding="utf-8")
    assert main(["restamp", str(other)]) == 1
    assert "is not a legenda.txt" in capsys.readouterr().err


def test_a_text_of_the_new_way_is_left_alone(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    shutil.copy(DATA / "rolling.legenda.txt", run / CAPTION_FILE)
    assert restamp.plan(run) == {}
