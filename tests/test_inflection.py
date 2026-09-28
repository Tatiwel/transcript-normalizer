"""D-031: plurals are the term spelled out; exact forms beat fuzzy guesses."""

from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned, plural_forms
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.core.standoff import KIND_ALIAS

PACK_V2 = Path(__file__).resolve().parents[1] / "packs" / "financas-ptbr.yaml"


@pytest.fixture(scope="module")
def v2():
    return load_pack(PACK_V2, learned=Learned())


def applied(pack, line):
    transcript = parse_caption(f"0:01 {line}")
    found = resolve_overlaps(find_annotations(transcript, pack))
    return transcript, [a for a in found if a.applied]


@pytest.mark.parametrize(
    "word, plurals",
    [
        ("dividendo", ("dividendos", "dividendoes")),
        ("bilhao", ("bilhaos", "bilhaoes", "bilhoes")),  # -ão -> -ões, folded
        ("capital", ("capitals", "capitales", "capitais")),  # -al -> -ais
        ("papel", ("papels", "papeles", "papeis")),  # -el -> -eis
        ("preco teto", ()),  # D-031 speaks of a word
    ],
)
def test_plural_forms(word, plurals):
    assert plural_forms(word) == plurals


@pytest.mark.parametrize(
    "line, word, term",
    [
        ("pagou dividendos em março", "dividendos", "dividendo"),
        ("os valuations estão altos", "valuations", "valuation"),
    ],
)
def test_a_plural_is_an_alias_never_a_correction(v2, line, word, term):
    """Measured after D-030: both were applied as corrections, rewriting the speaker."""
    transcript, found = applied(v2, line)
    hit = [a for a in found if a.original == word]
    assert [(a.term, a.kind, a.rule) for a in hit] == [(term, KIND_ALIAS, "term:alias")]
    assert dict(render_lines(transcript, found))["0:01"] == line


def test_a_span_with_an_exact_form_is_not_a_fuzzy_guess_at_another_term(v2):
    """Measured: `dividendos e -> dividend yield` 5x, over the exact `dividendos`."""
    _, found = applied(v2, "distribuição de dividendos e juros")
    assert not [a for a in found if a.term == "dividend yield"]
    assert [(a.original, a.term) for a in found if a.term == "dividendo"] == [("dividendos", "dividendo")]


def test_the_real_misrecognition_still_reaches_dividend_yield(v2):
    """(b) blocks guesses over exact forms, not the variant the pack lists."""
    _, found = applied(v2, "8% de dividend y aqui")
    assert ("dividend y", "dividend yield") in {(a.original, a.term) for a in found}


def test_an_explicit_entry_wins_over_a_generated_plural(tmp_path):
    """A plural that some term already lists belongs to that term."""
    path = tmp_path / "p.yaml"
    path.write_text(
        "terms:\n  - term: Leo\n    class: pessoa\n"
        "  - term: Leos Corp\n    class: companhia\n    variants: [leos]\n",
        encoding="utf-8",
    )
    _, found = applied(load_pack(path, learned=Learned()), "os leos")
    assert [(a.original, a.term, a.kind) for a in found] == [("leos", "Leos Corp", "correction")]
