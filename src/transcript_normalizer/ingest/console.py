"""What `fetch` tells the person running it (D-036).

On a terminal, and with `rich` installed, stages, progress and countdowns are
drawn with rich. Anywhere else (a pipe, a file, a test, a script) the same
events are plain lines, with no colour, no cursor movement and no carriage
returns, so a scripted caller reads text it can grep.
"""

from __future__ import annotations

import importlib.util
import sys
from contextlib import contextmanager
from typing import Callable, Iterator, TextIO


def _rich_available() -> bool:
    return importlib.util.find_spec("rich") is not None


class Output:
    def __init__(self, stream: TextIO | None = None, fancy: bool | None = None):
        self.stream = stream if stream is not None else sys.stdout
        if fancy is None:
            fancy = bool(getattr(self.stream, "isatty", lambda: False)()) and _rich_available()
        self.fancy = fancy
        self._console = None
        if fancy:
            from rich.console import Console

            self._console = Console(file=self.stream, highlight=False)

    # ------------------------------------------------------------- lines

    def stage(self, message: str) -> None:
        """A step of the chain starting."""
        if self._console:
            self._console.print(f"[bold cyan]»[/] [bold]{message}[/]")
        else:
            print(f"== {message}", file=self.stream)

    def info(self, message: str) -> None:
        if self._console:
            self._console.print(f"  {message}")
        else:
            print(f"   {message}", file=self.stream)

    def warn(self, message: str) -> None:
        if self._console:
            self._console.print(f"  [yellow]{message}[/]")
        else:
            print(f"   warning: {message}", file=self.stream)

    # ------------------------------------------------------------- time

    def countdown(self, seconds: float, message: str, sleep: Callable[[float], None]) -> None:
        """Wait `seconds` before a retry, saying how long, one second at a time.

        The wait is real (D-036: 2 s, then 4 s); the line stays on screen, so a
        person sees that it waited, not three attempts back to back.
        """
        if not self._console:
            print(f"   {message}, retrying in {seconds:g} s", file=self.stream)
            sleep(seconds)
            return
        from rich.live import Live

        left = seconds
        with Live(console=self._console, transient=False, auto_refresh=False) as live:
            while left > 0:
                live.update(f"  [yellow]{message}[/], retrying in {left:.0f} s", refresh=True)
                step = min(1.0, left)
                sleep(step)
                left -= step
            live.update(f"  [yellow]{message}[/], waited {seconds:g} s, retrying", refresh=True)

    @contextmanager
    def progress(self, total: float, description: str) -> Iterator[Callable[[float], None]]:
        """Yield `advance(amount)`; `total` is in the same unit (seconds of audio)."""
        if not self._console:
            print(f"   {description}: {total:.0f}s of audio", file=self.stream)
            yield lambda amount: None
            print(f"   {description}: done", file=self.stream)
            return
        from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

        with Progress(
            TextColumn("  {task.description}"),
            BarColumn(),
            TextColumn("{task.completed:.0f}/{task.total:.0f}s"),
            TimeRemainingColumn(),
            console=self._console,
            transient=False,
        ) as bar:
            task = bar.add_task(description, total=max(total, 0.001))
            yield lambda amount: bar.advance(task, max(amount, 0.0))
            bar.update(task, completed=max(total, 0.001))
