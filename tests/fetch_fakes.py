"""A fake yt-dlp API and a fake transcriber, so fetch runs with no network (D-036, D-057)."""

import shutil
from dataclasses import dataclass
from pathlib import Path

VTT = Path(__file__).resolve().parent / "data" / "rolling.vtt"
VIDEO_ID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
RATE_LIMITED = "ERROR: Unable to download video subtitles for 'pt': HTTP Error 429: Too Many Requests"


class DownloadError(Exception):
    """What yt-dlp raises; fetch only reads its message."""


class FakeYtDlp:
    """The platform as yt-dlp's API sees it (D-057): metadata, captions, audio.

    `open(params)` is what fetch calls in place of `yt_dlp.YoutubeDL(params)`.
    `caption` is what each caption download does, in order: "ok" writes a
    WebVTT, "429" fails rate-limited, anything else fails another way. The last
    entry repeats. `has_caption=False` offers no caption at all. `manual` and
    `automatic` are the track lists the platform reports (D-045); each caption
    download is recorded in `downloads` as (option, track), the option being
    `writesubtitles` or `writeautomaticsub`. `params` keeps every option set.
    """

    def __init__(self, caption=("ok",), has_caption=True, audio_ok=True, manual=(), automatic=("pt",)):
        self.caption = list(caption)
        self.has_caption = has_caption
        self.audio_ok = audio_ok
        self.manual = tuple(manual)
        self.automatic = tuple(automatic)
        self.calls: list[str] = []
        self.downloads: list[tuple[str, str]] = []
        self.params: list[dict] = []

    def open(self, params):
        self.params.append(params)
        return FakeYoutubeDL(self, params)

    def info(self):
        return {
            "id": VIDEO_ID,
            "title": "Video sintetico de teste",
            "uploader": "Canal de Teste",
            "upload_date": "20260825",
            "duration": 125,
            "subtitles": {c: [{}] for c in self.manual} if self.has_caption else {},
            "automatic_captions": {c: [{}] for c in self.automatic} if self.has_caption else {},
        }


class FakeYoutubeDL:
    """`yt_dlp.YoutubeDL`, as far as fetch uses it."""

    def __init__(self, platform: FakeYtDlp, params: dict):
        self.platform, self.params = platform, params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        assert url == URL and download is False
        self.platform.calls.append("metadata")
        return self.platform.info()

    def download(self, urls):
        platform, params = self.platform, self.params
        target = Path(params["outtmpl"]["default"]).parent
        if "format" in params:
            platform.calls.append("audio")
            if not platform.audio_ok:
                raise DownloadError("ERROR: audio unavailable")
            (target / "audio.m4a").write_bytes(b"\0" * 16)
            return 0
        platform.calls.append("caption")
        assert params["skip_download"] is True
        option = "writesubtitles" if params["writesubtitles"] else "writeautomaticsub"
        track = params["subtitleslangs"][0]
        platform.downloads.append((option, track))
        outcome = platform.caption.pop(0) if len(platform.caption) > 1 else platform.caption[0]
        if outcome == "ok":
            shutil.copy(VTT, target / f"legenda.{track}.vtt")
            return 0
        if outcome == "429":
            raise DownloadError(RATE_LIMITED)
        raise DownloadError(f"ERROR: {outcome}")


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

    def __init__(self, model, out=None):
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
    monkeypatch.setattr(fetch, "youtube_dl", ytdlp.open)
    monkeypatch.setattr(fetch, "missing_extra", lambda *modules: [])
    monkeypatch.setattr(fetch, "load_whisper", FakeWhisper)
    monkeypatch.setattr(fetch, "sleep", waits.append)
    return ytdlp, waits
