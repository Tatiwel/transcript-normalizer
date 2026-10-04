"""The interactive menu (D-051).

`transcript-normalizer` with no arguments, on a terminal, opens this menu.
Every action runs a subcommand through `cli.main`, the same entry point a script
uses, so nothing here is reachable only through the menu, and the menu never
does a subcommand's work in its own way. Without `rich` the menu is plain text.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .catalog import list_runs
from .runs import CAPTION_FILE, NORMALIZED_FILE, PENDING_FILE, needs_review_dir, runs_root

ITEMS = (
    ("1", "Fetch a video or file"),
    ("2", "Normalize a run"),
    ("3", "Review pending"),
    ("4", "Show a run's outputs"),
    ("5", "List runs"),
    ("6", "Help"),
    ("q", "Quit"),
)

HELP = (
    "transcript-normalizer fixes what a speech recognizer misheard in domain "
    "vocabulary (company names, acronyms, indicators, units) and never changes "
    "what the speaker said. Fetch a caption (or transcribe a file), normalize it "
    "against a domain pack, and review what the tool was unsure about; your "
    "answers are remembered for the next video. Every menu action is also a "
    "command (`fetch`, `normalize`, `normalize --confirm`, `list`). "
    "The full guide is docs/GUIDE.md."
)

#: How much of normalized.txt "Show a run's outputs" prints.
PREVIEW_LINES = 20


class Screen:
    """What the menu prints: rich panels on a terminal, plain lines elsewhere."""

    def __init__(self):
        self.console = None
        if sys.stdout.isatty() and importlib.util.find_spec("rich") is not None:
            from rich.console import Console

            self.console = Console(highlight=False)

    def menu(self) -> None:
        lines = [f"{key}. {label}" for key, label in ITEMS]
        if self.console:
            from rich.panel import Panel

            self.console.print(Panel("\n".join(lines), title="transcript-normalizer", expand=False))
        else:
            print("\n== transcript-normalizer")
            print("\n".join(lines))

    def say(self, text: str) -> None:
        print(text)

    def error(self, text: str) -> None:
        if self.console:
            self.console.print(f"[bold red]error:[/] {text}")
        else:
            print(f"error: {text}")


def ask(prompt: str) -> str | None:
    """One line of input, or None at end of input."""
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def yes(prompt: str) -> bool:
    return (ask(prompt) or "").lower().startswith("y")


def run_command(argv: list[str]) -> int:
    """A subcommand, exactly as typed on the command line."""
    from .cli import main

    try:
        return main(argv)
    except SystemExit as stop:  # argparse rejects its arguments this way
        return stop.code if isinstance(stop.code, int) else 2


# ------------------------------------------------------------------ actions


def choose_run(screen: Screen) -> Path | None:
    """The `list` table, numbered; the run directory picked, or None."""
    runs = list_runs()
    if not runs:
        screen.error(f"no runs under {runs_root()}; fetch a video first (1)")
        return None
    width = max(len(r.id) for r in runs)
    for number, r in enumerate(runs, 1):
        screen.say(f"  {number:2d}. {r.id:{width}s}  {r.date or '-':10s}  {r.title}")
    answer = ask("run number: ")
    if not answer:
        return None
    if not answer.isdigit() or not 1 <= int(answer) <= len(runs):
        screen.error(f"{answer!r} is not a number from the list")
        return None
    return runs_root() / runs[int(answer) - 1].id


def caption_of(screen: Screen, run: Path) -> Path | None:
    caption = run / CAPTION_FILE
    if not caption.exists():
        screen.error(f"{run.name} has no {CAPTION_FILE} to normalize")
        return None
    return caption


def fetch(screen: Screen) -> None:
    source = ask("URL or path to an audio/video file: ")
    if not source:
        return
    if "://" not in source:  # a local file goes straight to step 2 (D-038)
        code = run_command(["fetch", source])
    else:
        code = run_command(["fetch", source, "--caption-only"])
        if code == 1 and yes("no platform caption could be had. run with local speech recognition? [y/n] "):
            code = run_command(["fetch", source, "--whisper"])
    if code != 0:
        screen.error(f"fetch did not finish (exit {code})")


def normalize(screen: Screen) -> None:
    run = choose_run(screen)
    caption = run and caption_of(screen, run)
    if not caption:
        return
    code = run_command(["normalize", str(caption)])
    if code != 0:
        screen.error(f"normalize did not finish (exit {code})")
        return
    if not (needs_review_dir(run) / PENDING_FILE).exists():
        screen.say("nothing pending.")
        return
    if yes("review pending now? [y/n] "):
        review_caption(screen, caption)


def review(screen: Screen) -> None:
    run = choose_run(screen)
    caption = run and caption_of(screen, run)
    if caption:
        review_caption(screen, caption)


def review_caption(screen: Screen, caption: Path) -> None:
    code = run_command(["normalize", str(caption), "--confirm"])
    if code not in (0, 130):  # 130: interrupted, the answers so far are kept (D-037)
        screen.error(f"review did not finish (exit {code})")


def show(screen: Screen) -> None:
    run = choose_run(screen)
    if not run:
        return
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        screen.say(f"  {path}")
    normalized = run / NORMALIZED_FILE
    if not normalized.exists():
        screen.say("not normalized yet (2).")
        return
    lines = normalized.read_text(encoding="utf-8").splitlines()
    screen.say(f"\n{NORMALIZED_FILE}, first {min(PREVIEW_LINES, len(lines))} of {len(lines)} lines:")
    for line in lines[:PREVIEW_LINES]:
        screen.say(f"  {line}")


def listing(screen: Screen) -> None:
    run_command(["list"])


def help_text(screen: Screen) -> None:
    screen.say(HELP)


ACTIONS = {"1": fetch, "2": normalize, "3": review, "4": show, "5": listing, "6": help_text}


def run() -> int:
    """The menu loop: until `q`, end of input, or Ctrl+C."""
    screen = Screen()
    try:
        while True:
            screen.menu()
            choice = ask("> ")
            if choice is None or choice.lower() in ("q", "quit"):
                return 0
            action = ACTIONS.get(choice)
            if action is None:
                screen.error(f"{choice!r} is not on the menu")
                continue
            try:
                action(screen)
            except Exception as error:  # shown in the menu, never as a traceback
                screen.error(f"{type(error).__name__}: {error}")
    except KeyboardInterrupt:
        print()
        return 0
