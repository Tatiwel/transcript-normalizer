"""D-104: `tn update` reads what a newer release brings; `tn upgrade` installs it
the way this copy was installed. No network here: registry.fetch is replaced."""

import json
import subprocess
import sys

import pytest

from transcript_normalizer import registry, selfupdate
from transcript_normalizer.cli import main

CHANGELOG = """# Changelog

## Unreleased

## 0.8.8

2026-12-01. Something newer.

- the newest line

## 0.8.7

2026-11-23. Something new.

- a new line

## 0.8.6

2026-11-22. What is installed.
"""


@pytest.fixture
def online(monkeypatch):
    def fetch(url, timeout=None):
        if url == selfupdate.LATEST_URL:
            return json.dumps({"tag_name": "v0.8.8"}).encode()
        if url == selfupdate.CHANGELOG_URL.format(tag="v0.8.8"):
            return CHANGELOG.encode()
        raise AssertionError(url)

    monkeypatch.setattr(registry, "fetch", fetch)
    monkeypatch.setattr(selfupdate, "installed_version", lambda: "0.8.6")


def test_versions_are_compared_as_numbers():
    assert selfupdate.parse("v0.8.10") > selfupdate.parse("0.8.9")
    assert selfupdate.parse("0.9.0") > selfupdate.parse("0.8.99")
    assert selfupdate.parse("v1.0.0-rc1") == ()


def test_the_sections_between_the_two_versions():
    text = selfupdate.changes(CHANGELOG, "0.8.6", "v0.8.8")
    assert text.startswith("## 0.8.8") and "## 0.8.7" in text and "the newest line" in text
    assert "## 0.8.6" not in text and "Unreleased" not in text
    assert selfupdate.changes(CHANGELOG, "0.8.7", "v0.8.7") == ""


def test_update_says_what_is_newer_and_installs_nothing(online, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("update installed something"))
    assert main(["update"]) == 0
    out = capsys.readouterr().out
    assert "installed: 0.8.6\nlatest:    0.8.8\n" in out
    assert "## 0.8.8" in out and "## 0.8.7" in out and "`tn upgrade` installs it." in out


def test_update_when_up_to_date(online, monkeypatch, capsys):
    monkeypatch.setattr(selfupdate, "installed_version", lambda: "0.8.8")
    assert main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_offline_is_said(monkeypatch, capsys):
    def fetch(url, timeout=None):
        raise registry.RegistryError(f"could not reach {url}: no network")

    monkeypatch.setattr(registry, "fetch", fetch)
    assert main(["update"]) == 1
    assert "could not check for a newer version" in capsys.readouterr().err


def project(tmp_path, dependency='"transcript-normalizer[ingest]",'):
    folder = tmp_path / "tools" / "ingest"
    (folder / ".venv").mkdir(parents=True)
    (folder / "pyproject.toml").write_text(
        f'[project]\nname = "valuation-ingest"\ndependencies = [\n    {dependency}\n]\n', encoding="utf-8")
    return folder


def test_a_project_is_moved_to_the_new_tag_with_its_extras(tmp_path, online, monkeypatch, capsys):
    folder = project(tmp_path)
    monkeypatch.setattr(sys, "prefix", str(folder / ".venv"))
    monkeypatch.setattr(selfupdate.shutil, "which", lambda name: "/usr/bin/uv")
    ran = []
    monkeypatch.setattr(subprocess, "run", lambda argv: ran.append(argv) or subprocess.CompletedProcess(argv, 0))
    assert main(["upgrade"]) == 0
    assert ran == [["uv", "add", "--project", str(folder),
                    "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.8.8"]]
    out = capsys.readouterr().out
    assert "0.8.6 → 0.8.8 (project)" in out and "done: 0.8.8 is installed" in out


def test_a_uv_tool_is_known_by_its_receipt_wherever_it_is(tmp_path):
    tool = tmp_path / "opt" / "cli-envs" / "transcript-normalizer"  # a UV_TOOL_DIR of one's own
    tool.mkdir(parents=True)
    (tool / "uv-receipt.toml").write_text(
        '[tool]\nrequirements = [{ name = "transcript-normalizer", extras = ["captions"], '
        'git = "https://github.com/Tatiwel/transcript-normalizer?rev=v0.8.6" }]\n', encoding="utf-8")
    install = selfupdate.install_kind(tool)
    assert (install.kind, install.extras) == (selfupdate.UV_TOOL, "[captions]")  # as asked for
    assert selfupdate.command(install, "v0.8.8") == [
        "uv", "tool", "install", "--force",
        "transcript-normalizer[captions] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.8.8"]


def test_pip_keeps_the_largest_extra_installed(tmp_path, monkeypatch):
    present = {"yt_dlp", "questionary"}  # captions, which carries menu; not ingest
    monkeypatch.setattr(selfupdate.importlib.util, "find_spec", lambda name: object() if name in present else None)
    install = selfupdate.install_kind(tmp_path / "venv")
    assert (install.kind, install.extras) == (selfupdate.PIP, "[captions]")
    assert selfupdate.command(install, "v0.8.8")[:4] == [sys.executable, "-m", "pip", "install"]


@pytest.mark.parametrize("dependency", [
    '"transcript-normalizer-plugin>=1"', '"other-transcript-normalizer"',
])
def test_a_project_that_asks_for_another_package_is_not_this_one(tmp_path, dependency):
    folder = project(tmp_path, dependency + ",")
    assert selfupdate.install_kind(folder / ".venv").kind == selfupdate.PIP


def test_a_name_written_another_way_is_the_same_package(tmp_path):
    folder = project(tmp_path, '"Transcript_Normalizer[ingest]==0.8.6",')
    install = selfupdate.install_kind(folder / ".venv")
    assert (install.kind, install.extras, install.group) == (selfupdate.PROJECT, "[ingest]", "")


@pytest.mark.parametrize("group, flags", [("dev", ["--dev"]), ("tools", ["--group", "tools"])])
def test_a_declaration_in_a_group_is_moved_in_that_group(tmp_path, group, flags):
    folder = tmp_path / "proj"
    (folder / ".venv").mkdir(parents=True)
    (folder / "pyproject.toml").write_text(
        f'[project]\nname = "x"\ndependencies = []\n\n[dependency-groups]\n{group} = ["transcript-normalizer[menu]"]\n',
        encoding="utf-8")
    install = selfupdate.install_kind(folder / ".venv")
    assert (install.kind, install.group) == (selfupdate.PROJECT, group)
    assert selfupdate.command(install, "v0.8.8") == [
        "uv", "add", "--project", str(folder), *flags,
        "transcript-normalizer[menu] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.8.8"]


def test_the_repository_itself_is_a_checkout(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "transcript-normalizer"\n', encoding="utf-8")
    assert selfupdate.install_kind(tmp_path / ".venv").kind == selfupdate.CHECKOUT


def test_the_executable_says_where_to_download(online, monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("the executable ran an installer"))
    assert main(["upgrade"]) == 1
    assert "cannot replace itself" in capsys.readouterr().out


def test_upgrade_when_up_to_date_does_nothing(online, monkeypatch, capsys):
    monkeypatch.setattr(selfupdate, "installed_version", lambda: "0.8.8")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("installed while up to date"))
    assert main(["upgrade"]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_a_failed_install_says_the_command(tmp_path, online, monkeypatch, capsys):
    folder = project(tmp_path)
    monkeypatch.setattr(sys, "prefix", str(folder / ".venv"))
    monkeypatch.setattr(selfupdate.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(subprocess, "run", lambda argv: subprocess.CompletedProcess(argv, 2))
    assert main(["upgrade"]) == 2
    assert "run it by hand:\n  uv add --project" in capsys.readouterr().err


def test_without_uv_the_command_is_shown(tmp_path, online, monkeypatch, capsys):
    folder = project(tmp_path)
    monkeypatch.setattr(sys, "prefix", str(folder / ".venv"))
    monkeypatch.setattr(selfupdate.shutil, "which", lambda name: None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("ran without uv"))
    assert main(["upgrade"]) == 1
    assert "uv is not installed" in capsys.readouterr().err


def test_a_project_whose_environment_is_elsewhere_is_found_from_where_uv_runs(tmp_path, monkeypatch):
    folder = project(tmp_path)
    elsewhere = tmp_path / "envs" / "ingest"
    elsewhere.mkdir(parents=True)
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(elsewhere))
    monkeypatch.chdir(folder / ".venv")  # anywhere inside the project
    install = selfupdate.install_kind(elsewhere)
    assert (install.kind, install.where) == (selfupdate.PROJECT, folder.resolve())
    monkeypatch.delenv("UV_PROJECT_ENVIRONMENT")
    assert selfupdate.install_kind(elsewhere).kind == selfupdate.PIP  # not named: not guessed
