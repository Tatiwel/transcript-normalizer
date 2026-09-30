"""D-045: `<lang>-orig`, then a manual `<lang>`, then an automatic `<lang>`."""

import pytest
import yaml

from transcript_normalizer.cli import main
from transcript_normalizer.core.text import read_caption
from transcript_normalizer.ingest import Metadata, fetch
from transcript_normalizer.runs import CAPTION_FILE, META_FILE

from . import fetch_fakes
from .fetch_fakes import URL, VIDEO_ID, FakeYtDlp

# What 4tTmY8Buask offered, cut down: the spoken language as `pt-orig`, and
# `pt` among dozens of machine translations.
TRANSLATED = ("de", "en", "es", "fr", "pt", "pt-orig", "zh-Hans")


@pytest.mark.parametrize(
    "manual, automatic, expected",
    [
        ((), TRANSLATED, ("pt-orig", "automatica original")),
        (("pt",), TRANSLATED, ("pt-orig", "automatica original")),
        (("pt",), ("en", "pt"), ("pt", "manual")),
        ((), ("en", "pt"), ("pt", "automatica")),
        ((), ("en-orig", "pt"), ("pt", "automatica")),  # another language's original
        ((), ("en-orig", "pt-BR-orig", "pt"), ("pt-BR-orig", "automatica original")),
        (("pt-BR",), ("en-orig", "pt"), ("pt-BR", "manual")),
        ((), ("en-orig",), ("", "")),
    ],
)
def test_the_order_of_tracks(manual, automatic, expected):
    meta = Metadata(manual_captions=manual, automatic_captions=automatic)
    assert fetch.choose_language(meta, "pt") == expected


def fetched(tmp_path, monkeypatch, ytdlp):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, ytdlp)
    assert main(["fetch", URL]) == 0
    run = tmp_path / "runs" / VIDEO_ID
    header = read_caption(run / CAPTION_FILE).header_field("Origem da legenda")
    meta = yaml.safe_load((run / META_FILE).read_text(encoding="utf-8"))
    return header, meta


def test_the_original_track_is_downloaded_and_recorded(tmp_path, monkeypatch):
    fake = FakeYtDlp(manual=("pt",), automatic=TRANSLATED)
    header, meta = fetched(tmp_path, monkeypatch, fake)
    assert fake.downloads == [("--write-auto-subs", "pt-orig")]
    assert header == "automatica original (pt-orig)"
    assert (meta["caption_track"], meta["caption_source"]) == ("pt-orig", "automatica original")
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_with_no_original_a_manual_track_wins(tmp_path, monkeypatch):
    fake = FakeYtDlp(manual=("pt",), automatic=("pt",))
    header, meta = fetched(tmp_path, monkeypatch, fake)
    assert fake.downloads == [("--write-subs", "pt")]
    assert header == "manual (pt)"
    assert (meta["caption_track"], meta["caption_source"]) == ("pt", "manual")


def test_speech_recognition_records_no_track(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    assert main(["fetch", URL, "--whisper"]) == 0
    meta = yaml.safe_load((tmp_path / "runs" / VIDEO_ID / META_FILE).read_text(encoding="utf-8"))
    assert "caption_track" not in meta
