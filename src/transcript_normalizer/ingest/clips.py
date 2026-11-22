"""D-101: a passage written twice, transcribed again on its own.

D-092's lesson: the long file wrote a passage twice at 44:29 and lost what was
said there, and the same model on a clip of 44:02 to 44:33 got it right. So for
each passage D-092 finds, the stretch around it is cut from the same file and
transcribed alone, with the same model and language, and written to
needs-review/repeats/ beside the warning. It is help for whoever listens:
legenda.txt is not changed.

The window starts BEFORE seconds before the earliest first copy, since what
was lost may have been said before the passage the transcription repeated (in
that lesson, a sentence between 44:02 and 44:06), and ends AFTER seconds after
the line where the second copy ends.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from .. import stamps
from . import repeats as repeated

#: Seconds before the earliest first copy the window starts.
BEFORE = 15
#: Seconds after the line where the second copy ends the window ends.
AFTER = 10
#: The folder in needs-review/ the clips go to.
CLIPS_DIR = "repeats"
#: The rate faster-whisper takes samples at.
SAMPLE_RATE = 16000

#: (media, start seconds, end seconds) -> `m:ss text` lines, timed from the file's start.
Transcriber = Callable[[Path, float, float], str]


def stamp(seconds: float) -> str:
    return stamps.clock(seconds)  # D-103


def window(repeat: repeated.Repeat) -> tuple[int, int]:
    """The stretch transcribed again, in whole seconds from the file's start."""
    start = stamps.seconds(repeat.source_start) - BEFORE
    return max(start, 0), stamps.seconds(repeat.end) + AFTER


def file_name(repeat: repeated.Repeat) -> str:
    """`44-29.txt`: the second copy's time, with no colon (Windows has none in names)."""
    return stamps.in_name(repeat.start) + ".txt"


def decode_window(path: Path, start: float, end: float):
    """The samples of `path` from `start` to `end` seconds, mono, at 16 kHz,
    as float32, the way faster-whisper decodes a whole file. Only the stretch
    is decoded: the file is not read from its beginning."""
    import av  # faster-whisper's own decoder, in the ingest extra
    import numpy as np

    chunks = []
    with av.open(str(path)) as container:
        stream = container.streams.audio[0]
        # A whole file's transcription counts from its first audio sample, so
        # times here are from the audio stream's start, which a file may put
        # later than the container's (or a little before, for an encoder's delay).
        origin = float(stream.start_time * stream.time_base) if stream.start_time is not None else 0.0
        resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
        # The container's clock, in microseconds; it lands on a keyframe at or before.
        container.seek(int(max(origin + start - 1, 0) * av.time_base))
        position = None  # seconds of the next resampled sample, from the stream's start
        for frame in container.decode(stream):
            if position is None:
                position = float(frame.time) - origin if frame.time is not None else max(start - 1, 0)
            for resampled in resampler.resample(frame):
                samples = resampled.to_ndarray().reshape(-1)
                chunks.append((position, samples))
                position += len(samples) / SAMPLE_RATE
            if position is not None and position >= end:
                break
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    first = chunks[0][0]
    audio = np.concatenate([samples for _, samples in chunks]).astype(np.float32) / 32768.0
    begin = max(int(round((start - first) * SAMPLE_RATE)), 0)
    stop = max(int(round((end - first) * SAMPLE_RATE)), begin)
    return audio[begin:stop]


#: How the file transcribed again is known to be the one legenda.txt came from.
SAME_RUN = "Transcribed again right after legenda.txt was written, from the same file."
CHECKED = "The file was checked by its fingerprint (sha256 and size) against legenda.txt's header."
UNCHECKED = ("The file was NOT checked by its fingerprint: legenda.txt has none, and "
             "--unverified-source was given, so it was taken to be the file legenda.txt came from.")


def clip_text(repeat: repeated.Repeat, body: str, source: str, model: str, lang: str,
              origin: str) -> str:
    start, end = window(repeat)
    head = [
        f"The stretch {stamp(start)} to {stamp(end)}, transcribed again on its own.",
        f"legenda.txt wrote {repeated._span(repeat.start, repeat.end, 'to')} twice: it repeats "
        f"{repeated._sources(repeat, 'to', ' and ')} ({repeat.words} words), and what was said there "
        f"may be lost.",
        "",
        "This is help for listening. legenda.txt was not changed. A loss that wrote nothing twice",
        "is not found.",
        "",
        f"File: {source}",
        origin,
        f"Model: faster-whisper {model}, language {lang}. Times are from the file's start, at the",
        "start of each segment, as in legenda.txt.",
        "",
    ]
    return "\n".join(head) + (body.strip() or "(no speech found in this stretch)") + "\n"


def write_clips(
    found: list[repeated.Repeat], media: Path, review: Path, transcriber: Transcriber,
    model: str, lang: str, *, source: str, origin: str, warn: Callable[[str], None],
) -> list[Path]:
    """One file per passage in `review`/repeats/, the folder written anew. A
    passage whose stretch fails is said and skipped: the others still go."""
    folder = review / CLIPS_DIR
    try:  # what this writes helps; failing to write it never undoes the text
        if folder.exists():
            shutil.rmtree(folder)
        if not found:
            return []
        folder.mkdir(parents=True)
    except OSError as error:
        warn(f"could not write {folder}: {error}")
        return []
    written: list[Path] = []
    for repeat in found:
        start, end = window(repeat)
        try:
            body = transcriber(media, start, end)
        except Exception as error:  # a decoder or model failure on one stretch
            warn(f"could not transcribe {stamp(start)} to {stamp(end)} again: {error}")
            continue
        path = unique(folder / file_name(repeat), written)
        try:
            path.write_text(clip_text(repeat, body, source, model, lang, origin), encoding="utf-8")
        except OSError as error:
            warn(f"could not write {path}: {error}")
            continue
        written.append(path)
    return written


def unique(path: Path, taken: list[Path]) -> Path:
    """Two passages can start on the same line: the second is `44-29-2.txt`."""
    number, candidate = 1, path
    while candidate in taken:
        number += 1
        candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
    return candidate
