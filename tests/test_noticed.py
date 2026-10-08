"""D-066: "Add a term you noticed", after Normalize and in Show a run's outputs."""

import json

import yaml

from transcript_normalizer import load_pack, registry
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.runs import ANNOTATIONS_FILE

from .fetch_fakes import LINK, VIDEO_ID
from .test_interactive import menu

#: Fetch the fake video, normalize it with financas-ptbr, decline the review.
NORMALIZED = [*LINK, "", "1", "n"]


def own(tmp_path):
    return tmp_path / "packs" / "financas-ptbr.yaml"


def term(tmp_path, name):
    return next(t for t in yaml.safe_load(own(tmp_path).read_text(encoding="utf-8"))["terms"] if t["term"] == name)


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv(registry.INDEX_ENV, (tmp_path / "offline" / "index.json").as_uri())


def test_a_new_term_from_a_run(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    lines = [*NORMALIZED, "y", "y", "melhorou", "y", "Melhoria Energia", "5", "n", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    after = out.split("Add a term you noticed? [y/N]")[1]
    assert "financas-ptbr is a bundled pack, read-only." in after
    assert "in 1 line(s) of abcdefghijk:\n    0:13 o EBITDA da Taesa melhorou" in after
    assert "+ term     Melhoria Energia (companhia)" in after
    assert "+ variant  melhorou -> Melhoria Energia" in after
    assert term(tmp_path, "Melhoria Energia") == {
        "term": "Melhoria Energia", "class": "companhia", "variants": ["melhorou"],
    }
    assert "Normalize abcdefghijk again with it? [Y/n]" in after


def test_an_existing_term_gets_the_form_as_a_variant_or_an_alias(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    lines = [*NORMALIZED, "y", "y", "dividendos", "y", "dividendo", "2", "n", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "dividendo is in the pack. How did the speaker say it?" in out
    assert "dividendos" in term(tmp_path, "dividendo")["aliases"]
    lines = [*NORMALIZED, "y", "bastante", "y", "dividendo", "1", "n", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)  # the copy is there now: not asked again
    assert "read-only" not in out.split("Add a term you noticed? [y/N]")[1]
    assert "bastante" in term(tmp_path, "dividendo")["variants"]
    assert "warning: 'bastante'" not in out  # not on the pt-BR list of ordinary words


def test_a_form_not_in_the_run_is_asked_again(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    lines = [*NORMALIZED, "y", "y", "Petrobras", "", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "'Petrobras' is not in abcdefghijk's caption" in out
    assert out.count("The wrong form you saw") == 2


def test_normalizing_again_uses_the_new_variant(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    lines = [*NORMALIZED, "y", "y", "melhorou", "y", "Melhoria Energia", "5", "y", "n", "n", "n", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    annotations = json.loads((tmp_path / "runs" / VIDEO_ID / ANNOTATIONS_FILE).read_text(encoding="utf-8"))
    assert any(a["original"] == "melhorou" and a["term"] == "Melhoria Energia" for a in annotations)
    assert out.count("* Normalize  abcdefghijk") == 2  # after the fetch, and again


def test_show_a_run_offers_it_too(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch)
    lines = [*NORMALIZED, "n", "n", "4", "1", "y", "y", "Taesa", "y", "Taesa", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    shown = out.split("normalized.txt, first")[1]
    assert "Add a term you noticed? [y/N]" in shown and "* Add a term  abcdefghijk" in shown
    pack = load_pack(own(tmp_path), learned=Learned())
    assert pack.term_named("Taesa") is not None  # an existing term: asked how it was said
