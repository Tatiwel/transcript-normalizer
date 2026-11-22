"""The ingest extra: the header the core reads, and the boundary around it."""

import importlib.util
import subprocess
import sys

import pytest

from transcript_normalizer.cli import main
from transcript_normalizer.ingest import Metadata, caption_header, srt_to_lines
from transcript_normalizer.ingest import fetch

from .conftest import CAPTION

# What the fixture's header says: the video's title, channel and link are
# left out of the fixtures, and the link is a placeholder with the fixture's id.
FIXTURE_META = Metadata(
    id="fixture0001",
    title="fixture0001",
    channel="omitido",
    published="omitido",
)
FIXTURE_URL = "https://example.invalid/watch?v=fixture0001"
FIXTURE_DOWNLOADED = "2026-09-09"


def fixture_header() -> str:
    """The `#` block at the top of the fixture caption, the body stripped off."""
    lines = []
    for line in CAPTION.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line)
    return "\n".join(lines) + "\n"


#: The fixture was fetched before D-093, when the header did not say which
#: moment of the line the timestamp is. Everything else is the same.
BEFORE_D093 = (
    "# Cada linha comeca com o timestamp mm:ss. O timestamp e a\n"
    "# procedencia de qualquer afirmacao extraida daqui, do mesmo modo\n"
    "# que documento e pagina sao a procedencia de um PDF.\n"
)
SINCE_D093 = (
    "# Cada linha comeca com o timestamp do FIM do trecho: o\n"
    "# instante em que a legenda sai da tela. A fala comeca antes dele.\n"
    "# Antes de 1 hora, m:ss (44:29); depois, h:mm:ss (1:14:14).\n"  # D-103
)
#: D-102: the header no longer carries the rules of a program that uses it.
BEFORE_D102 = "# NAO E CONHECIMENTO AUTORADO. Nao carregue isto em conhecimento/.\n"


def test_header_writer_reproduces_the_fixture_header():
    written = caption_header(
        FIXTURE_META,
        FIXTURE_URL,
        source="automatica",
        lang="pt",
        downloaded=FIXTURE_DOWNLOADED,
    )
    assert BEFORE_D093 in fixture_header() and BEFORE_D102 in fixture_header()
    expected = fixture_header().replace(BEFORE_D093, SINCE_D093).replace(BEFORE_D102, "")
    assert written == expected.replace("antes de citar.", "antes de usar.")


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
    assert fetch.fetch_dir("fixture0001") == tmp_path / "runs" / "fixture0001"
    assert fetch.fetch_dir("fixture0001", tmp_path / "elsewhere") == tmp_path / "elsewhere"
