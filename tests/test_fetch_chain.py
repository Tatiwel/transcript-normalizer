"""D-036: fetch resolves its source in a fixed chain and records the step."""

import io

import pytest
import yaml

from transcript_normalizer.cli import main
from transcript_normalizer.core.text import read_caption
from transcript_normalizer.ingest import fetch
from transcript_normalizer.ingest.console import Output
from transcript_normalizer.runs import CAPTION_FILE, META_FILE

from . import fetch_fakes
from .fetch_fakes import URL, VIDEO_ID, FakeYtDlp


def fetched(tmp_path, monkeypatch, ytdlp, *extra):
    monkeypatch.chdir(tmp_path)
    fake, waits = fetch_fakes.install(monkeypatch, fetch, ytdlp)
    code = main(["fetch", URL, *extra])
    run = tmp_path / "runs" / VIDEO_ID
    return code, run, fake, waits


def step_of(run):
    """The `# Etapa:` header line and meta.yaml's record of the step."""
    header = read_caption(run / CAPTION_FILE).header_field("Etapa")
    meta = yaml.safe_load((run / META_FILE).read_text(encoding="utf-8"))
    return header, meta


def test_a_caption_ok_is_step_1(tmp_path, monkeypatch):
    code, run, fake, waits = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["ok"]))
    assert code == 0
    header, meta = step_of(run)
    assert header == "1, legenda da plataforma"
    assert (meta["step"], meta["step_name"], meta["retries"]) == (1, "platform caption", 0)
    assert "fallback_reason" not in meta
    assert fake.calls == ["metadata", "caption"] and waits == []


def test_b_two_429s_then_ok_is_step_1_with_the_retries_logged(tmp_path, monkeypatch, capsys):
    code, run, fake, waits = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["429", "429", "ok"]))
    assert code == 0
    header, meta = step_of(run)
    assert header == "1, legenda da plataforma, apos 2 nova(s) tentativa(s) por HTTP 429"
    assert (meta["step"], meta["retries"]) == (1, 2)
    assert waits == [2.0, 4.0]  # exponential backoff
    out = capsys.readouterr().out
    assert "HTTP 429 on the caption download (attempt 1/3), waiting 2s" in out
    assert "HTTP 429 on the caption download (attempt 2/3), waiting 4s" in out


def test_c_three_429s_fall_through_to_step_2(tmp_path, monkeypatch):
    code, run, fake, waits = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["429"]))
    assert code == 0
    header, meta = step_of(run)
    assert header == "2, reconhecimento de fala local (legenda falhou: HTTP 429 em 3 tentativas)"
    assert (meta["step"], meta["step_name"]) == (2, "local speech recognition")
    assert meta["fallback_reason"] == "legenda falhou: HTTP 429 em 3 tentativas"
    assert fake.calls == ["metadata", "caption", "caption", "caption", "audio"]
    assert waits == [2.0, 4.0]
    lines = [l.text for l in read_caption(run / CAPTION_FILE).lines]
    assert lines == ["o que que tá acontecendo com a SEMIG", "o dividendo caiu"]


def test_d_no_caption_available_is_step_2(tmp_path, monkeypatch):
    code, run, fake, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(has_caption=False))
    assert code == 0
    header, meta = step_of(run)
    assert header == "2, reconhecimento de fala local (sem legenda na plataforma)"
    assert meta["fallback_reason"] == "sem legenda na plataforma"
    assert "caption" not in fake.calls


def test_e_caption_only_with_no_caption_is_a_clear_error(tmp_path, monkeypatch, capsys):
    code, run, fake, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(has_caption=False), "--caption-only")
    assert code == 1
    err = capsys.readouterr().err
    assert "no platform caption" in err and "--caption-only" in err
    assert not (run / CAPTION_FILE).exists()
    assert "audio" not in fake.calls


def test_f_output_is_plain_when_not_a_tty(tmp_path, monkeypatch, capsys):
    fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["429", "ok"]))
    out = capsys.readouterr().out
    assert "== step 1: platform caption" in out
    assert "\x1b[" not in out and "\r" not in out  # no colour, no cursor games


def test_whisper_skips_step_1(tmp_path, monkeypatch):
    code, run, fake, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(), "--whisper")
    assert code == 0
    header, _ = step_of(run)
    assert header == "2, reconhecimento de fala local (pedido com --whisper)"
    assert fake.calls == ["metadata", "audio"]


def test_both_steps_failing_is_the_only_error(tmp_path, monkeypatch, capsys):
    code, run, _, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["429"], audio_ok=False))
    assert code == 1
    err = capsys.readouterr().err
    assert "could not get a text" in err
    assert "HTTP 429 on all 3 attempts" in err and "audio" in err
    assert not (run / CAPTION_FILE).exists()


def test_a_non_429_failure_is_not_retried_but_still_falls_through(tmp_path, monkeypatch):
    code, run, fake, waits = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["broken"]))
    assert code == 0 and waits == []
    header, _ = step_of(run)
    assert header == "2, reconhecimento de fala local (legenda falhou)"


def test_the_terminal_path_counts_down_with_rich():
    pytest.importorskip("rich")
    ticks: list[float] = []
    Output(stream=io.StringIO(), fancy=True).countdown(3, "HTTP 429", ticks.append)
    assert ticks == [1.0, 1.0, 1.0]


def test_impersonation_is_asked_for_only_when_curl_cffi_is_there(monkeypatch):
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    assert fetch.impersonation_params() == {}
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    assert fetch.impersonation_params() == {"impersonate": "chrome"}


def test_the_raw_subtitle_is_deleted_once_converted(tmp_path, monkeypatch):
    code, run, _, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["ok"]))
    assert code == 0 and (run / CAPTION_FILE).exists()
    assert not list(run.glob("legenda.*vtt")) and not list(run.glob("legenda.*srt"))


def test_keep_raw_keeps_the_subtitle(tmp_path, monkeypatch):
    code, run, _, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["ok"]), "--keep-raw")
    assert code == 0 and (run / "legenda.vtt").exists()


def test_ytdlp_runs_in_process_never_as_a_subprocess(tmp_path, monkeypatch):
    """D-057: `sys.executable -m yt_dlp` re-entered the frozen executable's CLI."""
    import subprocess

    def refuse(*args, **kwargs):
        raise AssertionError(f"fetch started a subprocess: {args}")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    code, run, fake, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["ok"]))
    assert code == 0 and fake.calls == ["metadata", "caption"]
    # The command line's options, as YoutubeDL parameters.
    caption = fake.params[1]
    assert caption["skip_download"] is True and caption["subtitleslangs"] == ["pt"]
    assert caption["writeautomaticsub"] is True and caption["quiet"] is True


def test_a_step_1_error_is_shown_verbatim(tmp_path, monkeypatch, capsys):
    code, _, _, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["[youtube] abcdefghijk: Sign in to confirm"]), "--caption-only")
    assert code == 1
    assert "the caption download failed: ERROR: [youtube] abcdefghijk: Sign in to confirm" in capsys.readouterr().err


def test_check_reports_each_tool_and_exits_0(monkeypatch, capsys):
    versions = {"yt_dlp": "2026.08.19", "curl_cffi": None, "faster_whisper": "1.2.1"}
    monkeypatch.setattr(fetch, "tool_version", versions.get)
    assert main(["fetch", "--check"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split()[:2] == ["yt-dlp", "2026.08.19"]
    assert lines[1].split()[:3] == ["curl_cffi", "not", "installed"]
    assert lines[2].split()[:2] == ["faster-whisper", "1.2.1"]


def test_check_reads_real_versions(capsys):
    """In the repository the ingest extra is installed (the dev group)."""
    pytest.importorskip("yt_dlp")
    assert main(["fetch", "--check"]) == 0
    first = capsys.readouterr().out.splitlines()[0].split()
    assert first[0] == "yt-dlp" and first[1][0].isdigit()


def test_fetch_without_a_url_says_so(capsys):
    assert main(["fetch"]) == 2
    assert "fetch needs a video url or a file (or --check)" in capsys.readouterr().err
