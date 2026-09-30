"""D-041: a term's canonical name spelled out is recognized, never substituted."""

from pathlib import Path

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.cli import report
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.core.standoff import KIND_ALIAS

PACK = Path(__file__).resolve().parents[1] / "fixtures" / "4wCtn8BWR4o" / "pack.yaml"
LINE = "Atualmente um Dividend Yield de 11,5%, quase 12% em Dividend Yield e anunciou um"


def run(line):
    pack = load_pack(PACK, learned=Learned())
    transcript = parse_caption(f"0:19 {line}")
    return transcript, resolve_overlaps(find_annotations(transcript, pack))


def test_dividend_yield_spelled_out_is_recognized_twice():
    """4wCtn8BWR4o 0:19: both mentions, as the speaker said them."""
    transcript, found = run(LINE)
    assert [(a.original, a.term, a.rule, a.kind) for a in found if a.applied] == [
        ("Dividend Yield", "dividend yield", "term:exact", KIND_ALIAS)
    ] * 2
    assert all(a.replacement == a.original for a in found if a.applied)
    assert dict(render_lines(transcript, found))["0:19"] == LINE


def test_the_report_lists_them_as_recognized():
    _, found = run(LINE)
    text = report(found)
    recognized = text.split("recognized (not changed):")[1]
    assert "Dividend Yield (2 occurrences) -> dividend yield" in recognized
