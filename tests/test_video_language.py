"""D-080: without --lang, fetch takes the video's own language."""

import pytest

from transcript_normalizer.cli import main
from transcript_normalizer.ingest import Metadata, fetch

from . import fetch_fakes
from .fetch_fakes import URL, FakeYtDlp


@pytest.mark.parametrize(
    "language, manual, automatic, expected",
    [
        # yt-dlp's `language` wins over everything else.
        ("en", ("pt",), ("en-orig", "pt-orig"), ("en", False)),
        ("es", (), ("en", "es"), ("es", False)),
        # spelt as its `-orig` track spells it
        ("pt-BR", (), ("en", "pt-BR-orig"), ("pt-BR", False)),
        # a regional code with only the base language's tracks: the base
        ("pt-BR", ("pt",), ("en",), ("pt", False)),
        # no `language`: the only `-orig` track
        ("", ("pt", "en"), ("de", "en-orig"), ("en", False)),
        # several `-orig` tracks (dubs): the only manual track
        ("", ("es",), ("en-orig", "pt-orig"), ("es", False)),
        # no `-orig` track: the only manual track
        ("", ("fr",), ("en", "fr"), ("fr", False)),
        # neither: the default, and a guess
        ("", ("fr", "en"), ("en", "fr"), (fetch.DEFAULT_LANG, True)),
        ("", (), ("en-orig", "pt-orig"), (fetch.DEFAULT_LANG, True)),
        ("", (), (), (fetch.DEFAULT_LANG, True)),
    ],
)
def test_the_video_language(language, manual, automatic, expected):
    meta = Metadata(language=language, manual_captions=manual, automatic_captions=automatic)
    assert fetch.video_language(meta) == expected


def fetched(tmp_path, monkeypatch, fake, *extra):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, fake)
    return main(["fetch", URL, *extra])


def test_an_english_video_gets_its_english_caption(tmp_path, monkeypatch, capsys):
    fake = FakeYtDlp(language="en", automatic=("en-orig", "pt"))
    assert fetched(tmp_path, monkeypatch, fake) == 0
    assert fake.downloads == [("writeautomaticsub", "en-orig")]
    assert "unknown" not in capsys.readouterr().out


def test_lang_given_wins(tmp_path, monkeypatch):
    fake = FakeYtDlp(language="en", automatic=("en-orig", "pt"))
    assert fetched(tmp_path, monkeypatch, fake, "--lang", "pt") == 0
    assert fake.downloads == [("writeautomaticsub", "pt")]


def test_the_only_original_when_the_site_names_no_language(tmp_path, monkeypatch):
    fake = FakeYtDlp(manual=("pt",), automatic=("en-orig", "pt"))
    assert fetched(tmp_path, monkeypatch, fake) == 0
    assert fake.downloads == [("writeautomaticsub", "en-orig")]


def test_the_only_manual_track_when_there_is_no_original(tmp_path, monkeypatch):
    fake = FakeYtDlp(manual=("es",), automatic=("es", "pt"))
    assert fetched(tmp_path, monkeypatch, fake) == 0
    assert fake.downloads == [("writesubtitles", "es")]


def test_otherwise_the_default_with_one_line_saying_so(tmp_path, monkeypatch, capsys):
    fake = FakeYtDlp(automatic=("en", "pt"))
    assert fetched(tmp_path, monkeypatch, fake) == 0
    assert fake.downloads == [("writeautomaticsub", "pt")]
    lines = [l for l in capsys.readouterr().out.splitlines() if "language is unknown" in l]
    assert len(lines) == 1 and "'pt'" in lines[0]


def test_speech_recognition_gets_the_base_language(tmp_path, monkeypatch):
    """faster-whisper takes `en`, not `en-US`."""
    fake = FakeYtDlp(language="en-US", has_caption=False)
    seen = []

    class Recording(fetch_fakes.FakeWhisper):
        def transcribe(self, audio, **options):
            seen.append(options["language"])
            return super().transcribe(audio, **options)

    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, fake)
    monkeypatch.setattr(fetch, "load_whisper", Recording)
    assert main(["fetch", URL]) == 0
    assert seen == ["en"]
