"""The regression test: every fixture, scored against its own gold file.

`experiments/exp2_units_and_threshold.py` is the reference behaviour. The only
deliberate difference is D-007: matching runs over the joined text, so an
annotation can straddle a caption break and is credited to every line it touches.
Every fixture is scored by D-026's one rule; see `transcript_normalizer.evaluate`.

Any change in the numbers asserted here must be a conscious commit that also
updates this table and `docs/DECISIONS.md`.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from transcript_normalizer.core.matcher import APPLY_THRESHOLD, MARK_THRESHOLD, find_annotations
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
    # D-030 (whole-word guard): +3 hits (`autocapex`, `Sabespe`, `segundo
    # trio`) and +10 false positives: the plural `dividendos` fuzzily corrected
    # to dividendo (8x) and the variant `tira` -> TIR (2x), both of which the
    # old substring guard happened to block. Was 147 / 16 after commit 7.
    "R2Qgz8tFWVI": Bounds(in_scope=167, min_hits=150, max_false_positives=26),
    # D-030: no hit, +13 false positives (`dividendos` 9x, `valuations` 3x,
    # `tira` 1x). Was 107 / 57. The touched `manter` row is 15:54 `divide a`.
    "wxgFO_fyfXg": Bounds(
        in_scope=225, min_hits=107, max_false_positives=70, max_manter_touched=1
    ),
}

FIXTURES = fixtures(FIXTURES_ROOT)


@pytest.fixture(scope="module", params=FIXTURES, ids=lambda f: f.name)
def scored(request):
    fixture = request.param
    transcript = fixture.load_transcript()
    annotations = find_annotations(transcript, fixture.load_pack())
    result = evaluate(transcript, annotations, fixture.load_gold())
    return fixture, annotations, result


def test_every_fixture_has_bounds():
    assert {f.name for f in FIXTURES} == set(BOUNDS), (
        "a fixture directory without a BOUNDS entry would go unchecked"
    )


def test_regression_against_gold(scored):
    fixture, _, result = scored
    bounds = BOUNDS[fixture.name]
    print(f"{fixture.name}\n{render(result)}")

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
    assert all(a.rule == "term:fuzzy" and MARK_THRESHOLD <= a.score < APPLY_THRESHOLD for a in low)
