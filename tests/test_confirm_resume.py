"""D-037: the confirmation loop saves as it goes, and survives Ctrl+C."""

import shutil

import pytest

from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned, load_learned, save_learned
from transcript_normalizer.runs import learned_file

from .conftest import CAPTION, PACK, medium_order


def answering(monkeypatch, answers, asked):
    """`input()` that gives `answers` in turn, then raises KeyboardInterrupt."""
    pending = list(answers)

    def fake_input(prompt=""):
        asked.append(prompt)
        if not pending:
            raise KeyboardInterrupt
        return pending.pop(0)

    monkeypatch.setattr("builtins.input", fake_input)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    return caption


def confirm(caption):
    return main([str(caption), "--pack", str(PACK), "--confirm"])


def test_an_interrupted_session_keeps_the_answers_it_was_given(workspace, monkeypatch, capsys):
    (t1, v1), (t2, v2) = medium_order()[:2]
    asked: list[str] = []
    answering(monkeypatch, ["y", "n"], asked)

    assert confirm(workspace) == 130
    assert len(asked) == 3  # two answered, the third interrupted

    learned = load_learned(learned_file(PACK))
    confirmed = [(t, c.variant) for t, cs in learned.confirmed.items() for c in cs]
    rejected = [(r.term, r.text) for r in learned.rejected]
    assert (confirmed, rejected) == ([(t1, v1)], [(t2, v2)])

    out = capsys.readouterr().out
    assert "interrupted: 2 answer(s) kept in" in out
    assert "learned layer written to" not in out  # that line is for a finished session


def test_a_rerun_only_asks_what_is_still_pending(workspace, monkeypatch):
    first, second = medium_order()[:2]
    answering(monkeypatch, ["y", "n"], [])
    confirm(workspace)

    asked: list[str] = []
    answering(monkeypatch, [], asked)  # interrupt at once: just see the first question
    confirm(workspace)
    assert len(asked) == 1
    for term, variant in (first, second):
        assert f"{variant} -> {term}?" not in asked[0]
    third_term, third_variant = medium_order()[2]
    assert f"{third_variant} -> {third_term}?" in asked[0]


def test_a_finished_session_still_says_where_it_wrote(workspace, monkeypatch, capsys):
    answering(monkeypatch, ["a"] * len({t for t, _ in medium_order()}), [])
    assert confirm(workspace) == 0
    assert "learned layer written to" in capsys.readouterr().out


def test_pending_after_an_interrupt_tells_asked_from_never_asked(workspace, monkeypatch):
    answering(monkeypatch, ["s"], [])  # skip the first, then Ctrl+C
    confirm(workspace)
    pending = (workspace.parent / "runs" / "R2Qgz8tFWVI" / "needs-review" / "pending.txt").read_text(
        encoding="utf-8"
    )
    first, second = medium_order()[:2]
    assert f"  {first[1]}  (" in pending and "[skipped]" in pending
    assert "[never asked]" in pending


def test_the_learned_file_is_written_atomically(tmp_path):
    path = tmp_path / "packs" / "x.learned.yaml"
    save_learned(Learned().confirm("CEMIG", "SEMIG"), path)
    save_learned(Learned().confirm("CEMIG", "SEMIC"), path)
    assert [p.name for p in path.parent.iterdir()] == ["x.learned.yaml"]  # no temp file left
    assert [c.variant for c in load_learned(path).confirmed["CEMIG"]] == ["SEMIC"]


def test_a_failed_write_leaves_the_old_file_whole(tmp_path, monkeypatch):
    path = tmp_path / "x.learned.yaml"
    save_learned(Learned().confirm("CEMIG", "SEMIG"), path)
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", fail)
    with pytest.raises(OSError):
        save_learned(Learned().confirm("CEMIG", "SEMIC"), path)
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["x.learned.yaml"]
