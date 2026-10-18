"""The review (D-072): one stop per pending form, in the order of the video.

Each stop shows the form in its caption line, the line before and the line
after, the other places it occurs, and a link to that moment of the video. One
question, whose default is "Decide later": Enter never decides anything, and a
form is rejected only by its "No". Nothing is written while the stops go on;
at the end a summary says what would be kept, and only a yes writes it.

"Only in this video" (D-073) is kept beside the run, in local-decisions.yaml,
and applied when that run is normalized; it never reaches the learned layer, a
pack or a contribution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

from .core.pack import Learned
from .core.standoff import BAND_HIGH, KIND_CORRECTION, QUESTION_BANDS, Annotation, in_band
from .core.text import Transcript

#: The answers, as cli's outcomes record them (D-019, D-020; `o` is D-073;
#: `c`, D-086, is "only in this video" saved for every video with a context).
YES, LOCAL, ALIAS, NO, LATER, CONTEXT = "y", "o", "l", "n", "s", "c"
#: D-086: how many of the run's terms the context question offers.
CONTEXT_CHOICES = 5

#: D-073: beside the run's annotations.json.
LOCAL_FILE = "local-decisions.yaml"
#: The `rule` of an annotation a local decision applied.
RULE_LOCAL = "local"


def form(annotation: Annotation) -> str:
    """The observed text, with the caption's line break collapsed to one space."""
    return " ".join(annotation.original.split())


@dataclass(frozen=True)
class Stop:
    """One pending form of one term, and every place it occurs, in order."""

    term: str
    form: str
    found: tuple[Annotation, ...]


def stops(annotations: list[Annotation]) -> list[Stop]:
    """D-072: one stop per (term, form) asked about, by its first occurrence."""
    by_pair: dict[tuple[str, str], list[Annotation]] = {}
    for a in sorted(in_band(annotations, QUESTION_BANDS), key=lambda a: (a.start, a.end)):
        by_pair.setdefault((a.term, form(a)), []).append(a)
    return [Stop(term, text, tuple(found)) for (term, text), found in by_pair.items()]


# ------------------------------------------------------------------ context


def seconds(stamp: str) -> int:
    """`m:ss` or `h:mm:ss` as seconds; 0 for anything else."""
    total = 0
    for part in stamp.split(":"):
        if not part.isdigit():
            return 0
        total = total * 60 + int(part)
    return total


_YOUTUBE = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def video_link(url: str, stamp: str) -> str:
    """D-072: where to watch this moment. YouTube: a link that starts there;
    another platform: its URL and the time, which it may not take in the link;
    no URL (a local file): ""."""
    if not url:
        return ""
    found = _YOUTUBE.search(url)
    if found:
        return f"https://youtu.be/{found.group(1)}?t={seconds(stamp)}"
    return f"{url} at {stamp}"


@dataclass(frozen=True)
class Context:
    """What a stop shows: (timestamp, text) before and after, the line with the
    form in «guillemets», and where else it occurs."""

    before: tuple[str, str] | None
    line: tuple[str, str]
    after: tuple[str, str] | None
    elsewhere: tuple[str, ...]
    link: str


def context(transcript: Transcript, stop: Stop) -> Context:
    first = stop.found[0]
    lines = transcript.spans(first.start, first.end) or (transcript.line_at(first.start),)
    head, tail = lines[0], lines[-1]
    text = transcript.text
    shown = f"{text[head.start:first.start]}«{text[first.start:first.end]}»{text[first.end:tail.end]}"
    at = lambda i: (transcript.lines[i].timestamp, transcript.lines[i].text)  # noqa: E731
    stamps = list(dict.fromkeys(transcript.line_at(a.start).timestamp for a in stop.found))
    return Context(
        before=at(head.index - 1) if head.index > 0 else None,
        line=(head.timestamp, " ".join(shown.split())),
        after=at(tail.index + 1) if tail.index + 1 < len(transcript.lines) else None,
        elsewhere=tuple(stamps[1:]),
        link=video_link(transcript.header_field("URL"), head.timestamp),
    )


# ------------------------------------------------------------------ the stops


def choices(term: str):
    from .prompts import Option

    return [
        Option(f"Yes: this is {term} (fix it from now on)", value=YES),
        Option("Yes, but only in this video", value=LOCAL),
        Option(f"This is {term}, said that way (recognise it, keep the text)", value=ALIAS),
        Option(f"No: this is not {term}", value=NO),
        Option("Decide later", "nothing is saved for it", value=LATER),
    ]


def show_stop(number: int, total: int, stop: Stop, seen: Context) -> None:
    from .prompts import mark, say, stage

    stage(f"{number} of {total}", f"{stop.form} → {stop.term}")
    occurrences = len(stop.found)
    say(mark(f"  {occurrences} occurrence{'s' if occurrences != 1 else ''} in this video", "hint"))
    if seen.before:
        say(mark(f"    {seen.before[0]}  {seen.before[1]}", "hint"))
    say(mark(f"  » {seen.line[0]}  ", "need"), seen.line[1])
    if seen.after:
        say(mark(f"    {seen.after[0]}  {seen.after[1]}", "hint"))
    if seen.elsewhere:
        say(mark("  also at ", "label"), ", ".join(seen.elsewhere))
    if seen.link:
        say(mark("  watch: ", "label"), mark(seen.link, "path"))


@dataclass
class Answers:
    """What a review was told, in the order it was told it."""

    given: dict[tuple[str, str], str] = field(default_factory=dict)
    ended: bool = False  # Back or Ctrl+C before the last stop
    contexts: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)  # D-086

    def of(self, value: str) -> list[tuple[str, str]]:
        return [pair for pair, answer in self.given.items() if answer == value]


def ask_context(stop: Stop, offered) -> tuple[str, ...]:
    """D-086: after "only in this video", once: the same answer for every video,
    but only where one of the run's terms appears. Enter keeps it local."""
    from . import prompts
    from .prompts import Option

    terms = [t for t in offered if t != stop.term][:CONTEXT_CHOICES]
    if not terms:
        return ()
    picked = prompts.multi_select(
        "Save it for every video, but only when one of these terms appears?",
        [Option(t, value=t) for t in terms],
        hint="terms found in this video; Enter keeps it for this video only",
    )
    return tuple(picked or ())


def ask_stops(transcript: Transcript, all_stops: list[Stop], offered=()) -> Answers:
    """D-072: the stops, one question each. Back (or Ctrl+C) ends them; what
    is left is for later. A form taken as one term is not asked again for
    another (its later occurrences took the answer already). `offered`: the
    run's terms, most frequent first, for D-086's context question."""
    from . import prompts

    answers = Answers()
    taken: set[str] = set()
    remaining = [s for s in all_stops]
    try:
        for number, stop in enumerate(remaining, 1):
            if stop.form in taken:
                continue
            show_stop(number, len(remaining), stop, context(transcript, stop))
            answer = prompts.select(
                f"Is «{stop.form}» {stop.term}?",
                choices(stop.term),
                hint="Enter decides later; b ends the review here",
                default=LATER,
            )
            if answer is None:
                answers.ended = True
                break
            if answer == LOCAL:
                terms = ask_context(stop, offered)
                if terms:
                    answer = CONTEXT
                    answers.contexts[(stop.term, stop.form)] = terms
            answers.given[(stop.term, stop.form)] = answer
            if answer in (YES, LOCAL, ALIAS, CONTEXT):
                taken.add(stop.form)
    except KeyboardInterrupt:
        answers.ended = True
    return answers


def summary_lines(answers: Answers, total: int) -> list[str]:
    """D-072: what saving would keep, before anything is written."""
    later = total - sum(1 for a in answers.given.values() if a != LATER)
    pairs = lambda value, sep: ", ".join(f"{f} {sep} {t}" for t, f in answers.of(value))  # noqa: E731
    lines = []
    remembered = (
        [f"{f} → {t}" for t, f in answers.of(YES)]
        + [f"{f} → {t} (only with {', '.join(answers.contexts[(t, f)])})" for t, f in answers.of(CONTEXT)]
        + [f"{f} (as said) = {t}" for t, f in answers.of(ALIAS)]
    )
    if remembered:
        lines.append(f"will remember: {', '.join(remembered)}")
    if answers.of(NO):
        lines.append(f"rejected: {pairs(NO, 'is not')}")
    if answers.of(LOCAL):
        lines.append(f"only in this video: {pairs(LOCAL, '→')}")
    lines.append(f"left for later: {later}")
    return lines


def apply(answers: Answers, learned: Learned) -> tuple[Learned, list[tuple[str, str]]]:
    """The learned layer with the answers that belong in it, and the local ones."""
    for (term, text), answer in answers.given.items():
        if answer == YES:
            learned = learned.confirm(term, text)
        elif answer == CONTEXT:
            learned = learned.confirm(term, text, context=answers.contexts[(term, text)])
        elif answer == ALIAS:
            learned = learned.alias(term, text)
        elif answer == NO:
            learned = learned.reject(text, term)
    return learned, answers.of(LOCAL)


# ------------------------------------------------------------------ local decisions (D-073)


def local_path(run: Path) -> Path:
    return Path(run) / LOCAL_FILE


def read_local(run: Path) -> list[tuple[str, str]]:
    """(term, form) pairs decided for this run only."""
    import yaml

    path = local_path(run)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    return [
        (str(d["term"]), " ".join(str(d["form"]).split()))
        for d in data.get("decisions") or []
        if isinstance(d, dict) and d.get("term") and d.get("form")
    ]


LOCAL_HEADER = (
    "# Answers \"only in this video\" from the review of this run. Applied when this\n"
    "# run is normalized; never in the learned layer, a pack or a contribution.\n"
)


def write_local(run: Path, pairs: list[tuple[str, str]]) -> Path | None:
    """Add `pairs` to the run's local decisions; None when there is nothing to add."""
    import yaml

    known = read_local(run)
    merged = known + [p for p in pairs if p not in known]
    if merged == known:
        return None
    path = local_path(run)
    body = yaml.safe_dump(
        {"decisions": [{"form": f, "term": t} for t, f in merged]}, allow_unicode=True, sort_keys=False
    )
    path.write_text(LOCAL_HEADER + body, encoding="utf-8")
    return path


def apply_local(annotations: list[Annotation], pairs: list[tuple[str, str]]) -> list[Annotation]:
    """D-073: a form decided for this run is applied here, as a high-band
    correction with rule `local`, wherever it was found for that term."""
    if not pairs:
        return annotations
    wanted = set(pairs)
    return [
        replace(a, band=BAND_HIGH, rule=RULE_LOCAL, kind=KIND_CORRECTION)
        if a.band != BAND_HIGH and (a.term, form(a)) in wanted
        else a
        for a in annotations
    ]
