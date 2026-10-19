"""D-087: an index entry, or a pack file, that needs a newer engine.

The running engine is pinned at 0.6.5 here, so the tests do not move when the
package's own version does; financas-ptbr 0.3.8 with `min_engine: 0.7.0` is
the case that made it necessary (D-086).
"""

import hashlib
import json

import pytest
import yaml

from transcript_normalizer import engine, interactive, merge, registry
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import EngineTooOld, load_pack
from transcript_normalizer.runs import BUNDLED_PACKS

from .test_interactive import menu
from .test_merge import UPSTREAM, pack_text, triple  # noqa: F401  (triple is a fixture)

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"
NEEDS = "financas-ptbr 0.3.8 needs transcript-normalizer 0.7.0 or later (this is 0.6.5)"


@pytest.fixture(autouse=True)
def engine_065(monkeypatch):
    monkeypatch.setattr(engine, "version", lambda: "0.6.5")


def publish(repo, packs):
    """packs: name -> (version, text, min_engine or None), or a list of
    (name, version, text, min_engine) when a name has several versions."""
    entries = []
    rows = packs if isinstance(packs, list) else [(n, *rest) for n, rest in packs.items()]
    for name, version, text, min_engine in rows:
        (repo / name / version).mkdir(parents=True, exist_ok=True)
        path = repo / name / version / "pack.yaml"
        path.write_text(text, encoding="utf-8")
        entry = {"name": name, "version": version, "language": "pt-BR", "description": "a pack",
                 "path": f"{name}/{version}/pack.yaml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if min_engine is not None:
            entry["min_engine"] = min_engine
        entries.append(entry)
    (repo / "index.json").write_text(json.dumps({"version": 1, "packs": entries}), encoding="utf-8")
    return (repo / "index.json").as_uri()


def financas(version):
    return BUNDLED.read_text(encoding="utf-8").replace("version: 0.3.8", f"version: {version}")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    repo = tmp_path / "repo"
    monkeypatch.setenv(registry.INDEX_ENV, publish(repo, {"financas-ptbr": ("0.3.8", financas("0.3.8"), "0.7.0")}))
    return repo


# ------------------------------------------------------------------ comparing versions


@pytest.mark.parametrize("required, running, too_old", [
    (None, "0.6.5", False),
    ("", "0.6.5", False),
    ("0.7.0", "0.6.5", True),
    ("0.7.0", "0.7.0", False),
    ("0.7", "0.7.0", False),
    ("0.7.0", "0.7", False),
    ("0.7.0", "0.10.0", False),  # numbers, not text
    ("0.7.0", "0.7.0.dev3", False),  # a build of the next release has its features
    ("0.7.0", "0.6.9rc1", True),
    ("0.7.0", "(version unknown)", False),  # a source checkout: let through
    ("seven", "9.9.9", True),  # cannot be checked: refused
])
def test_too_old_for(required, running, too_old):
    assert engine.too_old_for(required, running) is too_old


# ------------------------------------------------------------------ the index


def test_an_entry_without_min_engine_is_read_as_before(tmp_path):
    url = publish(tmp_path, {"financas-ptbr": ("0.3.7", financas("0.3.7"), None)})
    entry = registry.read_index(url)["financas-ptbr"]
    assert entry.min_engine == "" and not entry.too_new()


def test_an_entry_with_min_engine_is_read_and_held_back(repo):
    entries = registry.read_index(registry.index_url())
    entry = entries["financas-ptbr"]
    assert entry.min_engine == "0.7.0" and entry.too_new() and entry.needs() == NEEDS
    assert registry.installable(entries) == {}


def test_list_explains_it(repo, capsys):
    assert main(["pack", "list"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("financas-ptbr  0.3.8  pt-BR  bundled, needs 0.7.0+  ")
    assert f"{NEEDS}; it cannot be installed with this version" in out
    assert registry.RELEASES in out


def test_install_refuses_it_even_with_force(repo, tmp_path, capsys):
    for flags in ([], ["--force"]):
        assert main(["pack", "install", "financas-ptbr", *flags]) == 1
        err = capsys.readouterr().err
        assert NEEDS in err and "nothing was installed" in err
    assert not (tmp_path / "work" / "packs").exists()


def test_install_itself_never_writes_it(repo, tmp_path):
    entry = registry.read_index(registry.index_url())["financas-ptbr"]
    with pytest.raises(registry.RegistryError, match="needs transcript-normalizer 0.7.0"):
        registry.install(entry, registry.index_url(), tmp_path / "packs")
    assert not (tmp_path / "packs").exists()


def test_a_new_enough_engine_installs_it(repo, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(engine, "version", lambda: "0.7.0")
    assert main(["pack", "install", "financas-ptbr"]) == 0
    assert "installed financas-ptbr 0.3.8" in capsys.readouterr().out
    assert (tmp_path / "work" / "packs" / "financas-ptbr.yaml").exists()


def test_update_keeps_the_installed_version(tmp_path, monkeypatch, capsys):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    repo = tmp_path / "repo"
    monkeypatch.setenv(registry.INDEX_ENV, publish(repo, {"financas-ptbr": ("0.3.7", financas("0.3.7"), None)}))
    assert main(["pack", "install", "financas-ptbr"]) == 0
    target = tmp_path / "work" / "packs" / "financas-ptbr.yaml"
    before = target.read_bytes()
    publish(repo, {"financas-ptbr": ("0.3.8", financas("0.3.8"), "0.7.0")})
    capsys.readouterr()
    assert main(["pack", "update"]) == 0
    out = capsys.readouterr().out
    assert f"financas-ptbr: {NEEDS}; 0.3.7 is kept" in out and registry.RELEASES in out
    assert target.read_bytes() == before
    assert registry.installed()["financas-ptbr"]["version"] == "0.3.7"
    assert main(["pack", "list", "--installed"]) == 0
    out = capsys.readouterr().out
    assert "needs 0.7.0+ (0.3.8)" in out and "↑ update" not in out
    assert f"{NEEDS}; `pack update` leaves the one you have" in out


def test_the_menu_cache_keeps_min_engine(repo):
    from transcript_normalizer import packfiles

    packfiles.index_cache().parent.mkdir(parents=True)
    assert packfiles.index_cached_within(3)["financas-ptbr"].min_engine == "0.7.0"
    assert packfiles.cached_index()["financas-ptbr"].too_new()


def test_get_a_pack_in_the_menu_offers_nothing_it_cannot_install(repo, tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path / "work", monkeypatch, capsys, ["6", "2", "b", "q"])
    assert NEEDS in out and "Which pack?" not in out
    assert not (tmp_path / "work" / "packs" / "financas-ptbr.yaml").exists()


def test_get_a_pack_shows_it_but_does_not_let_it_be_picked(repo, tmp_path, monkeypatch, capsys):
    med = "language: pt-BR\nversion: 0.1.0\nterms:\n  - term: Paracetamol\n"
    publish(repo, {"financas-ptbr": ("0.3.8", financas("0.3.8"), "0.7.0"), "med-ptbr": ("0.1.0", med, None)})
    _, out, _ = menu(tmp_path / "work", monkeypatch, capsys, ["6", "2", "1", "2", "b", "q"])
    assert f"({NEEDS})" in out
    assert "installed med-ptbr 0.1.0" in out
    assert not (tmp_path / "work" / "packs" / "financas-ptbr.yaml").exists()


# ------------------------------------------------------------------ two versions of one pack

#: As the packs repository would publish 0.3.8: newest first, the one for older engines last.
BOTH = [("financas-ptbr", "0.3.8", financas("0.3.8"), "0.7.0"), ("financas-ptbr", "0.3.7", financas("0.3.7"), None)]


@pytest.fixture
def both(tmp_path, monkeypatch):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    monkeypatch.setenv(registry.INDEX_ENV, publish(tmp_path / "repo", BOTH))
    return tmp_path / "repo"


def test_an_engine_that_ignores_min_engine_takes_the_last_entry(both):
    """What 0.4.2 to 0.6.5 do with index.json: the last entry of a name, extra keys ignored."""
    data = json.loads((both / "index.json").read_text())
    old = {e["name"]: {f: e[f] for f in registry.FIELDS} for e in data["packs"]}
    assert old["financas-ptbr"]["version"] == "0.3.7"


def test_this_engine_takes_the_newest_it_can_use(both, monkeypatch):
    entry = registry.read_index(registry.index_url())["financas-ptbr"]
    assert entry.version == "0.3.7" and not entry.too_new()
    assert entry.held.version == "0.3.8" and entry.blocked.needs() == NEEDS
    monkeypatch.setattr(engine, "version", lambda: "0.7.0")
    entry = registry.read_index(registry.index_url())["financas-ptbr"]
    assert entry.version == "0.3.8" and entry.held is None and entry.blocked is None


def test_versions_sort_as_numbers(tmp_path):
    rows = [("financas-ptbr", v, financas(v), None) for v in ("0.3.10", "0.3.9")]
    assert registry.read_index(publish(tmp_path, rows))["financas-ptbr"].version == "0.3.10"


def test_install_and_update_take_the_older_one_and_say_why(both, tmp_path, capsys):
    assert main(["pack", "list"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("financas-ptbr  0.3.7  pt-BR  bundled  ")
    assert f"{NEEDS}; 0.3.7 is the newest for this version" in out
    assert main(["pack", "install", "financas-ptbr"]) == 0
    out = capsys.readouterr().out
    assert "installed financas-ptbr 0.3.7" in out and NEEDS in out
    target = tmp_path / "work" / "packs" / "financas-ptbr.yaml"
    assert "version: 0.3.7" in target.read_text("utf-8")
    assert main(["pack", "update"]) == 0
    assert f"financas-ptbr: 0.3.7 is the latest for this version; {NEEDS}" in capsys.readouterr().out
    assert main(["pack", "list", "--installed"]) == 0
    out = capsys.readouterr().out
    assert "↑ update" not in out and f"{NEEDS}; `pack update` leaves the one you have" in out


def test_update_from_an_older_one_stops_at_the_newest_it_can_use(tmp_path, monkeypatch, capsys):
    (tmp_path / "work").mkdir()
    monkeypatch.chdir(tmp_path / "work")
    repo = tmp_path / "repo"
    monkeypatch.setenv(registry.INDEX_ENV, publish(repo, [("financas-ptbr", "0.3.6", financas("0.3.6"), None)]))
    assert main(["pack", "install", "financas-ptbr"]) == 0
    publish(repo, BOTH)
    capsys.readouterr()
    assert main(["pack", "update"]) == 0
    out = capsys.readouterr().out
    assert "financas-ptbr: 0.3.6 → 0.3.7" in out and NEEDS in out
    assert registry.installed()["financas-ptbr"]["version"] == "0.3.7"


def test_the_cache_keeps_both(both):
    from transcript_normalizer import packfiles

    packfiles.index_cache().parent.mkdir(parents=True)
    packfiles.index_cached_within(3)
    entry = packfiles.cached_index()["financas-ptbr"]
    assert entry.version == "0.3.7" and entry.held.version == "0.3.8"


# ------------------------------------------------------------------ merges (D-069), the menu's background look


def test_a_copy_is_not_offered_an_upstream_it_cannot_use(triple, tmp_path, monkeypatch, capsys):  # noqa: F811
    from .test_merge import publish as publish_med

    url = publish_med(tmp_path / "repo", "0.2.0", pack_text(UPSTREAM, "0.2.0"))
    data = json.loads((tmp_path / "repo" / "index.json").read_text())
    data["packs"][0]["min_engine"] = "0.7.0"
    (tmp_path / "repo" / "index.json").write_text(json.dumps(data))
    monkeypatch.setenv(registry.INDEX_ENV, url)
    assert merge.offers() == []
    monkeypatch.setattr(interactive, "MERGE_CHECK_IN_BACKGROUND", False)
    interactive.start_merge_check()
    assert interactive.merge_offers() == []
    before = triple.read_bytes()
    assert main(["pack", "merge", "med"]) == 1
    out = capsys.readouterr()
    assert "med 0.2.0 needs transcript-normalizer 0.7.0 or later" in out.out
    assert triple.read_bytes() == before


# ------------------------------------------------------------------ a pack file copied by hand


def hand_copied(tmp_path, min_engine="0.7.0", name="financas-ptbr"):
    path = tmp_path / f"{name}.yaml"
    text = BUNDLED.read_text(encoding="utf-8").replace("version: 0.3.8\n", f"version: 0.3.8\nmin_engine: {min_engine}\n")
    path.write_text(text, encoding="utf-8")
    return path


def test_load_pack_refuses_a_pack_that_needs_a_newer_engine(tmp_path):
    path = hand_copied(tmp_path)
    with pytest.raises(EngineTooOld) as error:
        load_pack(path)
    assert str(error.value).startswith(
        f"{path}: this pack (0.3.8) needs transcript-normalizer 0.7.0 or later (this is 0.6.5)")
    assert isinstance(error.value, ValueError)  # the pack checks that catch ValueError refuse it too


def test_load_pack_takes_it_when_the_engine_is_new_enough(tmp_path, monkeypatch):
    path = hand_copied(tmp_path, "0.6.5")
    assert load_pack(path).version == "0.3.8"
    assert yaml.safe_load(path.read_text("utf-8"))["min_engine"] == "0.6.5"


def test_normalize_says_so_and_stops(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = hand_copied(tmp_path)
    caption = tmp_path / "c.txt"
    caption.write_text("o OPEX e o CAPEX\n", encoding="utf-8")
    assert main(["normalize", str(caption), "--pack", str(path)]) == 2
    err = capsys.readouterr().err
    assert "needs transcript-normalizer 0.7.0 or later" in err and "Traceback" not in err


def test_pack_import_refuses_it(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    path = hand_copied(tmp_path, name="fin")
    assert main(["pack", "import", str(path)]) != 0
    assert "needs transcript-normalizer 0.7.0 or later" in capsys.readouterr().err
    assert not (tmp_path / "packs" / "fin.yaml").exists()
