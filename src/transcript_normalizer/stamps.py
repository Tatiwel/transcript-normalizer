"""D-103: how a line's timestamp is written and read.

Before 1 hour a timestamp is `m:ss`, as it always was: `44:29`. From 1 hour on
it is `h:mm:ss`, as a video player shows it: `1:14:14`, not `74:14`. Every
reader takes both, so a text written before D-103 is read as it was.
"""

from __future__ import annotations

import re

#: A timestamp, either form.
STAMP = re.compile(r"(?:\d+:)?\d+:\d\d")


def clock(seconds: float) -> str:
    """`44:29` before 1 hour, `1:14:14` from 1 hour on."""
    total = max(int(seconds), 0)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def seconds(stamp: str) -> int | None:
    """`m:ss`, `mm:ss` (any number of minutes) or `h:mm:ss` in seconds; None for anything else."""
    if not STAMP.fullmatch(stamp):
        return None
    total = 0
    for part in stamp.split(":"):
        total = total * 60 + int(part)
    return total


def rewrite(stamp: str) -> str:
    """The same moment written the D-103 way: `74:14` becomes `1:14:14`."""
    value = seconds(stamp)
    return stamp if value is None else clock(value)


def in_name(stamp: str) -> str:
    """A timestamp in a file name, without colons (Windows has none): `1-14-14`."""
    return stamp.replace(":", "-")


def rewrite_line(line: str) -> str:
    """A `stamp text` line with its stamp written the D-103 way; any other line as it is."""
    stamp, space, text = line.partition(" ")
    if not space or seconds(stamp) is None:
        return line
    return f"{rewrite(stamp)} {text}"


def same_lines(a, b) -> bool:
    """The same lines, whichever way their stamps are written (D-103)."""
    return [rewrite_line(x) for x in a] == [rewrite_line(x) for x in b]
