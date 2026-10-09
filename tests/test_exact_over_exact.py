"""D-040: an exact term or alias span suppresses a shorter correction overlapping it."""

from pathlib import Path

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines

PACK = Path(__file__).resolve().parents[1] / "fixtures" / "4wCtn8BWR4o" / "pack.yaml"
LINE = "Atualmente um Dividend Yield de 11,5%, quase 12% em Dividend Yield e anunciou um"


def run(line):
    pack = load_pack(PACK, learned=Learned())
    transcript = parse_caption(f"0:19 {line}")
    return transcript, resolve_overlaps(find_annotations(transcript, pack))


def test_dividend_inside_dividend_yield_is_not_corrected():
    """4wCtn8BWR4o 0:19: the variant `dividend` of dividendo sits inside the term."""
    transcript, found = run(LINE)
    assert [a for a in found if a.applied and a.is_correction] == []
    assert dict(render_lines(transcript, found))["0:19"] == LINE


def test_dividend_on_its_own_is_still_corrected():
    _, found = run("pagou um dividend alto")
    assert [(a.original, a.term) for a in found if a.applied] == [("dividend", "dividendo")]


def test_the_guard_holds_when_the_longer_name_is_itself_rejected():
    """Why D-040 is not left to overlap resolution: a rejection by containment
    (D-027) of `dividend -> dividend yield` removes the name's own annotation, and
    then nothing longer is there to win the span. The guard still knows the name
    is spelled out and keeps `Dividend` from becoming dividendo, before resolution
    and after."""
    pack = load_pack(PACK, learned=Learned().reject("dividend", "dividend yield"))
    transcript = parse_caption(f"0:19 {LINE}")
    raw = find_annotations(transcript, pack)
    assert [a for a in raw if a.term == "dividendo" and a.original == "Dividend"] == []
    found = resolve_overlaps(raw)
    assert [a for a in found if a.applied and a.is_correction] == []
    assert dict(render_lines(transcript, found))["0:19"] == LINE


def test_the_shorter_correction_is_never_proposed_before_resolution():
    """D-040 acts in the matcher, not only through overlap resolution."""
    pack = load_pack(PACK, learned=Learned())
    raw = find_annotations(parse_caption(f"0:19 {LINE}"), pack)
    assert [a for a in raw if a.term == "dividendo" and a.original == "Dividend"] == []
