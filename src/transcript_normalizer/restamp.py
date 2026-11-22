"""D-103: `restamp`, a legenda.txt's timestamps rewritten the D-103 way.

A text written before D-103 has `74:14` where a video player shows `1:14:14`.
`restamp` rewrites the timestamp at the start of each line, and the ones in
the lines the program itself wrote about passages written twice (D-092,
D-101), and nothing else: no word changes, and a time said in the speech
("às 10:30") is left as it is. What it changes is kept first, in
`replaced-<date and time>/`, as D-091 keeps a replaced text.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from . import caption_guard, stamps
from .ingest.clips import CLIPS_DIR
from .ingest.header import CLOCK
from .ingest.repeats import REPEATS_FILE
from .runs import CAPTION_FILE, META_FILE, NEEDS_REVIEW_DIR

#: The program's own lines that name passages: every stamp in them is rewritten.
_OWN_LINE = re.compile(r"^(#\s+\S+ a \S+ repete |The stretch |legenda\.txt wrote |\S+ to \S+\s+repeats )")
#: A stretch file's name before D-103: `74-29.txt`, `74-29-2.txt`.
_OLD_NAME = re.compile(r"^(\d+)-(\d\d)(-\d+)?$")


def _all_stamps(line: str) -> str:
    return stamps.STAMP.sub(lambda m: stamps.rewrite(m.group(0)), line)


#: The header line before D-103 that named the form `mm:ss` (D-093's wording).
_OLD_FORM = "# Cada linha comeca com o timestamp mm:ss "


def rewrite_text(text: str) -> str:
    """Each line's leading timestamp, every stamp in the program's own passage
    lines, and the header's line on how a timestamp is written."""
    out = []
    clock_after = False
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        ending = line[len(content):]
        if clock_after:  # the line after the one that said `mm:ss`
            out.append(content + ending + CLOCK + (ending or "\n"))
            clock_after = False
            continue
        if content.startswith(_OLD_FORM):
            content = content.replace("timestamp mm:ss ", "timestamp ", 1)
            clock_after = True
        elif _OWN_LINE.match(content):
            content = _all_stamps(content)
        elif content.startswith("  ") and not content.startswith("#"):  # a quoted line in repeats.txt
            content = "  " + stamps.rewrite_line(content[2:])
        elif not content.startswith("#"):
            content = stamps.rewrite_line(content)
        out.append(content + ending)
    return "".join(out)


def new_name(name: str) -> str:
    """`74-29.txt` becomes `1-14-29.txt`; a name already the D-103 way stays."""
    stem, suffix = Path(name).stem, Path(name).suffix
    match = _OLD_NAME.match(stem)
    if not match or int(match.group(1)) < 60:
        return name
    rewritten = stamps.in_name(stamps.rewrite(f"{match.group(1)}:{match.group(2)}"))
    return f"{rewritten}{match.group(3) or ''}{suffix}"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def plan(run: Path) -> dict[Path, tuple[Path, str]]:
    """What changes: {file now: (file after, its text)}, only files that change."""
    changes: dict[Path, tuple[Path, str]] = {}
    files = [run / CAPTION_FILE, run / NEEDS_REVIEW_DIR / REPEATS_FILE]
    clips = run / NEEDS_REVIEW_DIR / CLIPS_DIR
    if clips.is_dir():
        files += sorted(clips.glob("*.txt"))
    for path in files:
        if not path.is_file():
            continue
        text = _read(path)
        after = rewrite_text(text)
        target = path.with_name(new_name(path.name)) if path.parent == clips else path
        if after != text or target != path:
            changes[path] = (target, after)
    return changes


def collisions(run: Path, changes: dict[Path, tuple[Path, str]]) -> str:
    """Why renaming would put two stretches under one name; "" when it would not."""
    clips = run / NEEDS_REVIEW_DIR / CLIPS_DIR
    staying = {p for p in clips.glob("*.txt") if p not in changes} if clips.is_dir() else set()
    seen: dict[Path, Path] = {}
    for path, (target, _) in changes.items():
        if target in staying:
            return f"{path.name} would take the name of {target.name}, which is there already"
        if target in seen:
            return f"{path.name} and {seen[target].name} would both be named {target.name}"
        seen[target] = path
    return ""


def run_restamp(args: argparse.Namespace) -> int:
    given = Path(args.path)
    caption = given / CAPTION_FILE if given.is_dir() else given
    if not caption.is_file():
        print(f"{caption} is not there: restamp takes a run folder or its {CAPTION_FILE}", file=sys.stderr)
        return 1
    run = caption.parent
    if caption.name != CAPTION_FILE:
        print(f"{caption} is not a {CAPTION_FILE}: restamp rewrites a run's text", file=sys.stderr)
        return 1
    changes = plan(run)
    clash = collisions(run, changes)
    if clash:
        print(f"{run}: {clash}; nothing was changed", file=sys.stderr)
        return 1
    if not changes:
        print(f"{caption}: every timestamp is already written as a video player shows it; nothing to do")
        return 0
    archived = caption_guard.archive(run)
    written: list[Path] = []
    try:
        for path, (target, text) in changes.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            written.append(target)  # before writing: a half-written file goes on a failure too
            target.write_text(text, encoding="utf-8")
        # What restamp leaves as it was comes back too: the source's record, the
        # stretches with nothing to rewrite, repeats.txt with nothing to rewrite.
        kept = [archived / CAPTION_FILE, archived / META_FILE, archived / NEEDS_REVIEW_DIR / REPEATS_FILE]
        clips = archived / NEEDS_REVIEW_DIR / CLIPS_DIR
        if clips.is_dir():
            kept += sorted(clips.glob("*.txt"))
        for source in kept:
            target = run / source.relative_to(archived)
            if source.is_file() and target not in changes and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                written.append(target)
                shutil.copy2(source, target)
    except BaseException:
        for path in reversed(written):
            path.unlink(missing_ok=True)
        for folder in (run / NEEDS_REVIEW_DIR / CLIPS_DIR, run / NEEDS_REVIEW_DIR):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
        caption_guard.restore(run, archived)
        raise
    def spoken(text: str) -> list[str]:
        return [line for line in text.splitlines() if line and not line.startswith("#")]

    lines = sum(1 for old, new in zip(spoken(_read(archived / CAPTION_FILE)), spoken(_read(caption)))
                if old != new)
    print(f"{caption}: {lines} line(s) rewritten, as a video player shows the time (1:14:14, not 74:14)")
    print(f"  the text before: {archived}")
    left = sorted(
        str(p.relative_to(archived)) for p in archived.rglob("*")
        if p.is_file() and p.relative_to(archived) not in {
            c.relative_to(run) for c in changes} and not (run / p.relative_to(archived)).exists()
    )
    if left:
        print(f"  {', '.join(left)} were made with the old timestamps and stay in {archived.name}/: "
              f"normalize again to make them anew")
    return 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path", help=f"a run folder, or its {CAPTION_FILE}")
    parser.set_defaults(run=run_restamp)
