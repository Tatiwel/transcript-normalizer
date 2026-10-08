"""The interactive menu (D-051, D-053).

`transcript-normalizer` with no arguments, on a terminal, opens this menu.
Every action runs a subcommand through `cli.main`, the same entry point a script
uses, so nothing here is reachable only through the menu, and the menu never
does a subcommand's work in its own way. The questions go through `prompts`:
arrow keys with questionary, numbered text without it.

The one exception is Settings (D-061), which writes the user's config.toml:
where runs/ and packs/ go, and the pack offered first. A script reaches the
same with TRANSCRIPT_NORMALIZER_HOME and --pack.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import helptext, prompts
from .catalog import list_runs
from .helptext import ACTIONS as ITEMS, QUIT
from .prompts import Option, detail, mark, say, stage
from .runs import (
    CAPTION_FILE,
    DATA_DIR_ENV,
    NORMALIZED_FILE,
    PENDING_FILE,
    base_dir,
    configured_dir,
    data_dir,
    default_pack,
    installed_packs,
    is_frozen,
    needs_review_dir,
    read_config,
    runs_root,
    write_config,
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
    prompts.rule()


def menu_options() -> list[Option]:
    return [
        Option(a.label, a.description, value=a.key, key=a.key, help=a.help, command=a.command)
        for a in ITEMS
    ] + [Option(QUIT.label, "", value=QUIT.key, key=QUIT.key, help="leave the menu")]


def first_screen() -> None:
    say(mark(f"transcript-normalizer {helptext.version()}", "title"))
    say(mark(helptext.build_line(), "hint"))
    # D-052, D-061: say where the files go, unless it is simply here.
    base = base_dir()
    detail("Working in" if base == Path.cwd() else "Your files", base, "path", indent="")
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


#: D-062: what the file dialog of "A file on this computer" offers.
MEDIA_SUFFIXES = (".mp3", ".m4a", ".wav", ".ogg", ".opus", ".mp4", ".mkv", ".webm", ".mov")


def fetch() -> None:
    """D-062: a link or a file; for a link, the platform's caption (which
    track) or local transcription; then the offer to normalize."""
    stage("Fetch")
    while True:
        where = prompts.select("Where is it?", [
            Option("A link (YouTube and others)", value="link"),
            Option("A file on this computer", value="file"),
        ])
        if where is None:
            return
        if (fetch_link() if where == "link" else fetch_file()) != BACK:
            return


def fetch_link() -> str | None:
    """Paste a link, read the video, choose caption or transcription."""
    from .ingest.console import Output
    from .ingest.fetch import NO_CAPTION, FetchError, missing_extra, read_metadata, tracks

    source = prompts.text("The video's link", hint="YouTube, Vimeo, TikTok, Instagram and others")
    if not source:
        return BACK
    if "://" not in source or missing_extra("yt_dlp"):
        # Not a link (a path typed here still works), or nothing to read links
        # with: fetch says which, in its own words.
        return after_fetch(run_command(["fetch", source]))
    try:
        meta = read_metadata(source, Output())
    except FetchError as failure:
        error(f"could not read the video: {failure}")
        return None
    for label, value, kind in (
        ("title", meta.title, "value"), ("channel", meta.channel, "value"),
        ("published", meta.published, "value"),
        ("duration", f"{meta.duration // 60}min{meta.duration % 60:02d}s", "number"),
    ):
        detail(label, value, kind)
    listed, translations = tracks(meta)
    if not listed and not translations:
        say(mark(NO_CAPTION, "need"))
        if transcription_unavailable():
            say(mark(f"  {transcription_unavailable()}", "hint"))
            return None
        if not prompts.confirm(
            "Transcribe the audio on this computer instead?",
            default=True,
            hint="downloads the audio and runs speech recognition; this can take minutes",
        ):
            return None
        return after_fetch(transcribe_link(source))
    while True:
        how = prompts.select(
            "Use the platform's caption, or transcribe the audio on this computer?",
            [
                Option("The platform's caption", "quick; the text the platform shows", value="caption"),
                Option("Transcribe the audio on this computer", "downloads the audio; can take minutes",
                       value="speech", disabled=transcription_unavailable(short=True)),
            ],
            default="caption",
        )
        if how is None:
            return BACK
        if how == "speech":
            return after_fetch(transcribe_link(source))
        track = choose_track(meta, listed, translations)
        if track is None:
            continue
        code = run_command(["fetch", source, "--track", track, "--caption-only", "--no-video-info"])
        if code == 1 and not transcription_unavailable() and prompts.confirm(
            "Transcribe the audio on this computer instead?",
            default=True,
            hint="downloads the audio and runs speech recognition; this can take minutes",
        ):
            code = transcribe_link(source)
        return after_fetch(code)


def transcription_unavailable(short: bool = False) -> str:
    """Why this installation cannot transcribe audio; "" when it can."""
    from .ingest.fetch import LITE_BUILD, is_lite_build, missing_extra

    if is_lite_build():
        return "full build only" if short else LITE_BUILD
    if missing_extra("faster_whisper"):
        return "needs the ingest extra" if short else (
            "Local transcription needs the ingest extra: pip install 'transcript-normalizer[ingest]'"
        )
    return ""


def transcribe_link(source: str) -> int:
    # The title, channel and duration are on screen already.
    return run_command(["fetch", source, "--whisper", "--no-video-info"])


#: The track-list option that opens the automatic translations.
TRANSLATIONS = "\0translations"
#: D-063: YouTube answers HTTP 429 to a translated track more often.
RATE_LIMITED = "(translations are rate-limited more often)"


def default_track(meta, listed) -> str | None:
    """D-045: the original-audio track; without one, what --lang would take."""
    from .ingest.fetch import AUTOMATIC_ORIGINAL, DEFAULT_LANG, choose_language

    for track in listed:
        if track.source == AUTOMATIC_ORIGINAL:
            return track.code
    code, _ = choose_language(meta, DEFAULT_LANG)
    return code or (listed[0].code if listed else None)


def choose_track(meta, listed, translations) -> str | None:
    """D-062: the caption track, by name; the default is today's choice.
    A video with one track has nothing to choose: it is named, not asked."""
    if len(listed) == 1 and not translations:
        detail("caption", listed[0].name)
        return listed[0].code
    options = [Option(t.name, value=t.code) for t in listed]
    if translations:
        options.append(Option("Other languages (automatic translations)…",
                              f"{len(translations)} language(s) {RATE_LIMITED}", value=TRANSLATIONS))
    while True:
        picked = prompts.select(
            "Which caption?",
            options,
            hint="the original audio's own caption is the closest to what was said",
            default=default_track(meta, listed),
        )
        if picked != TRANSLATIONS:
            return picked
        picked = prompts.select(
            "Which language?",
            [Option(t.name, RATE_LIMITED, value=t.code) for t in translations],
            hint="a machine translation of the original audio's caption",
        )
        if picked is not None:
            return picked


def fetch_file() -> str | None:
    """A file: a caption goes straight to normalizing, audio or video to
    local transcription."""
    from .cli import caption_run

    path = pick_file(Path.home())
    if path is NO_PICKER:
        say(mark("  no file dialog here; type the path instead", "hint"))
        answer = prompts.text(
            "Path to the file",
            hint="audio or video (transcribed here), or a .srt, .vtt or legenda.txt caption",
            kind="path",
        )
        path = Path(answer.strip().strip("'\"")).expanduser() if answer else None
    if path is None:
        return BACK
    if not path.is_file():
        error(f"no file at {path}")
        return None
    if path.suffix.lower() in CAPTION_SUFFIXES:  # already a text: nothing to transcribe
        normalize_run(caption_run(path), path, chained=True)
        return None
    return after_fetch(run_command(["fetch", str(path)]))


def after_fetch(code: int) -> None:
    """The step after a fetch: normalize, if the user wants."""
    if code != 0:
        error("fetch did not finish")
        return
    run = newest_run()
    if run and prompts.confirm("Next: normalize this run now?", default=True):
        normalize_run(run, chained=True)


#: The answer to "What is this video about?" that no installed pack covers.
NO_PACK = "\0none"


def pack_line(path: Path) -> str:
    """`pt-BR · 0.3.4 · 150 terms`: what the pack chooser shows beside a name."""
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return "(unreadable)"
    parts = [str(data.get("language") or "?"), str(data.get("version") or "?")]
    parts.append(f"{len(data.get('terms') or ())} terms")
    return " · ".join(parts)


#: D-061: config.toml's key for the pack offered first.
FIRST_PACK = "pack"


def packs_in_order() -> dict[str, Path]:
    """Every installed pack, the one chosen in Settings first."""
    packs = installed_packs()
    first = read_config().get(FIRST_PACK)
    if first in packs:
        packs = {first: packs[first], **{n: p for n, p in packs.items() if n != first}}
    return packs


def choose_pack(question: str, allow_none: bool) -> Path | str | None:
    """D-054: the pack for this video, NO_PACK for another area, None for back.

    With `allow_none` false and one pack installed, that pack, without asking.
    """
    packs = packs_in_order()
    if not allow_none and len(packs) == 1:
        return next(iter(packs.values()))
    options = [Option(name, pack_line(path), value=path) for name, path in packs.items()]
    if allow_none:
        options.append(Option("none / another area", "skip normalization: no pack covers it", value=NO_PACK))
    return prompts.select(
        question,
        options,
        hint="the pack whose terms this video uses; a pack applied to another field only does harm",
    )


#: The option of "Normalize which run?" that asks for a path instead.
A_FILE = "\0file"
#: What "Normalize a run" takes as a typed path.
CAPTION_SUFFIXES = (".txt", ".srt", ".vtt")


def typed_caption() -> Path | None:
    """A caption file the user types the path of, or None."""
    answer = prompts.text(
        "Path to a caption file",
        hint="a legenda.txt (m:ss text lines), or a .srt or .vtt subtitle",
        kind="path",
    )
    if not answer:
        return None
    path = Path(answer.strip().strip("'\"")).expanduser()
    if not path.is_file():
        error(f"no file at {path}")
        return None
    if path.suffix.lower() not in CAPTION_SUFFIXES:
        error(f"{path.name}: expected {', '.join(CAPTION_SUFFIXES)}")
        return None
    return path


#: What normalize_run returns when Back was chosen at its first question.
BACK = "back"


def normalize() -> None:
    """A run from the list, or a file typed by its path; Back from the pack
    question comes back to this list (D-061)."""
    from .cli import caption_run

    stage("Normalize")
    file_option = Option("A file…", "type the path to a .txt, .srt or .vtt", value=A_FILE, key="f")
    while True:
        runs = list_runs()
        if runs:
            width = max(len(r.id) for r in runs)
            picked = prompts.select(
                "Normalize which run?",
                [Option(r.id.ljust(width), f"{r.date or '-':10s}  {r.title}", value=r.id) for r in runs]
                + [file_option],
                hint="the video's id, its publication date and its title; f for a file",
            )
        else:
            picked = A_FILE
        if picked is None:
            return
        if picked != A_FILE:
            run, caption = runs_root() / picked, None
        else:
            caption = typed_caption()
            if not caption:
                if runs:
                    continue
                return
            run = caption_run(caption)
        if normalize_run(run, caption) != BACK:
            return


def normalize_run(run: Path, caption: Path | None = None, chained: bool = False) -> str | None:
    """Normalize, offer the review, then offer the folder.

    `chained` when another step led here, which then labels this one. BACK
    when the pack question was answered with Back, before anything was written.
    """
    from .cli import is_subtitle, is_unfit

    if chained:
        stage("Normalize", run.name)
    caption = caption or caption_of(run)
    if not caption:
        return None
    pack = choose_pack("What is this video about?", allow_none=True)
    if pack is None:
        return BACK
    if pack == NO_PACK:
        say(mark("No pack for this area, so nothing was normalized.", "need"))
        say(mark("  `transcript-normalizer pack list` shows the packs you can install.", "hint"))
        return None
    say(mark(f"Normalizing {run.name}", "title"))
    code = run_command(["normalize", str(caption), "--summary", "--menu", "--pack", str(pack)])
    if code != 0:
        error("normalize did not finish")
        return None
    if is_unfit(run):  # D-054: normalize said so, and applied nothing
        return None
    if is_subtitle(caption):  # converted into the run's legenda.txt
        caption = run / CAPTION_FILE
    count = pending_count(run)
    if not count:
        say(mark("Nothing to confirm. Done.", "ok"))
    else:
        say(mark("The result is usable as it is; reviewing only makes the next run better.", "hint"))
        if prompts.confirm(f"Next: review the {count} uncertain one(s) now?", default=True):
            review_run(run, caption, pack, chained=True)
            return None
    offer_folder(run)
    return None


#: D-061: what "Review pending" says on a run with nothing to ask.
NOTHING_TO_REVIEW = "nothing to review for this run"


def review() -> None:
    """A run, then a pack; Back from the pack question comes back to the runs."""
    from .cli import is_unfit

    stage("Review")
    while True:
        run = choose_run("Review which run?")
        if not run:
            return
        # A refused pack (D-054) leaves nothing pending either; there is no
        # folder to offer, since nothing was done.
        if is_unfit(run) or not pending_count(run):
            say(mark(NOTHING_TO_REVIEW, "need"))
            return
        pack = choose_pack("Review against which pack?", allow_none=False)
        if pack:
            review_run(run, pack=pack)
            return


def review_run(
    run: Path, caption: Path | None = None, pack: Path | None = None, chained: bool = False
) -> None:
    """The review; `chained` when normalize has just printed the counters."""
    caption = caption or caption_of(run)
    if not caption:
        return
    if chained:
        stage("Review", run.name)
    say(mark(f"Reviewing {run.name}", "title"))
    argv = ["normalize", str(caption), "--review", "--menu", "--quiet" if chained else "--summary"]
    code = run_command(argv + (["--pack", str(pack)] if pack else []))
    if code not in (0, 130):  # 130: interrupted, the answers so far are kept (D-037)
        error("review did not finish")
        return
    offer_contribution(pack)
    offer_folder(run)


def offer_contribution(pack: Path | None) -> None:
    """D-056: after a review, if the learned layer has something the pack does not."""
    from .contribute import items

    pack = pack or default_pack()
    if not items(pack):
        return
    if prompts.confirm("Contribute what you taught the tool?", default=False):
        run_command(["pack", "propose", "--pack", pack.stem])


def open_folder(path: Path) -> bool:
    """The system's file manager on `path`; False when there is none to call."""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - Windows only
            return True
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        if shutil.which(opener) is None:
            return False
        subprocess.Popen(
            [opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except OSError:
        return False


def offer_folder(run: Path) -> None:
    if not prompts.confirm("Open the folder?", default=False):
        return
    if open_folder(run):
        say("opened ", mark(run, "path"))
    else:
        say("the folder: ", mark(run, "path"))


def show() -> None:
    run = choose_run("Show which run?")
    if not run:
        return
    for path in sorted(p for p in run.rglob("*") if p.is_file()):
        say("  ", mark(path, "path"))
    normalized = run / NORMALIZED_FILE
    if not normalized.exists():
        say(mark("not normalized yet.", "need"))
        return
    lines = normalized.read_text(encoding="utf-8").splitlines()
    say(f"\n{NORMALIZED_FILE}, first {min(PREVIEW_LINES, len(lines))} of {len(lines)} lines:")
    print(helptext.wrap_block("\n".join(lines[:PREVIEW_LINES])))


def listing() -> None:
    run_command(["list"])


def help_text() -> None:
    run_command(["help"])


# ------------------------------------------------------------------ settings (D-061)

#: config.toml's key for the folder runs/ and packs/ go in.
DATA_DIR = "data_dir"
#: What pick_folder returns where there is no dialog to show.
NO_PICKER = object()


def default_folder() -> Path:
    """Where the files go when Settings has not chosen a folder."""
    return data_dir() if is_frozen() else Path.cwd()


def folder_source() -> str:
    """Why base_dir() is what it is, in a few words."""
    if os.environ.get(DATA_DIR_ENV):
        return f"from {DATA_DIR_ENV}, which wins over Settings"
    if configured_dir() is not None:
        return "chosen in Settings"
    return "the documents folder" if is_frozen() else "the current folder"


def system_dialog(ask):
    """`ask(filedialog, parent)` in the system's dialog: its answer, or NO_PICKER
    when there is no dialog here (no tkinter, or no display)."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return NO_PICKER
    try:
        root = tkinter.Tk()
    except tkinter.TclError:  # no display
        return NO_PICKER
    try:
        root.withdraw()
        root.attributes("-topmost", True)  # above the terminal, not behind it
        return ask(filedialog, root)
    finally:
        root.destroy()


def pick_folder(initial: Path):
    """The system's folder dialog: a Path, None when cancelled, or NO_PICKER."""
    chosen = system_dialog(lambda dialog, root: dialog.askdirectory(
        parent=root, initialdir=str(initial), mustexist=False, title="Where to save your files"
    ))
    return chosen if chosen is NO_PICKER else (Path(chosen) if chosen else None)


def pick_file(initial: Path):
    """D-062: the system's file dialog: a Path, None when cancelled, or NO_PICKER."""
    pattern = lambda suffixes: " ".join(f"*{s}" for s in suffixes)  # noqa: E731
    chosen = system_dialog(lambda dialog, root: dialog.askopenfilename(
        parent=root, initialdir=str(initial), title="The file to fetch",
        filetypes=[  # the first is the dialog's default (D-063)
            ("All supported (audio, video, captions)", pattern(MEDIA_SUFFIXES + CAPTION_SUFFIXES)),
            ("Audio or video", pattern(MEDIA_SUFFIXES)),
            ("Captions", pattern(CAPTION_SUFFIXES)),
            ("All files", "*"),
        ],
    ))
    return chosen if chosen is NO_PICKER else (Path(chosen) if chosen else None)


def picker_check() -> str:
    """The folder dialog's parts load (the release smoke test, D-061): no window."""
    import tkinter
    from tkinter import filedialog

    return f"tkinter {tkinter.Tcl().eval('info patchlevel')}, filedialog {filedialog.__name__}"


def typed_folder() -> Path | None:
    answer = prompts.text("The folder to save your files in", hint="it is created if it does not exist", kind="path")
    return Path(answer.strip().strip("'\"")).expanduser() if answer else None


def save_setting(key: str, value) -> None:
    settings = read_config()
    settings[key] = value
    write_config(settings)


def choose_folder() -> None:
    """Where to save your files: the dialog, or a typed path without one."""
    detail("now", base_dir(), "path")
    say(mark(f"  {folder_source()}", "hint"))
    options = [Option("Choose another folder…", "opens the folder dialog", value="pick")]
    if configured_dir() is not None:
        options.append(Option("Use the default again", str(default_folder()), value="default"))
    choice = prompts.select("Where to save your files", options)
    if choice is None:
        return
    if choice == "default":
        save_setting(DATA_DIR, None)
    else:
        folder = pick_folder(base_dir())
        if folder is NO_PICKER:
            say(mark("  no folder dialog here; type the path instead", "hint"))
            folder = typed_folder()
        if folder is None:
            return
        folder = folder.absolute()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as failure:
            error(f"cannot use {folder}: {failure.strerror or failure}")
            return
        save_setting(DATA_DIR, str(folder))
    say(mark("Saved. ", "ok"), "Your files go in ", mark(base_dir(), "path"))
    say(mark("  files saved before stay where they were", "hint"))
    if os.environ.get(DATA_DIR_ENV):
        say(mark(f"  {DATA_DIR_ENV} is set, and wins over this until it is unset", "need"))


def choose_first_pack() -> None:
    """The pack the menu offers first, when it asks what a video is about."""
    packs = installed_packs()
    picked = prompts.select(
        "Which pack should be offered first?",
        [Option(name, pack_line(path), value=name) for name, path in packs.items()],
        hint="`transcript-normalizer pack install <name>` adds more",
    )
    if picked is None:
        return
    save_setting(FIRST_PACK, picked)
    say(mark("Saved. ", "ok"), "Offered first: ", mark(picked, "path"))


def settings() -> None:
    stage("Settings")
    hint = "saved in your user settings, for every run of the menu"
    while True:
        first = next(iter(packs_in_order()), "")
        choice = prompts.select("What would you like to change?", [
            Option("Where to save your files", str(base_dir()), value="folder"),
            Option("The pack offered first", first, value="pack"),
        ], hint=hint)
        hint = ""  # once: the list comes back after each change
        if choice is None:
            return
        (choose_folder if choice == "folder" else choose_first_pack)()


ACTIONS = {
    "1": fetch, "2": normalize, "3": review, "4": show, "5": listing, "6": help_text, "7": settings,
}


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
                back=False,
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
