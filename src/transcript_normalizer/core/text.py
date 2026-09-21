"""Reading a caption file as one text with an offset map back to lines (D-007).

Platform captions break lines mid-phrase, so matching runs over the joined text.
Every character offset maps back to the caption line and timestamp it came from.
"""

from __future__ import annotations

import bisect
import unicodedata
from dataclasses import dataclass
from pathlib import Path

#: What caption lines are joined with. One character, so offsets stay simple.
JOIN = " "


@dataclass(frozen=True)
class Line:
    index: int
    timestamp: str
    text: str
    start: int  # offset of `text` inside Transcript.text
    end: int


@dataclass(frozen=True)
class Transcript:
    text: str
    lines: tuple[Line, ...]

    def _starts(self) -> list[int]:
        return [line.start for line in self.lines]

    def line_at(self, offset: int) -> Line:
        """The caption line a character offset belongs to."""
        i = bisect.bisect_right(self._starts(), offset) - 1
        return self.lines[max(i, 0)]

    def locate(self, offset: int) -> tuple[int, str]:
        """D-007's offset map: character offset -> (line index, timestamp)."""
        line = self.line_at(offset)
        return line.index, line.timestamp

    def spans(self, start: int, end: int) -> tuple[Line, ...]:
        """Every caption line an annotation touches. More than one when it straddles a break."""
        return tuple(l for l in self.lines if l.start < end and start < l.end)


def parse_caption(source: str) -> Transcript:
    """Parse `legenda.txt` contents: `#` header lines are skipped, each line is `m:ss text`."""
    source = unicodedata.normalize("NFC", source)
    lines: list[Line] = []
    parts: list[str] = []
    offset = 0
    index = 0
    for raw in source.splitlines():
        if raw.startswith("#"):
            continue
        stripped = raw.strip()
        if not stripped or " " not in stripped:
            continue
        timestamp, body = stripped.split(" ", 1)
        if offset:
            parts.append(JOIN)
            offset += len(JOIN)
        lines.append(Line(index, timestamp, body, offset, offset + len(body)))
        parts.append(body)
        offset += len(body)
        index += 1
    return Transcript(text="".join(parts), lines=tuple(lines))


def read_caption(path: str | Path) -> Transcript:
    return parse_caption(Path(path).read_text(encoding="utf-8"))
