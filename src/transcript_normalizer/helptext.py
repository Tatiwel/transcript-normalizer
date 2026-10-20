"""The help text (D-051): `transcript-normalizer help`, `--help`, menu item 8.

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
           "a link or a file; for a link, the platform's caption (you pick the track) or local "
           "transcription; a caption file goes straight to normalizing",
           f"{PROG} fetch <url|file> [--track <code>]"),
    Action("2", "Normalize a run", "fix domain terms in a fetched caption",
           "pick a run; shows what was corrected, recognized, applied to confirm and suggested, "
           "then offers the review if anything is pending",
           f"{PROG} runs/<id>/legenda.txt --summary"),
    Action("3", "Review pending", "answer what the tool was unsure about",
           "pick a run; the close guesses are already in normalized.txt, and the review can undo them; "
           "one stop per uncertain form, in the order of the video; Enter decides later, "
           "and a summary asks before anything is saved",
           f"{PROG} runs/<id>/legenda.txt --review"),
    Action("4", "Show a run's outputs", "where the files are, first lines of the result",
           "pick a run; lists its files and the first 20 lines of normalized.txt",
           "ls runs/<id>/"),
    Action("5", "List runs", "everything under runs/",
           "id, publication date and title of every run",
           f"{PROG} list"),
    Action("6", "Packs", "installed, get, create, edit, share",
           "the installed packs (with an update mark when a newer one is included or in the repository); "
           "get one, included in the program or from the packs repository; create one from a field template; edit one (add, "
           "edit, remove and show terms); import, export or remove a pack file; contribute a "
           "whole pack; and the pack the menu offers first",
           f"{PROG} pack list --installed"),
    Action("7", "Settings", "where to save your files, sign-in, keep the audio",
           "a folder dialog for where runs/ and packs/ go; the sign-in, your browser's login (a browser, or a "
           "cookies.txt file) for sites that ask you to sign in and YouTube's bot check; whether to "
           "keep the audio after transcribing. Kept in "
           "config.toml in your user settings. In a script, the variable and the flags win",
           f"TRANSCRIPT_NORMALIZER_HOME=<folder> {PROG}"),
    Action("8", "Help", "what each action does and its command",
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
            ("fetch <url|file>", "download a caption, or transcribe an audio or video file locally; `--list` checks a link without downloading (site, captions, audio, login) and `--track <code>` takes one caption track; `--keep-audio` keeps the audio after transcribing; `fetch --check` lists the fetch tools installed; --cookies-from-browser <browser> or --cookies <file> signs in, on any site"),
            ("normalize <legenda.txt>", "fix domain terms (a .srt or .vtt is converted first); --review (one stop per form, in the order of the video) or --confirm (form by form, by term) to answer what it was unsure about; --pack for your own pack; --force when the pack does not seem to fit"),
            ("list", "every run under runs/, with its date and title"),
            ("pack list | install <name> | update", "the packs installed, then those included in the program (installed offline) and in the packs repository, each marked; install one into packs/; update installed ones"),
            ("pack list --installed", "only the installed packs: version, language, terms, size, source, and ↑ where a newer one is included or in the repository"),
            ("pack create --template <field> --name <n> --lang <l>", "a new pack in packs/, with the field's classes and no terms"),
            ("pack import <file> | remove <name>", "check a pack file and copy it into packs/; delete an installed one (an included pack stays in the program)"),
            ("pack copy <name>", "make an included or repository pack your own, to edit"),
            ("pack add-term <pack> <term>", "add a term (--class, --alias, --variant), or forms to an existing one; --context <terms> for a variant that is also an ordinary word, matched only where those terms appear (--unless-near asks near others); checked, saved with the next patch version"),
            ("pack edit-term | remove-term", "change a term of a pack (--rename, --class, --add-variant, --remove-alias, …); remove one"),
            ("pack show <pack>", "a pack's terms with their forms; --search <text>, --page <n>"),
            ("pack export <name> [--to <path>]", "write <name>-<version>.yaml"),
            ("pack merge <name>", "merge a newer upstream version into your copy, asking about each conflict; --dry-run, --yes-theirs, --yes-mine"),
            ("pack propose --whole <name>", "propose a whole pack to the packs repository: shows it, asks, then opens a prefilled issue"),
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
            ("--review", "the close guesses (medium band) are already applied in normalized.txt; the review confirms them or undoes them. Names found by sound are only suggested, never applied until you say yes. One stop per uncertain form, in the order of the video: the line before, the line with the form, the line after, where else it occurs, and a link to that moment. Choose yes (fix it from now on), yes only in this video, said that way (recognise it, keep the text), no, or decide later; Enter decides later. At the end a summary, and nothing is saved unless you say yes to it. The menu reviews this way"),
            ("--confirm", "one question per form, grouped by term, answered with one of:"),
            ("y", "the recognizer garbled the term: correct it from now on"),
            ("o", "the same, but only in this video: kept beside the run, never learned or contributed"),
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
        ("YOUTUBE SAYS I'M A BOT", [
            ("why", "YouTube sometimes asks a connection to prove it is a person; it depends on your network (a VPN, a shared or busy one), not on the video"),
            ("sign in", "Settings → Sign-in (your browser's login) lists the browsers found on this computer: Firefox (works everywhere), one row for the Chromium-based ones (Chrome, Edge, Brave, Opera, Vivaldi, Chromium; on Windows they usually cannot be read), Safari on macOS; or a cookies.txt exported with a browser extension. \"How does this work?\" explains. In a script: `fetch --cookies-from-browser firefox`, `fetch --cookies cookies.txt`"),
            ("or wait", "try again later, or use a file from this computer. The guide, section 3, has the details"),
            ("other sites", "Instagram, most of Facebook, and private or followers-only videos anywhere ask you to sign in; the same sign-in is used for every site. Only YouTube has captions: on other sites the full build transcribes the audio. `fetch --list <url>` checks a link first"),
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


def whisper_available() -> bool:
    """Whether faster-whisper can be imported, without importing it."""
    import importlib.util

    try:
        return importlib.util.find_spec("faster_whisper") is not None
    except (ImportError, ValueError):
        return False


def build_line() -> str:
    """D-061: what this installation can do, under the version on the first screen."""
    from .runs import is_frozen

    whisper = whisper_available()
    if is_frozen():
        return ("full build: captions and local transcription" if whisper
                else "lite build: platform captions only (no local transcription)")
    return "captions + local transcription" if whisper else "captions only"


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
