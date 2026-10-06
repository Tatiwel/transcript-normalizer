"""D-036: fetch resolves its source in a fixed chain and records the step."""

import io
from pathlib import Path

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
    assert "HTTP 429 on the caption download (attempt 1/3), retrying in 2 s" in out
    assert "HTTP 429 on the caption download (attempt 2/3), retrying in 4 s" in out


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
    assert err.strip() == "This video has no caption."  # plain words, no flags
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


class Clock:
    """A fake clock: `sleep` advances it, and nothing really waits."""

    def __init__(self):
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds


def test_the_backoff_really_waits_between_attempts(tmp_path, monkeypatch, capsys):
    """D-036: 2 s, then 4 s, between the three attempts, not back to back."""
    clock = Clock()
    platform = FakeYtDlp(caption=["429", "429", "ok"])
    attempts = []
    opened = platform.open

    def open_at(params):
        if "subtitleslangs" in params:
            attempts.append(clock.now)
        return opened(params)

    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, platform)
    monkeypatch.setattr(fetch, "youtube_dl", open_at)
    monkeypatch.setattr(fetch, "sleep", clock.sleep)
    assert main(["fetch", URL]) == 0
    assert attempts == [0.0, 2.0, 6.0]
    out = capsys.readouterr().out
    assert out.index("retrying in 2 s") < out.index("retrying in 4 s")


def test_the_rich_countdown_counts_down_and_stays_on_screen():
    pytest.importorskip("rich")
    from rich.console import Console

    stream, ticks = io.StringIO(), []
    out = Output(stream=stream, fancy=True)
    out._console = Console(file=stream, force_terminal=True, highlight=False, width=80)  # redraws, as on a terminal
    out.countdown(2, "HTTP 429", ticks.append)
    assert ticks == [1.0, 1.0]
    import re

    shown = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", stream.getvalue())
    assert "retrying in 2 s" in shown and "retrying in 1 s" in shown
    assert "waited 2 s, retrying" in shown


def test_caption_only_says_429_in_plain_words(tmp_path, monkeypatch, capsys):
    code, _, _, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["429"]), "--caption-only")
    assert code == 1
    assert capsys.readouterr().err.strip() == "YouTube is limiting downloads right now (HTTP 429)."


def test_the_menu_s_second_call_does_not_repeat_the_video(tmp_path, monkeypatch, capsys):
    fetched(tmp_path, monkeypatch, FakeYtDlp(), "--whisper", "--no-video-info")
    out = capsys.readouterr().out
    assert "title:" not in out and "duration:" not in out


def test_selftest_audio_decodes_the_two_second_wav(capsys):
    pytest.importorskip("faster_whisper")
    wav = Path(__file__).resolve().parent / "data" / "two-seconds.wav"
    assert main(["fetch", "--selftest-audio", str(wav)]) == 0
    assert capsys.readouterr().out.strip() == "selftest: decoded 32000 samples from two-seconds.wav"


def test_selftest_audio_reports_a_decoding_failure(tmp_path, capsys, monkeypatch):
    pytest.importorskip("faster_whisper")
    import faster_whisper

    def broken(path):
        raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")

    monkeypatch.setattr(faster_whisper, "decode_audio", broken)
    assert main(["fetch", "--selftest-audio", str(tmp_path / "x.wav")]) == 1
    assert "TypeError: open() got an unexpected keyword argument 'metadata_errors'" in capsys.readouterr().err


def test_hugging_face_noise_is_silenced(monkeypatch):
    import os
    import warnings

    monkeypatch.delenv("HF_HUB_DISABLE_SYMLINKS_WARNING", raising=False)
    monkeypatch.delenv("HF_HUB_VERBOSITY", raising=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fetch.quiet_hugging_face()
        warnings.warn_explicit("symlinks are not supported", UserWarning, "file_download.py", 1, module="huggingface_hub.file_download")
    assert os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] == "1"
    assert os.environ["HF_HUB_VERBOSITY"] == "error"
    assert not caught


def test_a_cached_model_is_not_downloaded_again(monkeypatch, capsys):
    pytest.importorskip("faster_whisper")
    import faster_whisper.utils as utils
    import huggingface_hub

    monkeypatch.setattr(utils, "download_model", lambda model, local_files_only=False: "/cache/medium")
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda *a, **k: pytest.fail("downloaded"))
    assert fetch.model_path("medium", Output(stream=io.StringIO(), fancy=False)) == "/cache/medium"


def test_the_first_download_says_so_once(monkeypatch):
    pytest.importorskip("faster_whisper")
    import faster_whisper.utils as utils
    import huggingface_hub

    def not_cached(model, local_files_only=False):
        raise FileNotFoundError(model)

    got = {}
    monkeypatch.setattr(utils, "download_model", not_cached)
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda repo, **k: got.update(repo=repo, **k) or "/cache/new")
    stream = io.StringIO()
    assert fetch.model_path("medium", Output(stream=stream, fancy=False)) == "/cache/new"
    assert stream.getvalue().strip() == "downloading the speech model (about 1.5 GB, first time only)…"
    assert got["repo"] == "Systran/faster-whisper-medium" and "model.bin" in got["allow_patterns"]
