"""D-023: needs-review/pending.txt lists what is still unanswered, and why."""

import io
import shutil

from transcript_normalizer.cli import NEVER_ASKED, SKIPPED, main
from transcript_normalizer.runs import PENDING_FILE, needs_review_dir

from .conftest import CAPTION, PACK, output_dir

# The fixture's medium band, in the order the loop asks: 8 variants, 4 terms.
# (D-024 took `preço. Então` out of it; D-030 let the plural `dividendos` in,
# which made dividendo the busiest term.)
MEDIUM = [
    ("dividendo", "dividendos"), ("dividendo", "dividido"),
    ("CEMIG", "dos 10"), ("CEMIG", "e caiu"), ("CEMIG", "mês caiu"), ("CEMIG", "nesse ramo"),
    ("EBITDA", "de eBit"),
    ("preço teto", "preço dela"),
]


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
    assert text.count("CEMIG  (5 occurrences)") == 1
    assert "  dos 10  (2 occurrences)  [never asked]" in text
    assert "    0:37  Neste mês caiu 7% e desde o início do" in text
    # A list of what is left, not a set of questions.
    assert "[y]es" not in text


def test_answered_variants_leave_and_skipped_ones_say_so(tmp_path, monkeypatch):
    # yes, no on dividendo's two, skip on the next; end of input skips the rest.
    path = run(tmp_path, monkeypatch, "--confirm", answers=["y", "n", "s"])
    left = tagged(path.read_text(encoding="utf-8"))

    assert "dividendos" not in left and "dividido" not in left
    assert left == {variant: SKIPPED for _, variant in MEDIUM[2:]}


def test_an_alias_answer_is_an_answer(tmp_path, monkeypatch):
    path = run(tmp_path, monkeypatch, "--confirm", answers=["l"])
    assert "dividendos" not in tagged(path.read_text(encoding="utf-8"))


def test_nothing_pending_leaves_no_file_behind(tmp_path, monkeypatch):
    # The first run leaves a pending.txt; answering everything removes it.
    path = run(tmp_path, monkeypatch)
    assert path.exists()
    run(tmp_path, monkeypatch, "--confirm", answers=["a", "a", "y", "y"])
    assert not path.exists()
    assert not path.parent.exists()
