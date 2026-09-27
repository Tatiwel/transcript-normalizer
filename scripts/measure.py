"""Measurements that are reported, not asserted.

    uv run python scripts/measure.py

The regression test holds each fixture to its bounds. This prints the same
numbers side by side, and anything worth seeing that should not block a commit.
"""

from __future__ import annotations

from pathlib import Path

from transcript_normalizer.evaluate import evaluate_fixture, fixtures

ROOT = Path(__file__).resolve().parents[1]
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


def main() -> None:
    found = fixtures(ROOT / "fixtures")
    print("Per fixture, frozen fixture pack, no learned layer\n")
    print(table([(f"{f.name} ({f.convention})", evaluate_fixture(f).counts()) for f in found]))


if __name__ == "__main__":
    main()
