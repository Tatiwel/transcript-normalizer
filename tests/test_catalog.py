"""D-022: runs/<video-id>/, meta.yaml beside the caption, and `list`."""

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from transcript_normalizer.catalog import iso_date, list_runs, read_run
from transcript_normalizer.cli import main
from transcript_normalizer.ingest import fetch
from transcript_normalizer.runs import CAPTION_FILE, META_FILE

from .conftest import CAPTION

VTT = Path(__file__).resolve().parent / "data" / "rolling.vtt"
VIDEO = {
    "id": "abcdefghijk",
    "title": "Video sintetico de teste",
    "uploader": "Canal de Teste",
    "upload_date": "20260825",
    "duration": 125,
    "subtitles": {},
    "automatic_captions": {"pt": [{}]},
}
URL = "https://www.youtube.com/watch?v=abcdefghijk"


@pytest.fixture
def fake_ytdlp(monkeypatch):
    """yt-dlp as far as fetch can tell: metadata, then a WebVTT on disk."""

    def run(args):
        if "--dump-single-json" in args:
            return subprocess.CompletedProcess(args, 0, json.dumps(VIDEO), "")
        target = Path(args[args.index("--output") + 1]).parent
        shutil.copy(VTT, target / "legenda.pt.vtt")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(fetch, "run_ytdlp", run)
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: [])


def test_fetch_writes_meta_yaml_into_the_video_s_run(tmp_path, monkeypatch, fake_ytdlp):
    monkeypatch.chdir(tmp_path)
    assert main(["fetch", URL]) == 0

    run = tmp_path / "runs" / "abcdefghijk"
    assert (run / CAPTION_FILE).exists()
    meta = yaml.safe_load((run / META_FILE).read_text(encoding="utf-8"))
    assert list(meta) == ["title", "channel", "url", "published", "fetched_at"]
    assert meta["title"] == "Video sintetico de teste"
    assert meta["channel"] == "Canal de Teste"
    assert meta["url"] == URL
    assert meta["published"] == "2026-08-25"
    assert datetime.fromisoformat(meta["fetched_at"]).tzinfo is not None


def test_list_prints_id_date_and_title(tmp_path, monkeypatch, fake_ytdlp, capsys):
    monkeypatch.chdir(tmp_path)
    main(["fetch", URL])
    capsys.readouterr()

    assert main(["list"]) == 0
    assert capsys.readouterr().out == "abcdefghijk  2026-08-25  Video sintetico de teste\n"


def test_a_run_without_meta_is_described_from_its_caption_header(tmp_path):
    """Runs from before D-022, or from a local caption, still list properly."""
    run = tmp_path / "R2Qgz8tFWVI"
    run.mkdir()
    shutil.copy(CAPTION, run / CAPTION_FILE)

    found = read_run(run)
    assert (found.id, found.date, found.title, found.source) == (
        "R2Qgz8tFWVI",
        "2026-08-21",
        "CEMIG despencando, armadilha ou oportunidade?",
        "header",
    )


def test_list_is_every_run_oldest_video_first_and_nothing_else(tmp_path):
    for video, published, title in (
        ("bbbbbbbbbbb", "2026-09-02", "second"),
        ("aaaaaaaaaaa", "2026-08-01", "first"),
    ):
        (tmp_path / video).mkdir()
        (tmp_path / video / META_FILE).write_text(
            yaml.safe_dump({"title": title, "published": published}), encoding="utf-8"
        )
    (tmp_path / "learned").mkdir()  # left over from D-015's layout: not a run
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")

    assert [(r.id, r.date, r.title) for r in list_runs(tmp_path)] == [
        ("aaaaaaaaaaa", "2026-08-01", "first"),
        ("bbbbbbbbbbb", "2026-09-02", "second"),
    ]


def test_list_with_no_runs_says_so(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["list"]) == 0
    assert "no runs under" in capsys.readouterr().out


@pytest.mark.parametrize(
    "value, expected",
    [("20260825", "2026-08-25"), ("2026-08-25", "2026-08-25"), ("", ""), ("agosto", "agosto")],
)
def test_platform_dates_become_iso(value, expected):
    assert iso_date(value) == expected
