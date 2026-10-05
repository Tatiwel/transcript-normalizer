"""D-052: the standalone executable keeps runs/ and packs/ in the data directory."""

import shutil
import sys

import pytest

from transcript_normalizer import cli, runs
from transcript_normalizer.runs import (
    BUNDLED_PACKS,
    DATA_DIR_ENV,
    DEFAULT_PACK,
    base_dir,
    default_pack,
    learned_file,
    packs_root,
    runs_root,
)

from .conftest import CAPTION, FIXTURE_VIDEO_ID


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    """As PyInstaller runs it: `sys.frozen` set, started from some other directory."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    elsewhere = tmp_path / "where-the-system-started-it"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    home = tmp_path / "Documents" / "transcript-normalizer"
    monkeypatch.setenv(DATA_DIR_ENV, str(home))
    return home


def test_not_frozen_is_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not runs.is_frozen()
    assert runs_root() == tmp_path / "runs" and packs_root() == tmp_path / "packs"
    assert not (tmp_path / "runs").exists()  # nothing is created outside frozen mode


def test_frozen_uses_the_data_directory_and_creates_it(frozen):
    assert runs.is_frozen()
    assert base_dir() == frozen
    assert runs_root() == frozen / "runs" and runs_root().is_dir()
    assert packs_root() == frozen / "packs" and packs_root().is_dir()


def test_the_data_directory_is_under_the_documents_directory(tmp_path, monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    import platformdirs

    monkeypatch.setattr(platformdirs, "user_documents_dir", lambda: str(tmp_path / "Docs"))
    assert runs.data_dir() == tmp_path / "Docs" / "transcript-normalizer"


def test_a_frozen_run_writes_into_the_data_directory(frozen, tmp_path):
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert cli.main([str(caption)]) == 0
    assert (frozen / "runs" / FIXTURE_VIDEO_ID / "normalized.txt").exists()
    assert not (tmp_path / "where-the-system-started-it" / "runs").exists()
    # The bundled pack is the default; the learned layer would go beside the user's packs.
    assert default_pack() == BUNDLED_PACKS / DEFAULT_PACK
    assert learned_file(default_pack()).parent == frozen / "packs"


def test_the_menu_says_where_the_files_are(frozen, monkeypatch, capsys):
    monkeypatch.setattr(cli, "is_interactive", lambda: True)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("q\n"))
    assert cli.main([]) == 0
    assert f"your files: {frozen}" in capsys.readouterr().out
