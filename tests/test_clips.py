"""D-101: the stretch around a passage written twice, transcribed again on its
own, beside the warning; and `fetch FILE --recheck` for a text already there."""

import struct
import wave

import numpy as np
import pytest

from transcript_normalizer import caption_guard
from transcript_normalizer.caption_guard import EXIT_CAPTION_EXISTS
from transcript_normalizer.cli import main
from transcript_normalizer.ingest import clips, fetch
from transcript_normalizer.ingest.header import Metadata, caption_header, speech_header
from transcript_normalizer.ingest.repeats import REPEATS_FILE, Repeat
from transcript_normalizer.runs import CAPTION_FILE, NEEDS_REVIEW_DIR

from . import fetch_fakes
from .fetch_fakes import FakeYtDlp, Info, Segment
from .test_caption_guard import PASSAGE

# ------------------------------------------------------------------ the window


def test_the_window_of_the_lesson_that_motivated_it():
    # D-092's lesson: 44:29 to 44:33 repeats 44:06 and 44:24 to 44:29; what was
    # lost was said between 44:02 and 44:06, before the first copy.
    lesson = Repeat(start="44:29", end="44:33", source_start="44:06", source_end="44:29", words=24,
                    text="", sources=(("44:06", "44:06"), ("44:24", "44:29")))
    start, end = clips.window(lesson)
    assert (clips.stamp(start), clips.stamp(end)) == ("43:51", "44:43")
    assert start <= 44 * 60 + 2
    assert clips.file_name(lesson) == "44-29.txt"


def test_the_window_does_not_start_before_the_file():
    early = Repeat(start="0:20", end="0:22", source_start="0:05", source_end="0:08", words=20, text="")
    assert clips.window(early) == (0, 32)


# ------------------------------------------------------------------ decoding a stretch


def tone_wav(path, rate, seconds, channels=1):
    """Each second holds its own constant value, so a stretch shows where it came from."""
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        for second in range(seconds):
            value = 1000 * (second + 1)
            out.writeframes(struct.pack(f"<{channels}h", *([value] * channels)) * rate)
    return path


@pytest.mark.parametrize("rate, channels", [(16000, 1), (44100, 2), (8000, 1)])
def test_only_the_stretch_is_decoded_at_16_khz(tmp_path, rate, channels):
    path = tone_wav(tmp_path / "t.wav", rate, 10, channels)
    samples = clips.decode_window(path, 3, 5)
    assert samples.dtype == np.float32
    assert abs(len(samples) - 2 * clips.SAMPLE_RATE) <= 32
    middle = samples[len(samples) // 4: 3 * len(samples) // 4]
    first, second = middle[: len(middle) // 2], middle[len(middle) // 2:]
    assert np.median(first) == pytest.approx(4000 / 32768, abs=0.01)  # second 3 holds 4000
    assert np.median(second) == pytest.approx(5000 / 32768, abs=0.01)


def test_a_stretch_of_an_mp4_with_video_is_the_right_stretch(tmp_path):
    # The lessons are mp4 files: AAC audio beside a video stream. Second n holds
    # a tone of 200 + 100 n Hz, so the stretch's own frequencies say where it is.
    av = pytest.importorskip("av")
    path, rate = str(tmp_path / "aula.mp4"), 44100
    with av.open(path, "w") as container:
        video = container.add_stream("mpeg4", rate=10)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        audio = container.add_stream("aac", rate=rate)
        audio.layout = "stereo"
        blank = np.zeros((48, 64, 3), dtype=np.uint8)
        for _ in range(100):
            for packet in video.encode(av.VideoFrame.from_ndarray(blank, format="rgb24")):
                container.mux(packet)
        pts = 0
        for second in range(10):
            tone = (0.3 * np.sin(2 * np.pi * (200 + 100 * second) * np.arange(rate) / rate)).astype(np.float32)
            for at in range(0, rate, 1024):
                chunk = tone[at:at + 1024]
                frame = av.AudioFrame.from_ndarray(np.vstack([chunk, chunk]), format="fltp", layout="stereo")
                frame.sample_rate, frame.pts = rate, pts
                pts += len(chunk)
                for packet in audio.encode(frame):
                    container.mux(packet)
        for stream in (audio, video):
            for packet in stream.encode(None):
                container.mux(packet)
    samples = clips.decode_window(path, 6, 8)
    assert len(samples) == 2 * clips.SAMPLE_RATE
    found = []
    for second in (samples[:16000], samples[16000:]):
        spectrum = np.abs(np.fft.rfft(second[2000:14000]))
        found.append(round(np.fft.rfftfreq(12000, 1 / 16000)[spectrum.argmax()]))
    assert found == [800, 900]


def dominant(samples):
    spectrum = np.abs(np.fft.rfft(samples[2000:14000]))
    return round(np.fft.rfftfreq(12000, 1 / 16000)[spectrum.argmax()])


@pytest.mark.parametrize("suffix", [".mkv", ".mp4"])
def test_a_file_whose_audio_starts_late_is_timed_from_its_audio(tmp_path, suffix):
    # A whole file's transcription counts from its first audio sample. Here the
    # audio starts 5 s into the container; second n of it holds 200 + 100 n Hz.
    av = pytest.importorskip("av")
    decode_audio = pytest.importorskip("faster_whisper").decode_audio
    path, rate = str(tmp_path / f"late{suffix}"), 44100
    with av.open(path, "w") as container:
        audio = container.add_stream("aac", rate=rate)
        audio.layout = "mono"
        pts = 5 * rate
        for second in range(8):
            tone = (0.3 * np.sin(2 * np.pi * (200 + 100 * second) * np.arange(rate) / rate)).astype(np.float32)
            for at in range(0, rate, 1024):
                chunk = tone[at:at + 1024]
                frame = av.AudioFrame.from_ndarray(chunk[None, :], format="fltp", layout="mono")
                frame.sample_rate, frame.pts = rate, pts
                pts += len(chunk)
                for packet in audio.encode(frame):
                    container.mux(packet)
        for packet in audio.encode(None):
            container.mux(packet)
    whole = decode_audio(path)
    stretch = clips.decode_window(path, 2, 4)
    assert dominant(whole[2 * 16000:3 * 16000]) == 400
    assert [dominant(stretch[:16000]), dominant(stretch[16000:])] == [400, 500]


def two(start, sources):
    return [Repeat(start=start, end=start, source_start=s, source_end=s, words=20, text="") for s in sources]


def test_two_passages_on_one_line_get_two_files(tmp_path):
    warnings = []
    written = clips.write_clips(two("1:00", ["0:10", "0:20"]), tmp_path / "m.wav", tmp_path, lambda m, a, b: "",
                                "medium", "pt", source="m.wav", origin=clips.SAME_RUN, warn=warnings.append)
    assert [p.name for p in written] == ["1-00.txt", "1-00-2.txt"]
    assert "0:10" in written[0].read_text(encoding="utf-8") and "0:20" in written[1].read_text(encoding="utf-8")


def test_a_folder_that_cannot_be_written_is_said(tmp_path):
    review = tmp_path / "needs-review"
    review.write_text("a file where the folder would be", encoding="utf-8")
    warnings = []
    assert clips.write_clips(two("1:00", ["0:10"]), tmp_path / "m.wav", review, lambda m, a, b: "",
                             "medium", "pt", source="m.wav", origin=clips.SAME_RUN, warn=warnings.append) == []
    assert warnings and warnings[0].startswith("could not write")


# ------------------------------------------------------------------ after a transcription


def repeating_then_right(calls):
    """A whole file writes PASSAGE twice; its stretch, transcribed alone, has what was said."""

    def whisper(model, out=None):
        class Whisper:
            def transcribe(self, audio, **options):
                assert options["vad_filter"] is True and options["condition_on_previous_text"] is False
                if isinstance(audio, str):
                    return iter([
                        Segment(66.0, 70.0, PASSAGE),
                        Segment(89.0, 93.0, "porque " + PASSAGE),
                        Segment(95.0, 96.0, "beleza"),
                    ]), Info(duration=100.0)
                calls.append(len(audio))
                return iter([Segment(10.0, 14.0, "o que foi dito de verdade")]), Info(duration=52.0)

        return Whisper()

    return whisper


@pytest.fixture
def media(tmp_path, monkeypatch):
    path = tmp_path / "media" / "aula.wav"
    path.parent.mkdir()
    tone_wav(path, 16000, 2)
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    monkeypatch.setattr(clips, "decode_window", lambda path, start, end: np.zeros(int((end - start) * 16000),
                                                                                 dtype=np.float32))
    return path


def run(tmp_path):
    return tmp_path / "runs" / "aula"


def test_each_passage_s_stretch_is_transcribed_again_beside_the_warning(tmp_path, monkeypatch, capsys, media):
    calls = []
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right(calls))
    assert main(["fetch", str(media)]) == 0
    clip = run(tmp_path) / NEEDS_REVIEW_DIR / clips.CLIPS_DIR / "1-29.txt"
    text = clip.read_text(encoding="utf-8")
    assert calls == [(99 - 51) * 16000]  # 0:51 (1:06 less 15) to 1:39 (1:29 plus 10)
    assert text.startswith("The stretch 0:51 to 1:39, transcribed again on its own.")
    assert "1:01 o que foi dito de verdade" in text  # 10 s into the stretch, timed from the file's start
    assert "help for listening" in text and clips.SAME_RUN in text
    assert caption_guard.fingerprint(media) in text
    caption = (run(tmp_path) / CAPTION_FILE).read_text(encoding="utf-8")
    assert "o que foi dito de verdade" not in caption  # legenda.txt is not changed
    assert "(help for listening; legenda.txt not changed)" in capsys.readouterr().out


def test_a_stretch_that_fails_is_said_and_the_text_is_still_there(tmp_path, monkeypatch, capsys, media):
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right([]))

    def broken(path, start, end):
        raise RuntimeError("decoder said no")

    monkeypatch.setattr(clips, "decode_window", broken)
    assert main(["fetch", str(media)]) == 0
    assert "could not transcribe 0:51 to 1:39 again: decoder said no" in capsys.readouterr().out
    assert (run(tmp_path) / CAPTION_FILE).exists()
    assert not list((run(tmp_path) / NEEDS_REVIEW_DIR / clips.CLIPS_DIR).glob("*.txt"))


def test_no_passage_no_stretch(tmp_path, monkeypatch, media):
    assert main(["fetch", str(media)]) == 0  # the default fake writes nothing twice
    assert not (run(tmp_path) / NEEDS_REVIEW_DIR / clips.CLIPS_DIR).exists()


# ------------------------------------------------------------------ fetch FILE --recheck


def test_recheck_of_a_text_already_there(tmp_path, monkeypatch, capsys, media):
    calls = []
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right(calls))
    assert main(["fetch", str(media)]) == 0
    review = run(tmp_path) / NEEDS_REVIEW_DIR
    caption = (run(tmp_path) / CAPTION_FILE).read_bytes()
    (review / clips.CLIPS_DIR / "1-29.txt").unlink()
    capsys.readouterr()

    assert main(["fetch", str(media), "--recheck"]) == 0
    assert (run(tmp_path) / CAPTION_FILE).read_bytes() == caption
    text = (review / clips.CLIPS_DIR / "1-29.txt").read_text(encoding="utf-8")
    assert clips.CHECKED in text and "1:01 o que foi dito de verdade" in text
    assert "1 passage(s) came out twice, at 1:29" in capsys.readouterr().out
    assert len(calls) == 2


def test_recheck_with_another_file_is_refused(tmp_path, monkeypatch, capsys, media):
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right([]))
    assert main(["fetch", str(media)]) == 0
    other = tmp_path / "outro-curso" / "aula.wav"
    other.parent.mkdir()
    tone_wav(other, 16000, 3)
    before = sorted(p.relative_to(tmp_path) for p in run(tmp_path).rglob("*"))
    capsys.readouterr()
    assert main(["fetch", str(other), "--recheck"]) == EXIT_CAPTION_EXISTS
    assert "has other content" in capsys.readouterr().err
    assert sorted(p.relative_to(tmp_path) for p in run(tmp_path).rglob("*")) == before


def old_text(tmp_path, body, file_name="aula.wav"):
    """A legenda.txt as 0.8.1 wrote it: no fingerprint, no search for passages."""
    folder = run(tmp_path)
    folder.mkdir(parents=True)
    (folder / CAPTION_FILE).write_text(
        speech_header(Metadata(id="aula", title="aula"), "", "pt", "medium", file_name=file_name) + body,
        encoding="utf-8",
    )
    return folder / CAPTION_FILE


OLD_BODY = f"1:06 {PASSAGE}\n1:29 porque {PASSAGE}\n1:35 beleza\n"


def test_a_file_changed_during_the_recheck_keeps_no_stretch(tmp_path, monkeypatch, capsys, media):
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right([]))
    assert main(["fetch", str(media)]) == 0
    clip = run(tmp_path) / NEEDS_REVIEW_DIR / clips.CLIPS_DIR / "1-29.txt"

    def and_change(path, start, end):
        media.write_bytes(media.read_bytes() + b"\0\0")
        return np.zeros(16000, dtype=np.float32)

    monkeypatch.setattr(clips, "decode_window", and_change)
    capsys.readouterr()
    assert main(["fetch", str(media), "--recheck"]) == 1
    assert "changed while its stretches were transcribed again" in capsys.readouterr().out
    assert not clip.exists()


def test_an_old_text_is_rechecked_only_when_asked_and_says_so(tmp_path, monkeypatch, capsys, media):
    monkeypatch.setattr(fetch, "load_whisper", repeating_then_right([]))
    caption = old_text(tmp_path, OLD_BODY)
    before = caption.read_bytes()
    assert main(["fetch", str(media), "--recheck"]) == 1
    assert "has no fingerprint" in capsys.readouterr().err
    assert not (run(tmp_path) / NEEDS_REVIEW_DIR).exists()

    assert main(["fetch", str(media), "--recheck", "--unverified-source"]) == 0
    review = run(tmp_path) / NEEDS_REVIEW_DIR
    text = (review / clips.CLIPS_DIR / "1-29.txt").read_text(encoding="utf-8")
    assert clips.UNCHECKED in text and "NOT checked" in text
    assert (review / REPEATS_FILE).exists()  # 0.8.1 wrote none
    assert caption.read_bytes() == before


def test_an_old_text_of_another_file_name_is_refused_even_so(tmp_path, monkeypatch, capsys, media):
    old_text(tmp_path, OLD_BODY, file_name="outra.mp4")
    assert main(["fetch", str(media), "--recheck", "--unverified-source"]) == EXIT_CAPTION_EXISTS
    assert "not of aula.wav" in capsys.readouterr().err


def test_recheck_with_nothing_written_twice_says_so_and_clears_old_stretches(tmp_path, monkeypatch, capsys, media):
    old_text(tmp_path, "0:01 uma linha\n0:05 outra linha\n")
    stale = run(tmp_path) / NEEDS_REVIEW_DIR / clips.CLIPS_DIR
    stale.mkdir(parents=True)
    (stale / "9-99.txt").write_text("old", encoding="utf-8")
    assert main(["fetch", str(media), "--recheck", "--unverified-source"]) == 0
    assert "nenhum encontrado" in capsys.readouterr().out
    assert not stale.exists()


def test_recheck_needs_a_local_transcription(tmp_path, monkeypatch, capsys, media):
    assert main(["fetch", "https://www.youtube.com/watch?v=abc", "--recheck"]) == 2
    assert main(["fetch", str(media), "--recheck"]) == 1
    assert "has no legenda.txt" in capsys.readouterr().err
    folder = run(tmp_path)
    folder.mkdir(parents=True)
    (folder / CAPTION_FILE).write_text(
        caption_header(Metadata(id="aula", title="aula"), "https://example.invalid/v", "manual", "pt")
        + "0:01 a\n", encoding="utf-8")
    assert main(["fetch", str(media), "--recheck"]) == 1
    assert "only a local transcription" in capsys.readouterr().err
