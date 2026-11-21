"""D-100: learned entries for a term the pack no longer has are said, not
skipped in silence, and stay in the learned file."""

import shutil

from transcript_normalizer import load_pack
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import load_learned

from .conftest import CAPTION, PACK

ORPHANED = (
    "version: 1\n"
    "confirmed:\n"
    "  CEMIG:\n"
    "    - variant: semiga\n"
    "      date: '2026-09-20'\n"
    "  Termo Que Saiu:\n"
    "    - variant: termo que saio\n"
    "      date: '2026-09-20'\n"
    "    - variant: termu que saiu\n"
    "      date: '2026-09-21'\n"
    "aliases:\n"
    "  Termo Que Saiu:\n"
    "    - alias: TQS\n"
    "      date: '2026-09-22'\n"
    "rejected: []\n"
)


def test_the_pack_counts_the_entries_of_a_term_it_no_longer_has(tmp_path):
    learned = tmp_path / "pack.learned.yaml"
    learned.write_text(ORPHANED, encoding="utf-8")
    pack = load_pack(PACK, learned_from=learned)
    assert pack.orphaned_learned == (("Termo Que Saiu", 3),)
    assert load_pack(PACK, learned_from=tmp_path / "none.yaml").orphaned_learned == ()


def test_normalize_says_so_and_keeps_them_in_the_file(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    learned = tmp_path / "pack.learned.yaml"
    learned.write_text(ORPHANED, encoding="utf-8")
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert main(["normalize", str(caption), "--pack", str(PACK), "--learned", str(learned),
                 "--out", str(tmp_path / "out"), "--force"]) == 0
    err = capsys.readouterr().err
    assert f"{learned} has 3 learned entries for 1 term(s) this pack no longer has" in err
    assert "  Termo Que Saiu: 3" in err
    assert "`pack copy`, then `pack add-term`" in err
    assert learned.read_text(encoding="utf-8") == ORPHANED
    kept = load_learned(learned)
    assert len(kept.confirmed["Termo Que Saiu"]) == 2 and len(kept.aliases["Termo Que Saiu"]) == 1


def test_nothing_is_said_when_every_entry_has_its_term(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    learned = tmp_path / "pack.learned.yaml"
    learned.write_text(ORPHANED.split("  Termo Que Saiu:")[0] + "rejected: []\n", encoding="utf-8")
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert main(["normalize", str(caption), "--pack", str(PACK), "--learned", str(learned),
                 "--out", str(tmp_path / "out"), "--force"]) == 0
    assert "no longer has" not in capsys.readouterr().err
