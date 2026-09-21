"""`transcript-normalizer <legenda.txt> --pack <pack.yaml> [--confirm]`."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from .core.matcher import find_annotations, resolve_overlaps
from .core.pack import Learned, Pack, learned_path, load_pack, save_learned
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

#: How many example lines the confirmation loop shows per term.
EXAMPLES_PER_TERM = 3

#: The six columns of a gold file, and the status a draft row carries.
GOLD_COLUMNS = ("timestamp", "wrong", "correct", "term", "class", "status")
DRAFT_STATUS = "draft"

#: What the gold file calls the class of a unit-rule row.
UNIT_CLASS = "unidade"


def annotations_path(caption: Path) -> Path:
    return caption.with_suffix(".annotations.json")


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
    sections = [
        ("terms", group_by_term([a for a in high if a.rule != RULE_UNIT])),
        ("unit rules", group_by_term([a for a in high if a.rule == RULE_UNIT])),
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


def write_gold_draft(
    transcript: Transcript, annotations: list[Annotation], pack: Pack, path: Path
) -> Path:
    """The applied annotations as a gold.csv draft, for hand-checking a new fixture."""
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
                    a.replacement,
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


def confirm_loop(
    transcript: Transcript, annotations: list[Annotation], learned: Learned
) -> Learned:
    """D-011's confirmation loop, grouped by term. Writes only to the learned layer."""
    medium = in_band(annotations, BAND_MEDIUM)
    if not medium:
        print("nothing to confirm.")
        return learned

    by_term: dict[str, list[Annotation]] = defaultdict(list)
    for a in medium:
        by_term[a.term].append(a)

    for term, group in sorted(by_term.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        forms = Counter(form(a) for a in group)
        total = sum(forms.values())
        plural = "occurrence" if total == 1 else "occurrences"
        print(f"\n{term}  ({total} {plural})")
        print(f"  variants: {', '.join(f for f, _ in forms.most_common())}")
        for line in examples(transcript, group, EXAMPLES_PER_TERM):
            print(line)
        answer = ask(f"  confirm as variants of {term}? [y]es / [n]o / [s]kip: ")
        if answer.startswith("y"):
            for observed in forms:
                learned = learned.confirm(term, observed)
            print(f"  confirmed {len(forms)} variant(s) of {term}.")
        elif answer.startswith("n"):
            for observed in forms:
                learned = learned.reject(observed, term)
            print(f"  rejected {len(forms)} proposal(s) for {term}.")
        else:
            print("  skipped.")
    return learned


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="transcript-normalizer",
        description="Propose stand-off normalizations for a caption file. "
        "The transcript itself is never modified (D-004).",
    )
    parser.add_argument("caption", type=Path, help="caption file, e.g. legenda.txt")
    parser.add_argument("--pack", type=Path, required=True, help="domain pack, e.g. pack.yaml")
    parser.add_argument(
        "--gold-draft",
        type=Path,
        metavar="PATH.CSV",
        help="write the applied annotations as a gold.csv draft, status `draft`",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="review the medium band and record the answers in <pack>.learned.yaml (D-013)",
    )
    args = parser.parse_args(argv)

    pack = load_pack(args.pack)
    transcript = read_caption(args.caption)
    annotations = resolve_overlaps(find_annotations(transcript, pack))

    out_path = annotations_path(args.caption)
    write_json(annotations, out_path)

    print(f"{args.caption}: {len(transcript.lines)} caption lines, pack {pack.version}")
    print(report(annotations))
    print(f"\n{len(annotations)} annotations written to {out_path}")

    if args.gold_draft:
        draft = write_gold_draft(transcript, annotations, pack, args.gold_draft)
        print(f"{len(applied(annotations))} draft gold rows written to {draft}")

    if args.confirm:
        learned = confirm_loop(transcript, annotations, pack.learned)
        if not learned.is_empty():
            # D-013: the learned layer, never pack.yaml.
            path = save_learned(learned, learned_path(args.pack))
            print(f"\nlearned layer written to {path}")
    return 0
