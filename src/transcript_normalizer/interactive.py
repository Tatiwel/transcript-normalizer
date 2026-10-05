"""The interactive menu (D-051, D-053).

`transcript-normalizer` with no arguments, on a terminal, opens this menu.
Every action runs a subcommand through `cli.main`, the same entry point a script
uses, so nothing here is reachable only through the menu, and the menu never
does a subcommand's work in its own way. The questions go through `prompts`:
arrow keys with questionary, numbered text without it.
"""

from __future__ import annotations

from pathlib import Path

from . import helptext, prompts
from .catalog import list_runs
from .helptext import ACTIONS as ITEMS, QUIT
from .prompts import Option, mark, say
from .runs import (
    CAPTION_FILE,
    NORMALIZED_FILE,
    PENDING_FILE,
    base_dir,
    is_frozen,
    needs_review_dir,
    runs_root,
)

#: How much of normalized.txt "Show a run's outputs" prints.
PREVIEW_LINES = 20

TYPICAL_FLOW = "Typical flow: 1 fetch → 2 normalize → 3 review"


def run_command(argv: list[str]) -> int:
    """A subcommand, exactly as typed on the command line."""
    from .cli import main

    try:
        return main(argv)
    except SystemExit as stop:  # argparse rejects its arguments this way
        return stop.code if isinstance(stop.code, int) else 2


def error(text: str) -> None:
    say(mark(f"error: {text}", "bad"))


def separator() -> None:
    """A blank line and a dim rule, so one action's output ends visibly."""
    print()
    say(mark("─" * min(helptext.width(), 60), "hint"))


def menu_options() -> list[Option]:
    return [Option(a.label, a.description, value=a.key, key=a.key) for a in ITEMS] + [
        Option(QUIT.label, "", value=QUIT.key, key=QUIT.key)
    ]


def first_screen() -> None:
    say(mark(f"transcript-normalizer {helptext.version()}", "title"))
    # D-052: the executable keeps your files in the documents directory; say where.
    say("Your files: " if is_frozen() else "Working in: ", mark(base_dir(), "path"))
    say(TYPICAL_FLOW)
    say(mark(f"Keyboard: {prompts.legend('select')}", "hint"))


# ------------------------------------------------------------------ runs


def choose_run(question: str) -> Path | None:
    """A list of runs (id, date, title); the run directory picked, or None."""
    runs = list_runs()
    if not runs:
        error(f"no runs under {runs_root()}; fetch a video first (1)")
        return None
    width = max(len(r.id) for r in runs)
    picked = prompts.select(
        question,
        [Option(r.id.ljust(width), f"{r.date or '-':10s}  {r.title}", value=r.id) for r in runs],
        hint="the video's id, its publication date and its title",
    )
    return None if picked is None else runs_root() / picked


def caption_of(run: Path) -> Path | None:
    caption = run / CAPTION_FILE
    if not caption.exists():
        error(f"{run.name} has no {CAPTION_FILE} to normalize")
        return None
    return caption


def newest_run() -> Path | None:
    """The run whose caption was written last: the one a fetch just made."""
    captions = sorted(runs_root().glob(f"*/{CAPTION_FILE}"), key=lambda p: p.stat().st_mtime)
    return captions[-1].parent if captions else None


def pending_count(run: Path) -> int:
    """How many forms needs-review/pending.txt still lists (D-023)."""
    from .cli import NEVER_ASKED, SKIPPED

    pending = needs_review_dir(run) / PENDING_FILE
    if not pending.exists():
        return 0
    return sum(
        1
        for line in pending.read_text(encoding="utf-8").splitlines()
        if line.startswith("  ") and not line.startswith("    ") and line.endswith((NEVER_ASKED, SKIPPED))
    )


# ------------------------------------------------------------------ actions


def fetch() -> None:
    from .ingest.fetch import LITE_BUILD, is_lite_build, missing_extra

    source = prompts.text(
        "Fetch: a video URL, or the path to an audio or video file",
        hint="a link (YouTube and others) or a file on this computer; empty goes back",
    )
    if not source:
        return
    if "://" not in source:  # a local file goes straight to step 2 (D-038)
        code = run_command(["fetch", source])
    else:
        code = run_command(["fetch", source, "--caption-only"])
        if code == 1:
            if is_lite_build():
                say(mark(LITE_BUILD, "need"))
            elif not missing_extra("faster_whisper") and prompts.confirm(
                "No platform caption could be had. Transcribe the audio on this computer instead?",
                default=True,
                hint="downloads the audio and runs speech recognition; this can take minutes",
            ):
                code = run_command(["fetch", source, "--whisper"])
    if code != 0:
        error(f"fetch did not finish (exit {code})")
        return
    run = newest_run()
    if run and prompts.confirm("Next: normalize this run now?", default=True):
        normalize_run(run)


def normalize() -> None:
    run = choose_run("Normalize which run?")
    if run:
        normalize_run(run)


def normalize_run(run: Path) -> None:
    caption = caption_of(run)
    if not caption:
        return
    say(mark(f"Normalizing {run.name}", "title"))
    code = run_command(["normalize", str(caption), "--summary"])
    if code != 0:
        error(f"normalize did not finish (exit {code})")
        return
    count = pending_count(run)
    if not count:
        say(mark("Nothing to confirm. Done.", "ok"))
        return
    say(mark("The result is usable as it is; reviewing only makes the next run better.", "hint"))
    if prompts.confirm(f"Next: review the {count} uncertain one(s) now?", default=True):
        review_run(run)


def review() -> None:
    run = choose_run("Review which run?")
    if run:
        review_run(run)


def review_run(run: Path) -> None:
    caption = caption_of(run)
    if not caption:
        return
    say(mark(f"Reviewing {run.name}", "title"))
    code = run_command(["normalize", str(caption), "--summary", "--review"])
    if code not in (0, 130):  # 130: interrupted, the answers so far are kept (D-037)
        error(f"review did not finish (exit {code})")


def show() -> None:
    run = choose_run("Show which run?")
    if not run:
        return
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        say("  ", mark(path, "path"))
    normalized = run / NORMALIZED_FILE
    if not normalized.exists():
        say(mark("not normalized yet (2).", "need"))
        return
    lines = normalized.read_text(encoding="utf-8").splitlines()
    say(f"\n{NORMALIZED_FILE}, first {min(PREVIEW_LINES, len(lines))} of {len(lines)} lines:")
    print(helptext.wrap_block("\n".join(lines[:PREVIEW_LINES])))


def listing() -> None:
    run_command(["list"])


def help_text() -> None:
    run_command(["help"])


ACTIONS = {"1": fetch, "2": normalize, "3": review, "4": show, "5": listing, "6": help_text}


def run() -> int:
    """The menu loop: until Quit, Esc or empty input at the menu, or Ctrl+C."""
    first_screen()
    first = True
    try:
        while True:
            if not first:
                separator()
            first = False
            choice = prompts.select(
                "What would you like to do?",
                menu_options(),
                hint="pick an action; empty input or Esc here quits",
            )
            if choice is None or choice == QUIT.key:
                return 0
            try:
                ACTIONS[choice]()
            except Exception as failure:  # shown in the menu, never as a traceback
                error(f"{type(failure).__name__}: {failure}")
    except KeyboardInterrupt:
        print()
        return 0
