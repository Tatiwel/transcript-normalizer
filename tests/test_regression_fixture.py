"""The regression test: every fixture, scored against its own gold file.

`experiments/exp2_units_and_threshold.py` is the reference behaviour. The only
deliberate difference is D-007: matching runs over the joined text, so an
annotation can straddle a caption break and is credited to every line it touches.
How a gold row is scored depends on its status; see `transcript_normalizer.evaluate`.

Any change in the numbers asserted here must be a conscious commit that also
updates this table and `docs/DECISIONS.md`.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from transcript_normalizer.core.matcher import find_annotations
from transcript_normalizer.core.standoff import BAND_LOW, in_band
from transcript_normalizer.evaluate import evaluate, fixtures, render

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


@dataclass(frozen=True)
class Bounds:
    in_scope: int
    min_hits: int
    max_false_positives: int
    #: `manter` rows that may carry an applied annotation. Should be 0; a
    #: fixture that measures otherwise records the regression it has.
    max_manter_touched: int = 0


BOUNDS = {
    # D-021: its 8 `CPFE -> CPFL` rows are aliases now, and the frozen pack
    # still lists CPFE as a variant, so all 8 are substituted (was 156 / 9, D-014).
    "R2Qgz8tFWVI": Bounds(in_scope=168, min_hits=148, max_false_positives=17),
    # Measured when the fixture was added, with the frozen 0.1.0 pack and no
    # learned layer. The touched `manter` row is 15:54 `divide a` -> dividendo.
    "wxgFO_fyfXg": Bounds(
        in_scope=226, min_hits=103, max_false_positives=57, max_manter_touched=1
    ),
}

FIXTURES = fixtures(FIXTURES_ROOT)


@pytest.fixture(scope="module", params=FIXTURES, ids=lambda f: f.name)
def scored(request):
    fixture = request.param
    transcript = fixture.load_transcript()
    annotations = find_annotations(transcript, fixture.load_pack())
    result = evaluate(transcript, annotations, fixture.load_gold(), fixture.convention)
    return fixture, annotations, result


def test_every_fixture_has_bounds():
    assert {f.name for f in FIXTURES} == set(BOUNDS), (
        "a fixture directory without a BOUNDS entry would go unchecked"
    )


def test_regression_against_gold(scored):
    fixture, _, result = scored
    bounds = BOUNDS[fixture.name]
    print(f"{fixture.name} (gold {fixture.convention})\n{render(result)}")

    assert len(result.in_scope) == bounds.in_scope
    assert len(result.hits) >= bounds.min_hits
    assert len(result.false_positives) <= bounds.max_false_positives


def test_lines_marked_manter_have_no_applied_annotation(scored):
    fixture, _, result = scored
    print(f"{fixture.name}\n{render(result)}")
    touched = {where: t for where, t in result.touched_keep.items() if t}
    assert len(touched) <= BOUNDS[fixture.name].max_manter_touched, touched


def test_the_fixture_produces_low_band_marks(scored):
    """D-011's low band is reachable on real material, not just in theory."""
    _, annotations, _ = scored
    low = in_band(annotations, BAND_LOW)
    assert low
    assert all(not a.applied for a in low)
    assert all(a.rule == "term:fuzzy" and 60 <= a.score < 80 for a in low)
