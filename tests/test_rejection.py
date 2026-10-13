"""D-027: a rejected (text, term) suppresses every span for that term containing it."""

from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.core import matcher
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.evaluate import Fixture, evaluate

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Fixture(ROOT / "fixtures" / "wxgFO_fyfXg")
LEARNED = Path(__file__).resolve().parent / "data" / "wxgFO_fyfXg.learned.yaml"


def manter_touched(pack):
    transcript = FIXTURE.load_transcript()
    result = evaluate(
        transcript, find_annotations(transcript, pack), FIXTURE.load_gold(), pack.normalize
    )
    return result.touched_keep["15:54 divide a"]


def test_without_the_rejection_the_manter_row_is_touched(monkeypatch):
    """The measured regression: `divide a -> dividendo` on a must-not-touch row.

    Since D-047 `divide a` (82, reached from a variant) is only a mark, but
    `divide` (85) is still applied there, so the row is still touched. That is
    without D-083's common-word guard, which rejects `divide` on its own.
    """
    monkeypatch.setattr(matcher, "COMMON_WORD_GUARD", False)
    touched = manter_touched(load_pack(FIXTURE.pack, learned=Learned()))
    assert ("divide", "dividendo") in touched
    assert ("divide a", "dividendo") not in touched


def test_the_common_word_guard_keeps_the_manter_row_clean_without_a_rejection():
    """D-083: `divide` is an ordinary word, and not a word of `dividendo`."""
    assert manter_touched(load_pack(FIXTURE.pack, learned=Learned())) == []


def test_rejecting_divide_keeps_the_manter_row_clean(monkeypatch):
    monkeypatch.setattr(matcher, "COMMON_WORD_GUARD", False)
    pack = load_pack(FIXTURE.pack, learned_from=LEARNED)
    assert pack.is_rejected("divide", "dividendo")
    assert manter_touched(pack) == []


@pytest.fixture
def pack():
    return load_pack(FIXTURE.pack, learned_from=LEARNED)


@pytest.mark.parametrize(
    "span, rejected",
    [
        ("divide", True),
        ("divide a", True),  # the reported case
        ("ele divide a", True),
        ("dividida", False),  # a different word, not a longer span of this one
        ("dividendo", False),
        ("subdivide", False),  # whole words only
    ],
)
def test_containment_is_by_whole_words(pack, span, rejected):
    assert pack.is_rejected(span, "dividendo") is rejected


def test_a_rejection_says_nothing_about_another_term(pack):
    assert not pack.is_rejected("divide a", "EBITDA")


def test_other_proposals_on_the_same_line_survive(pack):
    found = find_annotations(parse_caption("0:01 ele divide a SEMIG em duas"), pack)
    applied = {(a.original, a.term) for a in found if a.applied}
    assert ("SEMIG", "CEMIG") in applied
    assert not [a for a in found if a.term == "dividendo" and "divide" in a.original]
