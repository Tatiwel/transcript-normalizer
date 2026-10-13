"""`transcript-normalizer fetch <url | file>`: a platform caption, or local speech.

D-036: the source is resolved in a fixed chain, and the step that produced the
text is recorded in the legenda.txt header and in meta.yaml.

1. The platform's caption. An HTTP 429 is retried with exponential backoff:
   three attempts in all.
2. If there is no caption, or step 1 fails, the audio is downloaded and
   transcribed locally with faster-whisper.
3. Only if both fail is it an error.

`--caption-only` stops after step 1; `--whisper` starts at step 2. A local audio
or video file starts at step 2 too, since it has no platform caption (D-038).
yt-dlp covers most platforms (YouTube, TikTok, Instagram, Vimeo, X, Twitch); the
tool never depends on third-party converter sites.

Speech recognition is not the same thing as asking an AI provider to transcribe:
it maps audio to text and does not fill a gap with something plausible. Its
errors are phonetic and visible, which is exactly what the domain packs correct.

The dependencies live in the `ingest` extra and are imported lazily, so the
engine stays installable without them.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import os
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

from ..catalog import write_meta
from ..runs import is_frozen, runs_root
from . import cookies as sign_in
from .console import Output
from .header import Metadata, caption_header, speech_header
from .subtitles import subtitle_to_lines

CAPTION_FILE = "legenda.txt"
SUBTITLE_STEM = "legenda"

#: What yt-dlp may leave behind, best first. WebVTT is what YouTube serves.
SUBTITLE_SUFFIXES = (".vtt", ".srt")

DEFAULT_LANG = "pt"
DEFAULT_MODEL = "medium"
SPEECH_MODELS = ("tiny", "base", "small", "medium", "large-v2", "large-v3")

#: What each step needs from the `ingest` extra.
REQUIRES = {"yt_dlp": "yt-dlp", "faster_whisper": "faster-whisper"}

#: D-036: attempts per yt-dlp call on HTTP 429, and the first wait (2s, then 4s).
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0

#: Replaced in tests, so a retry does not really wait.
sleep = time.sleep

STEP_CAPTION = 1
STEP_SPEECH = 2
STEP_NAMES = {STEP_CAPTION: "platform caption", STEP_SPEECH: "local speech recognition"}


class FetchError(Exception):
    """One step of the chain could not produce a text."""


class NoCaption(FetchError):
    """The platform has no caption in the language asked for."""


class RateLimited(FetchError):
    """HTTP 429 on every attempt."""


class SignInRequired(FetchError):
    """D-071: YouTube's bot check, age check or login wall; D-078: any site's
    login wall. The message is said plainly; yt-dlp's own, which names its
    flags, is kept in `raw`."""

    def __init__(self, plainly: str, raw: str = ""):
        super().__init__(plainly)
        self.raw = raw


class UnsupportedSite(FetchError):
    """D-079: yt-dlp has no extractor for this link ("Unsupported URL")."""


#: D-079: said instead of yt-dlp's "Unsupported URL", in the menu and in `fetch`.
UNSUPPORTED = "This site isn't supported. Download the video another way and use 'A file on this computer'."


class CookiesUnreadable(FetchError):
    """D-071: the browser or cookies.txt named for the sign-in could not be read."""


#: D-071: what YouTube's checks are, said to a person.
BOT_CHECK = "YouTube asked to confirm you are not a bot. This depends on your connection, not on the video."
SIGN_IN = "YouTube asks for a signed-in account to show this video (an age check, or members only)."
#: What `fetch` exits with when a site asks for a sign-in, so the menu can offer it.
EXIT_SIGN_IN = 3

#: Lowercased pieces of yt-dlp's messages, by what they mean (D-071).
BOT_MARKS = ("not a bot",)
SIGN_IN_MARKS = (
    # YouTube (D-071)
    "confirm your age", "age-restricted", "inappropriate for some users",
    "login details are needed", "only available for registered users",
    "members-only", "join this channel",
    # D-078: yt-dlp's own hint, which raise_login_required adds in every
    # extractor, in its three wordings ("Use --cookies-from-browser or
    # --cookies", "Use --cookies, --cookies-from-browser, ...", "Use --cookies
    # for the authentication")
    "use --cookies",
    # D-078: other extractors' words (yt_dlp/extractor: instagram, facebook,
    # tiktok, twitter, vimeo; there is no Kwai extractor)
    "login required", "rate-limit reached", "requires authentication", "authentication may be needed",
    "need to log in", "log into an account", "who follow this account", "accessing posts anonymously",
    "without being logged-in", "account is private", "videos are private", "protected tweet",
    "not authorized to view", "do not have permission to view", "only works when logged-in",
    "fresh cookies", "private video", "granted access to this video",
)

#: D-078: how a site is called, by yt-dlp's extractor name (before any `:`).
SITE_NAMES = {
    "youtube": "YouTube", "instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok",
    "twitter": "X (Twitter)", "vimeo": "Vimeo", "kwai": "Kwai", "twitch": "Twitch",
    "dailymotion": "Dailymotion", "threads": "Threads", "reddit": "Reddit", "soundcloud": "SoundCloud",
    "linkedin": "LinkedIn", "kick": "Kick", "bilibili": "Bilibili",
}
#: ... and by the link's host, when the message names no extractor.
SITE_HOSTS = {
    "youtube.com": "youtube", "youtu.be": "youtube", "instagram.com": "instagram",
    "facebook.com": "facebook", "fb.watch": "facebook", "tiktok.com": "tiktok", "x.com": "twitter",
    "twitter.com": "twitter", "vimeo.com": "vimeo", "kwai.com": "kwai", "twitch.tv": "twitch",
    "dailymotion.com": "dailymotion", "threads.net": "threads", "threads.com": "threads",
    "reddit.com": "reddit", "soundcloud.com": "soundcloud", "linkedin.com": "linkedin", "kick.com": "kick",
}


def site_name(message: str = "", url: str = "", extractor: str = "") -> str:
    """D-078: "Instagram", from yt-dlp's extractor (`[Instagram] …` in its
    message, or the info's `extractor_key`), else from the link's host."""
    from urllib.parse import urlsplit

    found = re.match(r"(?:ERROR: )?\[([^\]]+)\]", message.strip())
    key = (extractor or (found.group(1) if found else "")).split(":")[0].lower()
    if key and key != "generic":
        return SITE_NAMES.get(key, key.capitalize())
    host = urlsplit(url).hostname or ""
    for prefix in ("www.", "m.", "mobile."):
        host = host.removeprefix(prefix)
    key = next((k for h, k in SITE_HOSTS.items() if host == h or host.endswith("." + h)), "")
    return SITE_NAMES[key] if key else (host or "The site")


def sign_in_needed(message: str, url: str = "", cookies: sign_in.Cookies | None = None) -> str:
    """BOT_CHECK, or what a login wall means (D-078: any site), when yt-dlp's
    message is one; "". With a sign-in already set, the wall means that login
    may not be signed in to that site."""
    lowered = message.lower().replace("\u2019", "'")
    if any(mark in lowered for mark in BOT_MARKS):
        return BOT_CHECK
    if not any(mark in lowered for mark in SIGN_IN_MARKS):
        return ""
    site = site_name(message, url)
    if cookies is not None:
        if cookies.browser:
            return (f"The browser you chose ({sign_in.NAMES.get(cookies.browser, cookies.browser.capitalize())}) "
                    f"may not be signed in to {site}. Sign in there, or pick another browser in Settings.")
        return (f"The cookies.txt file you chose may not be signed in to {site}. Export it again while "
                f"signed in there, or pick another in Settings.")
    return SIGN_IN if site == "YouTube" else f"{site} asked you to sign in for this video."


@dataclass(frozen=True)
class Step:
    """What produced the text, as the header and meta.yaml record it (D-036)."""

    number: int
    retries: int = 0
    reason: str = ""  # why step 2 ran, if it did
    track: str = ""  # D-045: the caption track step 1 took, e.g. `pt-orig`
    track_source: str = ""  # manual | automatica | automatica original

    @property
    def name(self) -> str:
        return STEP_NAMES[self.number]

    def header(self) -> str:
        """The `# Etapa:` line, in the header's language (Portuguese)."""
        if self.number == STEP_CAPTION:
            line = "1, legenda da plataforma"
            if self.retries:
                line += f", apos {self.retries} nova(s) tentativa(s) por HTTP 429"
            return line
        return f"2, reconhecimento de fala local ({self.reason})"

    def meta(self) -> dict:
        data = {"step": self.number, "step_name": self.name, "retries": self.retries}
        if self.reason:
            data["fallback_reason"] = self.reason
        if self.track:
            data["caption_track"] = self.track
            data["caption_source"] = self.track_source
        return data


def fetch_dir(video_id: str, out: str | Path | None = None) -> Path:
    """`runs/<video-id>/`, or `out` when the caller names a directory (D-015)."""
    return Path(out) if out is not None else runs_root() / video_id


def missing_extra(*modules: str) -> list[str]:
    return [REQUIRES[m] for m in modules if importlib.util.find_spec(m) is None]


#: D-053: the `lite` executable has no speech recognition, and pip advice is no
#: use to someone who downloaded a program.
LITE_BUILD = (
    "This is the lite build; it cannot transcribe audio. "
    "Download the full build from the Releases page."
)


def is_lite_build() -> bool:
    return is_frozen() and importlib.util.find_spec("faster_whisper") is None


def report_missing(missing: list[str]) -> int:
    if is_lite_build() and REQUIRES["faster_whisper"] in missing:
        print(LITE_BUILD, file=sys.stderr)
        return 2
    print(
        f"fetch needs the `ingest` extra, which is not installed "
        f"(missing: {', '.join(missing)}).\n"
        f"Install it with one of:\n"
        f"    uv sync --extra ingest\n"
        f"    pip install 'transcript-normalizer[ingest]'",
        file=sys.stderr,
    )
    return 2


# --------------------------------------------------------------------------- yt-dlp
#
# D-057: yt-dlp runs in this process, through its Python API, never as
# `python -m yt_dlp`. In a PyInstaller executable `sys.executable` is the
# executable itself, so a subprocess re-entered this CLI with `-m yt_dlp`.


class _Quiet:
    """yt-dlp's logger: say nothing. Its errors come back as exceptions."""

    def debug(self, message):
        pass

    info = warning = error = debug


def impersonation_params() -> dict:
    """Browser impersonation, which is what gets past most HTTP 429s. It needs
    curl_cffi, part of the ingest extra; without it yt-dlp runs as before."""
    return {"impersonate": "chrome"} if importlib.util.find_spec("curl_cffi") else {}


def portable_params() -> dict:
    """D-070: a portable program keeps yt-dlp's cache in its own folder."""
    from ..runs import portable_cache

    cache = portable_cache()
    return {"cachedir": str(cache)} if cache else {}


@contextlib.contextmanager
def in_portable_cache():
    """D-070: in a portable program, yt-dlp runs with its cache folder as the
    working directory, so whatever its JavaScript runtime writes (a deno.lock)
    stays inside the portable folder. Elsewhere, nothing changes."""
    from ..runs import portable_cache

    cache = portable_cache()
    if cache is None:
        yield
        return
    cache.mkdir(parents=True, exist_ok=True)
    before = os.getcwd()
    os.chdir(cache)
    try:
        yield
    finally:
        os.chdir(before)


def youtube_dl(params: dict):
    """A `yt_dlp.YoutubeDL`. Replaced in tests by a fake with the same shape."""
    from yt_dlp import YoutubeDL  # the ingest extra, imported lazily

    params = dict(params)
    if "impersonate" in params:
        from yt_dlp.networking.impersonate import ImpersonateTarget

        params["impersonate"] = ImpersonateTarget.from_str(params["impersonate"])
    return YoutubeDL(params)


def is_rate_limited(message: str) -> bool:
    return "HTTP Error 429" in message or "Too Many Requests" in message


def cookie_params(cookies: sign_in.Cookies | None) -> dict:
    """D-071: the sign-in for yt-dlp; a cookies.txt that is not there is said
    here, before yt-dlp quietly carries on without it."""
    if cookies is None:
        return {}
    if cookies.file is not None and not cookies.file.is_file():
        raise CookiesUnreadable(f"There is no cookies file at {cookies.file}.")
    return cookies.params()


def unreadable_cookies(error: Exception, cookies: sign_in.Cookies | None) -> CookiesUnreadable | None:
    """D-071: yt-dlp's CookieLoadError, said with the browser or file and what to try.
    yt-dlp reports it and raises a DownloadError while handling it, so it is
    looked for in the chain; its own context is the cause."""
    loading = error
    while loading is not None and type(loading).__name__ != "CookieLoadError":
        loading = loading.__cause__ or loading.__context__
    if cookies is None or loading is None:
        return None
    cause = str(loading.__context__ or error).strip().removeprefix("ERROR: ")
    if cookies.browser:
        return CookiesUnreadable(
            f"Could not read the login from {cookies.browser.capitalize()} ({cause}). "
            + sign_in.browser_advice(cookies.browser)
        )
    return CookiesUnreadable(f"Could not read the cookies file {cookies.file} ({cause}).")


def ytdlp(params: dict, call, what: str, out: Output, cookies: sign_in.Cookies | None = None, url: str = ""):
    """Run `call(ydl)` on a YoutubeDL with `params`, retrying HTTP 429 with
    exponential backoff. Returns what `call` returned and how many retries it
    took; raises RateLimited, SignInRequired or CookiesUnreadable (D-071), or
    FetchError with yt-dlp's own message.

    `cookies`, when None, is what Settings chose (D-071)."""
    cookies = cookies or sign_in.configured()
    params = {"quiet": True, "no_warnings": True, "noprogress": True, "logger": _Quiet(),
              **impersonation_params(), **portable_params(), **cookie_params(cookies), **params}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with in_portable_cache(), youtube_dl(params) as ydl:
                return call(ydl), attempt - 1
        except Exception as error:  # yt-dlp's DownloadError, or anything under it
            unreadable = unreadable_cookies(error, cookies)
            if unreadable is not None:
                raise unreadable from error
            message = str(error).strip()
            if "unsupported url" in message.lower():  # D-079: no extractor for it
                raise UnsupportedSite(UNSUPPORTED) from error
            plainly = sign_in_needed(message, url, cookies)
            if plainly:
                raise SignInRequired(plainly, message) from error
            if not is_rate_limited(message):
                raise FetchError(f"{what} failed: {message[-600:]}") from error
        if attempt == MAX_ATTEMPTS:
            raise RateLimited(f"{what}: HTTP 429 on all {MAX_ATTEMPTS} attempts")
        wait = BACKOFF_SECONDS * 2 ** (attempt - 1)
        out.countdown(wait, f"HTTP 429 on {what} (attempt {attempt}/{MAX_ATTEMPTS})", sleep)
    raise AssertionError("unreachable")


def download(url: str):
    """`ydl.download([url])`, with a non-zero result as an error."""

    def call(ydl):
        code = ydl.download([url])
        if code:
            raise FetchError(f"yt-dlp returned {code}")
        return code

    return call


def read_metadata(url: str, out: Output | None = None, cookies: sign_in.Cookies | None = None) -> Metadata:
    """What the platform says about the video. Both steps need it."""
    data, _ = ytdlp(
        {"skip_download": True},
        lambda ydl: ydl.extract_info(url, download=False),
        "reading the video",
        out or Output(),
        cookies,
        url,
    )
    return Metadata(
        id=data.get("id", ""),
        title=data.get("title", ""),
        channel=data.get("uploader", ""),
        published=data.get("upload_date", ""),
        duration=data.get("duration", 0) or 0,
        manual_captions=tuple(sorted((data.get("subtitles") or {}).keys())),
        automatic_captions=tuple(sorted((data.get("automatic_captions") or {}).keys())),
        language=data.get("language") or "",
        site=site_name(url=url, extractor=data.get("extractor_key") or data.get("extractor") or ""),
        audio=audio_offered(data),
    )


def audio_offered(data: dict) -> str:
    """D-078: what `fetch --list` says about the audio: an audio-only format
    (what step 2 downloads first), or audio inside a video format, or ""."""
    formats = data.get("formats") or ([data] if data.get("url") else [])
    has = lambda codec: codec not in (None, "none")  # noqa: E731
    only = [f for f in formats if has(f.get("acodec")) and f.get("vcodec") == "none"]
    if only:
        return f"audio only ({', '.join(dict.fromkeys(f.get('ext') or '?' for f in only))})"
    if any(f.get("acodec") != "none" for f in formats):
        return "with the video"
    return ""


#: D-045: YouTube's suffix for the automatic caption in the spoken language.
ORIGINAL_SUFFIX = "-orig"
MANUAL = "manual"
AUTOMATIC = "automatica"
AUTOMATIC_ORIGINAL = "automatica original"
#: D-074: YouTube's automatic dubbing adds an `-orig` track per dubbed audio;
#: only the one in the video's own language is the original.
AUTOMATIC_DUBBED = "automatica dublada"


def original_language(meta: Metadata) -> str:
    """D-074: the base of the `-orig` track in the video's own language (yt-dlp's
    `language`), or "" when that is unknown or matches no `-orig` track; then
    every `-orig` track counts as original, as before."""
    spoken = meta.language.lower()
    if not spoken:
        return ""
    bases = [c[: -len(ORIGINAL_SUFFIX)] for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)]
    for base in bases:
        if base.lower() == spoken:
            return base
    for base in bases:
        if base.split("-")[0].lower() == spoken.split("-")[0]:
            return base
    return ""


def is_dubbed(meta: Metadata, code: str) -> bool:
    """D-074: an `-orig` track of a dubbed audio, not of the video's own."""
    original = original_language(meta)
    return bool(original) and code.endswith(ORIGINAL_SUFFIX) and code[: -len(ORIGINAL_SUFFIX)] != original


def video_language(meta: Metadata) -> tuple[str, bool]:
    """D-080: the caption language when `--lang` is not given, the video's own,
    and whether it was a guess.

    yt-dlp's `language` (as the matching `-orig` track spells it, when there is
    one). Without it, in a fixed order: the only `-orig` track, when there is
    exactly one; else the only manual track, when there is exactly one; else
    DEFAULT_LANG, which is the guess the caller says it made.
    """
    if meta.language:
        spoken = original_language(meta) or meta.language
        codes = {c[: -len(ORIGINAL_SUFFIX)] if c.endswith(ORIGINAL_SUFFIX) else c
                 for c in meta.manual_captions + meta.automatic_captions}
        base = spoken.split("-")[0]
        # `pt-BR` with only `pt` tracks: ask for the base, which finds them.
        if spoken not in codes and any(c.split("-")[0] == base for c in codes):
            return base, False
        return spoken, False
    orig = [c for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)]
    if len(orig) == 1:
        return orig[0][: -len(ORIGINAL_SUFFIX)], False
    if len(meta.manual_captions) == 1:
        return meta.manual_captions[0], False
    return DEFAULT_LANG, True


def unknown_language_notice() -> str:
    return f"the video's language is unknown: using '{DEFAULT_LANG}' (--lang chooses another)"


def choose_language(meta: Metadata, wanted: str, out: Output | None = None) -> tuple[str, str]:
    """Return (code, source), in D-045's order.

    1. the automatic caption of the spoken language, `<lang>-orig`;
    2. a manual `<lang>`;
    3. D-074: the automatic caption of a dubbed audio, `<lang>-orig` when
       `<lang>` is not the video's own language;
    4. an automatic `<lang>`, which is a machine translation whenever a
       `-orig` track of another language exists.

    Within each, exact match first. When only a regional variant exists, say so
    before choosing: asking for `pt` with both `pt-BR` and `pt-PT` available has
    no obvious answer, and picking alphabetically in silence decides by accident.
    """
    out = out or Output()
    orig = [c for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)]
    original = tuple(c[: -len(ORIGINAL_SUFFIX)] for c in orig if not is_dubbed(meta, c))
    dubbed = tuple(c[: -len(ORIGINAL_SUFFIX)] for c in orig if is_dubbed(meta, c))
    translated = tuple(c for c in meta.automatic_captions if not c.endswith(ORIGINAL_SUFFIX))
    for available, source, suffix in (
        (original, AUTOMATIC_ORIGINAL, ORIGINAL_SUFFIX),
        (meta.manual_captions, MANUAL, ""),
        (dubbed, AUTOMATIC_DUBBED, ORIGINAL_SUFFIX),
        (translated, AUTOMATIC, ""),
    ):
        if wanted in available:
            return wanted + suffix, source
        variants = sorted(c for c in available if c.split("-")[0] == wanted)
        if variants:
            if len(variants) > 1:
                out.warn(
                    f"'{wanted}' has more than one variant ({', '.join(variants)}). "
                    f"choosing '{variants[0]}'. pass --lang with the exact variant "
                    f"if you want another."
                )
            return variants[0] + suffix, source
    return "", ""


#: D-062: language names for the track list, by base code; others show their code.
LANGUAGE_NAMES = {
    "pt": "Portuguese", "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
}


def language_name(code: str) -> str:
    """`pt` is Portuguese, `pt-BR` is Portuguese (pt-BR), `xx` stays `xx`."""
    base = code.split("-")[0]
    name = LANGUAGE_NAMES.get(base)
    if name is None:
        return code
    return name if code == base else f"{name} ({code})"


@dataclass(frozen=True)
class Track:
    """One caption track, as `--track` names it and as a person reads it."""

    code: str  # yt-dlp's: `pt-orig`, `pt`, `en`
    source: str  # MANUAL, AUTOMATIC, AUTOMATIC_ORIGINAL (D-045) or AUTOMATIC_DUBBED (D-074)
    translated: bool = False  # automatic, beside an original-audio track

    @property
    def base(self) -> str:
        """The language part, without `-orig`: `pt`, `en-US`."""
        return self.code[: -len(ORIGINAL_SUFFIX)] if self.code.endswith(ORIGINAL_SUFFIX) else self.code

    @property
    def name(self) -> str:
        if self.source == AUTOMATIC_ORIGINAL:
            return f"{language_name(self.base)}, original audio (automatic)"
        if self.source == AUTOMATIC_DUBBED:
            return f"{language_name(self.base)}, dubbed audio (automatic)"
        if self.source == MANUAL:
            return f"{language_name(self.code)} (written by the channel)"
        return f"{language_name(self.code)} (automatic{' translation' if self.translated else ''})"


def tracks(meta: Metadata) -> tuple[list[Track], list[Track]]:
    """D-062: (the tracks to list, the automatic translations), in D-045's order.

    Listed: the original-audio tracks, the dubbed-audio ones (D-074), the
    manual ones, and the plain automatic ones when the video has no `-orig`
    track (then they are not translations). A code with a manual track is
    listed once, as manual, which is what `--track` takes for it.

    D-074: when yt-dlp names the video's language, the list goes by language:
    that language first (its original-audio track, then its manual one), then
    English, then the rest, each in the order above.
    """
    orig = [c for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)]
    originals = [Track(c, AUTOMATIC_ORIGINAL) for c in orig if not is_dubbed(meta, c)]
    dubbed = [Track(c, AUTOMATIC_DUBBED) for c in orig if is_dubbed(meta, c)]
    manual = [Track(c, MANUAL) for c in meta.manual_captions]
    automatic = [
        Track(c, AUTOMATIC, translated=bool(orig))
        for c in meta.automatic_captions
        if not c.endswith(ORIGINAL_SUFFIX) and c not in meta.manual_captions
    ]
    if not orig:
        return manual + automatic, []
    listed = originals + dubbed + manual
    spoken = original_language(meta).split("-")[0].lower()
    if spoken:
        def group(track: Track) -> int:
            base = track.base.split("-")[0].lower()
            return 0 if base == spoken else 1 if base == "en" else 2

        listed.sort(key=group)  # stable: the order above, within each language
    return listed, automatic


def track_named(meta: Metadata, code: str) -> Track | None:
    """`--track`: the track with exactly this code, manual first, or None."""
    if code.endswith(ORIGINAL_SUFFIX):
        if code not in meta.automatic_captions:
            return None
        return Track(code, AUTOMATIC_DUBBED if is_dubbed(meta, code) else AUTOMATIC_ORIGINAL)
    if code in meta.manual_captions:
        return Track(code, MANUAL)
    return Track(code, AUTOMATIC) if code in meta.automatic_captions else None


def summarise(codes: tuple[str, ...]) -> str:
    if not codes:
        return "none"
    if len(codes) <= 12:
        return ", ".join(codes)
    return f"{', '.join(codes[:12])} ... and {len(codes) - 12} more"


def caption_params(code: str, source: str, target: Path) -> dict:
    """The YoutubeDL options for a subtitle download, as the platform serves it:
    what `--write-subs` or `--write-auto-subs`, `--skip-download`, `--sub-langs`
    and `--output` were on the command line.

    Deliberately no conversion option: that hands the job to ffmpeg, and the
    caption path should not need a system binary. WebVTT is converted in Python
    by `subtitles.vtt_to_lines`. Nothing calls ffmpeg: faster-whisper decodes audio through PyAV.
    """
    return {
        "writesubtitles": source == MANUAL,
        "writeautomaticsub": source != MANUAL,
        "skip_download": True,
        "subtitleslangs": [code],
        "outtmpl": {"default": str(target / f"{SUBTITLE_STEM}.%(ext)s")},
    }


def download_caption(
    url: str, code: str, source: str, target: Path, out: Output | None = None,
    cookies: sign_in.Cookies | None = None,
) -> tuple[Path, int]:
    """The subtitle file, and how many 429 retries it took."""
    _, retries = ytdlp(
        caption_params(code, source, target), download(url), "the caption download", out or Output(), cookies, url
    )
    found = next(
        (
            path
            for suffix in SUBTITLE_SUFFIXES
            for path in sorted(target.glob(f"{SUBTITLE_STEM}*{suffix}"))
        ),
        None,
    )
    if found is None:
        raise FetchError(
            "yt-dlp finished without error but no subtitle file appeared "
            f"({', '.join(SUBTITLE_SUFFIXES)})"
        )
    # yt-dlp writes legenda.<lang>.<ext>; the fixed name saves the reader from
    # having to know which language came out. The language stays in the header.
    fixed = target / f"{SUBTITLE_STEM}{found.suffix}"
    if found != fixed:
        found.replace(fixed)
        found = fixed
    return found, retries


def clear_partial_audio(target: Path) -> list[Path]:
    """D-059: what an earlier attempt left of the audio (`audio.*`, `*.part`)."""
    stale = sorted({*target.glob("audio.*"), *target.glob("*.part")})
    for path in stale:
        path.unlink(missing_ok=True)
    return stale


def is_range_error(message: str) -> bool:
    """HTTP 416: a resumed download asked for bytes past the end of the file."""
    return "HTTP Error 416" in message or "Requested range not satisfiable" in message


def download_audio(
    url: str, target: Path, out: Output | None = None, cookies: sign_in.Cookies | None = None
) -> Path:
    """Download the audio track without converting, which needs no ffmpeg.

    D-059: always from zero. A file left by an earlier attempt is deleted first,
    yt-dlp is told not to resume (`continuedl`), and an HTTP 416 still answered
    is met once more from a clean directory.
    """
    out = out or Output()
    params = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "nopart": True,
        "continuedl": False,
        "outtmpl": {"default": str(target / "audio.%(ext)s")},
    }
    if clear_partial_audio(target):
        out.info("removed an incomplete audio file from an earlier attempt")
    try:
        ytdlp(params, download(url), "the audio download", out, cookies, url)
    except FetchError as error:
        if not is_range_error(str(error)):
            raise
        clear_partial_audio(target)
        out.info("the audio download asked for a range the server does not have; starting over")
        ytdlp(params, download(url), "the audio download", out, cookies, url)
    found = sorted(target.glob("audio.*"))
    if not found:
        raise FetchError("the audio download finished without error but no audio appeared")
    return found[-1]


# --------------------------------------------------------------------------- speech


#: What `fetch` says before the first download of a model, by size.
MODEL_SIZES = {"tiny": "75 MB", "base": "145 MB", "small": "485 MB", "medium": "1.5 GB",
               "large-v2": "3 GB", "large-v3": "3 GB"}


def quiet_hugging_face() -> None:
    """Hugging Face's warnings say nothing a person can act on here (symlinks on
    Windows, unauthenticated requests). Silenced before anything imports it."""
    import os
    import warnings

    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    warnings.filterwarnings("ignore", category=UserWarning, module=r"huggingface_hub(\.|$)")
    warnings.filterwarnings("ignore", message=r".*rich is experimental.*")


def model_path(model: str, out: Output) -> str:
    """The model's local folder, downloading it the first time with one line of
    our own and a progress bar. faster-whisper's own download shows nothing."""
    from faster_whisper.utils import _MODELS, download_model  # the ingest extra

    try:
        return download_model(model, local_files_only=True)
    except Exception:  # not in the cache yet
        pass
    size = MODEL_SIZES.get(model, "")
    out.info(f"downloading the speech model ({f'about {size}, ' if size else ''}first time only)…")
    import huggingface_hub

    tqdm_class = None
    if out.fancy:
        from tqdm.rich import tqdm as tqdm_class  # a rich progress bar
    else:  # a pipe or a file: no bar at all, rather than tqdm's carriage returns
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()
    return huggingface_hub.snapshot_download(
        _MODELS.get(model, model),
        # The files faster-whisper's download_model asks for.
        allow_patterns=["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"],
        tqdm_class=tqdm_class,
    )


def load_whisper(model: str, out: Output | None = None):
    """The faster-whisper model. Replaced in tests by a fake transcriber."""
    quiet_hugging_face()
    from faster_whisper import WhisperModel  # the ingest extra, imported lazily

    return WhisperModel(model_path(model, out or Output()), device="cpu", compute_type="int8")


def run_selftest_audio(path: Path) -> int:
    """`fetch --selftest-audio FILE` (hidden): decode FILE the way transcription
    does, with no model and no network. The release workflow runs it inside the
    full executable to prove its audio stack works (D-058)."""
    try:
        from faster_whisper import decode_audio  # the ingest extra
    except ImportError as error:
        print(f"selftest: faster-whisper does not import: {error}", file=sys.stderr)
        return 1
    try:
        samples = decode_audio(str(path))
    except Exception as error:
        print(f"selftest: decoding {path} failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(f"selftest: decoded {len(samples)} samples from {path.name}")
    return 0


def duration_text(seconds: int) -> str:
    """`28min53s`; D-079: "unknown" when the site gave none (Instagram)."""
    if not seconds:
        return "unknown"
    return f"{seconds // 60}min{seconds % 60:02d}s"


def transcribe(audio: Path, lang: str, model: str, out: Output | None = None) -> tuple[str, float]:
    """Local speech recognition, as `m:ss text` lines, and the audio's length
    in seconds as the decoder measured it (D-079), 0 when it says nothing.

    `vad_filter` is required, not optional. Without it a stretch with no speech,
    such as a jingle or background music, produces text nobody said: measured
    against a pure 440Hz tone, which returned an invented sentence without the
    filter and no segment at all with it. That is the only way speech
    recognition invents, and it is mitigable.
    """
    out = out or Output()
    out.info(f"loading speech model '{model}'")
    engine = load_whisper(model, out)
    segments, info = engine.transcribe(
        str(audio), language=lang.split("-")[0], vad_filter=True, condition_on_previous_text=False
    )
    lines = []
    done = 0.0
    with out.progress(total=float(info.duration or 0), description="transcribing") as advance:
        for segment in segments:
            advance(max(segment.end - done, 0.0))
            done = max(done, segment.end)
            text = segment.text.strip()
            if not text:
                continue
            minutes, seconds = divmod(int(segment.start), 60)
            lines.append(f"{minutes}:{seconds:02d} {text}")
    out.info(f"segments with speech: {len(lines)}")
    return "\n".join(lines), float(info.duration or 0)


def measured(meta: Metadata, seconds: float, out: Output) -> Metadata:
    """D-079: a site that gave no duration gets the audio's own, said and kept."""
    if meta.duration or not seconds:
        return meta
    meta = replace(meta, duration=round(seconds), duration_from_audio=True)
    out.detail("duration", f"{duration_text(meta.duration)} (measured from the audio)", "number")
    return meta


# --------------------------------------------------------------------------- the chain


def save_meta(
    target: Path, meta: Metadata, url: str | None, step: Step | None = None, path: Path | None = None
) -> Path:
    """D-022: runs/<id>/meta.yaml, with the step of D-036 that produced the text,
    and (D-038) whether the input was a url or a local file."""
    extra = {"source": "file", "path": str(path)} if path is not None else {"source": "url"}
    if meta.duration:  # D-079: in seconds, when known; measured when the site gave none
        extra["duration"] = meta.duration
        if meta.duration_from_audio:
            extra["duration_from"] = "audio"
    extra.update(step.meta() if step else {})
    return write_meta(target, meta.title, meta.channel, url, meta.published, extra=extra)


def local_media(source: str) -> Path | None:
    """The local file `source` names, or None if it is a url (D-038)."""
    if "://" in source:
        return None
    path = Path(source).expanduser()
    return path.resolve() if path.is_file() else None


def run_file(args: argparse.Namespace, media: Path, out: Output) -> int:
    """D-038: a local audio or video file. No platform caption, so step 2 only."""
    if args.caption_only:
        print(f"{media.name} is a local file: it has no platform caption, and "
              f"--caption-only forbids local speech recognition", file=sys.stderr)
        return 1
    if args.list:
        print("--list lists a video's platform captions; a local file has none", file=sys.stderr)
        return 2
    missing = missing_extra("faster_whisper")
    if missing:
        return report_missing(missing)

    args.lang = args.lang or DEFAULT_LANG  # no site to say the language: as before D-080
    meta = Metadata(id=media.stem, title=media.stem)
    target = fetch_dir(media.stem, args.out)  # D-018 rule 3: the file's stem
    target.mkdir(parents=True, exist_ok=True)
    out.detail("file", media, "path")
    out.detail("directory", target, "path")
    out.stage(f"step 2: {STEP_NAMES[STEP_SPEECH]}")
    step = Step(STEP_SPEECH, reason="arquivo local")
    try:
        body, seconds = transcribe(media, args.lang, args.model, out)
    except Exception as error:  # a decoder or model failure: the chain's step 3
        print(f"could not transcribe {media}: {error}", file=sys.stderr)
        return 1
    meta = measured(meta, seconds, out)
    caption = target / CAPTION_FILE
    caption.write_text(
        speech_header(meta, "", args.lang, args.model, step=step.header(), file_name=media.name)
        + body
        + "\n",
        encoding="utf-8",
    )
    out.detail("meta", save_meta(target, meta, None, step, path=media), "path")
    out.detail("text", caption, "path", note=f"(step {step.number}, {step.name})")
    return 0


def step_caption(
    args: argparse.Namespace, meta: Metadata, target: Path, out: Output, cookies: sign_in.Cookies | None = None
) -> Step:
    """Step 1: the platform's caption. Raises NoCaption, RateLimited or FetchError."""
    if getattr(args, "track", None):  # D-062: this exact track, or nothing
        track = track_named(meta, args.track)
        if track is None:
            raise NoCaption(
                f"there is no caption track '{args.track}' for this video "
                f"(manual: {summarise(meta.manual_captions)}; "
                f"automatic: {summarise(meta.automatic_captions)})"
            )
        code, source = track.code, track.source
    else:
        code, source = choose_language(meta, args.lang, out)
    if not code:
        raise NoCaption(
            f"there is no caption in '{args.lang}' for this video "
            f"(manual: {summarise(meta.manual_captions)}; "
            f"automatic: {summarise(meta.automatic_captions)})"
        )
    out.info(f"caption chosen: {code} ({source})")
    subtitle, retries = download_caption(args.url, code, source, target, out, cookies)
    step = Step(STEP_CAPTION, retries=retries, track=code, track_source=source)
    body = subtitle_to_lines(subtitle.read_text(encoding="utf-8"), subtitle.suffix)
    caption = target / CAPTION_FILE
    caption.write_text(
        caption_header(meta, args.url, source, code, step=step.header()) + body + "\n",
        encoding="utf-8",
    )
    # legenda.txt holds everything the subtitle had that the tool reads; the
    # raw file stays only when asked for.
    if getattr(args, "keep_raw", False):
        out.detail("subtitle", subtitle, "path")
    else:
        subtitle.unlink()
    return step


def step_speech(
    args: argparse.Namespace, meta: Metadata, target: Path, reason: str, out: Output,
    cookies: sign_in.Cookies | None = None,
) -> tuple[Step, Metadata]:
    """Step 2: local speech recognition, and the metadata with the measured
    duration when the site gave none (D-079). Raises FetchError."""
    if is_lite_build():  # D-057: only here, where step 2 is really needed
        raise FetchError(LITE_BUILD)
    missing = missing_extra("faster_whisper")
    if missing:
        raise FetchError(f"local speech recognition needs {', '.join(missing)} (the ingest extra)")
    audio = download_audio(args.url, target, out, cookies)
    out.detail("audio", audio, "path")
    body, seconds = transcribe(audio, args.lang, args.model, out)
    meta = measured(meta, seconds, out)  # D-079
    step = Step(STEP_SPEECH, reason=reason)
    (target / CAPTION_FILE).write_text(
        speech_header(meta, args.url, args.lang, args.model, step=step.header()) + body + "\n",
        encoding="utf-8",
    )
    keep_or_delete(audio, meta, target, keeps_audio(args), out)
    return step, meta


#: D-078: config.toml's key for Settings → "Keep the audio after transcribing".
KEEP_AUDIO = "keep_audio"


def keeps_audio(args: argparse.Namespace) -> bool:
    """`--keep-audio`, else Settings; off by default."""
    from ..runs import read_config

    return bool(getattr(args, "keep_audio", False)) or read_config().get(KEEP_AUDIO) == "yes"


def keep_or_delete(audio: Path, meta: Metadata, target: Path, keep: bool, out: Output) -> Path | None:
    """D-078: once the text is written, the audio goes, unless it is kept;
    then it is named after the video, `<id>.<ext>`."""
    if not keep:
        audio.unlink(missing_ok=True)
        out.info("the audio was deleted; --keep-audio, or Settings, keeps it")
        return None
    kept = target / f"{meta.id or audio.stem}{audio.suffix}"
    if kept != audio:
        audio.replace(kept)
    out.detail("audio kept", kept, "path")
    return kept


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "url",
        nargs="?",
        metavar="URL_OR_FILE",
        help="a video url, or a local audio or video file (which goes straight to step 2)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="print which fetch tools are installed (yt-dlp, curl_cffi, faster-whisper) and their versions",
    )
    parser.add_argument(
        "--out",
        type=Path,
        metavar="DIR",
        help="write into DIR instead of runs/<video-id>/",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--whisper",
        action="store_true",
        help="skip the platform caption: transcribe the audio locally (step 2 only)",
    )
    source.add_argument(
        "--caption-only",
        action="store_true",
        help="use the platform caption or fail; never fall back to local speech (step 1 only)",
    )
    parser.add_argument(
        "--lang",
        help="caption language code. default: the video's own language, as the site reports it "
        f"(else its only original or only manual track, else {DEFAULT_LANG})",
    )
    parser.add_argument(
        "--track",
        metavar="CODE",
        help="take exactly this caption track, as `--list` names it (`pt-orig`, `pt`, `en`); "
        "a code with a manual track takes that one. Instead of --lang's choice",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"speech recognition model: {', '.join(SPEECH_MODELS)}. "
        f"default: {DEFAULT_MODEL}. below medium it gets domain terms wrong often",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="check a link without downloading: the site, title, duration, caption tracks (or none), "
        "whether there is audio to transcribe, and whether the site asks for a login",
    )
    signed = parser.add_mutually_exclusive_group()
    signed.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        choices=sign_in.BROWSERS,
        help="use this browser's login, for a site that asks you to sign in or YouTube's bot check "
        f"({', '.join(sign_in.BROWSERS)}; Firefox works best). Instead of Settings",
    )
    signed.add_argument(
        "--cookies",
        metavar="FILE",
        help="use the login in this cookies.txt file (Netscape format). Instead of Settings",
    )
    # Hidden: for the menu, which runs fetch twice when it moves from step 1 to
    # step 2 (D-053), and for the release workflow's smoke test (D-058).
    parser.add_argument("--no-video-info", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--selftest-audio", metavar="FILE", type=Path, help=argparse.SUPPRESS)
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="after transcribing, keep the downloaded audio in the run folder as <id>.<ext>; "
        "by default it is deleted. Instead of Settings",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="keep the downloaded legenda.vtt or .srt; by default it is deleted once converted",
    )


#: D-057: what `fetch --check` reports, and what each tool is for.
CHECKED = (
    ("yt_dlp", "yt-dlp", "platform captions and audio downloads"),
    ("curl_cffi", "curl_cffi", "browser impersonation, against HTTP 429"),
    ("faster_whisper", "faster-whisper", "local speech recognition"),
)


def tool_version(module: str) -> str | None:
    """The version of an importable module, or None if it does not import.

    Read from the module itself, since a frozen executable may not carry the
    package metadata; the metadata is the fallback."""
    try:
        imported = importlib.import_module(module)
    except Exception:  # not installed, or installed but broken: not usable either way
        return None
    version = getattr(getattr(imported, "version", None), "__version__", None) or getattr(
        imported, "__version__", None
    )
    if version is None:
        from importlib.metadata import PackageNotFoundError, version as installed

        try:
            version = installed(module.replace("_", "-"))
        except PackageNotFoundError:
            version = "installed"
    return str(version)


#: What step 1's failure means, said to a person (the menu's path, --caption-only).
NO_CAPTION = "This video has no caption."
#: D-078: most sites other than YouTube have no captions at all.
FULL_CAN_TRANSCRIBE = "The full build can transcribe its audio on this computer."


TOO_MANY_REQUESTS = "YouTube is limiting downloads right now (HTTP 429)."


def no_captions(site: str) -> str:
    return f"{site} doesn't provide captions for this video." if site else NO_CAPTION


def undo_attempt(target: Path, before: set[Path], existed: bool) -> int:
    """D-059: remove what this attempt wrote under `target`, and the directory
    itself if the attempt created it and it is now empty. Files that were there
    before (an earlier run's meta.yaml, say) stay. Returns how many it removed."""
    removed = 0
    for path in sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path in before:
            continue
        if path.is_dir():
            if not any(path.iterdir()):
                path.rmdir()
        else:
            path.unlink(missing_ok=True)
            removed += 1
    if not existed and target.exists() and not any(target.iterdir()):
        target.rmdir()
    return removed


def report_sign_in(error: FetchError, args: argparse.Namespace) -> int:
    """D-071: YouTube's check, or a sign-in that could not be read, in plain
    words. The ways out name the flags, except for the menu (--no-video-info),
    which offers them as choices. Exits EXIT_SIGN_IN for YouTube's check."""
    print(error, file=sys.stderr)
    if not isinstance(error, SignInRequired):
        return 1
    if not args.no_video_info:
        print(
            "Ways out: sign in with your browser's login (--cookies-from-browser firefox, or "
            "--cookies cookies.txt; or set it once in the menu's Settings), or try again later.",
            file=sys.stderr,
        )
    return EXIT_SIGN_IN


def list_site(meta: Metadata, out: Output) -> int:
    """D-078: `fetch --list`, a quick check of a link on any site, nothing
    downloaded: the captions, whether there is audio to transcribe, and that
    the site did not ask for a login (it would have stopped earlier)."""
    if not meta.manual_captions and not meta.automatic_captions:
        out.detail("captions", f"none ({no_captions(meta.site)})")
    else:
        # D-045: the source track first and in full; the translations may be summarised.
        orig = [c for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)]
        originals = [c for c in orig if not is_dubbed(meta, c)]
        dubbed = [c for c in orig if is_dubbed(meta, c)]  # D-074
        translated = tuple(c for c in meta.automatic_captions if not c.endswith(ORIGINAL_SUFFIX))
        out.info(f"original: {', '.join(originals) or 'none'}")
        if dubbed:
            out.info(f"dubbed: {', '.join(dubbed)}")
        out.info(f"manual captions: {summarise(meta.manual_captions)}")
        out.info(f"automatic captions: {summarise(translated)}")
    out.detail("audio", meta.audio or "none offered")
    out.detail("login", "not asked")
    return 0


def run_check() -> int:
    """`fetch --check`: one line per tool, installed or not. Always exits 0."""
    width = max(len(name) for _, name, _ in CHECKED)
    for module, name, purpose in CHECKED:
        version = tool_version(module)
        print(f"{name:{width}s}  {version or 'not installed':14s}  {purpose}")
    return 0


def run(args: argparse.Namespace) -> int:
    """Fetch a caption for a video: the platform's, or local speech recognition (D-036)."""
    if args.check:
        return run_check()
    if args.selftest_audio:
        return run_selftest_audio(args.selftest_audio)
    if not args.url:
        print("fetch needs a video url or a file (or --check)", file=sys.stderr)
        return 2
    out = Output()
    if args.model not in SPEECH_MODELS:
        print(
            f"unknown speech model: {args.model!r}\nvalid: {', '.join(SPEECH_MODELS)}",
            file=sys.stderr,
        )
        return 2
    media = local_media(args.url)
    if media is not None:
        return run_file(args, media, out)
    if "://" not in args.url:
        print(f"{args.url}: no such file, and not a url", file=sys.stderr)
        return 1

    missing = missing_extra("yt_dlp")
    if missing:
        return report_missing(missing)

    cookies = sign_in.chosen(args.cookies_from_browser, args.cookies)
    try:
        meta = read_metadata(args.url, out, cookies)
    except UnsupportedSite as error:  # D-079: plainly, and nothing else
        print(error, file=sys.stderr)
        return 1
    except (SignInRequired, CookiesUnreadable) as error:
        if args.list and isinstance(error, SignInRequired):  # D-078: part of the check
            out.detail("site", site_name(error.raw, args.url))
            out.detail("login", f"asked: {error}")
            return EXIT_SIGN_IN
        return report_sign_in(error, args)
    except FetchError as error:
        print(f"could not read the video: {error}", file=sys.stderr)
        return 1
    if not args.no_video_info:  # the menu's second call has shown it already
        if args.list:
            out.detail("site", meta.site)
        out.detail("title", meta.title)
        out.detail("channel", meta.channel)
        out.detail("published", meta.published)
        out.detail("duration", duration_text(meta.duration), "number")

    if args.list:
        return list_site(meta, out)

    if not args.lang:  # D-080: the video's own language
        args.lang, guessed = video_language(meta)
        if guessed:
            out.info(unknown_language_notice())

    target = fetch_dir(meta.id, args.out)
    # D-059: what was here before this attempt, so a failure can take back
    # exactly what it added and leave an earlier run as it was.
    existed = target.exists()
    before = {p for p in target.rglob("*")} if existed else set()
    target.mkdir(parents=True, exist_ok=True)
    out.detail("directory", target, "path")

    def give_back() -> None:
        removed = undo_attempt(target, before, existed)
        if removed:
            out.info(f"removed {removed} file(s) this attempt had written")

    step = None
    failures: list[str] = []
    if args.whisper:
        reason = "pedido com --whisper"
    else:
        out.stage(f"step 1: {STEP_NAMES[STEP_CAPTION]}")
        try:
            step = step_caption(args, meta, target, out, cookies)
        except (SignInRequired, CookiesUnreadable) as error:
            # The audio would meet the same check: no use falling through.
            give_back()
            return report_sign_in(error, args)
        except NoCaption as error:
            # D-079: a site with no captions at all gets the menu's sentence; the
            # detailed line is for one with captions, none in the language asked
            # (or not the --track named).
            has_any = bool(meta.manual_captions or meta.automatic_captions)
            reason = "sem legenda na plataforma"
            plainly = str(error) if has_any or args.track else no_captions(meta.site)
            failures.append(plainly)
            if is_lite_build() and not args.caption_only and not (has_any or args.track):
                # D-078: no step 2 here, and nothing failed: say what would help.
                print(f"{plainly} {FULL_CAN_TRANSCRIBE}", file=sys.stderr)
                give_back()
                return 1
        except RateLimited as error:
            failures.append(str(error))
            reason = f"legenda falhou: HTTP 429 em {MAX_ATTEMPTS} tentativas"
            plainly = TOO_MANY_REQUESTS
        except FetchError as error:
            failures.append(str(error))
            reason, plainly = "legenda falhou", f"The caption could not be downloaded: {error}"
        if step is None:
            if args.caption_only:
                # Step 1 was all that was asked for: say why in plain words,
                # without naming flags (the menu asks its next question after).
                print(plainly, file=sys.stderr)
                give_back()
                return 1
            out.warn(failures[-1])

    if step is None:
        out.stage(f"step 2: {STEP_NAMES[STEP_SPEECH]}")
        try:
            step, meta = step_speech(args, meta, target, reason, out, cookies)
        except (SignInRequired, CookiesUnreadable) as error:
            give_back()
            return report_sign_in(error, args)
        except Exception as error:  # FetchError, or a decoder or model failure
            failures.append(str(error) if isinstance(error, FetchError) else f"{type(error).__name__}: {error}")
            print("could not get a text for this video:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            give_back()
            return 1

    caption = target / CAPTION_FILE
    out.detail("meta", save_meta(target, meta, args.url, step), "path")
    out.detail("text", caption, "path", note=f"(step {step.number}, {step.name})")
    out.detail("lines", len(caption.read_text(encoding="utf-8").splitlines()), "number")
    return 0
