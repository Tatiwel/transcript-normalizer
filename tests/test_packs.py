"""D-017: packs/ is the user's knowledge directory; fixtures/ packs are frozen."""

import shutil
import subprocess

import pytest

from transcript_normalizer import load_pack
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.runs import (
    BUNDLED_PACKS,
    DEFAULT_PACK,
    default_pack,
    learned_file,
    packs_root,
)

from .conftest import CAPTION, FIXTURE, FIXTURE_VIDEO_ID, PACK

REPO_PACK = BUNDLED_PACKS / DEFAULT_PACK


def test_the_repo_ships_a_usable_default_pack():
    pack = load_pack(REPO_PACK, learned=Learned())
    assert pack.terms
    assert pack.unit_rules
    # packs/ grows from the frozen fixture copy (D-017); nothing is dropped.
    assert {t.term for t in pack.terms} >= {t.term for t in load_pack(PACK, learned=Learned()).terms}


def test_pack_defaults_to_the_packs_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "packs").mkdir()
    shutil.copy(REPO_PACK, tmp_path / "packs" / DEFAULT_PACK)
    assert default_pack() == tmp_path / "packs" / DEFAULT_PACK  # the user's copy wins
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    assert main([str(caption)]) == 0  # no --pack
    assert (tmp_path / "runs" / FIXTURE_VIDEO_ID / "annotations.json").exists()


def test_the_repo_s_packs_directory_holds_no_curated_pack():
    """D-043: the curated pack ships in the package; packs/ is the user's.

    Only what git tracks there: a pack installed locally is user data, ignored
    by git (D-088), and does not belong to the repository."""
    root = FIXTURE.parents[1]
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not installed: the tracked files in packs/ cannot be listed")
    listed = subprocess.run([git, "ls-files", "--stage", "--", "packs"], cwd=root,
                            capture_output=True, text=True)
    if listed.returncode != 0:
        pytest.skip(f"not a git checkout, so packs/ has no tracked files to check: {listed.stderr.strip()}")
    # Each line: "<mode> <object> <stage>\t<path>"; mode 120000 is a symlink.
    tracked = [line.split("\t", 1) for line in listed.stdout.splitlines()]
    assert f"packs/{DEFAULT_PACK}" not in {path for _, path in tracked}
    assert not any(meta.startswith("120000 ") for meta, _ in tracked)


def test_with_no_packs_directory_the_default_is_the_bundled_pack(tmp_path, monkeypatch):
    """After `pip install`, from any directory, the default still resolves."""
    monkeypatch.chdir(tmp_path)
    assert default_pack() == BUNDLED_PACKS / DEFAULT_PACK
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    assert main([str(caption)]) == 0  # no --pack, no packs/
    assert (tmp_path / "runs" / FIXTURE_VIDEO_ID / "annotations.json").exists()


def test_a_missing_pack_is_an_error_not_a_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    assert main([str(caption), "--pack", str(tmp_path / "nope.yaml")]) == 2
    assert "no pack at" in capsys.readouterr().err


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
