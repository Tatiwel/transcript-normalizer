"""D-086: writing a context, in a pack file, from the command line, from the
menu and from the review; and what a pack may not say."""

import pytest
import yaml

from transcript_normalizer import load_pack, review
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned

from .test_packedit import EDIT, data, home, med, terms  # noqa: F401  (fixtures)
from .test_interactive import menu
from .test_review_stops import LOCAL, layer, reviewed

BASE = """\
language: pt-BR
version: test
classes: [indicador, conceito]
terms:
  - term: OPEX
    class: indicador
    variants: [Ox]
{extra}
  - term: CAPEX
    class: indicador
  - term: tipo
    class: conceito
"""


def pack_with(tmp_path, extra):
    path = tmp_path / "p.yaml"
    path.write_text(BASE.format(extra=extra), encoding="utf-8")
    return path


# ------------------------------------------------------------------ the pack file


def test_a_context_entry_must_be_a_term_of_the_pack(tmp_path):
    path = pack_with(tmp_path, "    context: {Ox: [CAPEZ]}")
    with pytest.raises(ValueError) as error:
        load_pack(path, learned=Learned())
    message = str(error.value)
    assert str(path) in message and "'OPEX'" in message and "'CAPEZ'" in message
    assert "is not a term of this pack" in message


def test_an_unless_near_entry_too(tmp_path):
    path = pack_with(tmp_path, "    context: {Ox: [CAPEX]}\n    unless_near: {Ox: [Capex]}")
    with pytest.raises(ValueError, match="'Capex' is not a term of this pack"):
        load_pack(path, learned=Learned())


def test_a_context_entry_must_not_be_an_ordinary_word(tmp_path):
    path = pack_with(tmp_path, "    context: {Ox: [tipo]}")
    with pytest.raises(ValueError, match="context must be a specific term, not an ordinary word"):
        load_pack(path, learned=Learned())


def test_a_context_names_a_form_of_its_own_term(tmp_path):
    path = pack_with(tmp_path, "    context: {Oxe: [CAPEX]}")
    with pytest.raises(ValueError, match="'Oxe', which is not its name or one of its variants"):
        load_pack(path, learned=Learned())


def test_a_valid_context_loads(tmp_path):
    pack = load_pack(pack_with(tmp_path, "    context: {Ox: [CAPEX]}"), learned=Learned())
    ox = next(c for c in pack.candidates if c.folded == "ox")
    assert ox.context == ("CAPEX",) and ox.unless_near == ()


# ------------------------------------------------------------------ the command line


@pytest.fixture
def fin(home, capsys):  # noqa: F811
    """A pack of the user's own, with two indicators and an ordinary word."""
    assert main(["pack", "create", "--template", "financas", "--name", "fin", "--lang", "pt-BR"]) == 0
    for argv in (["CAPEX", "--class", "indicador"], ["OPEX", "--class", "indicador"],
                 ["pecuária", "--class", "conceito"], ["tipo", "--class", "conceito"]):
        assert main(["pack", "add-term", "fin", *argv]) == 0
    capsys.readouterr()
    return home / "packs" / "fin.yaml"


def test_add_term_with_context_and_unless_near(fin, capsys):
    argv = ["pack", "add-term", "fin", "OPEX", "--variant", "Ox",
            "--context", "capex", "--unless-near", "pecuária"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert "context  Ox: only with CAPEX; asked near pecuária" in out
    opex = terms(fin)["OPEX"]
    assert opex["variants"] == ["Ox"]
    assert opex["context"] == {"Ox": ["CAPEX"]} and opex["unless_near"] == {"Ox": ["pecuária"]}
    load_pack(fin, learned=Learned())


def test_add_term_context_without_a_variant_is_for_the_name(fin):
    assert main(["pack", "add-term", "fin", "Vale", "--class", "companhia", "--context", "CAPEX"]) == 0
    assert terms(fin)["Vale"]["context"] == {"Vale": ["CAPEX"]}


def test_add_term_refuses_an_unknown_context_term(fin, capsys):
    assert main(["pack", "add-term", "fin", "OPEX", "--variant", "Ox", "--context", "EBITDAX"]) == 1
    assert "'EBITDAX' is not a term of fin" in capsys.readouterr().err
    assert "variants" not in terms(fin)["OPEX"]


def test_add_term_refuses_an_ordinary_word_as_context(fin, capsys):
    assert main(["pack", "add-term", "fin", "OPEX", "--variant", "Ox", "--context", "tipo"]) == 1
    assert "context must be a specific term, not an ordinary word" in capsys.readouterr().err


def test_unless_near_needs_a_context(fin, capsys):
    assert main(["pack", "add-term", "fin", "OPEX", "--variant", "Opeques", "--unless-near", "CAPEX"]) == 1
    assert "--unless-near goes with --context" in capsys.readouterr().err


def test_a_short_variant_needs_a_context(fin, capsys):
    """D-005 refuses `Ox` on its own; D-086 lets a context answer for it."""
    assert main(["pack", "add-term", "fin", "OPEX", "--variant", "Ox"]) == 1
    assert "under 3 letters" in capsys.readouterr().err
    assert main(["pack", "add-term", "fin", "OPEX", "--variant", "Ox", "--context", "CAPEX"]) == 0


# ------------------------------------------------------------------ the menu


def test_menu_add_a_term_asks_whether_a_variant_is_an_ordinary_word(med, home, monkeypatch, capsys):  # noqa: F811
    assert main(["pack", "add-term", "med", "insulina", "--class", "farmaco"]) == 0
    # Edit a pack -> med -> Add a term: metformina, farmaco, no alias, one variant;
    # then the context question: `a`, insulina.
    lines = [*EDIT, "2", "1", "metformina", "6", "", "metiformina", "", "a", "b", "b", "q"]
    _, out, _ = menu(home, monkeypatch, capsys, lines)
    assert ("Is 'metiformina' also an ordinary word? If so, pick the pack terms that appear in a video "
            "when it means metformina") in out
    assert terms(med)["metformina"]["context"] == {"metiformina": ["insulina"]}


def test_menu_enter_skips_the_context(med, home, monkeypatch, capsys):  # noqa: F811
    assert main(["pack", "add-term", "med", "insulina", "--class", "farmaco"]) == 0
    lines = [*EDIT, "2", "1", "metformina", "6", "", "metiformina", "", "", "b", "b", "q"]
    menu(home, monkeypatch, capsys, lines)
    assert terms(med)["metformina"] == {"term": "metformina", "class": "farmaco", "variants": ["metiformina"]}


# ------------------------------------------------------------------ the review


def test_only_in_this_video_can_be_saved_with_a_context(tmp_path, monkeypatch, capsys):
    # Klabine: only in this video, then `a`, the first of the run's terms; the rest later.
    reviewed(tmp_path, monkeypatch, [LOCAL, "a", "", "", "y"])
    out = capsys.readouterr().out
    assert "Save it for every video, but only when one of these terms appears?" in out
    offered = out.split("Save it for every video")[1].split("\n")[1:]
    first = next(line.split("[ ] ")[1].strip() for line in offered if "[ ] " in line)
    assert f"will remember: Klabine → Klabin (only with {first})" in out
    confirmed = layer(tmp_path).confirmed["Klabin"]
    assert [(c.variant, c.context) for c in confirmed] == [("Klabine", (first,))]
    assert not review.local_path(tmp_path / "runs" / "review").exists()
    saved = yaml.safe_load((tmp_path / "packs" / "financas-ptbr.learned.yaml").read_text(encoding="utf-8"))
    assert saved["confirmed"]["Klabin"][0]["context"] == [first]


def test_enter_keeps_it_for_this_video_only(tmp_path, monkeypatch, capsys):
    reviewed(tmp_path, monkeypatch, [LOCAL, "", "", "", "y"])
    assert layer(tmp_path).is_empty()
    assert review.read_local(tmp_path / "runs" / "review") == [("Klabin", "Klabine")]


def test_a_variant_learned_with_a_context_is_proposed_with_it(tmp_path):
    from transcript_normalizer import contribute

    path = pack_with(tmp_path, "")
    learned = Learned().confirm("OPEX", "Oxe", "2026-10-17", context=("CAPEX",))
    found = contribute.items(path, learned)
    assert [i.line() for i in found] == ["  + variant   Oxe -> OPEX  (only with CAPEX)"]
    text = contribute.contribution_yaml("p", "test", found, "2026-10-17")
    assert yaml.safe_load(text)["entries"][0]["context"] == ["CAPEX"]
