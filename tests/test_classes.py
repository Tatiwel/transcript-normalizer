"""D-021: eight classes, a closed list. A label for consumers, never for matching."""

import csv
from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, parse_caption
from transcript_normalizer.core.pack import CLASSES, Learned
from transcript_normalizer.runs import BUNDLED_PACKS

ROOT = Path(__file__).resolve().parents[1]
PACKS = [
    BUNDLED_PACKS / "financas-ptbr.yaml",
    *sorted((ROOT / "fixtures").glob("*/pack.yaml")),
]
GOLDS = sorted((ROOT / "fixtures").glob("*/gold.csv"))


def test_the_list_is_the_eight_of_d021():
    assert CLASSES == (
        "companhia", "indicador", "conceito", "unidade",
        "pessoa", "organizacao", "ferramenta", "sigla",
    )


@pytest.mark.parametrize("path", PACKS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_pack_term_uses_a_listed_class(path):
    pack = load_pack(path, learned=Learned())
    assert {t.klass for t in pack.terms} <= set(CLASSES) | {None}


@pytest.mark.parametrize("path", GOLDS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_in_scope_gold_row_uses_a_listed_class(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["term"]]
    # Blank means unlabelled; any value that is present must be on the list.
    assert {r["class"] for r in rows} - {""} <= set(CLASSES)


def test_an_unlisted_class_is_refused(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text("language: pt-BR\nterms:\n  - term: X\n    class: gestora\n", encoding="utf-8")
    with pytest.raises(ValueError, match="gestora"):
        load_pack(path, learned=Learned())


def test_class_does_not_affect_matching_except_for_units(tmp_path):
    """D-021, with D-028's one exception: a `unidade` term is never fuzzy."""
    def run(klass):
        path = tmp_path / f"{klass}.yaml"
        path.write_text(
            f"language: pt-BR\nterms:\n  - term: CEMIG\n    class: {klass}\n    variants: [SEMIG]\n",
            encoding="utf-8",
        )
        found = find_annotations(parse_caption("0:01 a SEMIG caiu"), load_pack(path, learned=Learned()))
        return [(a.original, a.term, a.rule, a.band) for a in found]

    assert run("companhia") == run("sigla") != []

    def fuzzy(klass):
        path = tmp_path / f"f{klass}.yaml"
        path.write_text(f"language: pt-BR\nterms:\n  - term: bilhão\n    class: {klass}\n", encoding="utf-8")
        found = find_annotations(parse_caption("0:01 foi 1 milhão só"), load_pack(path, learned=Learned()))
        return [a.original for a in found]

    assert "milhão" in fuzzy("conceito")  # any other class: a fuzzy near-miss
    assert fuzzy("unidade") == []
