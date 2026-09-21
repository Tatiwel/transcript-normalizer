"""The regression test: the evaluation of exp2, replayed against the gold file.

`experiments/exp2_units_and_threshold.py` is the reference behaviour. The only
deliberate difference is D-007: matching runs over the joined text, so an
annotation can straddle a caption break and is credited to every line it touches.

Any change in the numbers asserted here must be a conscious commit that also
updates this test and `docs/DECISIONS.md`.
"""

import csv
from collections import Counter, defaultdict

from transcript_normalizer.core.pack import fold
from transcript_normalizer.core.standoff import BAND_LOW, in_band

from .conftest import GOLD

MIN_HITS = 156
MAX_FALSE_POSITIVES = 9


def key(s: str) -> str:
    """The gold file compares text loosely: folded, with runs of space collapsed."""
    return " ".join(fold(s).split())


def rows():
    with GOLD.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def evaluate(transcript, annotations):
    # D-011: only the applied bands count. Low marks are passive.
    annotations = [a for a in annotations if a.applied]

    by_timestamp = defaultdict(list)  # every line an annotation touches
    home = {}  # annotation -> the line it starts on
    for a in annotations:
        for line in transcript.spans(a.start, a.end):
            by_timestamp[line.timestamp].append(a)
        home[id(a)] = transcript.locate(a.start)[1]

    gold = rows()
    in_scope = [g for g in gold if g["term"] and g["status"] != "manter"]
    keep = [g for g in gold if g["status"] == "manter"]

    hits, misses = [], []
    per_term = defaultdict(lambda: [0, 0])
    used = []
    for g in in_scope:
        found = None
        for a in by_timestamp.get(g["timestamp"], []):
            if a.term != g["term"]:
                continue
            if key(g["wrong"]) in key(a.original) or key(a.original) in key(
                g["wrong"]
            ):
                found = a
                break
        per_term[g["term"]][1] += 1
        if found is None:
            misses.append(g)
        else:
            hits.append((g, found))
            per_term[g["term"]][0] += 1
            used.append(found)

    # False positives: annotations that credit no in-scope gold row, minus the
    # ones that merely nest inside (or around) an annotation that did. exp2 compared
    # proposals within a caption line; annotations can straddle a break, so the
    # comparison is against every used annotation that shares a line with this one.
    used_ids = {id(a) for a in used}
    used_by_timestamp = defaultdict(list)
    for a in used:
        for line in transcript.spans(a.start, a.end):
            used_by_timestamp[line.timestamp].append(a)

    false_positives = []
    for a in annotations:
        if id(a) in used_ids:
            continue
        neighbours = {
            id(u): u
            for line in transcript.spans(a.start, a.end)
            for u in used_by_timestamp.get(line.timestamp, ())
        }
        if any(
            key(a.original) in key(u.original) or key(u.original) in key(a.original)
            for u in neighbours.values()
        ):
            continue
        false_positives.append((home[id(a)], a))

    touched_keep = {
        g["timestamp"]: [
            (a.original, a.term) for a in by_timestamp.get(g["timestamp"], [])
        ]
        for g in keep
    }
    return {
        "in_scope": in_scope,
        "hits": hits,
        "misses": misses,
        "false_positives": false_positives,
        "per_term": per_term,
        "touched_keep": touched_keep,
    }


def render(result) -> str:
    out = [
        f"in scope: {len(result['in_scope'])}   "
        f"hits: {len(result['hits'])}   "
        f"misses: {len(result['misses'])}   "
        f"false positives: {len(result['false_positives'])}",
        "",
        "per term (hits/total):",
    ]
    for term, (hit, total) in sorted(
        result["per_term"].items(), key=lambda kv: -kv[1][1]
    ):
        out.append(f"  {term:20s} {hit:3d}/{total}")
    out += ["", "misses:"]
    for g in result["misses"]:
        out.append(
            f"  {g['timestamp']:6s} {g['wrong']!r} -> {g['term']}"
        )
    out += ["", "false positives:"]
    counted = Counter((a.original, a.term) for _, a in result["false_positives"])
    for (original, term), n in counted.most_common():
        out.append(f"  {n:3d}x {original!r} -> {term}")
    out += ["", "lines that must stay untouched (applied annotations only):"]
    for timestamp, touched in result["touched_keep"].items():
        out.append(f"  {timestamp} {touched}")
    return "\n".join(out)


def test_regression_against_gold(transcript, annotations):
    result = evaluate(transcript, annotations)
    print(render(result))  # pytest shows this only when the test fails

    assert len(result["in_scope"]) == 168
    assert len(result["hits"]) >= MIN_HITS
    assert len(result["false_positives"]) <= MAX_FALSE_POSITIVES


def test_lines_marked_manter_have_no_applied_annotation(transcript, annotations):
    result = evaluate(transcript, annotations)
    print(render(result))
    assert result["touched_keep"] == {"7:30": [], "10:27": []}


def test_the_fixture_produces_low_band_marks(annotations):
    """D-011's low band is reachable on real material, not just in theory."""
    low = in_band(annotations, BAND_LOW)
    assert low
    assert all(not a.applied for a in low)
    assert all(a.rule == "term:fuzzy" and 60 <= a.score < 80 for a in low)
