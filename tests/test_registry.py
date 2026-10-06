"""D-055: pack list, install and update against a local file:// index."""

import hashlib
import json

import pytest

from transcript_normalizer import registry
from transcript_normalizer.cli import main
from transcript_normalizer.runs import BUNDLED_PACKS, default_pack, installed_packs

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"


def publish(repo, version="0.3.4", sha=None, text=None):
    """A packs repository on disk: one pack and its index."""
    (repo / "financas-ptbr").mkdir(parents=True, exist_ok=True)
    pack = repo / "financas-ptbr" / "pack.yaml"
    pack.write_text(text or BUNDLED.read_text(encoding="utf-8"), encoding="utf-8")
    entry = {
        "name": "financas-ptbr",
        "version": version,
        "language": "pt-BR",
        "description": "Brazilian stock-market videos",
        "path": "financas-ptbr/pack.yaml",
        "sha256": sha or hashlib.sha256(pack.read_bytes()).hexdigest(),
    }
    (repo / "index.json").write_text(json.dumps({"version": 1, "packs": [entry]}), encoding="utf-8")
    return (repo / "index.json").as_uri()


@pytest.fixture
def index(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    url = publish(tmp_path / "repo")
    monkeypatch.setenv(registry.INDEX_ENV, url)
    return tmp_path / "repo"


def test_list_shows_the_index_and_what_is_here(index, capsys):
    assert main(["pack", "list"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "financas-ptbr  0.3.4  pt-BR  bundled  Brazilian stock-market videos"


def test_install_writes_into_packs_and_becomes_the_default(index, tmp_path, capsys):
    assert main(["pack", "install", "financas-ptbr"]) == 0
    target = tmp_path / "work" / "packs" / "financas-ptbr.yaml"
    assert target.read_bytes() == BUNDLED.read_bytes()
    assert "installed financas-ptbr 0.3.4" in capsys.readouterr().out
    assert default_pack() == target and installed_packs()["financas-ptbr"] == target
    assert main(["pack", "list"]) == 0
    assert "installed 0.3.4" in capsys.readouterr().out
    assert main(["pack", "install", "financas-ptbr"]) == 0
    assert "already installed" in capsys.readouterr().out


def test_a_sha256_mismatch_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, publish(tmp_path / "repo", sha="0" * 64))
    assert main(["pack", "install", "financas-ptbr"]) == 1
    assert "does not match the index's sha256" in capsys.readouterr().err
    assert not (tmp_path / "packs").exists()


def test_an_unknown_pack_is_an_error(index, capsys):
    assert main(["pack", "install", "biomed-ptbr"]) == 1
    assert "no pack called biomed-ptbr" in capsys.readouterr().err


def test_an_unreachable_index_is_a_message(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    url = (tmp_path / "nowhere" / "index.json").as_uri()
    assert main(["pack", "list", "--index", url]) == 1
    err = capsys.readouterr().err
    assert err.startswith(f"could not read the packs index: could not reach {url}")
    assert "Traceback" not in err


def test_update_installs_a_newer_version(index, tmp_path, capsys):
    assert main(["pack", "install", "financas-ptbr"]) == 0
    newer = BUNDLED.read_text(encoding="utf-8").replace("version: 0.3.4", "version: 0.3.5")
    publish(index, version="0.3.5", text=newer)
    assert main(["pack", "update"]) == 0
    assert "financas-ptbr: 0.3.4 → 0.3.5" in capsys.readouterr().out
    assert "version: 0.3.5" in (tmp_path / "work" / "packs" / "financas-ptbr.yaml").read_text("utf-8")
    assert main(["pack", "update"]) == 0
    assert "0.3.5 is the latest" in capsys.readouterr().out


def test_update_and_install_leave_a_pack_edited_here_alone(index, tmp_path, capsys):
    assert main(["pack", "install", "financas-ptbr"]) == 0
    target = tmp_path / "work" / "packs" / "financas-ptbr.yaml"
    target.write_text(target.read_text("utf-8") + "# mine\n", encoding="utf-8")
    publish(index, version="0.3.5")
    assert main(["pack", "update"]) == 0
    assert "was edited here; left as it is" in capsys.readouterr().out
    assert main(["pack", "install", "financas-ptbr"]) == 1
    assert "pass --force" in capsys.readouterr().err
    assert target.read_text("utf-8").endswith("# mine\n")
    assert main(["pack", "install", "financas-ptbr", "--force"]) == 0
    assert target.read_bytes() == BUNDLED.read_bytes()


def test_update_with_nothing_installed(index, capsys):
    assert main(["pack", "update"]) == 0
    assert "nothing to update" in capsys.readouterr().out


def test_a_name_that_would_leave_packs_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    url = publish(repo)
    data = json.loads((repo / "index.json").read_text())
    data["packs"][0]["name"] = "../evil"
    (repo / "index.json").write_text(json.dumps(data))
    assert main(["pack", "list", "--index", url]) == 1
    assert "not a pack name: ../evil" in capsys.readouterr().err
