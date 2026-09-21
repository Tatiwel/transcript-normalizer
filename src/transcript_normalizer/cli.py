"""`transcript-normalizer <legenda.txt> --pack <pack.yaml>`."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from .matcher import find_annotations, resolve_overlaps
from .pack import load_pack
from .standoff import RULE_UNIT, Annotation, write_json
from .text import read_caption


def annotations_path(caption: Path) -> Path:
    return caption.with_suffix(".annotations.json")


def report(annotations: list[Annotation]) -> str:
    """One line per term: the observed forms, how often, and what they normalize to."""
    forms: dict[str, Counter] = defaultdict(Counter)
    units: dict[str, Counter] = defaultdict(Counter)
    for a in annotations:
        target = units if a.rule == RULE_UNIT else forms
        target[a.term][" ".join(a.original.split())] += 1

    out: list[str] = []
    for title, groups in (("terms", forms), ("unit rules", units)):
        if not groups:
            continue
        out.append(f"{title}:")
        for term, counter in sorted(
            groups.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])
        ):
            total = sum(counter.values())
            listed = ", ".join(form for form, _ in counter.most_common())
            plural = "occurrence" if total == 1 else "occurrences"
            out.append(f"  {listed} ({total} {plural}) -> {term}")
        out.append("")
    if not out:
        out.append("no annotations.")
    return "\n".join(out).rstrip("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="transcript-normalizer",
        description="Propose stand-off normalizations for a caption file. "
        "The transcript itself is never modified (D-004).",
    )
    parser.add_argument("caption", type=Path, help="caption file, e.g. legenda.txt")
    parser.add_argument(
        "--pack", type=Path, required=True, help="domain pack, e.g. pack.yaml"
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
    return 0
