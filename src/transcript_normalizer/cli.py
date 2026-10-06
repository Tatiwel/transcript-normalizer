"""The `transcript-normalizer` command.

    transcript-normalizer [normalize] <legenda.txt> --pack <pack.yaml>
    transcript-normalizer fetch <url>
    transcript-normalizer list
    transcript-normalizer pack list | install <name> | update
    transcript-normalizer help          (also --help; the same text as menu item 6)
    transcript-normalizer               (on a terminal: the interactive menu, D-051)

`normalize` is the default, so a caption file may be given straight away.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import csv
import os
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .core.fit import MIN_FIT_TERMS, fitting_terms
from .core.matcher import find_annotations, resolve_overlaps
from .core.pack import Learned, Pack, load_pack, save_learned
from .core.render import render_normalized
from .core.standoff import (
    BAND_HIGH,
    BAND_LOW,
    BAND_MEDIUM,
    RULE_UNIT,
    Annotation,
    applied,
    in_band,
    write_json,
)
from .core.text import Transcript, read_caption
from .catalog import list_runs
from .languages import LanguageNotFound
from .ingest import fetch as ingest_fetch
from .runs import (
    ANNOTATIONS_FILE,
    CAPTION_FILE,
    CORRECTIONS_FILE,
    NORMALIZED_FILE,
    PENDING_FILE,
    REPORT_FILE,
    default_pack,
    learned_file,
    needs_review_dir,
    run_dir,
    runs_root,
)

PROG = "transcript-normalizer"
COMMANDS = ("normalize", "fetch", "list", "pack", "help")

#: How many example lines the confirmation loop shows per variant (D-019).
EXAMPLES_PER_VARIANT = 3

#: The six columns of a gold file, and the status a draft row carries.
GOLD_COLUMNS = ("timestamp", "wrong", "correct", "term", "class", "status")
DRAFT_STATUS = "draft"

#: What the gold file calls the class of a unit-rule row.
UNIT_CLASS = "unidade"

#: D-019: one question per variant, not per term group. `a` and `r` answer the
#: current variant and every variant of the current term after it. D-020 adds
#: `l`: it is this term, but the speaker said it that way.
CONFIRM_PROMPT = (
    "    {variant} -> {term}? "
    "[y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no: "
)
BULK_ANSWERS = {"a": "y", "r": "n"}

#: D-023: why a variant is still in needs-review/pending.txt.
NEVER_ASKED = "[never asked]"
SKIPPED = "[skipped]"


def form(annotation: Annotation) -> str:
    """The observed text, with the caption's line break collapsed to one space."""
    return " ".join(annotation.original.split())


def group_by_term(annotations: list[Annotation]) -> dict[str, Counter]:
    groups: dict[str, Counter] = defaultdict(Counter)
    for a in annotations:
        groups[a.term][form(a)] += 1
    return groups


def _lines(groups: dict[str, Counter]) -> list[str]:
    out = []
    for term, counter in sorted(groups.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        total = sum(counter.values())
        listed = ", ".join(f for f, _ in counter.most_common())
        plural = "occurrence" if total == 1 else "occurrences"
        out.append(f"  {listed} ({total} {plural}) -> {term}")
    return out


def report(annotations: list[Annotation]) -> str:
    """High band by term, then the unit rules, then D-011's medium band to confirm."""
    high = [a for a in annotations if a.band == BAND_HIGH]
    fixed = [a for a in high if a.is_correction]
    sections = [
        ("terms", group_by_term([a for a in fixed if a.rule != RULE_UNIT])),
        ("unit rules", group_by_term([a for a in fixed if a.rule == RULE_UNIT])),
        # D-020: another name of the term, as the speaker said it.
        ("recognized (not changed)", group_by_term([a for a in high if a.is_alias])),
        ("to confirm", group_by_term(in_band(annotations, BAND_MEDIUM))),
    ]

    out: list[str] = []
    for title, groups in sections:
        if not groups:
            continue
        out.append(f"{title}:")
        out += _lines(groups)
        out.append("")

    low = in_band(annotations, BAND_LOW)
    if low:
        out.append(f"{len(low)} low-confidence marks, not applied")
    if not out:
        out.append("no annotations.")
    return "\n".join(out).rstrip("\n")


def examples(transcript: Transcript, annotations: list[Annotation], limit: int) -> list[str]:
    out = []
    for a in annotations[:limit]:
        lines = transcript.spans(a.start, a.end)
        stamp = "/".join(l.timestamp for l in lines)
        text = " ".join(" ".join(l.text for l in lines).split())
        out.append(f"    {stamp}  {text}")
    return out


def write_corrections(
    transcript: Transcript, annotations: list[Annotation], pack: Pack, path: Path
) -> Path:
    """needs-review/corrections.csv (D-023): the applied annotations as a gold.csv
    draft, same columns, status `draft`, for hand-checking a new fixture. Alias
    rows are in it too, with `correct` equal to `wrong`, since a gold file needs
    them."""
    klass = {t.term: (t.klass or "") for t in pack.terms}
    rows = sorted(applied(annotations), key=lambda a: (a.start, a.end))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(GOLD_COLUMNS)
        for a in rows:
            writer.writerow(
                [
                    transcript.locate(a.start)[1],
                    form(a),
                    form(a) if a.is_alias else a.replacement,  # D-020: left as said
                    a.term,
                    UNIT_CLASS if a.rule == RULE_UNIT else klass.get(a.term, ""),
                    DRAFT_STATUS,
                ]
            )
    return path


def ask(prompt: str) -> str:
    """One answer from the user. End of input counts as `skip`."""
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "s"


def confirm_groups(annotations: list[Annotation]) -> list[tuple[str, list[Annotation]]]:
    """D-011's medium band, grouped by term, busiest first."""
    by_term: dict[str, list[Annotation]] = defaultdict(list)
    for a in in_band(annotations, BAND_MEDIUM):
        by_term[a.term].append(a)
    return sorted(by_term.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def variant_groups(group: list[Annotation]) -> list[tuple[str, list[Annotation]]]:
    """One entry per observed form, busiest first, then alphabetically (D-019)."""
    by_form: dict[str, list[Annotation]] = defaultdict(list)
    for a in group:
        by_form[form(a)].append(a)
    return sorted(by_form.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def occurrences(count: int) -> str:
    return f"{count} occurrence" if count == 1 else f"{count} occurrences"


def term_heading(term: str, group: list[Annotation]) -> str:
    """The term is named once; the questions below it are per variant."""
    return f"{term}  ({occurrences(len(group))})"


def variant_block(
    transcript: Transcript, term: str, variant: str, found: list[Annotation]
) -> tuple[str, str]:
    """One variant of one term: (body, prompt), with that variant's own examples."""
    body = "\n".join(
        [
            f"  {variant}  ({occurrences(len(found))})",
            *examples(transcript, found, EXAMPLES_PER_VARIANT),
        ]
    )
    return body, CONFIRM_PROMPT.format(variant=variant, term=term)


def pending_text(
    transcript: Transcript,
    annotations: list[Annotation],
    outcomes: dict[tuple[str, str], str] | None = None,
) -> tuple[str, int]:
    """needs-review/pending.txt (D-023): every unanswered variant, grouped by term.

    Each variant keeps its own example lines (D-019) and says why it is still
    here: `[never asked]` when the run had no --confirm, `[skipped]` when the
    user answered `s`. A variant that got any other answer is not pending.
    Returns the text and how many variants it lists.
    """
    blocks, count = [], 0
    for term, group in confirm_groups(annotations):
        lines = []
        for variant, found in variant_groups(group):
            answer = None if outcomes is None else outcomes.get((term, variant))
            if answer is None:
                tag = NEVER_ASKED  # no --confirm, or the loop was interrupted first
            elif answer.startswith("s"):
                tag = SKIPPED
            else:
                continue
            body, _ = variant_block(transcript, term, variant, found)
            head, *examples_ = body.split("\n")
            lines.append(f"{head}  {tag}")
            lines.extend(examples_)
            count += 1
        if lines:
            blocks.append("\n".join([term_heading(term, group), *lines]))
    return ("\n\n".join(blocks) + "\n" if blocks else ""), count


def write_pending(
    out_dir: Path,
    transcript: Transcript,
    annotations: list[Annotation],
    outcomes: dict[tuple[str, str], str] | None = None,
) -> tuple[Path, int]:
    """Write pending.txt, or remove a stale one when nothing is left pending."""
    path = needs_review_dir(out_dir) / PENDING_FILE
    text, count = pending_text(transcript, annotations, outcomes)
    if count:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    elif path.exists():
        path.unlink()
        if not any(path.parent.iterdir()):
            path.parent.rmdir()
    return path, count


@dataclass
class Session:
    """Where a --confirm session got to (D-037)."""

    learned: Learned
    outcomes: dict[tuple[str, str], str] = field(default_factory=dict)
    kept: int = 0  # answers written to the learned layer
    interrupted: bool = False


def confirm_loop(
    transcript: Transcript,
    annotations: list[Annotation],
    learned: Learned,
    save=None,
) -> Session:
    """D-011's confirmation loop, one question per variant (D-019).

    A term-level answer cannot express a mixed group, so the term is shown once
    and each of its variants is asked about separately. `a` and `r` answer the
    current variant and the rest of that term's variants; they do not carry to
    the next term. `l` records the variant as an alias of the term (D-020): it
    will be recognized from then on and never substituted.

    D-037: `save(learned)` runs after every answer that changes the layer, so
    an interrupted session keeps what it was told; Ctrl+C ends the loop and the
    session says it was interrupted.
    """
    session = Session(learned)
    groups = confirm_groups(annotations)
    if not groups:
        print("nothing to confirm.")
        return session
    try:
        _ask_all(transcript, groups, session, save)
    except KeyboardInterrupt:
        session.interrupted = True
    return session


def _ask_all(transcript, groups, session: Session, save) -> None:
    learned, outcomes = session.learned, session.outcomes

    for term, group in groups:
        print(f"\n{term_heading(term, group)}")
        bulk = None
        for variant, found in variant_groups(group):
            body, prompt = variant_block(transcript, term, variant, found)
            print(body)

            answer = bulk if bulk else ask(prompt)
            bulk = BULK_ANSWERS.get(answer[:1], bulk)
            answer = BULK_ANSWERS.get(answer[:1], answer)

            if answer.startswith("y"):
                learned = learned.confirm(term, variant)
                outcomes[(term, variant)] = "y"
                print(f"    confirmed: {variant} -> {term}")
            elif answer.startswith("n"):
                learned = learned.reject(variant, term)
                outcomes[(term, variant)] = "n"
                print(f"    rejected: {variant} -> {term}")
            elif answer.startswith("l"):
                learned = learned.alias(term, variant)
                outcomes[(term, variant)] = "l"
                print(f"    alias: {variant} is {term}, left as said")
            else:
                outcomes[(term, variant)] = "s"
                print("    skipped.")
                continue
            # D-037: every answer is on disk before the next question.
            session.learned = learned
            session.kept += 1
            if save is not None:
                save(learned)


# ------------------------------------------------------------------ D-053


def print_summary(annotations: list[Annotation], normalized: Path) -> None:
    """The menu's view of a run: three counters and where the result is.

    `report.txt` keeps the full report; this is what `--summary` prints instead.
    """
    from .prompts import mark, say

    fixed = [a for a in annotations if a.band == BAND_HIGH and a.is_correction]
    recognized = [a for a in annotations if a.band == BAND_HIGH and a.is_alias]
    doubtful = sum(len(variant_groups(group)) for _, group in confirm_groups(annotations))
    pairs = list(dict.fromkeys(f"{a.original} → {a.replacement}" for a in fixed))[:2]
    say(mark(f"corrected {len(fixed)}", "ok"), f"  ({', '.join(pairs)})" if pairs else "")
    say(mark(f"recognized {len(recognized)}", "title"), "  (terms already spelled right, left as they are)")
    say(mark(f"to confirm {doubtful}", "need"), "  (the tool was unsure; your answer is remembered)")
    say("result: ", mark(normalized, "path"))


#: How much of an example line the review screen shows around the form.
EXAMPLE_WIDTH = 72


def highlighted_example(transcript: Transcript, annotation: Annotation) -> str:
    """One example line, the form in «guillemets», cut to fit one row."""
    lines = transcript.spans(annotation.start, annotation.end)
    stamp = lines[0].timestamp
    text = " ".join(" ".join(l.text for l in lines).split())
    form = annotation.original
    at = text.find(form)
    if at < 0:
        return f"{stamp}  {text[:EXAMPLE_WIDTH]}"
    text = f"{text[:at]}«{form}»{text[at + len(form):]}"
    start = max(0, min(at - 25, len(text) - EXAMPLE_WIDTH))
    if start:  # begin at a word, not in the middle of one
        space = text.find(" ", start, at)
        start = space + 1 if space >= 0 else start
    clip = text[start : start + EXAMPLE_WIDTH]
    return f"{stamp}  {'…' if start else ''}{clip}{'…' if start + EXAMPLE_WIDTH < len(text) else ''}"


def review_terms(
    transcript: Transcript,
    annotations: list[Annotation],
    learned: Learned,
    save=None,
) -> Session:
    """D-053: the review one term per screen, as a multi-select.

    Selected forms are the recognizer mishearing the term: confirmed. The rest
    are rejected. Of the selected, a second question takes those the speaker
    really said that way: aliases instead of variants (D-020). Esc on a term
    leaves all its forms pending. The learned layer is saved after each term.
    """
    from .prompts import Option, multi_select

    session = Session(learned)
    groups = confirm_groups(annotations)
    if not groups:
        print("nothing to confirm.")
        return session
    try:
        for term, group in groups:
            forms = variant_groups(group)
            options = [
                Option(
                    variant,
                    f"{occurrences(len(found))} · {highlighted_example(transcript, found[0])}",
                    value=variant,
                )
                for variant, found in forms
            ]
            chosen = multi_select(
                f'Which of these are the recognizer mishearing "{term}"?',
                options,
                hint=f"pick the ones that should read {term}; the others are rejected",
            )
            if chosen is None:
                for variant, _ in forms:
                    session.outcomes[(term, variant)] = "s"
                continue
            aliases = []
            if chosen:
                aliases = multi_select(
                    f'Any of these are "{term}" said another way (keep the text, just recognise it)?',
                    [o for o in options if o.result in chosen],
                    hint="a ticker, a plural, a nickname: the speaker's own words. - if none",
                ) or []
            for variant, _ in forms:
                if variant in aliases:
                    session.learned = session.learned.alias(term, variant)
                    session.outcomes[(term, variant)] = "l"
                elif variant in chosen:
                    session.learned = session.learned.confirm(term, variant)
                    session.outcomes[(term, variant)] = "y"
                else:
                    session.learned = session.learned.reject(variant, term)
                    session.outcomes[(term, variant)] = "n"
                session.kept += 1
            if save is not None:
                save(session.learned)  # D-037, per term
    except KeyboardInterrupt:
        session.interrupted = True
    return session


def review_path(out_dir: Path, name: str) -> Path:
    directory = needs_review_dir(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / name


def keep_original(caption: Path, out_dir: Path) -> Path:
    """D-016: the raw caption sits next to what was rendered from it."""
    target = out_dir / caption.name
    if not (target.exists() and target.samefile(caption)):
        shutil.copyfile(caption, target)
    return target


#: Subtitle files `normalize` converts into a run's legenda.txt first.
SUBTITLE_SUFFIXES = (".srt", ".vtt")


def is_subtitle(path: Path) -> bool:
    return Path(path).suffix.lower() in SUBTITLE_SUFFIXES


def caption_run(caption: Path, out: Path | None = None) -> Path:
    """The run directory `normalize <caption>` writes into, without writing anything.

    A .srt or .vtt goes to `runs/<stem>/`; a legenda.txt follows D-018.
    """
    caption = Path(caption)
    if is_subtitle(caption):
        return Path(out) if out is not None else runs_root() / caption.stem
    return run_dir(caption, out, read_caption(caption).header_field("URL"))


def convert_subtitle(subtitle: Path, out: Path | None = None) -> Path:
    """A .srt or .vtt the user already has, as `runs/<stem>/legenda.txt`.

    The same converter fetch uses, with a header that names the file. The
    subtitle itself is left where it is.
    """
    from .ingest.header import file_header
    from .ingest.subtitles import subtitle_to_lines

    subtitle = Path(subtitle)
    target = caption_run(subtitle, out)
    target.mkdir(parents=True, exist_ok=True)
    body = subtitle_to_lines(subtitle.read_text(encoding="utf-8-sig"), subtitle.suffix)
    caption = target / CAPTION_FILE
    caption.write_text(file_header(subtitle.name, subtitle.stem) + body + "\n", encoding="utf-8")
    return caption


#: D-054: what normalize says when the pack does not fit the transcript.
NOT_FIT = (
    "pack {name} does not seem to fit this transcript ({found} terms found); "
    "nothing applied. Use --force to apply anyway."
)


def refuse_unfit(args: argparse.Namespace, transcript: Transcript, out_dir: Path, found: int) -> int:
    """D-054: normalized.txt identical to the input, no annotations, no questions."""
    message = NOT_FIT.format(name=args.pack.stem, found=found)
    write_json([], out_dir / ANNOTATIONS_FILE)
    (out_dir / NORMALIZED_FILE).write_text(render_normalized(transcript, []), encoding="utf-8")
    keep_original(args.caption, out_dir)
    write_pending(out_dir, transcript, [])  # removes a stale pending.txt
    (out_dir / REPORT_FILE).write_text(f"{args.caption}: {message}\n", encoding="utf-8")
    print(message)
    return 0


def is_unfit(run: Path) -> bool:
    """Whether the run's last normalize refused for D-054 (the menu asks)."""
    report_file = Path(run) / REPORT_FILE
    return report_file.exists() and "does not seem to fit" in report_file.read_text(encoding="utf-8")


def run_normalize(args: argparse.Namespace) -> int:
    if not args.caption.exists():
        print(f"no caption at {args.caption}; run fetch first", file=sys.stderr)
        return 1
    if is_subtitle(args.caption):
        args.caption = convert_subtitle(args.caption, args.out)
        print(f"converted to {args.caption}")
    if not args.pack.exists():
        print(f"no pack at {args.pack}", file=sys.stderr)
        if args.pack == default_pack():
            print(
                "that is the default pack; pass --pack, or put one in "
                f"{default_pack().parent}{os.sep} (D-017).",
                file=sys.stderr,
            )
        return 2

    learned_at = learned_file(args.pack, args.learned)
    try:
        pack = load_pack(args.pack, learned_from=learned_at, allow_generic=args.allow_generic)
    except LanguageNotFound as error:
        print(error, file=sys.stderr)
        return 2
    transcript = read_caption(args.caption)
    annotations = resolve_overlaps(find_annotations(transcript, pack))

    out_dir = run_dir(args.caption, args.out, transcript.header_field("URL"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # D-054: a pack that names fewer than three of its terms here does not fit.
    found = len(fitting_terms(annotations))
    if found < MIN_FIT_TERMS and not args.force:
        return refuse_unfit(args, transcript, out_dir, found)

    written = [write_json(annotations, out_dir / ANNOTATIONS_FILE)]

    # D-016: rendered views, plus the original kept beside them.
    normalized = out_dir / NORMALIZED_FILE
    normalized.write_text(render_normalized(transcript, annotations), encoding="utf-8")
    written.append(normalized)
    written.append(keep_original(args.caption, out_dir))

    # D-023: what needs a person goes under needs-review/.
    if args.corrections:
        written.append(
            write_corrections(
                transcript, annotations, pack, review_path(out_dir, CORRECTIONS_FILE)
            )
        )
    # As things stand before any --confirm: everything in the medium band is
    # pending and nothing has been asked. The loop below rewrites it.
    pending, count = write_pending(out_dir, transcript, annotations)
    if count:
        written.append(pending)

    written.append(out_dir / REPORT_FILE)

    lines = [
        f"{args.caption}: {len(transcript.lines)} caption lines, pack {pack.version}",
        report(annotations),
        "",
        f"{len(annotations)} annotations, {len(applied(annotations))} applied",
        f"written to {out_dir}{os.sep}",
    ]
    lines += [f"  {path.relative_to(out_dir)}" for path in written]
    text = "\n".join(lines) + "\n"

    (out_dir / REPORT_FILE).write_text(text, encoding="utf-8")
    if args.summary:
        print_summary(annotations, normalized)
    elif not args.quiet:
        print(text, end="")

    if args.gold_draft_used:
        print("--gold-draft is now --corrections (D-023)", file=sys.stderr)

    if args.confirm or args.review:
        # D-013 and D-017: the learned layer under packs/, never pack.yaml.
        # D-037: saved after every answer (--confirm) or every term (--review).
        ask_all = review_terms if args.review else confirm_loop
        session = ask_all(
            transcript, annotations, pack.learned, save=lambda learned: save_learned(learned, learned_at)
        )
        pending, count = write_pending(out_dir, transcript, annotations, session.outcomes)
        if session.interrupted:
            print(
                f"\ninterrupted: {session.kept} answer(s) kept in {learned_at}; "
                f"run {'--review' if args.review else '--confirm'} again to go on from there"
            )
            return 130
        if not session.learned.is_empty():
            print(f"\nlearned layer written to {save_learned(session.learned, learned_at)}")
        if count:
            print(f"{count} variant(s) still pending in {pending}")
        else:
            print("nothing left pending.")
    return 0


def run_list(args: argparse.Namespace) -> int:
    """D-022: id, date and title of every run."""
    runs = list_runs()
    if not runs:
        print(f"no runs under {runs_root()}")
        return 0
    width = max(len(r.id) for r in runs)
    for r in runs:
        print(f"{r.id:{width}s}  {r.date or '-':10s}  {r.title}")
    return 0


def run_help(args: argparse.Namespace | None = None) -> int:
    """D-051: sectioned help, the same for `help`, `--help` and the menu."""
    from .helptext import render

    print(render(), end="")
    return 0


def shown(path: Path) -> str:
    """A path relative to the current directory when it is under it."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def add_normalize_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "caption",
        type=Path,
        help="caption file: a legenda.txt, or a .srt or .vtt (converted into runs/<stem>/ first)",
    )
    parser.add_argument(
        "--pack",
        type=Path,
        default=default_pack(),
        help=f"domain pack. default: {shown(default_pack())}",
    )
    parser.add_argument(
        "--out",
        type=Path,
        metavar="DIR",
        help="write into DIR instead of runs/<id>/",
    )
    parser.add_argument(
        "--learned",
        type=Path,
        metavar="PATH",
        help="learned layer file, instead of packs/<pack-name>.learned.yaml",
    )
    parser.add_argument(
        "--corrections",
        action="store_true",
        help="also write needs-review/corrections.csv, the applied annotations "
        "as a gold draft with status `draft`",
    )
    # D-023: the old name, kept hidden for one release.
    parser.add_argument(
        "--gold-draft", dest="gold_draft_used", action="store_true", help=argparse.SUPPRESS
    )
    asking = parser.add_mutually_exclusive_group()
    asking.add_argument(
        "--confirm",
        action="store_true",
        help="review the medium band form by form and record the answers in the learned layer (D-013)",
    )
    asking.add_argument(
        "--review",
        action="store_true",
        help="the same, one screen per term: pick the forms that are the term (D-053)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="print three counters instead of the full report; report.txt is unchanged",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=f"apply the pack even when fewer than {MIN_FIT_TERMS} of its terms are found "
        "with confidence (D-054)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print neither the report nor the counters (the menu, when it has just shown them); "
        "report.txt is unchanged",
    )
    parser.add_argument(
        "--allow-generic",
        action="store_true",
        help="if the pack's language has no module, match with the generic one "
        "(no inflections, no unit rules) instead of stopping (D-033)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Domain-term normalization for ASR transcripts and auto-captions. "
        "The transcript is never modified (D-004) and every output goes under "
        "runs/ (D-015).",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    normalize = commands.add_parser(
        "normalize",
        help="annotate a caption file against a domain pack (the default command)",
        description="Propose stand-off normalizations for a caption file.",
    )
    add_normalize_arguments(normalize)
    normalize.set_defaults(run=run_normalize)

    fetch = commands.add_parser(
        "fetch",
        help="download a platform caption, or transcribe locally with --whisper",
        description=ingest_fetch.run.__doc__,
    )
    ingest_fetch.add_arguments(fetch)
    fetch.set_defaults(run=ingest_fetch.run)

    listing = commands.add_parser(
        "list",
        help="print id, date and title for every run",
        description="List every run under runs/: the video id, its publication "
        "date and its title (D-022).",
    )
    listing.set_defaults(run=run_list)

    from . import registry

    packs = commands.add_parser(
        "pack",
        help="list, install and update packs from the packs repository (D-055)",
        description=f"Domain packs from {registry.REPOSITORY}, installed into packs/.",
    )
    registry.add_arguments(packs)

    helping = commands.add_parser("help", help="how to use the tool, by section")
    helping.set_defaults(run=run_help)

    return parser


def is_interactive() -> bool:
    """D-051: a person at a terminal, not a script or a pipe."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # D-051: no arguments on a terminal opens the menu; anywhere else argparse
    # prints the usage and exits 2, as it always has.
    if not argv and is_interactive():
        from .interactive import run

        return run()
    # The top-level --help is the sectioned help; `<command> --help` stays argparse's.
    if argv[:1] in (["-h"], ["--help"]):
        return run_help()
    # `normalize` is the default: a bare caption file still works.
    if argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "normalize")
    args = build_parser().parse_args(argv)
    if getattr(args, "gold_draft_used", False):
        args.corrections = True
    try:
        return args.run(args)
    except FileNotFoundError as error:  # a message, never a traceback
        print(f"no file at {error.filename or error}", file=sys.stderr)
        return 1
