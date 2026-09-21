"""Turning an SRT into the `m:ss text` body of a `legenda.txt`."""

from __future__ import annotations

import re

#: How far back the de-duplication looks, in seconds.
WINDOW_SECONDS = 30.0


def _seconds(mark: str) -> float:
    hours, minutes, seconds = mark.strip().replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def srt_to_lines(srt: str) -> str:
    """Convert SRT to `m:ss text` lines.

    Automatic captions roll: every block repeats the previous line and adds the
    new one, with blocks of tens of milliseconds padding between them. Emitting
    block by block would duplicate almost everything.

    The rule is to emit each physical line once, timestamped with the END of the
    block it appeared in. The end is used because that is what the platform's own
    transcript panel attributes, so this text can be compared against that one
    without an offset.

    The comparison uses a TIME window, not the set of everything emitted so far
    and not a count of blocks. A global set would discard a phrase the speaker
    really did repeat at two different moments, and nobody would notice it
    missing. A block count does not work either, because a neighbouring block in
    the file can be minutes away in time when there is an edit cut.

    The rolling format repeats within a few seconds. A thirty second window
    covers that with room to spare and lets real repetition through.
    """
    out: list[str] = []
    recent: list[tuple[float, str]] = []

    for block in re.split(r"\n\s*\n", srt.replace("\r", "").strip()):
        parts = [p.strip() for p in block.split("\n")]
        timing = next((p for p in parts if "-->" in p), None)
        if not timing:
            continue
        start, end = (_seconds(x) for x in timing.split("-->"))
        recent = [(t, l) for t, l in recent if start - t <= WINDOW_SECONDS]
        neighbours = {l for _, l in recent}
        for line in parts:
            if not line or "-->" in line or line.isdigit():
                continue
            recent.append((start, line))
            if line in neighbours:
                continue
            out.append(f"{int(end) // 60}:{int(end) % 60:02d} {line}")

    return "\n".join(out)
