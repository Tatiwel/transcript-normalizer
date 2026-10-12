"""A fake yt-dlp API and a fake transcriber, so fetch runs with no network (D-036, D-057)."""

import shutil
from dataclasses import dataclass
from pathlib import Path

VTT = Path(__file__).resolve().parent / "data" / "rolling.vtt"
VIDEO_ID = "abcdefghijk"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
RATE_LIMITED = "ERROR: Unable to download video subtitles for 'pt': HTTP Error 429: Too Many Requests"
RANGE_ERROR = "ERROR: unable to download video data: HTTP Error 416: Requested range not satisfiable"
#: D-071: what yt-dlp raised on a real Windows user, curly apostrophe and all.
BOT_CHECK = (
    "ERROR: [youtube] abcdefghijk: Sign in to confirm you\u2019re not a bot. Use --cookies-from-browser "
    "or --cookies for the authentication. See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ  for how to "
    "manually pass cookies"
)


class DownloadError(Exception):
    """What yt-dlp raises; fetch only reads its message."""


class CookieLoadError(Exception):
    """What yt-dlp raises when the cookies cannot be read; the cause is its context."""


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

    def __init__(self, caption=("ok",), has_caption=True, audio_ok=True, manual=(), automatic=("pt",), audio=None,
                 metadata=("ok",), unreadable_browser=False, url=URL, site="", formats=None, video_id=VIDEO_ID,
                 duration=125):
        self.caption = list(caption)
        self.has_caption = has_caption
        # Each audio download, in order: "ok", "416" (leaves a .part behind,
        # D-059) or "fail". The last entry repeats.
        self.audio = list(audio or (("ok",) if audio_ok else ("fail",)))
        self.manual = tuple(manual)
        self.automatic = tuple(automatic)
        self.calls: list[str] = []
        self.downloads: list[tuple[str, str]] = []
        self.params: list[dict] = []
        # D-071: each metadata read, in order: "ok", or "bot" for YouTube's
        # check. The last entry repeats. `cookies` keeps what each call read
        # from its cookies file, as yt-dlp's cookie jar would.
        self.metadata = list(metadata)
        self.unreadable_browser = unreadable_browser
        # D-078: another site: its link, yt-dlp's extractor_key, its formats.
        self.url, self.site, self.formats, self.video_id = url, site, formats, video_id
        self.duration = duration  # D-079: None, as Instagram gives none
        self.cookies: list[str] = []

    def open(self, params):
        self.params.append(params)
        return FakeYoutubeDL(self, params)

    def info(self):
        extra = {"extractor_key": self.site} if self.site else {}
        if self.formats is not None:
            extra["formats"] = self.formats
        return {
            **extra,
            "id": self.video_id,
            "title": "Video sintetico de teste",
            "uploader": "Canal de Teste",
            "upload_date": "20260825",
            "duration": self.duration,
            "subtitles": {c: [{}] for c in self.manual} if self.has_caption else {},
            "automatic_captions": {c: [{}] for c in self.automatic} if self.has_caption else {},
        }


class FakeYoutubeDL:
    """`yt_dlp.YoutubeDL`, as far as fetch uses it."""

    def __init__(self, platform: FakeYtDlp, params: dict):
        self.platform, self.params = platform, params

    def __enter__(self):
        if self.params.get("cookiesfrombrowser") and self.platform.unreadable_browser:
            # As yt-dlp does: the cause, its CookieLoadError, then report_error's DownloadError.
            try:
                try:
                    raise PermissionError("Failed to decrypt with DPAPI")
                except PermissionError:
                    raise CookieLoadError("failed to load cookies")
            except CookieLoadError:
                raise DownloadError("ERROR: Failed to decrypt with DPAPI")
        if self.params.get("cookiefile"):
            self.platform.cookies.append(Path(self.params["cookiefile"]).read_text(encoding="utf-8"))
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        assert url == self.platform.url and download is False
        platform = self.platform
        platform.calls.append("metadata")
        outcome = platform.metadata.pop(0) if len(platform.metadata) > 1 else platform.metadata[0]
        if outcome == "bot":
            raise DownloadError(BOT_CHECK)
        if outcome != "ok":  # D-078: another extractor's message, as given
            raise DownloadError(outcome)
        return platform.info()

    def download(self, urls):
        platform, params = self.platform, self.params
        target = Path(params["outtmpl"]["default"]).parent
        if "format" in params:
            platform.calls.append("audio")
            outcome = platform.audio.pop(0) if len(platform.audio) > 1 else platform.audio[0]
            if outcome == "416":
                (target / "audio.m4a.part").write_bytes(b"\0" * 8)
                raise DownloadError(RANGE_ERROR)
            if outcome != "ok":
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

#: D-062: the menu's way to the platform caption: Fetch, a link, the url, and
#: enter on "Use the platform's caption, or transcribe…" (the caption).
LINK = ["1", "1", URL, ""]
