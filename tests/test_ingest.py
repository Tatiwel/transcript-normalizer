"""The ingest extra: the header the core reads, and the boundary around it."""

import importlib.util
import subprocess
import sys

import pytest

from transcript_normalizer.cli import main
from transcript_normalizer.ingest import Metadata, caption_header, srt_to_lines
from transcript_normalizer.ingest import fetch

from .conftest import CAPTION

# What the platform reported for the fixture video.
FIXTURE_META = Metadata(
    id="R2Qgz8tFWVI",
    title="CEMIG despencando, armadilha ou oportunidade?",
    channel="Geração Dividendos",
    published="20260821",
)
FIXTURE_URL = "https://youtu.be/R2Qgz8tFWVI"
FIXTURE_DOWNLOADED = "2026-09-09"


def fixture_header() -> str:
    """The `#` block at the top of the fixture caption, the body stripped off."""
    lines = []
    for line in CAPTION.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines) + "\n"


def test_header_writer_reproduces_the_fixture_header():
    written = caption_header(
        FIXTURE_META,
        FIXTURE_URL,
        source="automatica",
        lang="pt",
        downloaded=FIXTURE_DOWNLOADED,
    )
    assert written == fixture_header()


def test_the_written_header_is_what_the_core_skips():
    from transcript_normalizer import parse_caption

    header = caption_header(
        FIXTURE_META, FIXTURE_URL, source="automatica", lang="pt",
        downloaded=FIXTURE_DOWNLOADED,
    )
    transcript = parse_caption(header + "0:02 primeira linha\n0:05 segunda linha\n")
    assert [(l.timestamp, l.text) for l in transcript.lines] == [
        ("0:02", "primeira linha"),
        ("0:05", "segunda linha"),
    ]


def test_srt_to_lines_collapses_the_rolling_repetition():
    srt = (
        "1\n00:00:01,000 --> 00:00:03,000\nprimeira linha\n\n"
        "2\n00:00:03,000 --> 00:00:05,000\nprimeira linha\nsegunda linha\n\n"
        "3\n00:00:05,000 --> 00:00:07,000\nsegunda linha\nterceira linha\n"
    )
    assert srt_to_lines(srt) == "0:03 primeira linha\n0:05 segunda linha\n0:07 terceira linha"


def test_fetch_says_so_when_the_extra_is_not_installed(monkeypatch, capsys):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)

    assert main(["fetch", "https://example.invalid/video"]) == 2

    err = capsys.readouterr().err
    assert "ingest" in err
    assert "yt-dlp" in err
    assert "uv sync --extra ingest" in err


@pytest.mark.parametrize("module", ["yt_dlp", "faster_whisper"])
def test_importing_the_core_does_not_import_the_extra(module):
    code = (
        "import sys, transcript_normalizer, transcript_normalizer.core.matcher;"
        f"print({module!r} in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_fetch_writes_under_runs_by_video_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert fetch.fetch_dir("R2Qgz8tFWVI") == tmp_path / "runs" / "R2Qgz8tFWVI"
    assert fetch.fetch_dir("R2Qgz8tFWVI", tmp_path / "elsewhere") == tmp_path / "elsewhere"
