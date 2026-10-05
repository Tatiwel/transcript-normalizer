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
import importlib.util
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ..catalog import write_meta
from ..runs import runs_root
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


def report_missing(missing: list[str]) -> int:
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


def impersonation_args() -> list[str]:
    """Browser impersonation, which is what gets past most HTTP 429s. It needs
    curl_cffi, part of the ingest extra; without it yt-dlp runs as before."""
    return ["--impersonate", "chrome"] if importlib.util.find_spec("curl_cffi") else []


def run_ytdlp(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "yt_dlp", *impersonation_args(), *args],
        capture_output=True,
        text=True,
    )


def is_rate_limited(result: subprocess.CompletedProcess) -> bool:
    text = f"{result.stderr}\n{result.stdout}"
    return "HTTP Error 429" in text or "Too Many Requests" in text


def ytdlp(args: list[str], what: str, out: Output) -> tuple[subprocess.CompletedProcess, int]:
    """Run yt-dlp, retrying HTTP 429 with exponential backoff. Returns the result
    and how many retries it took; raises RateLimited or FetchError otherwise."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = run_ytdlp(args)
        if result.returncode == 0:
            return result, attempt - 1
        if not is_rate_limited(result):
            raise FetchError(f"{what} failed: {result.stderr.strip()[-600:]}")
        if attempt == MAX_ATTEMPTS:
            raise RateLimited(f"{what}: HTTP 429 on all {MAX_ATTEMPTS} attempts")
        wait = BACKOFF_SECONDS * 2 ** (attempt - 1)
        out.countdown(wait, f"HTTP 429 on {what} (attempt {attempt}/{MAX_ATTEMPTS})", sleep)
    raise AssertionError("unreachable")


def read_metadata(url: str, out: Output | None = None) -> Metadata:
    """What the platform says about the video. Both steps need it."""
    result, _ = ytdlp(["--dump-single-json", "--skip-download", url], "reading the video", out or Output())
    data = json.loads(result.stdout)
    return Metadata(
        id=data.get("id", ""),
        title=data.get("title", ""),
        channel=data.get("uploader", ""),
        published=data.get("upload_date", ""),
        duration=data.get("duration", 0) or 0,
        manual_captions=tuple(sorted((data.get("subtitles") or {}).keys())),
        automatic_captions=tuple(sorted((data.get("automatic_captions") or {}).keys())),
    )


#: D-045: YouTube's suffix for the automatic caption in the spoken language.
ORIGINAL_SUFFIX = "-orig"
MANUAL = "manual"
AUTOMATIC = "automatica"
AUTOMATIC_ORIGINAL = "automatica original"


def choose_language(meta: Metadata, wanted: str, out: Output | None = None) -> tuple[str, str]:
    """Return (code, source), in D-045's order.

    1. the automatic caption of the spoken language, `<lang>-orig`;
    2. a manual `<lang>`;
    3. an automatic `<lang>`, which is a machine translation whenever a
       `-orig` track of another language exists.

    Within each, exact match first. When only a regional variant exists, say so
    before choosing: asking for `pt` with both `pt-BR` and `pt-PT` available has
    no obvious answer, and picking alphabetically in silence decides by accident.
    """
    out = out or Output()
    original = tuple(
        c[: -len(ORIGINAL_SUFFIX)] for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX)
    )
    translated = tuple(c for c in meta.automatic_captions if not c.endswith(ORIGINAL_SUFFIX))
    for available, source, suffix in (
        (original, AUTOMATIC_ORIGINAL, ORIGINAL_SUFFIX),
        (meta.manual_captions, MANUAL, ""),
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


def summarise(codes: tuple[str, ...]) -> str:
    if not codes:
        return "none"
    if len(codes) <= 12:
        return ", ".join(codes)
    return f"{', '.join(codes[:12])} ... and {len(codes) - 12} more"


def caption_args(url: str, code: str, source: str, target: Path) -> list[str]:
    """The yt-dlp arguments for a subtitle download, as the platform serves it.

    Deliberately no conversion flag: that hands the job to ffmpeg, and the
    caption path should not need a system binary. WebVTT is converted in Python
    by `subtitles.vtt_to_lines`. Nothing calls ffmpeg: faster-whisper decodes audio through PyAV.
    """
    return [
        "--write-subs" if source == MANUAL else "--write-auto-subs",
        "--skip-download",
        "--sub-langs",
        code,
        "--output",
        str(target / f"{SUBTITLE_STEM}.%(ext)s"),
        url,
    ]


def download_caption(
    url: str, code: str, source: str, target: Path, out: Output | None = None
) -> tuple[Path, int]:
    """The subtitle file, and how many 429 retries it took."""
    _, retries = ytdlp(caption_args(url, code, source, target), "the caption download", out or Output())
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


def download_audio(url: str, target: Path, out: Output | None = None) -> Path:
    """Download the audio track without converting, which needs no ffmpeg."""
    ytdlp(
        ["-f", "bestaudio[ext=m4a]/bestaudio", "--no-part", "--output", str(target / "audio.%(ext)s"), url],
        "the audio download",
        out or Output(),
    )
    found = sorted(target.glob("audio.*"))
    if not found:
        raise FetchError("the audio download finished without error but no audio appeared")
    return found[-1]


# --------------------------------------------------------------------------- speech


def load_whisper(model: str):
    """The faster-whisper model. Replaced in tests by a fake transcriber."""
    from faster_whisper import WhisperModel  # the ingest extra, imported lazily

    return WhisperModel(model, device="cpu", compute_type="int8")


def transcribe(audio: Path, lang: str, model: str, out: Output | None = None) -> str:
    """Local speech recognition, as `m:ss text` lines.

    `vad_filter` is required, not optional. Without it a stretch with no speech,
    such as a jingle or background music, produces text nobody said: measured
    against a pure 440Hz tone, which returned an invented sentence without the
    filter and no segment at all with it. That is the only way speech
    recognition invents, and it is mitigable.
    """
    out = out or Output()
    out.info(f"loading speech model '{model}' (the first run downloads it)")
    engine = load_whisper(model)
    segments, info = engine.transcribe(
        str(audio), language=lang, vad_filter=True, condition_on_previous_text=False
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
    return "\n".join(lines)


# --------------------------------------------------------------------------- the chain


def save_meta(
    target: Path, meta: Metadata, url: str | None, step: Step | None = None, path: Path | None = None
) -> Path:
    """D-022: runs/<id>/meta.yaml, with the step of D-036 that produced the text,
    and (D-038) whether the input was a url or a local file."""
    extra = {"source": "file", "path": str(path)} if path is not None else {"source": "url"}
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

    meta = Metadata(id=media.stem, title=media.stem)
    target = fetch_dir(media.stem, args.out)  # D-018 rule 3: the file's stem
    target.mkdir(parents=True, exist_ok=True)
    out.info(f"file: {media}")
    out.info(f"directory: {target}")
    out.stage(f"step 2: {STEP_NAMES[STEP_SPEECH]}")
    step = Step(STEP_SPEECH, reason="arquivo local")
    try:
        body = transcribe(media, args.lang, args.model, out)
    except Exception as error:  # a decoder or model failure: the chain's step 3
        print(f"could not transcribe {media}: {error}", file=sys.stderr)
        return 1
    caption = target / CAPTION_FILE
    caption.write_text(
        speech_header(meta, "", args.lang, args.model, step=step.header(), file_name=media.name)
        + body
        + "\n",
        encoding="utf-8",
    )
    out.info(f"meta:  {save_meta(target, meta, None, step, path=media)}")
    out.info(f"text:  {caption} (step {step.number}, {step.name})")
    return 0


def step_caption(args: argparse.Namespace, meta: Metadata, target: Path, out: Output) -> Step:
    """Step 1: the platform's caption. Raises NoCaption, RateLimited or FetchError."""
    code, source = choose_language(meta, args.lang, out)
    if not code:
        raise NoCaption(
            f"there is no caption in '{args.lang}' for this video "
            f"(manual: {summarise(meta.manual_captions)}; "
            f"automatic: {summarise(meta.automatic_captions)})"
        )
    out.info(f"caption chosen: {code} ({source})")
    subtitle, retries = download_caption(args.url, code, source, target, out)
    step = Step(STEP_CAPTION, retries=retries, track=code, track_source=source)
    body = subtitle_to_lines(subtitle.read_text(encoding="utf-8"), subtitle.suffix)
    caption = target / CAPTION_FILE
    caption.write_text(
        caption_header(meta, args.url, source, code, step=step.header()) + body + "\n",
        encoding="utf-8",
    )
    out.info(f"subtitle: {subtitle}")
    return step


def step_speech(
    args: argparse.Namespace, meta: Metadata, target: Path, reason: str, out: Output
) -> Step:
    """Step 2: local speech recognition. Raises FetchError."""
    missing = missing_extra("faster_whisper")
    if missing:
        raise FetchError(f"local speech recognition needs {', '.join(missing)} (the ingest extra)")
    audio = download_audio(args.url, target, out)
    out.info(f"audio: {audio}")
    body = transcribe(audio, args.lang, args.model, out)
    step = Step(STEP_SPEECH, reason=reason)
    (target / CAPTION_FILE).write_text(
        speech_header(meta, args.url, args.lang, args.model, step=step.header()) + body + "\n",
        encoding="utf-8",
    )
    out.info("the audio can be deleted once you have checked the text; it is not knowledge")
    return step


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "url",
        metavar="URL_OR_FILE",
        help="a video url, or a local audio or video file (which goes straight to step 2)",
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
        "--lang", default=DEFAULT_LANG, help=f"caption language code. default: {DEFAULT_LANG}"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"speech recognition model: {', '.join(SPEECH_MODELS)}. "
        f"default: {DEFAULT_MODEL}. below medium it gets domain terms wrong often",
    )
    parser.add_argument(
        "--list", action="store_true", help="only list the caption languages available"
    )


def run(args: argparse.Namespace) -> int:
    """Fetch a caption for a video: the platform's, or local speech recognition (D-036)."""
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

    try:
        meta = read_metadata(args.url, out)
    except FetchError as error:
        print(f"could not read the video: {error}", file=sys.stderr)
        return 1
    out.info(f"title: {meta.title}")
    out.info(f"channel: {meta.channel}")
    out.info(f"published: {meta.published}")
    out.info(f"duration: {meta.duration // 60}min{meta.duration % 60:02d}s")

    if args.list:
        # D-045: the source track first and in full; the translations may be summarised.
        originals = tuple(c for c in meta.automatic_captions if c.endswith(ORIGINAL_SUFFIX))
        translated = tuple(c for c in meta.automatic_captions if not c.endswith(ORIGINAL_SUFFIX))
        out.info(f"original: {', '.join(originals) or 'none'}")
        out.info(f"manual captions: {summarise(meta.manual_captions)}")
        out.info(f"automatic captions: {summarise(translated)}")
        return 0

    target = fetch_dir(meta.id, args.out)
    target.mkdir(parents=True, exist_ok=True)
    out.info(f"directory: {target}")

    step = None
    failures: list[str] = []
    if args.whisper:
        reason = "pedido com --whisper"
    else:
        out.stage(f"step 1: {STEP_NAMES[STEP_CAPTION]}")
        try:
            step = step_caption(args, meta, target, out)
        except NoCaption as error:
            failures.append(str(error))
            reason = "sem legenda na plataforma"
        except RateLimited as error:
            failures.append(str(error))
            reason = f"legenda falhou: HTTP 429 em {MAX_ATTEMPTS} tentativas"
        except FetchError as error:
            failures.append(str(error))
            reason = "legenda falhou"
        if step is None:
            out.warn(failures[-1])
            if args.caption_only:
                print(
                    f"no platform caption, and --caption-only forbids local speech "
                    f"recognition: {failures[-1]}",
                    file=sys.stderr,
                )
                return 1

    if step is None:
        out.stage(f"step 2: {STEP_NAMES[STEP_SPEECH]}")
        try:
            step = step_speech(args, meta, target, reason, out)
        except FetchError as error:
            failures.append(str(error))
            print("could not get a text for this video:", file=sys.stderr)
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1

    caption = target / CAPTION_FILE
    out.info(f"meta:  {save_meta(target, meta, args.url, step)}")
    out.info(f"text:  {caption} (step {step.number}, {step.name})")
    out.info(f"lines: {len(caption.read_text(encoding='utf-8').splitlines())}")
    return 0
