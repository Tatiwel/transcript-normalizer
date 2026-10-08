"""D-064, D-065: classes per pack, field templates, and the Packs menu with
its commands: pack list --installed, create, import, remove."""

import hashlib
import json
import time

import pytest
import yaml

from transcript_normalizer import load_pack, packfiles, registry, runs
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import CLASSES, COMMON_CLASSES, Learned
from transcript_normalizer.runs import BUNDLED_PACKS

from .test_interactive import menu

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"

FIELDS = {
    "financas": ["companhia", "indicador", "conceito", "ferramenta"],
    "medicina": ["doenca", "farmaco", "procedimento", "anatomia", "exame"],
    "direito": ["lei", "instituicao", "instrumento", "conceito"],
    "tecnologia": ["linguagem", "biblioteca", "protocolo", "produto", "conceito"],
    "engenharia": ["material", "componente", "norma", "processo"],
    "educacao-ciencias": ["conceito", "metodo", "grandeza"],
    "esportes": ["time", "competicao", "posicao", "regra"],
    "politica-governo": ["orgao", "cargo", "programa", "lei"],
    "agro": ["cultura", "insumo", "praga", "tecnica"],
    "geral": ["conceito", "produto", "lugar"],
}


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A data folder of its own, and an index that is not there (offline)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, (tmp_path / "offline" / "index.json").as_uri())
    return tmp_path


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


# ------------------------------------------------------------------ D-064 classes


def pack_text(classes_line, klass):
    return f"language: pt-BR\n{classes_line}terms:\n  - term: Dipirona\n    class: {klass}\n"


def test_a_declared_class_loads(tmp_path):
    path = write(tmp_path / "med.yaml", pack_text("classes: [farmaco, doenca]\n", "farmaco"))
    pack = load_pack(path, learned=Learned())
    assert pack.terms[0].klass == "farmaco"
    assert pack.classes == (*COMMON_CLASSES, "farmaco", "doenca")


def test_a_class_not_declared_is_an_error_naming_file_and_term(tmp_path):
    path = write(tmp_path / "med.yaml", pack_text("classes: [farmaco]\n", "companhia"))
    with pytest.raises(ValueError) as error:
        load_pack(path, learned=Learned())
    message = str(error.value)
    assert str(path) in message and "'Dipirona'" in message and "'companhia'" in message
    assert "add it to `classes:`" in message


@pytest.mark.parametrize("klass", COMMON_CLASSES)
def test_the_common_classes_are_always_allowed(tmp_path, klass):
    path = write(tmp_path / "med.yaml", pack_text("classes: [farmaco]\n", klass))
    assert load_pack(path, learned=Learned()).terms[0].klass == klass


def test_a_pack_without_classes_keeps_d021s_eight(tmp_path):
    path = write(tmp_path / "old.yaml", pack_text("", "companhia"))
    assert set(load_pack(path, learned=Learned()).classes) == set(CLASSES)
    with pytest.raises(ValueError, match="farmaco"):
        load_pack(write(tmp_path / "old2.yaml", pack_text("", "farmaco")), learned=Learned())


def test_classes_must_be_a_list_of_names(tmp_path):
    with pytest.raises(ValueError, match="must be a list"):
        load_pack(write(tmp_path / "bad.yaml", pack_text("classes: farmaco\n", "farmaco")), learned=Learned())


def test_financas_declares_its_eight():
    data = yaml.safe_load(BUNDLED.read_text(encoding="utf-8"))
    assert data["classes"] == list(CLASSES)


# ------------------------------------------------------------------ D-065 templates


def test_the_ten_templates_and_their_classes():
    found = packfiles.templates()
    assert list(found) == list(FIELDS)
    assert {field: list(t.classes) for field, t in found.items()} == FIELDS


@pytest.mark.parametrize("field", FIELDS)
def test_each_template_loads_and_validates(field):
    template = packfiles.templates()[field]
    data = yaml.safe_load(template.path.read_text(encoding="utf-8"))
    assert data["terms"] == [] and data["name"] == "NAME" and data["language"] == "LANG"
    assert set(template.description) == {"en", "pt-BR"}
    assert all(line and "\n" not in line for line in template.description.values())
    pack = packfiles.check(template.path)  # LANG has no module: the generic one
    assert pack.terms == () and pack.classes == (*COMMON_CLASSES, *FIELDS[field])


@pytest.mark.parametrize("field", FIELDS)
def test_create_from_each_template(home, capsys, field):
    assert main(["pack", "create", "--template", field, "--name", f"my-{field}", "--lang", "pt-BR"]) == 0
    target = home / "packs" / f"my-{field}.yaml"
    assert f"created {target}" in capsys.readouterr().out
    pack = load_pack(target, learned=Learned())  # pt-BR has a module: no --allow-generic
    assert pack.terms == () and pack.classes == (*COMMON_CLASSES, *FIELDS[field])
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert data["name"] == f"my-{field}" and data["version"] == "0.1.0" and "template" not in data
    assert runs.installed_packs()[f"my-{field}"] == target


def test_create_refuses_what_it_should(home, capsys):
    args = ["pack", "create", "--template", "medicina", "--lang", "pt-BR", "--name"]
    assert main([*args, "Medicina"]) == 1
    assert "lowercase letters, digits and hyphens" in capsys.readouterr().err
    assert main([*args, "financas-ptbr"]) == 1
    assert "bundled pack" in capsys.readouterr().err
    assert main([*args, "med"]) == 0
    assert main([*args, "med"]) == 1
    assert "already there" in capsys.readouterr().err
    assert main(["pack", "create", "--template", "astrologia", "--name", "x", "--lang", "pt-BR"]) == 1
    assert "no template called 'astrologia'" in capsys.readouterr().err


def test_create_in_a_language_with_no_module_says_so(home, capsys):
    assert main(["pack", "create", "--template", "tecnologia", "--name", "tech-de", "--lang", "de"]) == 0
    assert "no language module for de" in capsys.readouterr().out


# ------------------------------------------------------------------ import


def test_import_a_valid_file(home, capsys):
    source = write(home / "direito-ptbr.yaml", pack_text("classes: [lei]\n", "lei"))
    assert main(["pack", "import", str(source)]) == 0
    target = home / "packs" / "direito-ptbr.yaml"
    assert target.read_bytes() == source.read_bytes()
    assert f"imported direito-ptbr into {target}: 1 terms, language pt-BR" in capsys.readouterr().out
    assert main(["pack", "import", str(source)]) == 1
    assert "pass --force" in capsys.readouterr().err
    assert main(["pack", "import", str(source), "--force"]) == 0


@pytest.mark.parametrize("text,said", [
    (pack_text("classes: [lei]\n", "farmaco"), "'farmaco', which is not one of this pack's classes"),
    ("terms:\n  - term: X\n", "declares no language"),
    ("language: pt-BR\nterms: [\n", "is not YAML"),
    ("language: pt-BR\nterms:\n  - variants: [x]\n", "is not a pack"),
])
def test_import_refuses_an_invalid_file(home, capsys, text, said):
    source = write(home / "bad.yaml", text)
    assert main(["pack", "import", str(source)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("not imported: ") and said in err and "Traceback" not in err
    assert not (home / "packs" / "bad.yaml").exists()


def test_import_refuses_a_name_that_is_not_a_pack_name(home, capsys):
    source = write(home / "My Pack.yaml", pack_text("", "conceito"))
    assert main(["pack", "import", str(source)]) == 1
    assert "rename the file" in capsys.readouterr().err


# ------------------------------------------------------------------ remove


def test_remove_refuses_the_bundled_pack(home, capsys):
    assert main(["pack", "remove", "financas-ptbr"]) == 1
    assert "bundled with the program and cannot be removed" in capsys.readouterr().err
    assert BUNDLED.exists()


def test_remove_deletes_from_packs_and_keeps_the_learned_layer(home, capsys):
    main(["pack", "create", "--template", "medicina", "--name", "med", "--lang", "pt-BR"])
    learned = write(home / "packs" / "med.learned.yaml", "version: 1\n")
    capsys.readouterr()
    assert main(["pack", "remove", "med"]) == 0
    out = capsys.readouterr().out
    assert not (home / "packs" / "med.yaml").exists() and learned.exists()
    assert f"kept {learned}" in out
    assert main(["pack", "remove", "med"]) == 1
    assert "no pack called med" in capsys.readouterr().err


def test_removing_a_copy_of_the_bundled_pack_brings_the_bundled_one_back(home, capsys):
    (home / "packs").mkdir()
    (home / "packs" / "financas-ptbr.yaml").write_bytes(BUNDLED.read_bytes())
    registry.write_installed({"financas-ptbr": {"version": "0.3.6", "sha256": "x"}})
    assert main(["pack", "remove", "financas-ptbr"]) == 0
    assert "the bundled financas-ptbr is used again" in capsys.readouterr().out
    assert runs.installed_packs()["financas-ptbr"] == BUNDLED
    assert registry.installed() == {}


# ------------------------------------------------------------------ installed table


def table(out):
    return [line.split() for line in out.splitlines()]


def test_installed_table_offline(home, capsys):
    main(["pack", "create", "--template", "medicina", "--name", "med", "--lang", "pt-BR"])
    capsys.readouterr()
    assert main(["pack", "list", "--installed"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].split() == ["name", "version", "language", "terms", "size", "(KB)", "source"]
    assert lines[1].split()[:4] == ["financas-ptbr", load_pack(BUNDLED).version, "pt-BR", str(len(load_pack(BUNDLED).terms))]
    assert lines[1].split()[-1] == "bundled"
    assert lines[2].split()[:4] == ["med", "0.1.0", "pt-BR", "0"] and lines[2].split()[-1] == "mine"
    assert "update" not in lines[0] and "↑" not in out
    assert "the packs repository was not reached" in out


def test_installed_table_never_waits_more_than_the_limit(home, monkeypatch, capsys):
    def slow(url, timeout=None):
        time.sleep(5)
        return {}

    monkeypatch.setattr(registry, "read_index", slow)
    monkeypatch.setattr(packfiles, "INDEX_WAIT_SECONDS", 0.2)
    started = time.monotonic()
    assert main(["pack", "list", "--installed"]) == 0
    assert time.monotonic() - started < 2
    assert "update" not in capsys.readouterr().out.splitlines()[0]


def test_the_limit_is_three_seconds():
    assert packfiles.INDEX_WAIT_SECONDS == 3


def publish(repo, packs):
    """A packs index on disk: {name: (version, text)}."""
    entries = []
    for name, (version, text) in packs.items():
        (repo / name).mkdir(parents=True, exist_ok=True)
        path = repo / name / "pack.yaml"
        path.write_text(text, encoding="utf-8")
        entries.append({
            "name": name, "version": version, "language": "pt-BR", "description": f"{name} terms",
            "path": f"{name}/pack.yaml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (repo / "index.json").write_text(json.dumps({"version": 1, "packs": entries}), encoding="utf-8")
    return (repo / "index.json").as_uri()


def test_installed_table_with_an_index_marks_newer_versions(home, monkeypatch, capsys):
    med = pack_text("classes: [farmaco]\n", "farmaco") + "version: 0.1.0\n"
    url = publish(home / "repo", {"med-ptbr": ("0.1.0", med)})
    monkeypatch.setenv(registry.INDEX_ENV, url)
    assert main(["pack", "install", "med-ptbr"]) == 0
    main(["pack", "create", "--template", "geral", "--name", "mine", "--lang", "pt-BR"])
    publish(home / "repo", {
        "med-ptbr": ("0.2.0", med.replace("0.1.0", "0.2.0")),
        "financas-ptbr": ("9.9.9", BUNDLED.read_text(encoding="utf-8")),
        "mine": ("5.0.0", "language: pt-BR\nterms: []\n"),
    })
    capsys.readouterr()
    assert main(["pack", "list", "--installed"]) == 0
    out = capsys.readouterr().out
    lines = {line.split()[0]: line for line in out.splitlines() if line}
    assert lines["name"].split()[-1] == "update"
    assert lines["financas-ptbr"].endswith("bundled     ↑ update (9.9.9)")
    assert "repository  ↑ update (0.2.0)" in lines["med-ptbr"]
    assert lines["mine"].rstrip().endswith("mine")  # never marked: it is yours
    assert "`transcript-normalizer pack install <name>` gets it" in out


# ------------------------------------------------------------------ the menu


def test_the_menu_has_packs_and_settings_no_longer_has_the_pack(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "b", "q"])
    assert "   6. Packs                   installed, get, create, edit, share" in out
    for item in ("Installed packs", "Get a pack", "Create a pack", "Edit a pack", "Import a pack file",
                 "Export a pack file", "Remove a pack", "Contribute a pack", "The pack offered first",
                 "b. <- Back"):
        assert item in out.split("* Packs")[1]


def test_menu_installed_packs_is_the_command(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "1", "b", "q"])
    assert "name           version  language  terms  size (KB)  source" in out


def test_menu_create_a_pack_and_offer_it_first(home, monkeypatch, capsys):
    lines = ["6", "3", "2", "medicina-ptbr", "pt-BR", "y", "b", "q"]
    _, out, _ = menu(home, monkeypatch, capsys, lines)
    assert "   2. medicina            Medicine: diseases, drugs, procedures, anatomy, exams." in out
    assert (home / "packs" / "medicina-ptbr.yaml").exists()
    assert runs.read_config() == {"pack": "medicina-ptbr"}
    assert "The pack offered first   medicina-ptbr" in out


def test_menu_create_with_a_bad_name_writes_nothing(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "3", "1", "Not A Name", "pt-BR", "b", "q"])
    assert "lowercase letters, digits and hyphens" in out
    assert not (home / "packs").exists() and runs.read_config() == {}


def test_menu_import_with_a_typed_path(home, monkeypatch, capsys):
    source = write(home / "agro-ptbr.yaml", pack_text("classes: [praga]\n", "praga"))
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "5", str(source), "b", "q"])
    assert "no file dialog here; type the path instead" in out
    assert (home / "packs" / "agro-ptbr.yaml").exists()


def test_menu_import_uses_the_file_dialog_on_yaml(home, monkeypatch, capsys):
    from .test_interactive import fake_tkinter

    source = write(home / "agro-ptbr.yaml", pack_text("classes: [praga]\n", "praga"))
    tk = fake_tkinter(monkeypatch, str(source))
    menu(home, monkeypatch, capsys, ["6", "5", "b", "q"])
    (_, asked), = [c for c in tk.calls if isinstance(c, tuple)]
    assert asked["filetypes"][0] == ("Pack files", "*.yaml")
    assert (home / "packs" / "agro-ptbr.yaml").exists()


def test_menu_remove_asks_twice_and_shows_the_path(home, monkeypatch, capsys):
    main(["pack", "create", "--template", "agro", "--name", "agro-ptbr", "--lang", "pt-BR"])
    target = home / "packs" / "agro-ptbr.yaml"
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "7", "2", "y", "n", "b", "q"])
    assert f"file: {target}" in out and "Remove agro-ptbr?" in out and "Really remove it?" in out
    assert target.exists()  # the second answer was no
    menu(home, monkeypatch, capsys, ["6", "7", "2", "y", "y", "b", "q"])
    assert not target.exists()


def test_menu_remove_refuses_the_bundled_pack_without_asking(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "7", "1", "b", "q"])
    assert "bundled with the program and cannot be removed" in out
    assert "Remove financas-ptbr?" not in out


def test_menu_get_a_pack_offline_says_so(home, monkeypatch, capsys):
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "2", "b", "q"])
    assert "the packs repository could not be reached" in out


def test_menu_get_a_pack_installs_the_pick(home, monkeypatch, capsys):
    med = pack_text("classes: [farmaco]\n", "farmaco")
    monkeypatch.setenv(registry.INDEX_ENV, publish(home / "repo", {"med-ptbr": ("0.1.0", med)}))
    _, out, _ = menu(home, monkeypatch, capsys, ["6", "2", "1", "b", "q"])
    assert "med-ptbr   0.1.0 · med-ptbr terms" in out
    assert (home / "packs" / "med-ptbr.yaml").exists()
