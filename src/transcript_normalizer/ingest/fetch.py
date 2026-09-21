"""`transcript-normalizer fetch <url>`: a caption from the platform, or local speech.

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
from pathlib import Path

from ..runs import runs_root
from .header import Metadata, caption_header, speech_header
from .srt import srt_to_lines

CAPTION_FILE = "legenda.txt"
SRT_FILE = "legenda.srt"

DEFAULT_LANG = "pt"
DEFAULT_MODEL = "medium"
SPEECH_MODELS = ("tiny", "base", "small", "medium", "large-v2", "large-v3")

#: What each command needs from the `ingest` extra.
REQUIRES = {"yt_dlp": "yt-dlp", "faster_whisper": "faster-whisper"}


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


def run_ytdlp(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "yt_dlp", *args], capture_output=True, text=True
    )


def read_metadata(url: str) -> Metadata:
    result = run_ytdlp(["--dump-single-json", "--skip-download", url])
    if result.returncode != 0:
        print("could not read the video:", file=sys.stderr)
        print(result.stderr.strip()[:800], file=sys.stderr)
        raise SystemExit(1)
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


def choose_language(meta: Metadata, wanted: str) -> tuple[str, str]:
    """Return (code, source). A manual caption is preferred over an automatic one.

    Exact match first. When only a regional variant exists, say so before
    choosing: asking for `pt` with both `pt-BR` and `pt-PT` available has no
    obvious answer, and picking alphabetically in silence decides by accident.
    """
    for available, source in (
        (meta.manual_captions, "manual"),
        (meta.automatic_captions, "automatica"),
    ):
        if wanted in available:
            return wanted, source
        variants = sorted(c for c in available if c.split("-")[0] == wanted)
        if variants:
            if len(variants) > 1:
                print(
                    f"warning: '{wanted}' has more than one variant "
                    f"({', '.join(variants)}). choosing '{variants[0]}'. pass "
                    f"--lang with the exact variant if you want another."
                )
            return variants[0], source
    return "", ""


def summarise(codes: tuple[str, ...]) -> str:
    if not codes:
        return "none"
    if len(codes) <= 12:
        return ", ".join(codes)
    return f"{', '.join(codes[:12])} ... and {len(codes) - 12} more"


def download_caption(url: str, code: str, source: str, target: Path) -> Path:
    args = [
        "--write-subs" if source == "manual" else "--write-auto-subs",
        "--skip-download",
        "--convert-subs",
        "srt",
        "--sub-langs",
        code,
        "--output",
        str(target / "legenda.%(ext)s"),
        url,
    ]
    result = run_ytdlp(args)
    if result.returncode != 0:
        print("could not download the caption:", file=sys.stderr)
        print(result.stderr.strip()[:800], file=sys.stderr)
        raise SystemExit(1)

    found = sorted(target.glob("legenda*.srt"))
    if not found:
        print("yt-dlp finished without error but no .srt appeared", file=sys.stderr)
        raise SystemExit(1)
    # yt-dlp writes legenda.<lang>.srt; the fixed name saves the reader from
    # having to know which language came out. The language stays in the header.
    srt = found[0]
    fixed = target / SRT_FILE
    if srt != fixed:
        srt.replace(fixed)
        srt = fixed
    return srt


def download_audio(url: str, target: Path) -> Path:
    """Download the audio track without converting, which needs no ffmpeg."""
    result = run_ytdlp(
        [
            "-f",
            "bestaudio[ext=m4a]/bestaudio",
            "--no-part",
            "--output",
            str(target / "audio.%(ext)s"),
            url,
        ]
    )
    if result.returncode != 0:
        print("could not download the audio:", file=sys.stderr)
        print(result.stderr.strip()[-900:], file=sys.stderr)
        raise SystemExit(1)
    found = sorted(target.glob("audio.*"))
    if not found:
        print("download finished without error but no audio appeared", file=sys.stderr)
        raise SystemExit(1)
    return found[-1]


def transcribe(audio: Path, lang: str, model: str) -> str:
    """Local speech recognition, as `m:ss text` lines.

    `vad_filter` is required, not optional. Without it a stretch with no speech,
    such as a jingle or background music, produces text nobody said: measured
    against a pure 440Hz tone, which returned an invented sentence without the
    filter and no segment at all with it. That is the only way speech
    recognition invents, and it is mitigable.
    """
    from faster_whisper import WhisperModel  # the ingest extra, imported lazily

    print(f"transcribing with model '{model}', this can take a while")
    engine = WhisperModel(model, device="cpu", compute_type="int8")
    segments, _info = engine.transcribe(
        str(audio), language=lang, vad_filter=True, condition_on_previous_text=False
    )
    lines = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        minutes, seconds = divmod(int(segment.start), 60)
        lines.append(f"{minutes}:{seconds:02d} {text}")
    print(f"segments with speech: {len(lines)}")
    return "\n".join(lines)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("url", help="video url")
    parser.add_argument(
        "--out",
        type=Path,
        metavar="DIR",
        help="write into DIR instead of runs/<video-id>/",
    )
    parser.add_argument(
        "--whisper",
        action="store_true",
        help="ignore the platform caption and transcribe the audio locally",
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
    needed = ("yt_dlp", "faster_whisper") if args.whisper else ("yt_dlp",)
    missing = missing_extra(*needed)
    if missing:
        return report_missing(missing)

    if args.whisper and args.model not in SPEECH_MODELS:
        print(
            f"unknown speech model: {args.model!r}\nvalid: {', '.join(SPEECH_MODELS)}",
            file=sys.stderr,
        )
        return 2

    meta = read_metadata(args.url)
    print(f"\ntitle: {meta.title}")
    print(f"channel: {meta.channel}")
    print(f"published: {meta.published}")
    print(f"duration: {meta.duration // 60}min{meta.duration % 60:02d}s")

    if args.list:
        print(f"\nmanual captions: {summarise(meta.manual_captions)}")
        print(f"automatic captions: {summarise(meta.automatic_captions)}")
        return 0

    target = fetch_dir(meta.id, args.out)
    target.mkdir(parents=True, exist_ok=True)
    print(f"directory: {target}")
    caption = target / CAPTION_FILE

    if args.whisper:
        audio = download_audio(args.url, target)
        print(f"audio: {audio}")
        body = transcribe(audio, args.lang, args.model)
        caption.write_text(
            speech_header(meta, args.url, args.lang, args.model) + body + "\n",
            encoding="utf-8",
        )
        print(f"text: {caption}")
        print(
            "\nThe audio can be deleted once you have checked the text. "
            "It is not knowledge."
        )
        return 0

    code, source = choose_language(meta, args.lang)
    if not code:
        print(f"\nthere is no caption in '{args.lang}' for this video.", file=sys.stderr)
        print(f"manual: {summarise(meta.manual_captions)}", file=sys.stderr)
        print(f"automatic: {summarise(meta.automatic_captions)}", file=sys.stderr)
        print("use --list to see the whole list", file=sys.stderr)
        print(
            "\nif the video has no caption in any useful language, use --whisper "
            "for local speech recognition. Do not use an AI provider to "
            "transcribe: it summarises and fills gaps with what sounds plausible.",
            file=sys.stderr,
        )
        return 2

    print(f"caption chosen: {code} ({source})")
    srt = download_caption(args.url, code, source, target)
    caption.write_text(
        caption_header(meta, args.url, source, code)
        + srt_to_lines(srt.read_text(encoding="utf-8"))
        + "\n",
        encoding="utf-8",
    )
    print(f"\nsrt:   {srt}")
    print(f"text:  {caption}")
    print(f"lines: {len(caption.read_text(encoding='utf-8').splitlines())}")
    return 0
