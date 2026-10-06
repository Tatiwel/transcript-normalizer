"""Measurements that are reported, not asserted.

    uv run python scripts/measure.py [caption ...]

Captions given on the command line are added to the pack-fit table (D-054):
a run from another field, such as the silence run of D-035.

The regression test holds each fixture to its bounds. This prints the same
numbers side by side, and anything worth seeing that should not block a commit.
"""

from __future__ import annotations

import sys
from pathlib import Path

from transcript_normalizer.core.fit import MIN_FIT_TERMS, fitting_terms
from transcript_normalizer.core.text import read_caption

from transcript_normalizer.core.matcher import MARK_THRESHOLD, find_annotations, resolve_overlaps
from transcript_normalizer.core.pack import Learned, load_pack
from transcript_normalizer.core.standoff import BAND_LOW, in_band
from transcript_normalizer.evaluate import Fixture, evaluate_fixture, fixtures
from transcript_normalizer.runs import BUNDLED_PACKS

ROOT = Path(__file__).resolve().parents[1]
PACK = BUNDLED_PACKS / "financas-ptbr.yaml"
COLUMNS = (
    "in scope",
    "hits",
    "misses",
    "false positives",
    "aliases recognized",
    "aliases wrongly substituted",
)


def table(rows: list[tuple[str, dict[str, int]]]) -> str:
    width = max(len(name) for name, _ in rows)
    head = f"{'fixture':{width}s}  " + "  ".join(COLUMNS)
    out = [head, "-" * len(head)]
    for name, counts in rows:
        cells = "  ".join(f"{counts[c]:>{len(c)}d}" for c in COLUMNS)
        out.append(f"{name:{width}s}  {cells}")
    return "\n".join(out)


def pack_effect(found: list[Fixture]) -> str:
    """Each fixture against the current packs/ pack, beside its frozen numbers.

    Not a bound: the regression test keeps the frozen pack so the fixture's
    numbers stay comparable over time. This shows what the pack itself buys.
    """
    pack = load_pack(PACK, learned=Learned())
    rows = []
    for fixture in found:
        rows += [
            (f"{fixture.name} frozen {fixture.load_pack().version}", evaluate_fixture(fixture).counts()),
            (f"{fixture.name} bundled {pack.version}", evaluate_fixture(fixture, pack).counts()),
        ]
    return table(rows)


def low_band(found: list[Fixture], thresholds=(60, MARK_THRESHOLD)) -> str:
    """How many low-band marks each fixture gets at each lower threshold.

    Counted as the CLI reports them, after overlap resolution: the number a run
    prints as "low-confidence marks, not applied".
    """
    head = f"{'fixture':12s}  " + "  ".join(f"low at {t}" for t in thresholds)
    out = [head, "-" * len(head)]
    for f in found:
        transcript, pack = f.load_transcript(), f.load_pack()
        counts = [
            len(in_band(resolve_overlaps(find_annotations(transcript, pack, threshold=t)), BAND_LOW))
            for t in thresholds
        ]
        out.append(f"{f.name:12s}  " + "  ".join(f"{c:>{len(f'low at {t}')}d}" for c, t in zip(counts, thresholds)))
    return "\n".join(out)


def pack_fit(found: list[Fixture], extra: list[Path]) -> str:
    """D-054: distinct high-band terms per caption, frozen and bundled pack."""
    bundled = load_pack(PACK, learned=Learned())
    head = f"{'caption':16s}  {'frozen':>6s}  {'bundled ' + bundled.version:>14s}  fits (>= {MIN_FIT_TERMS})"
    out = [head, "-" * len(head)]
    cases = [(f.name, f.load_transcript(), f.load_pack()) for f in found]
    cases += [(path.parent.name, read_caption(path), None) for path in extra]
    for name, transcript, frozen in cases:
        counts = [
            len(fitting_terms(resolve_overlaps(find_annotations(transcript, pack)))) if pack else None
            for pack in (frozen, bundled)
        ]
        cells = f"{counts[0] if counts[0] is not None else '-':>6}  {counts[1]:>14d}"
        out.append(f"{name:16s}  {cells}  {'yes' if counts[1] >= MIN_FIT_TERMS else 'no'}")
    return "\n".join(out)


def main() -> None:
    found = fixtures(ROOT / "fixtures")
    print("Per fixture, frozen fixture pack, no learned layer\n")
    print(table([(f.name, evaluate_fixture(f).counts()) for f in found]))
    print("\n\nNon-blocking: every fixture against the bundled financas-ptbr.yaml, no learned layer\n")
    print(pack_effect(found))
    print("\n\nLow band, lower threshold 60 vs 70 (D-029 chose 70; frozen fixture packs)\n")
    print(low_band(found))
    print("\n\nPack fit: distinct terms with a high-band annotation, units aside (D-054)\n")
    print(pack_fit(found, [Path(arg) for arg in sys.argv[1:]]))


if __name__ == "__main__":
    main()
