"""Turning a subtitle file into the `m:ss text` body of a `legenda.txt`.

SRT and WebVTT are both cue lists, so one de-duplicator serves both. WebVTT is
handled here in Python rather than by asking yt-dlp to convert, because that
conversion wants ffmpeg on the system and the caption path should not need it.
"""

from __future__ import annotations

import html
import re

#: How far back the de-duplication looks, in seconds.
WINDOW_SECONDS = 30.0

#: WebVTT cue payloads carry inline timing and styling tags.
_TAG = re.compile(r"<[^>]*>")


def _seconds(mark: str) -> float:
    parts = mark.strip().replace(",", ".").split(":")
    if len(parts) == 2:  # WebVTT may leave the hours out
        parts = ["0", *parts]
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clean(line: str) -> str:
    return html.unescape(_TAG.sub("", line)).replace(" ", " ").strip()


def _cues(text: str) -> list[tuple[float, float, list[str]]]:
    """`(start, end, payload lines)` per cue, in file order.

    Everything before the timing line of a block is discarded: that is the cue
    number in SRT and the optional cue identifier in WebVTT. A block with no
    timing line at all is not a cue, which is how the `WEBVTT` header and any
    `NOTE` block fall away.
    """
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").strip()):
        lines = [line.strip() for line in block.split("\n")]
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            continue
        head, tail = lines[timing].split("-->", 1)
        start = _seconds(head)
        end = _seconds(tail.split()[0])  # WebVTT puts cue settings after the end
        payload = [_clean(line) for line in lines[timing + 1 :]]
        cues.append((start, end, [line for line in payload if line]))
    return cues


def cues_to_lines(cues: list[tuple[float, float, list[str]]]) -> str:
    """Emit each physical caption line once, as `m:ss text`.

    Automatic captions roll: every cue repeats the previous line and adds the
    new one, with cues of tens of milliseconds padding between them. Emitting
    cue by cue would duplicate almost everything.

    Each line is timestamped with the END of the cue it appeared in. The end is
    used because that is what the platform's own transcript panel attributes, so
    this text can be compared against that one without an offset.

    The comparison uses a TIME window, not the set of everything emitted so far
    and not a count of cues. A global set would discard a phrase the speaker
    really did repeat at two different moments, and nobody would notice it
    missing. A cue count does not work either, because a neighbouring cue in the
    file can be minutes away in time when there is an edit cut.

    The rolling format repeats within a few seconds. A thirty second window
    covers that with room to spare and lets real repetition through.
    """
    out: list[str] = []
    recent: list[tuple[float, str]] = []

    for start, end, payload in cues:
        recent = [(t, l) for t, l in recent if start - t <= WINDOW_SECONDS]
        neighbours = {l for _, l in recent}
        for line in payload:
            recent.append((start, line))
            if line in neighbours:
                continue
            out.append(f"{int(end) // 60}:{int(end) % 60:02d} {line}")

    return "\n".join(out)


def srt_to_lines(srt: str) -> str:
    """Convert SRT to `m:ss text` lines."""
    return cues_to_lines(_cues(srt))


def vtt_to_lines(vtt: str) -> str:
    """Convert WebVTT to `m:ss text` lines, tags and cue settings stripped."""
    return cues_to_lines(_cues(vtt))


def subtitle_to_lines(text: str, suffix: str) -> str:
    """Dispatch on the file extension yt-dlp happened to leave behind."""
    if suffix.lower() == ".vtt":
        return vtt_to_lines(text)
    return srt_to_lines(text)
