"""D-066: editing a pack: copy, add-term, edit-term, remove-term, show, export,
and the menu's Edit a pack, all through the plain adapter."""

import pytest
import yaml

from transcript_normalizer import load_pack, packedit, registry, runs
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.runs import BUNDLED_PACKS

from .test_interactive import menu

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, (tmp_path / "offline" / "index.json").as_uri())
    return tmp_path


@pytest.fixture
def med(home, capsys):
    """A pack of the user's own, from the medicina template."""
    assert main(["pack", "create", "--template", "medicina", "--name", "med", "--lang", "pt-BR"]) == 0
    capsys.readouterr()
    return home / "packs" / "med.yaml"


def data(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def terms(path):
    return {t["term"]: t for t in data(path)["terms"]}


# ------------------------------------------------------------------ add-term


def test_add_a_term_with_its_forms_and_the_version_bumps(med, capsys):
    argv = ["pack", "add-term", "med", "metformina", "--class", "farmaco",
            "--alias", "Glifage", "--variant", "metiformina", "--variant", "met forming"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "+ term     metformina (farmaco)" in out and "+ alias    Glifage -> metformina" in out
    assert "saved" in out and "(med 0.1.1)" in out
    assert terms(med)["metformina"] == {
        "term": "metformina", "class": "farmaco",
        "aliases": ["Glifage"], "variants": ["metiformina", "met forming"],
    }
    pack = load_pack(med, learned=Learned())
    assert pack.version == "0.1.1" and pack.term_named("Glifage").term == "metformina"


def test_adding_to_an_existing_term_adds_the_forms(med, capsys):
    main(["pack", "add-term", "med", "metformina", "--class", "farmaco"])
    assert main(["pack", "add-term", "med", "Metformina", "--variant", "metiformina"]) == 0
    assert "metformina is in the pack; adding to it:" in capsys.readouterr().out
    assert terms(med)["metformina"]["variants"] == ["metiformina"]
    assert data(med)["version"] == "0.1.2"


def test_a_variant_under_three_letters_is_refused_with_the_reason(med, capsys):
    before = med.read_bytes()
    assert main(["pack", "add-term", "med", "metformina", "--class", "farmaco", "--variant", "mt"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("nothing saved: variant 'mt' refused: under 3 letters") and "(D-005)" in err
    assert med.read_bytes() == before


def test_a_variant_of_ordinary_words_is_saved_with_a_warning(med, capsys):
    assert main(["pack", "add-term", "med", "dipirona", "--class", "farmaco", "--variant", "esse amigo"]) == 0
    out = capsys.readouterr().out
    assert "warning: 'esse amigo' is made of ordinary words" in out and "(D-032)" in out
    assert terms(med)["dipirona"]["variants"] == ["esse amigo"]


def test_a_class_not_in_the_pack_is_refused(med, capsys):
    assert main(["pack", "add-term", "med", "CEMIG", "--class", "companhia"]) == 1
    assert "class 'companhia' is not one of this pack's classes" in capsys.readouterr().err


def test_a_form_of_another_term_is_refused(med, capsys):
    main(["pack", "add-term", "med", "metformina", "--class", "farmaco", "--variant", "metiformina"])
    assert main(["pack", "add-term", "med", "dipirona", "--class", "farmaco", "--variant", "metiformina"]) == 1
    assert "already a form of metformina" in capsys.readouterr().err
    assert "dipirona" not in terms(med)


def test_bundled_and_repository_packs_are_read_only(home, capsys):
    assert main(["pack", "add-term", "financas-ptbr", "X", "--class", "conceito"]) == 1
    assert "is a bundled pack, read-only; `transcript-normalizer pack copy financas-ptbr`" in capsys.readouterr().err


# ------------------------------------------------------------------ copy


def test_copy_of_the_bundled_pack_is_used_instead_and_editable(home, capsys):
    assert main(["pack", "copy", "financas-ptbr"]) == 0
    target = home / "packs" / "financas-ptbr.yaml"
    assert target.read_bytes() == BUNDLED.read_bytes() and runs.installed_packs()["financas-ptbr"] == target
    assert main(["pack", "add-term", "financas-ptbr", "emissão", "--class", "conceito", "--variant", "mississões"]) == 0
    text = target.read_text(encoding="utf-8")
    assert text.startswith(packedit.header(BUNDLED.read_text(encoding="utf-8")))  # the comments on top stay
    before, after = data(BUNDLED), data(target)
    assert after["version"] == packedit.bump(before["version"])
    assert after["terms"][:-1] == before["terms"] and after["unit_rules"] == before["unit_rules"]


def test_copy_of_a_repository_pack_stops_its_updates(home, capsys):
    (home / "packs").mkdir()
    (home / "packs" / "med-ptbr.yaml").write_text("language: pt-BR\nversion: 0.1.0\nterms: []\n", encoding="utf-8")
    import hashlib

    sha = hashlib.sha256((home / "packs" / "med-ptbr.yaml").read_bytes()).hexdigest()
    registry.write_installed({"med-ptbr": {"version": "0.1.0", "sha256": sha}})
    assert main(["pack", "copy", "med-ptbr"]) == 0
    assert "is yours now" in capsys.readouterr().out and registry.installed() == {}
    assert main(["pack", "add-term", "med-ptbr", "dipirona", "--class", "conceito"]) == 0


# ------------------------------------------------------------------ edit, remove, show


def test_edit_term_changes_forms_class_and_name(med, capsys):
    main(["pack", "add-term", "med", "metformina", "--class", "farmaco", "--variant", "metiformina"])
    assert main(["pack", "edit-term", "med", "metformina", "--add-variant", "met forming",
                 "--remove-variant", "metiformina", "--add-alias", "Glifage", "--class", "doenca"]) == 0
    assert terms(med)["metformina"] == {
        "term": "metformina", "class": "doenca", "aliases": ["Glifage"], "variants": ["met forming"],
    }
    assert main(["pack", "edit-term", "med", "metformina", "--rename", "Metformina"]) == 0
    assert list(terms(med)) == ["Metformina"] and data(med)["version"] == "0.1.3"
    assert main(["pack", "edit-term", "med", "Metformina", "--remove-alias", "nope"]) == 1
    assert "'nope' is not one of Metformina's aliases" in capsys.readouterr().err


def test_remove_term(med, capsys):
    main(["pack", "add-term", "med", "metformina", "--class", "farmaco"])
    assert main(["pack", "remove-term", "med", "metformina"]) == 0
    assert terms(med) == {}
    assert main(["pack", "remove-term", "med", "metformina"]) == 1
    assert "no term called 'metformina'" in capsys.readouterr().err


def test_show_pages_and_searches(home, capsys):
    assert main(["pack", "show", "financas-ptbr", "--page", "1"]) == 0
    out = capsys.readouterr().out.splitlines()
    total = len(data(BUNDLED)["terms"])
    assert out[0] == f"financas-ptbr: {total} terms, 1-{packedit.PAGE_SIZE}"
    assert len(out) == 1 + packedit.PAGE_SIZE and out[1].startswith("  CEMIG  (companhia)  aliases: Cemig")
    assert main(["pack", "show", "financas-ptbr", "--search", "semig"]) == 0
    found = capsys.readouterr().out.splitlines()
    assert found[0].startswith("financas-ptbr: ") and "matching 'semig'" in found[0]
    assert any(line.startswith("  CEMIG  ") for line in found[1:])


# ------------------------------------------------------------------ export


def test_export_writes_name_and_version(med, home, capsys):
    assert main(["pack", "export", "med"]) == 0
    assert (home / "med-0.1.0.yaml").read_bytes() == med.read_bytes()
    assert main(["pack", "export", "financas-ptbr", "--to", str(home / "out")]) == 0
    version = data(BUNDLED)["version"]
    assert (home / "out" / f"financas-ptbr-{version}.yaml").read_bytes() == BUNDLED.read_bytes()
    assert main(["pack", "export", "med", "--to", str(home / "x" / "mine.yaml")]) == 0
    assert (home / "x" / "mine.yaml").exists()


# ------------------------------------------------------------------ the menu


EDIT = ["6", "4"]  # Packs, Edit a pack


def test_menu_edit_offers_a_copy_of_a_bundled_pack(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, [*EDIT, "1", "n", "b", "q"])
    assert "financas-ptbr is a bundled pack, read-only." in out
    assert "Make your own copy of financas-ptbr to edit it?" in out
    assert not (home / "packs" / "financas-ptbr.yaml").exists()
    _, out, _ = menu(home, monkeypatch, capsys, [*EDIT, "1", "y", "b", "b", "q"])
    assert (home / "packs" / "financas-ptbr.yaml").exists() and "Edit financas-ptbr" in out


def test_menu_add_a_term_with_aliases_and_variants(med, home, monkeypatch, capsys):
    # Edit a pack -> med (2nd: after the bundled one) -> Add a term
    lines = [*EDIT, "2", "1", "metformina", "6", "Glifage", "", "metiformina", "mt", "", "b", "b", "q"]
    _, out, _ = menu(home, monkeypatch, capsys, lines)
    assert "Which class?" in out and "Other correct names" in out and "What the recognizer wrote instead" in out
    assert "variant 'mt' refused" in out  # all or nothing: nothing saved
    assert "metformina" not in terms(med)
    lines = [*EDIT, "2", "1", "metformina", "6", "Glifage", "", "metiformina", "", "b", "b", "q"]
    menu(home, monkeypatch, capsys, lines)
    assert terms(med)["metformina"] == {
        "term": "metformina", "class": "farmaco", "aliases": ["Glifage"], "variants": ["metiformina"],
    }


def test_menu_edit_remove_and_show_terms(med, home, monkeypatch, capsys):
    main(["pack", "add-term", "med", "metformina", "--class", "farmaco"])
    capsys.readouterr()
    # Edit a term: search "metf", pick 1, Add variants, one, end.
    lines = [*EDIT, "2", "2", "metf", "1", "2", "metiformina", "", "b", "b", "q"]
    _, out, _ = menu(home, monkeypatch, capsys, lines)
    assert "What would you like to change in metformina?" in out
    assert terms(med)["metformina"]["variants"] == ["metiformina"]
    # Show terms, then Search…
    _, out, _ = menu(home, monkeypatch, capsys, [*EDIT, "2", "4", "1", "metif", "b", "b", "b", "q"])
    assert "med: 1 terms, 1-1" in out and "med: 1 matching 'metif'" in out
    # Remove a term asks once
    _, out, _ = menu(home, monkeypatch, capsys, [*EDIT, "2", "3", "metf", "1", "y", "b", "b", "q"])
    assert "Remove metformina from med? [y/N]" in out and terms(med) == {}


def test_menu_show_terms_pages(home, monkeypatch, capsys):
    main(["pack", "copy", "financas-ptbr"])
    _, out, _ = menu(home, monkeypatch, capsys, [*EDIT, "1", "4", "1", "b", "b", "b", "q"])
    assert f"1-{packedit.PAGE_SIZE}" in out and f"{packedit.PAGE_SIZE + 1}-{2 * packedit.PAGE_SIZE}" in out


def test_menu_export(med, home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "6", "2", str(home / "out"), "b", "q"])
    assert "no folder dialog here" in out and (home / "out" / "med-0.1.0.yaml").exists()
