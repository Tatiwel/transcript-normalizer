"""A fake yt-dlp and a fake transcriber, so fetch runs with no network (D-036)."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

VTT = Path(__file__).resolve().parent / "data" / "rolling.vtt"
VIDEO_ID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
RATE_LIMITED = "ERROR: Unable to download video subtitles for 'pt': HTTP Error 429: Too Many Requests"


class FakeYtDlp:
    """Answers the three calls fetch makes: metadata, the caption, the audio.

    `caption` is what each caption download does, in order: "ok" writes a
    WebVTT, "429" fails rate-limited, anything else fails another way. The last
    entry repeats. `has_caption=False` offers no caption at all. `manual` and
    `automatic` are the track lists the platform reports (D-045); each caption
    download is recorded in `downloads` as (flag, track).
    """

    def __init__(self, caption=("ok",), has_caption=True, audio_ok=True, manual=(), automatic=("pt",)):
        self.caption = list(caption)
        self.has_caption = has_caption
        self.audio_ok = audio_ok
        self.manual = tuple(manual)
        self.automatic = tuple(automatic)
        self.calls: list[str] = []
        self.downloads: list[tuple[str, str]] = []

    def __call__(self, args):
        if "--dump-single-json" in args:
            self.calls.append("metadata")
            video = {
                "id": VIDEO_ID,
                "title": "Video sintetico de teste",
                "uploader": "Canal de Teste",
                "upload_date": "20260825",
                "duration": 125,
                "subtitles": {c: [{}] for c in self.manual} if self.has_caption else {},
                "automatic_captions": {c: [{}] for c in self.automatic} if self.has_caption else {},
            }
            return subprocess.CompletedProcess(args, 0, json.dumps(video), "")
        target = Path(args[args.index("--output") + 1]).parent
        if "-f" in args:
            self.calls.append("audio")
            if not self.audio_ok:
                return subprocess.CompletedProcess(args, 1, "", "ERROR: audio unavailable")
            (target / "audio.m4a").write_bytes(b"\0" * 16)
            return subprocess.CompletedProcess(args, 0, "", "")
        self.calls.append("caption")
        track = args[args.index("--sub-langs") + 1]
        self.downloads.append((args[0], track))
        outcome = self.caption.pop(0) if len(self.caption) > 1 else self.caption[0]
        if outcome == "ok":
            shutil.copy(VTT, target / f"legenda.{track}.vtt")
            return subprocess.CompletedProcess(args, 0, "", "")
        if outcome == "429":
            return subprocess.CompletedProcess(args, 1, "", RATE_LIMITED)
        return subprocess.CompletedProcess(args, 1, "", f"ERROR: {outcome}")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Info:
    duration: float


class FakeWhisper:
    """What faster-whisper's model returns: segments, and the audio's length."""

    def __init__(self, model):
        self.model = model

    def transcribe(self, audio, **options):
        assert options["vad_filter"] is True  # D-036 keeps the fetch rule on
        segments = [
            Segment(0.5, 3.0, "o que que tá acontecendo com a SEMIG"),
            Segment(64.0, 67.0, "o dividendo caiu"),
        ]
        return iter(segments), Info(duration=70.0)


def install(monkeypatch, fetch, ytdlp=None):
    """Put the fakes in place of yt-dlp, faster-whisper and the waits."""
    ytdlp = ytdlp or FakeYtDlp()
    waits: list[float] = []
    monkeypatch.setattr(fetch, "run_ytdlp", ytdlp)
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: [])
    monkeypatch.setattr(fetch, "load_whisper", FakeWhisper)
    monkeypatch.setattr(fetch, "sleep", waits.append)
    return ytdlp, waits
