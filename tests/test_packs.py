"""D-017: packs/ is the user's knowledge directory; fixtures/ packs are frozen."""

import shutil

import pytest

from transcript_normalizer import load_pack
from transcript_normalizer.cli import main
from transcript_normalizer.runs import DEFAULT_PACK, default_pack, learned_file, packs_root

from .conftest import CAPTION, FIXTURE, FIXTURE_VIDEO_ID, PACK

REPO_PACK = FIXTURE.parents[1] / "packs" / DEFAULT_PACK


def test_the_repo_ships_a_usable_default_pack():
    pack = load_pack(REPO_PACK)
    assert pack.terms
    assert pack.unit_rules
    assert {t.term for t in pack.terms} == {t.term for t in load_pack(PACK).terms}


def test_pack_defaults_to_the_packs_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_pack() == tmp_path / "packs" / DEFAULT_PACK

    (tmp_path / "packs").mkdir()
    shutil.copy(REPO_PACK, default_pack())
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    assert main([str(caption)]) == 0  # no --pack
    assert (tmp_path / "runs" / FIXTURE_VIDEO_ID / "annotations.json").exists()


def test_a_missing_default_pack_is_an_error_not_a_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    assert main([str(caption)]) == 2

    err = capsys.readouterr().err
    assert "no pack at" in err
    assert "D-017" in err


@pytest.mark.parametrize("pack_name", ["pack.yaml", "financas-ptbr.yaml"])
def test_the_learned_layer_never_lands_in_the_pack_s_own_directory(
    tmp_path, monkeypatch, pack_name
):
    monkeypatch.chdir(tmp_path)
    # Even for a pack read straight out of fixtures/, which must stay clean.
    assert learned_file(PACK).parent == packs_root()
    assert learned_file(FIXTURE / pack_name) == tmp_path / "packs" / (
        pack_name.replace(".yaml", ".learned.yaml")
    )
