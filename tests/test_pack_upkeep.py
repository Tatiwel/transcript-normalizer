"""D-095: an edited pack keeps its generated part; D-096: `pack import` takes
the pack's name, not the export's file name; D-097: the menu updates an
installed pack that was not edited."""

import hashlib
import json

import pytest
import yaml

from transcript_normalizer import packedit, registry
from transcript_normalizer.cli import main
from transcript_normalizer.runs import BUNDLED_PACKS

from .test_interactive import menu

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, (tmp_path / "offline" / "index.json").as_uri())
    return tmp_path


GENERATED_PACK = """\
# A pack with a generated part.
language: pt-BR
version: 0.1.0
classes: [companhia, conceito]
terms:
  - term: dividendo
    class: conceito
    variants: [dividendu]
  # >>> início da parte gerada
  # gerado por tools/gerar.py; não editar à mão
  - term: Alfa
    class: companhia
    match: exact
    aliases: [ALFA3]
  - term: Beta
    class: companhia
    match: exact
    aliases: [BETA3]
  # <<< fim da parte gerada
"""


@pytest.fixture
def gen(home):
    (home / "packs").mkdir()
    path = home / "packs" / "gen.yaml"
    path.write_text(GENERATED_PACK, encoding="utf-8")
    return path


def names(path):
    return [t["term"] for t in yaml.safe_load(path.read_text(encoding="utf-8"))["terms"]]


# ------------------------------------------------------------------ D-095


def test_the_generated_part_is_read_with_its_markers():
    block = packedit.generated_block(GENERATED_PACK)
    assert block.names == ("Alfa", "Beta")
    assert block.opening == ("  # >>> início da parte gerada\n", "  # gerado por tools/gerar.py; não editar à mão\n")
    assert block.closing == "  # <<< fim da parte gerada\n"
    assert packedit.generated_block("terms: []\n") is None
    assert packedit.generated_block("  # >>> opened, never closed\n") is None


def test_a_term_added_by_hand_goes_before_the_generated_part(gen, capsys):
    assert main(["pack", "add-term", "gen", "payout", "--class", "conceito"]) == 0
    text = gen.read_text(encoding="utf-8")
    assert names(gen) == ["dividendo", "payout", "Alfa", "Beta"]
    assert packedit.generated_block(text) == packedit.generated_block(GENERATED_PACK)
    assert text.index("- term: payout") < text.index("# >>> início") < text.index("- term: Alfa")
    assert text.index("- term: Beta") < text.index("# <<< fim")


def test_editing_or_removing_a_generated_term_keeps_the_markers(gen, capsys):
    assert main(["pack", "edit-term", "gen", "Beta", "--add-variant", "beita"]) == 0
    block = packedit.generated_block(gen.read_text(encoding="utf-8"))
    assert block.names == ("Alfa", "Beta")
    assert main(["pack", "remove-term", "gen", "Alfa"]) == 0
    assert packedit.generated_block(gen.read_text(encoding="utf-8")).names == ("Beta",)


def test_a_generated_term_renamed_by_hand_leaves_the_generated_part(gen, capsys):
    assert main(["pack", "edit-term", "gen", "Alfa", "--rename", "Alfa Holding"]) == 0
    assert names(gen) == ["dividendo", "Alfa Holding", "Beta"]
    assert packedit.generated_block(gen.read_text(encoding="utf-8")).names == ("Beta",)


def test_a_pack_without_a_generated_part_is_written_as_before(home):
    data = {"language": "pt-BR", "version": "0.1.0", "terms": [{"term": "a"}]}
    assert packedit.dump("", dict(data)) == packedit.dump("", dict(data), None)
    assert "# >>>" not in packedit.dump("", dict(data))


def test_the_export_of_an_edited_pack_keeps_the_markers(gen, home, capsys):
    assert main(["pack", "add-term", "gen", "payout", "--class", "conceito"]) == 0
    assert main(["pack", "export", "gen", "--to", str(home / "out")]) == 0
    exported = (home / "out" / "gen-0.1.1.yaml").read_text(encoding="utf-8")
    assert packedit.generated_block(exported).names == ("Alfa", "Beta")


# ------------------------------------------------------------------ D-096


def write_pack(path, version="0.1.3"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"language: pt-BR\nversion: {version}\nterms:\n  - term: dipirona\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("relative, version, name", [
    ("out/med-ptbr-0.1.3.yaml", "0.1.3", "med-ptbr"),  # as pack export names it
    ("repo/med-ptbr/pack.yaml", "0.1.3", "med-ptbr"),  # the packs repository's layout
    ("repo/med-ptbr/0.1.2/pack.yaml", "0.1.2", "med-ptbr"),  # an old version kept there
    ("out/med-ptbr.yaml", "0.1.3", "med-ptbr"),  # as before
    ("out/med-ptbr-2.yaml", "0.1.3", "med-ptbr-2"),  # a number that is not the version stays
])
def test_import_takes_the_pack_s_name(home, capsys, relative, version, name):
    source = write_pack(home / relative, version)
    assert main(["pack", "import", str(source)]) == 0
    assert (home / "packs" / f"{name}.yaml").read_bytes() == source.read_bytes()
    assert sorted(p.name for p in (home / "packs").glob("*.yaml")) == [f"{name}.yaml"]


def test_import_says_where_the_name_came_from_and_name_overrides_it(home, capsys):
    source = write_pack(home / "out" / "med-ptbr-0.1.3.yaml")
    assert main(["pack", "import", str(source)]) == 0
    assert "the name med-ptbr comes from med-ptbr-0.1.3.yaml" in capsys.readouterr().out
    assert main(["pack", "import", str(source), "--name", "outro-ptbr"]) == 0
    assert (home / "packs" / "outro-ptbr.yaml").exists()


def test_an_exported_pack_imports_back_over_itself_only_with_force(home, capsys):
    write_pack(home / "packs" / "med-ptbr.yaml")
    assert main(["pack", "export", "med-ptbr", "--to", str(home / "out")]) == 0
    exported = home / "out" / "med-ptbr-0.1.3.yaml"
    assert main(["pack", "import", str(exported)]) == 1
    assert "already there; pass --force" in capsys.readouterr().err
    assert main(["pack", "import", str(exported), "--force"]) == 0


# ------------------------------------------------------------------ D-097


@pytest.fixture
def older(home):
    """financas-ptbr installed as it was at an older version: the included one is newer."""
    text = BUNDLED.read_text(encoding="utf-8")
    current = yaml.safe_load(text)["version"]
    text = text.replace(f"\nversion: {current}\n", "\nversion: 0.0.1\n", 1)
    (home / "packs").mkdir()
    path = home / "packs" / "financas-ptbr.yaml"
    path.write_text(text, encoding="utf-8")
    registry.write_installed({"financas-ptbr": {"version": "0.0.1",
                                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}})
    return current


def test_the_menu_says_a_newer_included_version_is_there_and_installs_it(home, monkeypatch, capsys, older):
    # Packs, then its last option, Update packs.
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "10", "b", "q"])
    notice = f"financas-ptbr {older} is included in this version (installed: 0.0.1). Packs → Update packs installs it."
    assert out.split("What would you like to do?")[0].count(notice) == 1  # on the first screen
    assert f"10. Update packs" in out and f"financas-ptbr 0.0.1 → {older} (included)\n" in out
    assert f"financas-ptbr: 0.0.1 → {older} (included in the program)" in out
    record = json.loads((home / "packs" / "installed.json").read_text(encoding="utf-8"))
    assert record["financas-ptbr"]["version"] == older
    assert (home / "packs" / "financas-ptbr.yaml").read_bytes() == BUNDLED.read_bytes()


def test_an_edited_pack_is_not_offered_an_update(home, monkeypatch, capsys, older):
    path = home / "packs" / "financas-ptbr.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")  # edited here
    _, out, _ = menu(home, monkeypatch, capsys, ["q"])
    assert "is included in this version" not in out


def test_no_update_option_without_an_installed_pack(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "b", "q"])
    assert "Update packs" not in out


def test_a_generated_term_written_with_another_key_first_stays_inside(gen, capsys):
    text = gen.read_text(encoding="utf-8").replace(
        "  - term: Beta\n    class: companhia\n", "  - class: companhia\n    term: Beta\n")
    gen.write_text(text, encoding="utf-8")
    assert packedit.generated_block(text).names == ("Alfa", "Beta")
    assert main(["pack", "add-term", "gen", "payout", "--class", "conceito"]) == 0
    assert names(gen) == ["dividendo", "payout", "Alfa", "Beta"]
    assert packedit.generated_block(gen.read_text(encoding="utf-8")).names == ("Alfa", "Beta")


def test_import_of_pack_yaml_from_inside_its_folder(home, monkeypatch, capsys):
    folder = home / "repo" / "med-ptbr"
    write_pack(folder / "pack.yaml")
    monkeypatch.chdir(folder)
    monkeypatch.setenv("TRANSCRIPT_NORMALIZER_HOME", str(home))
    assert main(["pack", "import", "pack.yaml"]) == 0
    assert (home / "packs" / "med-ptbr.yaml").exists()


def test_the_only_generated_term_written_class_first_stays_inside(home, capsys):
    (home / "packs").mkdir()
    path = home / "packs" / "gen.yaml"
    path.write_text(GENERATED_PACK.replace(
        "  - term: Alfa\n    class: companhia\n    match: exact\n    aliases: [ALFA3]\n", "").replace(
        "  - term: Beta\n    class: companhia\n", "  - class: companhia\n    term: Beta\n"), encoding="utf-8")
    assert main(["pack", "add-term", "gen", "payout", "--class", "conceito"]) == 0
    text = path.read_text(encoding="utf-8")
    assert packedit.generated_block(text).names == ("Beta",)
    assert text.index("- term: payout") < text.index("# >>> início") < text.index("term: Beta") < text.index("# <<< fim")
