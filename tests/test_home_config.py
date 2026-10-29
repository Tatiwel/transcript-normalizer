"""D-089: TRANSCRIPT_NORMALIZER_HOME moves config.toml too, beside runs/ and packs/."""

import platformdirs
import pytest

from transcript_normalizer import runs

#: The real one: conftest replaces it with a temporary file for every test.
REAL_CONFIG_FILE = runs.config_file


def files_under(folder):
    return sorted(p for p in folder.rglob("*") if p.is_file())


@pytest.fixture
def user_config(tmp_path, monkeypatch):
    """The real config_file, with the platform's configuration directory
    redirected to a temporary folder, so no test reaches the developer's."""
    redirected = tmp_path / "user-config"
    redirected.mkdir()
    monkeypatch.setattr(platformdirs, "user_config_dir", lambda *a, **k: str(redirected))
    monkeypatch.setattr(runs, "config_file", REAL_CONFIG_FILE)
    monkeypatch.setattr(runs, "portable_dir", lambda: None)
    return redirected


def test_without_the_variable_settings_go_to_the_user_config_dir(user_config):
    runs.write_config({"pack": "financas-ptbr"})
    assert files_under(user_config) == [user_config / runs.CONFIG_FILE]
    assert runs.read_config() == {"pack": "financas-ptbr"}


def test_the_variable_moves_settings_into_its_folder(user_config, tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv(runs.DATA_DIR_ENV, str(home))
    assert runs.config_file() == home / runs.CONFIG_FILE
    assert runs.write_config({"pack": "financas-ptbr"}) == home / runs.CONFIG_FILE
    assert files_under(home) == [home / runs.CONFIG_FILE]
    assert runs.read_config() == {"pack": "financas-ptbr"}
    assert files_under(user_config) == []


def test_with_the_variable_the_user_config_is_not_read(user_config, tmp_path, monkeypatch):
    (user_config / runs.CONFIG_FILE).write_text('data_dir = "/elsewhere"\n', encoding="utf-8")
    monkeypatch.setenv(runs.DATA_DIR_ENV, str(tmp_path / "home"))
    assert runs.read_config() == {}
