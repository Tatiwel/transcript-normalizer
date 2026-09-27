"""Measurements that are reported, not asserted.

    uv run python scripts/measure.py

The regression test holds each fixture to its bounds. This prints the same
numbers side by side, and anything worth seeing that should not block a commit.
"""

from __future__ import annotations

from pathlib import Path

from transcript_normalizer.core.pack import Learned, load_pack
from transcript_normalizer.evaluate import Fixture, evaluate_fixture, fixtures

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "financas-ptbr.yaml"
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


def pack_effect() -> str:
    """wxgFO_fyfXg against the current packs/ pack, beside its frozen numbers.

    Not a bound: the regression test keeps the frozen pack so the fixture's
    numbers stay comparable over time. This shows what the pack itself buys.
    """
    fixture = Fixture(ROOT / "fixtures" / "wxgFO_fyfXg")
    pack = load_pack(PACK, learned=Learned())
    rows = [
        (f"frozen pack {fixture.load_pack().version}", evaluate_fixture(fixture).counts()),
        (f"packs/ {pack.version}", evaluate_fixture(fixture, pack).counts()),
    ]
    return table(rows)


def main() -> None:
    found = fixtures(ROOT / "fixtures")
    print("Per fixture, frozen fixture pack, no learned layer\n")
    print(table([(f"{f.name} ({f.convention})", evaluate_fixture(f).counts()) for f in found]))
    print("\n\nNon-blocking: wxgFO_fyfXg against packs/financas-ptbr.yaml, no learned layer\n")
    print(pack_effect())


if __name__ == "__main__":
    main()
