"""The help text (D-051): `transcript-normalizer help`, `--help`, menu item 6.

Sections, one line per entry, aligned, like `gh help`. Plain text, so a pipe or
a test reads the same thing a terminal shows; long entries wrap at the width
given, under their own description column.
"""

from __future__ import annotations

import re
import shutil
import textwrap
from dataclasses import dataclass

PROG = "transcript-normalizer"
MARGIN = 2


@dataclass(frozen=True)
class Action:
    """One menu item: what it is called, what it does, and the command it runs."""

    key: str
    label: str
    description: str  # beside the label in the menu
    help: str  # its line under MENU
    command: str  # the equivalent command, as typed


ACTIONS = (
    Action("1", "Fetch a video or file", "download a caption, or transcribe audio locally",
           "asks for a URL or a path; platform caption first, local speech recognition if you agree",
           f"{PROG} fetch <url|file>"),
    Action("2", "Normalize a run", "fix domain terms in a fetched caption",
           "pick a run; shows three counters, then offers the review if anything is pending",
           f"{PROG} runs/<id>/legenda.txt --summary"),
    Action("3", "Review pending", "answer what the tool was unsure about",
           "pick a run; one screen per term: pick the forms that are the term",
           f"{PROG} runs/<id>/legenda.txt --review"),
    Action("4", "Show a run's outputs", "where the files are, first lines of the result",
           "pick a run; lists its files and the first 20 lines of normalized.txt",
           "ls runs/<id>/"),
    Action("5", "List runs", "everything under runs/",
           "id, publication date and title of every run",
           f"{PROG} list"),
    Action("6", "Help", "what each action does and its command",
           "this help; `?` on any question explains its options",
           f"{PROG} help"),
)
QUIT = Action("q", "Quit", "", "", "")


def sections() -> list[tuple[str, list[tuple[str, str]]]]:
    return [
        ("USAGE", [
            (PROG, "on a terminal: the interactive menu"),
            (f"{PROG} <command> [options]", ""),
            (f"{PROG} <legenda.txt>", "same as `normalize <legenda.txt>`"),
        ]),
        ("COMMANDS", [
            ("fetch <url|file>", "download a caption, or transcribe an audio or video file locally"),
            ("normalize <legenda.txt>", "fix domain terms; --review (term by term) or --confirm (form by form) to answer what it was unsure about; --pack for your own pack"),
            ("list", "every run under runs/, with its date and title"),
            ("pack list | install <name> | update", "packs from the packs repository, installed into packs/"),
            ("pack propose [--pack <name>]", "contribute what your reviews taught the tool: shows it, asks, then opens a prefilled issue"),
            ("help", "this help; `<command> --help` lists a command's options"),
        ]),
        ("MENU", [(f"{a.key}. {a.label}", a.help, a.command) for a in ACTIONS]),
        ("WHAT HAPPENS", [
            ("runs/<id>/legenda.txt", "the transcript as received, with a header saying where it came from"),
            ("runs/<id>/normalized.txt", "the transcript with corrections applied, same lines and timestamps"),
            ("runs/<id>/annotations.json", "every correction and recognition, as data"),
            ("runs/<id>/report.txt", "what the command printed"),
            ("runs/<id>/needs-review/", "what still needs your answer (pending.txt)"),
        ]),
        ("THE REVIEW LOOP", [
            ("--review", "one screen per term: select (space) the forms that are the term, then enter; the others are rejected; then say which of those the speaker really said that way (aliases). The menu reviews this way"),
            ("--confirm", "one question per form, answered with one of:"),
            ("y", "the recognizer garbled the term: correct it from now on"),
            ("n", "not this term: never propose it again"),
            ("l", "this term, said that way: recognize it, never change it"),
            ("s", "not sure: asked again next time; two seconds of doubt is a skip"),
            ("a", "yes to this form and the remaining forms of the same term"),
            ("r", "no to this form and the remaining forms of the same term"),
        ]),
        ("EXAMPLES", [
            (f"{PROG} fetch https://youtu.be/4wCtn8BWR4o", ""),
            (f"{PROG} runs/4wCtn8BWR4o/legenda.txt --confirm", ""),
            (f"{PROG} aula.txt --pack packs/biomed-ptbr.yaml", ""),
        ]),
        ("LEARN MORE", [
            ("docs/GUIDE.md", "the guide"),
            ("docs/GUIDE.pt-BR.md", "o guia, em português"),
            ("CONTRIBUTING.md", "adding a language, building a pack, measuring it"),
        ]),
    ]


def version() -> str:
    """The installed version, from the package metadata."""
    from importlib.metadata import PackageNotFoundError, version as installed

    try:
        return installed("transcript-normalizer")
    except PackageNotFoundError:
        return "(version unknown)"


def width() -> int:
    return shutil.get_terminal_size((80, 24)).columns


_KEEP = "\x00"  # a space that does not break: inside `a command`


def _wrap(text: str, cols: int, first: str, rest: str) -> list[str]:
    """textwrap, but a `backticked command` is never split, and no hyphen breaks."""
    text = re.sub(r"`[^`]*`", lambda m: m.group(0).replace(" ", _KEEP), text)
    lines = textwrap.wrap(
        text, cols, initial_indent=first, subsequent_indent=rest,
        break_on_hyphens=False, break_long_words=False,
    )
    return [line.replace(_KEEP, " ") for line in lines] or [first.rstrip()]


def entries(rows: list[tuple], cols: int, margin: int = MARGIN) -> list[str]:
    """Two aligned columns; the right one wraps under itself.

    A row may carry a third element, the equivalent command, which goes on a
    line of its own under the description, or further left if it does not fit.
    """
    left = max((len(row[0]) for row in rows if row[1]), default=0)
    out = []
    for l, r, *command in rows:
        if not r:
            out += _wrap(l, cols, " " * margin, " " * (margin + 2))
            continue
        indent = " " * (margin + left + 2)
        out += _wrap(r, max(cols, len(indent) + 20), " " * margin + l.ljust(left) + "  ", indent)
        if command:
            text = f"`{command[0]}`"
            out.append((indent if len(indent) + len(text) <= cols else " " * (margin + 2)) + text)
    return out


def render(cols: int | None = None) -> str:
    cols = cols or width()
    out = []
    for title, rows in sections():
        out += [title, *entries(rows, cols), ""]
    return "\n".join(out).rstrip() + "\n"


def wrap_block(text: str, cols: int | None = None, margin: int = MARGIN) -> str:
    """Long output (show) at the terminal width, with a left margin."""
    cols = cols or width()
    lines = []
    for line in text.splitlines():
        head = len(line) - len(line.lstrip())
        # A `m:ss  text` line keeps its text column when it wraps.
        stamp = line.lstrip().split("  ", 1)
        hang = len(stamp[0]) + 2 if len(stamp) == 2 and ":" in stamp[0] else 0
        lines += _wrap(line.strip(), cols, " " * (margin + head), " " * (margin + head + hang))
    return "\n".join(lines)
