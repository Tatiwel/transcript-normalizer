"""Rendering the applied layer back over the caption (D-016).

A rendered file is a view, never a source. `annotations.json` stays the record
and the caption itself is never modified (D-004), so anything here can be thrown
away and rebuilt from the stand-off layer.
"""

from __future__ import annotations

from .standoff import Annotation, applied
from .text import Transcript

#: What separates the timestamp from the text in a rendered line.
TIMESTAMP_GAP = "  "


def render_lines(
    transcript: Transcript, annotations: list[Annotation]
) -> list[tuple[str, str]]:
    """`(timestamp, text)` per caption line, with the applied annotations substituted.

    One line out per caption line in, so the timestamps carry over untouched. An
    annotation that straddles a caption break is written where it starts, and the
    part of it that fell on the next line is dropped from there.

    Expects non-overlapping annotations, which is what `resolve_overlaps` returns.
    """
    text = transcript.text
    ordered = sorted(applied(annotations), key=lambda a: (a.start, a.end))

    rendered: list[tuple[str, str]] = []
    for line in transcript.lines:
        pieces: list[str] = []
        cursor = line.start
        for a in ordered:
            if a.end <= line.start or a.start >= line.end:
                continue
            if a.start > cursor:
                pieces.append(text[cursor:a.start])
            if a.start >= line.start:  # the annotation starts on this line
                pieces.append(a.replacement)
            cursor = min(a.end, line.end)
        pieces.append(text[cursor:line.end])
        rendered.append((line.timestamp, "".join(pieces).strip()))
    return rendered


def render_normalized(transcript: Transcript, annotations: list[Annotation]) -> str:
    """The whole caption as `m:ss  text`, one line per caption line."""
    lines = render_lines(transcript, annotations)
    return "".join(f"{stamp}{TIMESTAMP_GAP}{body}\n" for stamp, body in lines)
