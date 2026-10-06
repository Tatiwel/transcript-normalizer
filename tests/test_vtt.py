"""WebVTT is converted in Python, so the caption path needs no ffmpeg."""

from pathlib import Path

from transcript_normalizer import parse_caption
from transcript_normalizer.ingest import Metadata, caption_header, subtitle_to_lines
from transcript_normalizer.ingest import fetch, vtt_to_lines

DATA = Path(__file__).resolve().parent / "data"
VTT = DATA / "rolling.vtt"
EXPECTED = DATA / "rolling.legenda.txt"

SYNTHETIC = Metadata(
    id="synthetic",
    title="Video sintetico de teste",
    channel="Canal de Teste",
    published="20260101",
)
URL = "https://example.invalid/synthetic"
DOWNLOADED = "2026-01-02"


def test_a_vtt_becomes_the_expected_legenda_txt():
    written = (
        caption_header(SYNTHETIC, URL, source="automatica", lang="pt", downloaded=DOWNLOADED)
        + vtt_to_lines(VTT.read_text(encoding="utf-8"))
        + "\n"
    )
    assert written == EXPECTED.read_text(encoding="utf-8")


def test_the_converted_file_is_readable_by_the_core():
    transcript = parse_caption(EXPECTED.read_text(encoding="utf-8"))
    assert [l.timestamp for l in transcript.lines] == ["0:03", "0:06", "0:09", "1:07"]
    assert transcript.lines[1].text == "SEMIG? Bateu aí 10:17,"


def test_rolling_repetition_is_dropped_but_real_repetition_is_kept():
    lines = vtt_to_lines(VTT.read_text(encoding="utf-8")).splitlines()
    # The first line rolls through three consecutive cues and is emitted once...
    assert lines[0] == "0:03 o que que tá acontecendo com"
    # ...but the same words a minute later are a real repetition, not a roll.
    assert lines[-1] == "1:07 o que que tá acontecendo com"


def test_cue_tags_settings_and_entities_are_stripped():
    text = vtt_to_lines(VTT.read_text(encoding="utf-8"))
    assert "<c>" not in text and "align:start" not in text
    assert "&amp;" not in text and "&" in text
    assert "WEBVTT" not in text and "Kind: captions" not in text


def test_the_dispatcher_picks_the_parser_from_the_suffix():
    vtt = VTT.read_text(encoding="utf-8")
    assert subtitle_to_lines(vtt, ".vtt") == vtt_to_lines(vtt)

    srt = "1\n00:00:01,000 --> 00:00:03,000\numa linha\n"
    assert subtitle_to_lines(srt, ".srt") == "0:03 uma linha"


def test_the_caption_download_does_not_ask_ytdlp_to_convert(tmp_path):
    # A conversion flag would hand the job to ffmpeg; the caption path must not.
    params = fetch.caption_params("pt", "automatica", tmp_path)
    assert not [k for k in params if "convert" in k or k == "postprocessors"]
    assert params["writeautomaticsub"] is True and params["writesubtitles"] is False
    assert params["subtitleslangs"] == ["pt"] and params["skip_download"] is True
    assert fetch.caption_params("pt", "manual", tmp_path)["writesubtitles"] is True


def test_a_downloaded_vtt_is_picked_up_and_renamed(tmp_path, monkeypatch):
    """yt-dlp writes legenda.<lang>.vtt; the fixed name is what gets converted."""
    class YoutubeDL:
        def __init__(self, params):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, urls):
            (tmp_path / "legenda.pt.vtt").write_text(VTT.read_text("utf-8"), "utf-8")
            return 0

    monkeypatch.setattr(fetch, "youtube_dl", YoutubeDL)
    found, retries = fetch.download_caption(URL, "pt", "automatica", tmp_path)

    assert (found, retries) == (tmp_path / "legenda.vtt", 0)
    assert not (tmp_path / "legenda.pt.vtt").exists()
    assert subtitle_to_lines(found.read_text("utf-8"), found.suffix).startswith("0:03 ")
