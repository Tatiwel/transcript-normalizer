"""D-054: a pack that names fewer than three of its terms does not fit."""

import json
import shutil
from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, read_caption, resolve_overlaps
from transcript_normalizer.cli import main
from transcript_normalizer.core.fit import MIN_FIT_TERMS, fitting_terms
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.runs import (
    ANNOTATIONS_FILE,
    BUNDLED_PACKS,
    NORMALIZED_FILE,
    REPORT_FILE,
    installed_packs,
)

from .fetch_fakes import LINK, URL
from .test_interactive import DATA, menu

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = sorted(p.parent for p in (ROOT / "fixtures").glob("*/gold.csv"))
BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"
NOT_FIT = (
    "pack financas-ptbr does not seem to fit this transcript (1 terms found); "
    "nothing applied. Use --force to apply anyway."
)


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.name)
@pytest.mark.parametrize("which", ["bundled", "frozen"])
def test_every_fixture_fits_its_pack(fixture, which):
    pack = load_pack(BUNDLED if which == "bundled" else fixture / "pack.yaml", learned=Learned())
    found = resolve_overlaps(find_annotations(read_caption(fixture / "legenda.txt"), pack))
    assert len(fitting_terms(found)) >= MIN_FIT_TERMS


def unfit_run(tmp_path, monkeypatch, *extra):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(DATA / "rolling.legenda.txt", caption)  # SEMIG, and nothing else of the pack
    code = main([str(caption), *extra])
    return code, tmp_path / "runs" / "legenda"  # no video id in its url: the stem


def test_an_unfit_pack_applies_nothing(tmp_path, monkeypatch, capsys):
    code, run = unfit_run(tmp_path, monkeypatch)
    assert code == 0
    assert capsys.readouterr().out == NOT_FIT + "\n"
    normalized = (run / NORMALIZED_FILE).read_text(encoding="utf-8")
    assert "SEMIG?" in normalized and "CEMIG" not in normalized
    assert json.loads((run / ANNOTATIONS_FILE).read_text(encoding="utf-8")) == []
    assert NOT_FIT in (run / REPORT_FILE).read_text(encoding="utf-8")
    assert not (run / "needs-review").exists()


def test_force_applies_anyway(tmp_path, monkeypatch, capsys):
    code, run = unfit_run(tmp_path, monkeypatch, "--force")
    assert code == 0 and "does not seem to fit" not in capsys.readouterr().out
    assert "CEMIG?" in (run / NORMALIZED_FILE).read_text(encoding="utf-8")


def test_a_pack_in_packs_wins_over_the_bundled_one(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "packs").mkdir()
    shutil.copy(BUNDLED, tmp_path / "packs" / "financas-ptbr.yaml")
    shutil.copy(BUNDLED, tmp_path / "packs" / "biomed-ptbr.yaml")
    (tmp_path / "packs" / "biomed-ptbr.learned.yaml").write_text("version: 1\n", encoding="utf-8")
    assert installed_packs() == {
        "financas-ptbr": tmp_path / "packs" / "financas-ptbr.yaml",
        "biomed-ptbr": tmp_path / "packs" / "biomed-ptbr.yaml",
    }


# ------------------------------------------------------------------ the menu


def test_the_menu_asks_what_the_video_is_about(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "2", "q"])
    assert "What is this video about?" in out
    assert "   1. financas-ptbr         pt-BR · " in out
    assert "   2. none / another area   skip normalization" in out
    assert "No pack for this area, so nothing was normalized." in out
    assert not list((tmp_path / "runs").glob(f"*/{NORMALIZED_FILE}"))


def test_the_menu_does_not_offer_a_review_when_the_pack_does_not_fit(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, [*LINK, "", "1", "q"], vtt="rolling.vtt")
    assert "does not seem to fit this transcript" in out
    assert "Nothing to confirm" not in out and "Open the folder?" not in out
    # D-061: the menu has no --force to offer, so it names what it has.
    assert "Pick another pack in Settings, or install one with pack install." in out
    assert "--force" not in out
