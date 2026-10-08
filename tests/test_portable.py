"""D-070: with portable.txt beside the program, every byte stays in its folder."""

import platformdirs
import pytest

from transcript_normalizer import cli, runs
from transcript_normalizer.ingest import fetch
from transcript_normalizer.runs import CAPTION_FILE, NORMALIZED_FILE

from . import fetch_fakes
from .fetch_fakes import URL, VIDEO_ID, FakeYtDlp
from .test_interactive import menu

#: The real one: conftest replaces it with a temporary file for every test.
REAL_CONFIG_FILE = runs.config_file


def files_under(folder):
    return sorted(p for p in folder.rglob("*") if p.is_file())


@pytest.fixture
def portable(tmp_path, monkeypatch):
    """A program folder with portable.txt, a temporary home for the user's
    folders, and a current directory of its own: all three are checked."""
    app = tmp_path / "app"
    app.mkdir()
    (app / runs.PORTABLE_FILE).write_text("portable: everything stays in data/ beside the program\n", encoding="utf-8")
    home = tmp_path / "home"
    for var, sub in (("HOME", ""), ("USERPROFILE", ""), ("APPDATA", "AppData/Roaming"),
                     ("LOCALAPPDATA", "AppData/Local"), ("XDG_CONFIG_HOME", ".config"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_DOCUMENTS_DIR", "Documents")):
        (home / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(home / sub))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(runs, "program_dir", lambda: app)
    monkeypatch.setattr(runs, "config_file", REAL_CONFIG_FILE)
    monkeypatch.setenv("HF_HOME", "unset-by-the-test")  # restored after the test
    return app, home, elsewhere


def test_the_user_folders_are_the_temporary_home(portable):
    _, home, _ = portable
    for folder in (platformdirs.user_config_dir(), platformdirs.user_documents_dir(), platformdirs.user_cache_dir()):
        assert folder.startswith(str(home))


def test_a_fetch_and_normalize_write_only_inside_the_portable_folder(portable, monkeypatch, capsys):
    app, home, elsewhere = portable
    fake, _ = fetch_fakes.install(monkeypatch, fetch, FakeYtDlp())
    assert cli.main(["fetch", URL]) == 0
    data = app / runs.PORTABLE_DATA
    caption = data / "runs" / VIDEO_ID / CAPTION_FILE
    assert caption.exists()
    assert cli.main(["normalize", str(caption)]) == 0
    assert (data / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()
    runs.write_config({"pack": "financas-ptbr"})  # what the menu's settings write
    assert (data / runs.CONFIG_FILE).exists()
    # The model and yt-dlp's cache go inside too.
    import os

    assert os.environ["HF_HOME"] == str(data / "models")
    assert all(p.get("cachedir") == str(data / "cache") for p in fake.params)
    # Nothing in the user's home (config, documents, ~/.cache) or the current directory.
    assert files_under(home) == [] and files_under(elsewhere) == []
    assert all(str(p).startswith(str(app)) for p in files_under(app))


def test_yt_dlp_runs_inside_the_cache_folder(portable, monkeypatch):
    app, _, elsewhere = portable
    seen = []

    class Recorder(FakeYtDlp):
        def open(self, params):
            import os

            seen.append(os.getcwd())
            return super().open(params)

    fetch_fakes.install(monkeypatch, fetch, Recorder())
    assert cli.main(["fetch", URL]) == 0
    import os

    assert seen and set(seen) == {str(app / runs.PORTABLE_DATA / "cache")}
    assert os.getcwd() == str(elsewhere)  # and back afterwards


def test_the_variable_still_wins(portable, tmp_path, monkeypatch):
    monkeypatch.setenv(runs.DATA_DIR_ENV, str(tmp_path / "scripted"))
    assert runs.base_dir() == tmp_path / "scripted"


def test_settings_says_portable_and_offers_no_picker(portable, monkeypatch, capsys):
    app, _, elsewhere = portable
    _, out, _ = menu(elsewhere, monkeypatch, capsys, ["7", "q"])
    data = app / runs.PORTABLE_DATA
    assert f"portable mode: everything stays in {data}" in out
    assert "Choose another folder" not in out and f"Your files: {data}" in out


def test_without_portable_txt_nothing_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "program_dir", lambda: tmp_path)
    assert runs.portable_dir() is None and fetch.portable_params() == {}
