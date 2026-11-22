"""Draw the menu as the README shows it: docs/images/menu.svg (D-105).

The picture is the program itself, not a mock-up: it runs `transcript-normalizer`
with no arguments in a pseudo-terminal, as a person at a terminal would, presses
the keys given (↓ by default, so one item is selected), reads the screen with a
terminal emulator, and writes what is on it, colours and all, as an SVG. Run it
again after a change to the menu, from a checkout with the dev tools:

    uv run --with pyte python scripts/menu_svg.py [down ...]

It needs a POSIX pseudo-terminal (Linux or macOS). The folder the menu says it
works in is a temporary one, shown as ~/Documents/transcript-normalizer.
"""

from __future__ import annotations

import io
import os
import select
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images" / "menu.svg"
COLS, ROWS = 96, 22
SHOWN_HOME = "~/Documents/transcript-normalizer"
KEYS = {"down": b"\x1b[B", "up": b"\x1b[A"}


def capture(keys: list[str]) -> tuple[object, str]:
    import fcntl
    import pty
    import struct
    import termios

    import pyte

    home = tempfile.mkdtemp(prefix="tn")
    pid, fd = pty.fork()
    if pid == 0:  # the child: the menu, on a terminal
        os.chdir(home)
        env = dict(os.environ, TERM="xterm-256color", COLUMNS=str(COLS), LINES=str(ROWS),
                   TRANSCRIPT_NORMALIZER_HOME=home, HOME=home, NO_COLOR="")
        env.pop("NO_COLOR")
        os.execve(sys.executable, [sys.executable, "-c",
                                   "from transcript_normalizer.cli import main; raise SystemExit(main([]))"], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))

    class Screen(pyte.Screen):
        def write_process_input(self, data):  # answers the terminal's cursor position request
            os.write(fd, data.encode())

    screen = Screen(COLS, ROWS)
    stream = pyte.ByteStream(screen)

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if ready:
                try:
                    stream.feed(os.read(fd, 65536))
                except OSError:
                    return

    pump(4)
    for key in keys:
        os.write(fd, KEYS[key])
        pump(1)
    os.kill(pid, 9)
    return screen, home


def colour(name: str):
    if name in ("default", None):
        return None
    if len(name) == 6 and all(c in "0123456789abcdefABCDEF" for c in name):
        return "#" + name
    return {"brightblack": "bright_black"}.get(name, name)


def render(screen, home: str) -> str:
    from rich.console import Console
    from rich.style import Style
    from rich.text import Text

    text = Text()
    rows = [y for y in range(ROWS) if "".join(screen.buffer[y][x].data for x in range(COLS)).strip()]
    for y in range(max(rows) + 1 if rows else 0):
        cells = [screen.buffer[y][x] for x in range(COLS)]
        line = "".join(cell.data for cell in cells)
        at = line.find(home)
        if at >= 0:  # the temporary folder, shown as the usual one, in the path's own style
            cells = cells[:at] + [cells[at]._replace(data=c) for c in SHOWN_HOME] + cells[at + len(home):]
        for cell in cells:
            text.append(cell.data, Style(color=colour(cell.fg), bold=cell.bold, italic=cell.italics,
                                         underline=cell.underscore, reverse=cell.reverse))
        text.rstrip()
        text.append("\n")
    text.rstrip()
    console = Console(record=True, width=COLS, force_terminal=True, color_system="truecolor", file=io.StringIO())
    console.print(text)
    return console.export_svg(title="transcript-normalizer")


def main(argv: list[str]) -> int:
    keys = argv or ["down"]
    screen, home = capture(keys)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(screen, home), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
