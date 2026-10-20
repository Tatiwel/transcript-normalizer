"""D-088: the pack that ships inside the program is included, not installed.

A fresh data folder has no pack installed. "What is this video about?" lists
the installed packs, then the included ones and the repository's, each with
its mark; picking one installs it, as `pack install` does, and normalizes.
"""

import hashlib
import json

import pytest

from transcript_normalizer import registry, runs
from transcript_normalizer.cli import main
from transcript_normalizer.runs import BUNDLED_PACKS, NORMALIZED_FILE

from .conftest import CAPTION
from .fetch_fakes import LINK, VIDEO_ID
from .test_interactive import menu

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"
VERSION = "0.3.8"
MED = "language: pt-BR\nversion: 0.1.0\nclasses: [farmaco]\nterms:\n  - term: Dipirona\n    class: farmaco\n"


def publish(repo, packs):
    """A packs repository on disk: name -> (version, text)."""
    entries = []
    for name, (version, text) in packs.items():
        (repo / name).mkdir(parents=True, exist_ok=True)
        path = repo / name / "pack.yaml"
        path.write_text(text, encoding="utf-8")
        entries.append({"name": name, "version": version, "language": "pt-BR", "description": f"{name} terms",
                        "path": f"{name}/pack.yaml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (repo / "index.json").write_text(json.dumps({"version": 1, "packs": entries}), encoding="utf-8")
    return (repo / "index.json").as_uri()


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fresh data folder, and an index that is not there (offline)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, (tmp_path / "offline" / "index.json").as_uri())
    return tmp_path


def about(out):
    """The options of the first "What is this video about?"."""
    block = out.split("What is this video about?")[1]
    return [line.strip() for line in block.split("\n> ")[0].splitlines() if line.strip()[:2].rstrip(".").isalnum()
            and ". " in line]


# ------------------------------------------------------------------ nothing installed


def test_a_fresh_folder_has_no_pack_installed(home):
    assert runs.installed_packs() == {}
    assert list(runs.included_packs()) == ["financas-ptbr"]
    assert registry.installed() == {}


def test_the_question_shows_the_included_pack_as_not_installed(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "b", "q"])
    assert "No pack installed yet: you will be asked what the video is about." in out.splitlines()
    options = about(out)
    assert options[0].startswith("1. financas-ptbr")
    assert options[0].endswith(f"pt-BR · {VERSION} · 70 terms  (included, not installed)")
    assert options[1].startswith("2. Create your own from a template…")
    assert options[2].startswith("3. None / another area")
    assert options[3] == "b. <- Back"
    assert runs.installed_packs() == {}  # Back installed nothing


def test_choosing_it_installs_it_and_normalizes(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "1", "n", "n", "n", "q"])
    target = home / "packs" / "financas-ptbr.yaml"
    assert f"installed financas-ptbr {VERSION} in {target} (included in the program)" in out
    assert target.read_bytes() == BUNDLED.read_bytes()
    assert (home / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()
    # The same record `pack install` writes for a download, so update and merge work alike.
    assert registry.installed() == {
        "financas-ptbr": {"version": VERSION, "sha256": hashlib.sha256(BUNDLED.read_bytes()).hexdigest()},
    }
    # Next time it is installed: listed first, unmarked, and the first screen offers it.
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "b", "q"])
    assert "Pack offered first: financas-ptbr" in out.splitlines()
    options = about(out)
    assert options[0].startswith("1. financas-ptbr") and options[0].endswith(f"pt-BR · {VERSION} · 70 terms")
    assert options[1].startswith("2. Create your own")


def test_the_order_installed_included_repository_template_none(home, monkeypatch, capsys):
    monkeypatch.setenv(registry.INDEX_ENV, publish(home / "repo", {"med-ptbr": ("0.1.0", MED)}))
    main(["pack", "create", "--template", "geral", "--name", "mine", "--lang", "pt-BR"])
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "b", "q"])
    labels = [o.split()[1] for o in about(out)]
    assert labels == ["mine", "financas-ptbr", "med-ptbr", "Create", "None", "<-"]
    assert about(out)[2].endswith("pt-BR · 0.1.0 · med-ptbr terms  (from the packs repository)")


def test_a_repository_pack_is_installed_when_chosen(home, monkeypatch, capsys):
    monkeypatch.setenv(registry.INDEX_ENV, publish(home / "repo", {"med-ptbr": ("0.1.0", MED)}))
    menu(home, monkeypatch, capsys, [*LINK, "", "2", "n", "q"])  # it does not fit; no term to add
    assert (home / "packs" / "med-ptbr.yaml").read_text(encoding="utf-8") == MED
    assert registry.installed()["med-ptbr"]["version"] == "0.1.0"


def test_create_your_own_from_a_template(home, monkeypatch, capsys):
    lines = [*LINK, "", "2", "2", "med-ptbr", "pt-BR", "y", "q"]  # the template: medicina, second
    _, out, _ = menu(home, monkeypatch, capsys, lines)
    assert (home / "packs" / "med-ptbr.yaml").exists()
    assert "Add its terms (Packs → Edit a pack), then normalize this run again." in out
    assert not (home / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()


# ------------------------------------------------------------------ offline


def test_offline_the_question_still_lists_the_included_pack(home, monkeypatch, capsys):
    # conftest's index is a file that is not there: unreachable, at once.
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "b", "q"])
    assert [o.split()[1] for o in about(out)] == ["financas-ptbr", "Create", "None", "<-"]


def test_offline_get_a_pack_lists_the_included_pack(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "2", "1", "b", "q"])
    assert "only the packs included in the program are listed" in out
    assert f"   1. financas-ptbr   {VERSION}  (included, not installed)" in out
    assert f"installed financas-ptbr {VERSION}" in out and "financas-ptbr" in runs.installed_packs()


def test_pack_install_works_offline_for_an_included_pack(home, capsys):
    assert main(["pack", "install", "financas-ptbr"]) == 0
    target = home / "packs" / "financas-ptbr.yaml"
    assert capsys.readouterr().out == f"installed financas-ptbr {VERSION} in {target} (included in the program)\n"
    assert main(["pack", "install", "financas-ptbr"]) == 0
    assert "already installed" in capsys.readouterr().out
    assert main(["pack", "install", "biomed-ptbr"]) == 1  # not included: the repository is needed
    assert "could not reach" in capsys.readouterr().err


def test_install_included_never_reads_the_repository(home, monkeypatch, capsys):
    def unreachable(*args, **kwargs):
        raise AssertionError("read the repository")

    monkeypatch.setattr(registry, "fetch", unreachable)
    assert main(["pack", "install", "financas-ptbr", "--included"]) == 0
    assert main(["pack", "install", "med-ptbr", "--included"]) == 1
    assert "no pack called med-ptbr is included in this program" in capsys.readouterr().err


def test_pack_list_shows_the_three_sources(home, monkeypatch, capsys):
    monkeypatch.setenv(registry.INDEX_ENV, publish(home / "repo", {"med-ptbr": ("0.1.0", MED)}))
    main(["pack", "create", "--template", "geral", "--name", "mine", "--lang", "pt-BR"])
    capsys.readouterr()
    assert main(["pack", "list"]) == 0
    rows = capsys.readouterr().out.splitlines()
    assert rows[0].startswith("mine           0.1.0  pt-BR  installed (yours)  ")
    assert rows[1].startswith(f"financas-ptbr  {VERSION}  pt-BR  (included, not installed)  ")
    assert rows[2] == "med-ptbr       0.1.0  pt-BR  (from the packs repository)  med-ptbr terms"
    # Offline: the repository's are left out, and it says so.
    assert main(["pack", "list", "--index", (home / "nowhere.json").as_uri()]) == 0
    out = capsys.readouterr().out
    assert "financas-ptbr" in out and "med-ptbr" not in out
    assert "the packs repository was not reached" in out


def test_the_repository_s_newer_version_wins_over_the_included_one(home, monkeypatch, capsys):
    newer = BUNDLED.read_text(encoding="utf-8").replace(f"version: {VERSION}", "version: 9.9.9")
    monkeypatch.setenv(registry.INDEX_ENV, publish(home / "repo", {"financas-ptbr": ("9.9.9", newer)}))
    assert main(["pack", "list"]) == 0
    assert capsys.readouterr().out.startswith("financas-ptbr  9.9.9  pt-BR  (included, not installed)  ")
    assert main(["pack", "install", "financas-ptbr"]) == 0
    out = capsys.readouterr().out
    assert "installed financas-ptbr 9.9.9" in out and "(sha256 checked)" in out
    assert "version: 9.9.9" in (home / "packs" / "financas-ptbr.yaml").read_text(encoding="utf-8")


# ------------------------------------------------------------------ existing users


def test_an_installed_pack_is_unaffected(home, monkeypatch, capsys):
    # Installed before 0.7.0, from the repository at an older version, then a run.
    (home / "packs").mkdir()
    old = BUNDLED.read_text(encoding="utf-8").replace(f"version: {VERSION}", "version: 0.3.7")
    target = home / "packs" / "financas-ptbr.yaml"
    target.write_text(old, encoding="utf-8")
    registry.write_installed({"financas-ptbr": {"version": "0.3.7",
                                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}})
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "1", "n", "n", "n", "q"])
    assert "Pack offered first: financas-ptbr" in out.splitlines()
    assert [o.split()[1] for o in about(out)] == ["financas-ptbr", "Create", "None", "<-"]
    assert "(included, not installed)" not in out and "installed financas-ptbr" not in out
    assert target.read_text(encoding="utf-8") == old  # used as it is: nothing installed over it
    assert (home / "runs" / VIDEO_ID / NORMALIZED_FILE).exists()
    # `pack update` brings it to the included version, without a connection.
    assert main(["pack", "update"]) == 1  # the index was not reached, and it says so
    captured = capsys.readouterr()
    assert "could not read the packs index" in captured.err
    assert f"financas-ptbr: 0.3.7 → {VERSION} (included in the program)" in captured.out
    assert target.read_bytes() == BUNDLED.read_bytes()


def test_a_copy_of_the_user_s_is_unaffected(home, monkeypatch, capsys):
    assert main(["pack", "copy", "financas-ptbr"]) == 0  # an included pack can be copied uninstalled
    target = home / "packs" / "financas-ptbr.yaml"
    copy = target.read_bytes()
    assert b"based_on: financas-ptbr@" in copy
    _, out, _ = menu(home, monkeypatch, capsys, [*LINK, "", "1", "n", "n", "n", "q"])
    assert "(included, not installed)" not in out
    assert target.read_bytes() == copy and registry.installed() == {}
    assert main(["pack", "update"]) == 0
    assert "nothing to update" in capsys.readouterr().out and target.read_bytes() == copy


def test_normalize_on_the_command_line_is_unchanged(home, capsys):
    # --pack still falls back to the included pack: a script needs no install.
    assert runs.default_pack() == BUNDLED
    assert main([str(CAPTION), "--quiet"]) == 0
    assert runs.installed_packs() == {}
