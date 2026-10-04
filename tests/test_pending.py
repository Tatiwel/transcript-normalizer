"""D-023: needs-review/pending.txt lists what is still unanswered, and why."""

import io
import shutil

from transcript_normalizer.cli import NEVER_ASKED, SKIPPED, main
from transcript_normalizer.runs import PENDING_FILE, needs_review_dir

from .conftest import CAPTION, PACK, medium_order, output_dir

# The fixture's medium band, in the order the loop asks it (derived).
MEDIUM = medium_order()


def run(tmp_path, monkeypatch, *extra, answers=None):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    if answers is not None:
        monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{a}\n" for a in answers)))
    assert main([str(caption), "--pack", str(PACK), *extra]) == 0
    return needs_review_dir(output_dir(caption)) / PENDING_FILE


def tagged(text):
    """{variant: tag} for every variant line in pending.txt."""
    out = {}
    for line in text.splitlines():
        for tag in (NEVER_ASKED, SKIPPED):
            if line.startswith("  ") and not line.startswith("    ") and line.endswith(tag):
                out[line.strip().split("  (")[0]] = tag
    return out


def test_without_confirm_everything_is_never_asked(tmp_path, monkeypatch):
    text = run(tmp_path, monkeypatch).read_text(encoding="utf-8")
    assert tagged(text) == {variant: NEVER_ASKED for _, variant in MEDIUM}
    # Grouped by term, each variant with its own examples (D-019).
    assert text.count("CEMIG  (2 occurrences)") == 1
    assert "  e caiu  (1 occurrence)  [never asked]" in text
    assert "    0:37  Neste mês caiu 7% e desde o início do" in text
    # A list of what is left, not a set of questions.
    assert "[y]es" not in text


def test_answered_variants_leave_and_skipped_ones_say_so(tmp_path, monkeypatch):
    # yes, no on the first two variants, skip on the third; end of input skips the rest.
    path = run(tmp_path, monkeypatch, "--confirm", answers=["y", "n", "s"])
    left = tagged(path.read_text(encoding="utf-8"))

    assert MEDIUM[0][1] not in left and MEDIUM[1][1] not in left
    assert left == {variant: SKIPPED for _, variant in MEDIUM[2:]}


def test_an_alias_answer_is_an_answer(tmp_path, monkeypatch):
    path = run(tmp_path, monkeypatch, "--confirm", answers=["l"])
    assert MEDIUM[0][1] not in tagged(path.read_text(encoding="utf-8"))


def test_nothing_pending_leaves_no_file_behind(tmp_path, monkeypatch):
    # The first run leaves a pending.txt; answering everything removes it.
    path = run(tmp_path, monkeypatch)
    assert path.exists()
    groups = len(dict.fromkeys(term for term, _ in MEDIUM))
    run(tmp_path, monkeypatch, "--confirm", answers=["a"] * groups)  # all-yes, every term
    assert not path.exists()
    assert not path.parent.exists()
