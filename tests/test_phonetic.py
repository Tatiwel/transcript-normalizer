"""D-050: a pt-BR consonant skeleton is a fourth matching source, for names only."""

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.languages import generic, pt_br

# exp3's hold-out: BR Partners with its canonical name and aliases, no variants.
TERMS = [
    {"term": "BR Partners", "class": "companhia", "aliases": ["BRBI11", "Partners"]},
    {"term": "Warren Buffett", "class": "pessoa"},
    {"term": "small cap", "class": "conceito", "aliases": ["small caps"]},
]


def pack_of(tmp_path, terms=TERMS, language="pt-BR", **extra):
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump({"language": language, "version": "test", "terms": terms}), "utf-8")
    extra.setdefault("learned", Learned())
    return load_pack(path, **extra)


def phonetic(pack, line):
    found = resolve_overlaps(find_annotations(parse_caption(f"0:01 {line}"), pack))
    return [(a.original, a.term, a.score, a.band) for a in found if a.rule == "term:phonetic"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Partners", "prtnrs"),
        ("BR Portness", "brprtns"),
        ("Berry Portene", "brprtn"),
        ("alto", "wt"),  # l before a consonant is vocalized
        ("cessão", "s"),  # s/c/ç -> s, doubles collapse
        ("gente", "jnt"),  # g/j -> j
    ],
)
def test_the_skeleton(text, expected):
    assert pt_br.skeleton(text) == expected


@pytest.mark.parametrize(
    "line, original, score",
    [
        ("a Berry Portene subiu", "Berry Portene", 85),
        ("comprei Portance ontem", "Portance", 90),
        ("hoje a Portinas caiu", "Portinas", 90),  # not `a Portinas`, not `Portinas caiu`
    ],
)
def test_exp3_hits_are_medium_band_proposals(tmp_path, line, original, score):
    assert phonetic(pack_of(tmp_path), line) == [(original, "BR Partners", score, "medium")]


def test_under_85_is_not_proposed(tmp_path):
    """exp3 at 80: `aportar` -> BR Partners (80) was a false positive."""
    assert phonetic(pack_of(tmp_path), "quero aportar mais") == []


def test_never_high_band_even_at_100(tmp_path):
    """wxgFO_fyfXg 36:41: `Warn Buffet` has the skeleton of `Warren Buffett`."""
    assert phonetic(pack_of(tmp_path), "do Warn Buffet. Tem") == [
        ("Warn Buffet", "Warren Buffett", 100, "medium")
    ]


def test_names_only(tmp_path):
    """A conceito term is not compared, however close its skeleton."""
    assert phonetic(pack_of(tmp_path), "uma smol caps boa") == []


def test_only_where_the_other_sources_left_nothing(tmp_path):
    terms = [dict(TERMS[0], variants=["Portance"])]
    found = resolve_overlaps(find_annotations(parse_caption("0:01 comprei Portance ontem"), pack_of(tmp_path, terms)))
    assert [(a.original, a.rule) for a in found if a.applied] == [("Portance", "term:variant")]


def test_a_rejected_pair_is_not_proposed(tmp_path):
    pack = pack_of(tmp_path, learned=Learned().reject("Portance", "BR Partners"))
    assert phonetic(pack, "comprei Portance ontem") == []


def test_the_generic_language_has_no_phonetic_source(tmp_path):
    assert generic.skeleton is None
    pack = pack_of(tmp_path, language="zz", allow_generic=True)
    assert phonetic(pack, "a Berry Portene subiu") == []
