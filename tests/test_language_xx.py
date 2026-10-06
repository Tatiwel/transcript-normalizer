"""D-033: the core runs on any language that has a module, and only then.

`xx` does not exist. tests/data/xx/ holds a 20-line caption and a 3-term pack
in it, and tests/lang_xx.py a module for it: the template for adding a language.
"""

import shutil
from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, read_caption, resolve_overlaps
from transcript_normalizer import languages
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.render import render_lines
from transcript_normalizer.languages import LanguageNotFound, generic

from . import lang_xx

DATA = Path(__file__).resolve().parent / "data" / "xx"
PACK = DATA / "pack.yaml"
CAPTION = DATA / "legenda.txt"


@pytest.fixture
def xx_registered(monkeypatch):
    """Register the fake module for this test only."""
    monkeypatch.setitem(languages._REGISTRY, "xx", lang_xx)


def found(pack):
    transcript = read_caption(CAPTION)
    annotations = resolve_overlaps(find_annotations(transcript, pack))
    return transcript, {(a.original, a.term, a.rule, a.kind) for a in annotations if a.applied}


# ---------------------------------------------------------------- (3) no module


def test_a_pack_in_a_language_with_no_module_is_refused():
    with pytest.raises(LanguageNotFound) as error:
        load_pack(PACK, learned=Learned())
    message = str(error.value)
    assert "'xx'" in message and "languages/xx.py" in message and "--allow-generic" in message


def test_the_cli_says_so_and_stops(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main([str(CAPTION), "--pack", str(PACK)]) == 2
    assert "no language module for 'xx'" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_a_pack_that_names_no_language_is_refused(tmp_path):
    """D-002: the tool never infers the language."""
    path = tmp_path / "p.yaml"
    path.write_text("terms:\n  - term: fnord\n    class: conceito\n", encoding="utf-8")
    with pytest.raises(LanguageNotFound, match="declares no language"):
        load_pack(path, learned=Learned())


# ---------------------------------------------------------------- (1) generic


def test_the_core_runs_end_to_end_with_the_generic_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert main([str(caption), "--pack", str(PACK), "--allow-generic", "--force"]) == 0

    run = tmp_path / "runs" / "xxLanguages"
    for name in ("annotations.json", "normalized.txt", "report.txt", "legenda.txt"):
        assert (run / name).exists(), name
    normalized = (run / "normalized.txt").read_text(encoding="utf-8").splitlines()
    assert len(normalized) == 20
    assert "0:03  a Glorbank vasta minde" in normalized


def test_generic_has_no_inflections_no_units_and_the_common_boundaries():
    pack = load_pack(PACK, learned=Learned(), allow_generic=True)
    assert pack.language is generic
    _, hits = found(pack)
    assert ("glorbenk", "Glorbank", "term:variant", "correction") in hits
    assert ("glorbanc", "Glorbank", "term:fuzzy", "correction") in hits  # fuzzy is core
    assert not [h for h in hits if h[1] in ("fnord", "zorkon")]
    assert ("glorb | bank", "Glorbank", "term:variant", "correction") in hits  # `|` is not a boundary


# ---------------------------------------------------------------- (2) a module


def test_inflections_unit_rules_and_boundaries_come_from_the_module(xx_registered):
    pack = load_pack(PACK, learned=Learned())
    assert pack.language is lang_xx
    transcript, hits = found(pack)

    # The module's one inflection: `fnordix` is `fnord` spelled out (D-031a).
    assert ("fnordix", "fnord", "term:alias", "alias") in hits
    # The module's one unit rule, resolved to the pack's unidade term (D-006).
    assert ("12 zk", "zorkon", "unit", "correction") in hits
    assert dict(render_lines(transcript, resolve_overlaps(find_annotations(transcript, pack))))[
        "0:09"
    ] == "blorp vasta 12 zorkon minde"
    # The module's boundary: no n-gram runs across `|` (D-024).
    assert not [h for h in hits if "|" in h[0]]


def test_a_module_that_breaks_the_protocol_is_refused():
    import types

    broken = types.ModuleType("broken")
    broken.normalize = lambda text: text
    with pytest.raises(TypeError, match="inflections"):
        languages.register("zz", broken)
