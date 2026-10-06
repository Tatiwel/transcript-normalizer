"""D-038: fetch takes a local audio or video file as well as a url."""

import wave

import pytest
import yaml

from transcript_normalizer.catalog import list_runs
from transcript_normalizer.cli import main
from transcript_normalizer.core.text import read_caption
from transcript_normalizer.ingest import fetch
from transcript_normalizer.runs import CAPTION_FILE, META_FILE

from . import fetch_fakes


class NoYtDlp:
    """A local file must never reach yt-dlp."""

    def open(self, params):
        raise AssertionError(f"yt-dlp was called for a local file: {params}")


@pytest.fixture
def wav(tmp_path):
    """A tenth of a second of 16 kHz silence: a real file, small enough to commit to nothing."""
    path = tmp_path / "media" / "entrevista-cemig.wav"
    path.parent.mkdir()
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\0\0" * 1600)
    return path


def fetched(tmp_path, monkeypatch, *argv):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, NoYtDlp())
    return main(["fetch", *argv])


def test_a_local_file_is_transcribed_into_runs_by_its_stem(tmp_path, monkeypatch, wav):
    assert fetched(tmp_path, monkeypatch, str(wav)) == 0

    run = tmp_path / "runs" / "entrevista-cemig"  # D-018 rule 3
    transcript = read_caption(run / CAPTION_FILE)
    assert transcript.header_field("Arquivo") == "entrevista-cemig.wav"
    assert transcript.header_field("URL") == ""
    assert transcript.header_field("Etapa") == "2, reconhecimento de fala local (arquivo local)"
    assert [l.text for l in transcript.lines] == ["o que que tá acontecendo com a SEMIG", "o dividendo caiu"]

    meta = yaml.safe_load((run / META_FILE).read_text(encoding="utf-8"))
    assert (meta["source"], meta["path"]) == ("file", str(wav.resolve()))
    assert (meta["step"], meta["url"]) == (2, None)


def test_a_relative_path_is_recorded_absolute(tmp_path, monkeypatch, wav):
    monkeypatch.chdir(wav.parent)
    fetch_fakes.install(monkeypatch, fetch, NoYtDlp())
    assert main(["fetch", wav.name, "--out", str(tmp_path / "out")]) == 0
    meta = yaml.safe_load((tmp_path / "out" / META_FILE).read_text(encoding="utf-8"))
    assert meta["path"] == str(wav.resolve())


def test_the_run_is_listed_by_its_stem(tmp_path, monkeypatch, wav):
    fetched(tmp_path, monkeypatch, str(wav))
    assert [r.id for r in list_runs(tmp_path / "runs")] == ["entrevista-cemig"]


def test_caption_only_makes_no_sense_for_a_file(tmp_path, monkeypatch, wav, capsys):
    assert fetched(tmp_path, monkeypatch, str(wav), "--caption-only") == 1
    assert "no platform caption" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_a_path_that_is_neither_a_file_nor_a_url_is_a_clear_error(tmp_path, monkeypatch, capsys):
    assert fetched(tmp_path, monkeypatch, "nao-existe.mp4") == 1
    assert "no such file, and not a url" in capsys.readouterr().err


def test_a_url_run_records_its_source_too(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch)
    assert main(["fetch", fetch_fakes.URL]) == 0
    meta = yaml.safe_load((tmp_path / "runs" / fetch_fakes.VIDEO_ID / META_FILE).read_text(encoding="utf-8"))
    assert meta["source"] == "url" and "path" not in meta
