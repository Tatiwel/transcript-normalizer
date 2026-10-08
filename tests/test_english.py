"""D-068: the English module, and phonetic classes per pack."""

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, parse_caption, resolve_overlaps
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import LEGACY_PHONETIC_CLASSES, Learned
from transcript_normalizer.languages import en, for_code
from transcript_normalizer.packfiles import templates

from .test_interactive import menu

CAPTION = """\
0:01 Welcome back. Today we look at Nvidya and its quarter.
0:04 Revenue came in at 35 bn, up from last year.
0:08 The data center segment alone made 30 B.
0:11 Gaming added 3 M new users, they said.
0:15 Analysts at Goldman expect more GPUS next year;
0:19 the price to earnings ratio is still high.
0:22 Two companies, AMD and Intel, are behind.
0:26 Nvidia's margins keep growing.
0:29 That is it for the Nvidya update.
0:33 See you next week.
"""

PACK = {
    "language": "en",
    "version": "0.1.0",
    "classes": ["company", "metric", "product"],
    "terms": [
        {"term": "Nvidia", "class": "company", "variants": ["Nvidya"]},
        {"term": "GPU", "class": "product"},
        {"term": "data center", "class": "metric"},
        {"term": "billion", "class": "unidade"},
        {"term": "million", "class": "unidade"},
    ],
}


@pytest.fixture
def english(tmp_path):
    path = tmp_path / "tech-en.yaml"
    path.write_text(yaml.safe_dump(PACK), encoding="utf-8")
    caption = tmp_path / "legenda.txt"
    caption.write_text(CAPTION, encoding="utf-8")
    return path, caption


def found(path, text=CAPTION):
    return resolve_overlaps(find_annotations(parse_caption(text), load_pack(path, learned=Learned())))


def test_the_module_is_found_and_folds(english):
    assert for_code("en") is en
    assert en.normalize("Café, NVIDIA!").split() == ["cafe", "nvidia"]


@pytest.mark.parametrize("word, bases", [
    ("companies", {"company"}), ("gpus", {"gpu"}), ("boxes", {"box"}), ("class", set()),
])
def test_inflections(word, bases):
    assert bases <= en.inflections(word) and (bases or en.inflections(word) == set())


def test_a_ten_line_caption_against_a_three_term_pack(english):
    path, _ = english
    got = {(a.original, a.term) for a in found(path) if a.applied}
    assert ("Nvidya", "Nvidia") in got  # a variant, twice
    assert sum(1 for a in found(path) if a.original == "Nvidya" and a.applied) == 2
    assert ("35 bn", "billion") in got and ("30 B", "billion") in got and ("3 M", "million") in got
    recognized = {(a.original, a.term) for a in found(path)}
    assert ("GPUS", "GPU") in recognized  # a plural is the term, said that way
    assert ("data center", "data center") in recognized


def test_a_sentence_boundary_stops_a_phrase(english):
    path, _ = english
    assert "data center" in [a.term for a in found(path, "0:01 the data center grew")]
    assert "data center" not in [a.term for a in found(path, "0:01 the data. Center stage")]


def test_the_cli_normalizes_an_english_caption_without_allow_generic(english, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path, caption = english
    assert main([str(caption), "--pack", str(path), "--summary"]) == 0
    assert "no language module" not in capsys.readouterr().err


def test_the_menu_passes_allow_generic_only_without_a_module(tmp_path, monkeypatch, capsys):
    from .fetch_fakes import LINK

    monkeypatch.chdir(tmp_path)
    main(["pack", "create", "--template", "geral", "--name", "geral-de", "--lang", "de"])
    capsys.readouterr()
    # Fetch, normalize with the German pack (second in the list): generic, said once.
    # It has no terms, so it does not fit (D-054); then no term to add.
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "2", "n", "q"])
    assert out.count("no language module for de: matching with the generic one") == 1
    assert "pass --allow-generic" not in out
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "1", "n", "n", "n", "q"])
    assert "no language module" not in out


# ------------------------------------------------------------------ phonetic classes


def pack(tmp_path, **fields):
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump({"language": "pt-BR", "terms": [], **fields}), encoding="utf-8")
    return load_pack(path, learned=Learned())


def test_default_phonetic_classes(tmp_path):
    assert pack(tmp_path).phonetic_classes == LEGACY_PHONETIC_CLASSES  # no classes: line
    assert pack(tmp_path, classes=["farmaco"]).phonetic_classes == ("pessoa", "organizacao")
    assert pack(tmp_path, classes=["companhia"]).phonetic_classes == ("pessoa", "organizacao", "companhia")


def test_declared_phonetic_classes_must_be_classes(tmp_path):
    assert pack(tmp_path, classes=["farmaco"], phonetic_classes=["farmaco"]).phonetic_classes == ("farmaco",)
    with pytest.raises(ValueError, match="phonetic_classes:` names time"):
        pack(tmp_path, classes=["farmaco"], phonetic_classes=["time"])


def test_the_templates_set_their_lists():
    found_ = {f: t.phonetic_classes for f, t in templates().items() if t.phonetic_classes}
    assert found_ == {
        "medicina": ("farmaco", "doenca", "pessoa", "organizacao"),
        "tecnologia": ("produto", "biblioteca", "linguagem", "pessoa", "organizacao"),
        "esportes": ("time", "pessoa", "competicao"),
    }


def test_a_phonetic_class_of_the_pack_is_compared_and_only_asked(tmp_path):
    terms = [{"term": "Losartana", "class": "farmaco"}]
    line = parse_caption("0:01 tomei Lasirtono ontem")

    def phonetic(**fields):
        p = pack(tmp_path, classes=["farmaco"], terms=terms, **fields)
        return [(a.original, a.band, a.applied) for a in find_annotations(line, p) if a.rule == "term:phonetic"]

    assert phonetic() == []  # farmaco is not a name by default
    assert phonetic(phonetic_classes=["farmaco"]) == [("Lasirtono", "ask", False)]


def test_financas_keeps_d050s_two():
    from transcript_normalizer.runs import BUNDLED_PACKS

    assert load_pack(BUNDLED_PACKS / "financas-ptbr.yaml").phonetic_classes == ("companhia", "pessoa")
