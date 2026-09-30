"""D-031: plurals are the term spelled out; exact forms beat fuzzy guesses."""

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.languages.pt_br import inflections
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.core.standoff import KIND_ALIAS
from transcript_normalizer.runs import BUNDLED_PACKS

PACK_V2 = BUNDLED_PACKS / "financas-ptbr.yaml"


@pytest.fixture(scope="module")
def v2():
    return load_pack(PACK_V2, learned=Learned())


def applied(pack, line):
    transcript = parse_caption(f"0:01 {line}")
    found = resolve_overlaps(find_annotations(transcript, pack))
    return transcript, [a for a in found if a.applied]


@pytest.mark.parametrize(
    "plural, singular",
    [
        ("dividendos", "dividendo"),  # -s
        ("bilhoes", "bilhao"),  # -ão -> -ões, on normalized text
        ("capitais", "capital"),  # -al -> -ais
        ("papeis", "papel"),  # -el -> -eis
        ("tetos", "teto"),
    ],
)
def test_pt_br_inflections_give_the_base_form(plural, singular):
    """D-031a, pt-BR: the module maps a plural back to its singular."""
    assert singular in inflections(plural)


@pytest.mark.parametrize("word", ["preco teto", "", "dividendo"])
def test_no_base_form_for_several_words_nothing_or_a_singular(word):
    """D-031 speaks of a word; a singular is not an inflection of anything here."""
    assert inflections(word) == set()


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
        "language: pt-BR\nterms:\n  - term: Leo\n    class: pessoa\n"
        "  - term: Leos Corp\n    class: companhia\n    variants: [leos]\n",
        encoding="utf-8",
    )
    _, found = applied(load_pack(path, learned=Learned()), "os leos")
    assert [(a.original, a.term, a.kind) for a in found] == [("leos", "Leos Corp", "correction")]


def test_a_fuzzy_span_inside_an_exact_one_is_not_a_guess_either(v2):
    """D-034: `market` sits inside `market cap`; D-031(b)'s containment missed it."""
    transcript = parse_caption("0:01 do que o seu market cap atual")
    everything = find_annotations(transcript, v2)
    assert not [a for a in everything if a.term == "market share"]


def test_overlap_counts_in_both_directions_and_partly(v2):
    """D-034: inside, around, or sharing a word with another term's exact form."""
    transcript = parse_caption("0:01 o market cap e o dividend y aqui")
    everything = find_annotations(transcript, v2)
    assert not [a for a in everything if a.term == "market share"]  # `o market`, `market`
    assert not [a for a in everything if a.rule == "term:fuzzy" and a.original == "o dividend"]
