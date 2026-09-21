"""D-013: confirmations and rejections live beside the pack, never inside it."""

import hashlib
import io
import shutil

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, read_caption
from transcript_normalizer.cli import main
from transcript_normalizer.pack import learned_path, load_learned

from .conftest import CAPTION, PACK


def pack_copy(tmp_path, drop_variants=()):
    """A working copy of the fixture pack, so nothing under fixtures/ is touched."""
    data = yaml.safe_load(PACK.read_text(encoding="utf-8"))
    if drop_variants:
        for term in data["terms"]:
            term["variants"] = [
                v for v in term.get("variants", []) if v not in drop_variants
            ]
    path = tmp_path / "pack.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), "utf-8")
    return path


def at(transcript, annotations, timestamp, original):
    return [
        a
        for a in annotations
        if a.original == original
        and timestamp in {l.timestamp for l in transcript.spans(a.start, a.end)}
    ]


def test_confirmed_variant_is_matched_as_a_high_band_variant(tmp_path, transcript):
    path = pack_copy(tmp_path, drop_variants=("semiga",))

    # Without the learned layer, 21:34 is only a fuzzy guess.
    before = at(transcript, find_annotations(transcript, load_pack(path)), "21:34", "semiga")
    assert [(a.rule, a.band) for a in before] == [("term:fuzzy", "medium")]

    learned_path(path).write_text(
        "version: 1\n"
        "confirmed:\n"
        "  CEMIG:\n"
        "    - variant: semiga\n"
        "      date: '2026-09-20'\n"
        "rejected: []\n",
        "utf-8",
    )
    pack = load_pack(path)
    assert "semiga" in pack.terms[0].learned_variants

    after = at(transcript, find_annotations(transcript, pack), "21:34", "semiga")
    assert len(after) == 1
    assert after[0].term == "CEMIG"
    assert after[0].rule == "term:variant"
    assert after[0].band == "high"
    assert after[0].score == 100


def test_a_rejected_pair_is_never_proposed_again(tmp_path, transcript):
    path = pack_copy(tmp_path)

    before = at(transcript, find_annotations(transcript, load_pack(path)), "19:36", "preço dela")
    assert [(a.term, a.band) for a in before] == [("preço teto", "medium")]

    learned_path(path).write_text(
        "version: 1\n"
        "confirmed: {}\n"
        "rejected:\n"
        "  - text: preço dela\n"
        "    term: preço teto\n"
        "    date: '2026-09-20'\n",
        "utf-8",
    )
    pack = load_pack(path)
    assert pack.is_rejected("preco dela", "preço teto")

    after = find_annotations(transcript, pack)
    assert not at(transcript, after, "19:36", "preço dela")
    assert not [a for a in after if a.original == "preço dela"]


def test_confirm_run_writes_the_learned_file_and_never_the_pack(
    tmp_path, monkeypatch, capsys
):
    path = pack_copy(tmp_path)
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    # One `y`, one `n`, then end of input, which the loop treats as skip.
    monkeypatch.setattr("sys.stdin", io.StringIO("y\nn\n"))
    assert main([str(caption), "--pack", str(path), "--confirm"]) == 0

    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before

    learned = load_learned(learned_path(path))
    assert learned.confirmed, "the `y` answer should have confirmed a term"
    assert learned.rejected, "the `n` answer should have recorded a rejection"
    for confirmations in learned.confirmed.values():
        assert all(c.decided for c in confirmations)
    assert all(r.decided for r in learned.rejected)

    out = capsys.readouterr().out
    assert "to confirm:" in out
    assert str(learned_path(path)) in out


def test_a_second_run_honours_what_the_first_one_learned(tmp_path, monkeypatch):
    path = pack_copy(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    main([str(caption), "--pack", str(path), "--confirm"])

    rejected = load_learned(learned_path(path)).rejected
    assert rejected
    transcript = read_caption(caption)
    annotations = find_annotations(transcript, load_pack(path))
    for r in rejected:
        assert not [
            a for a in annotations if a.term == r.term and " ".join(a.original.split()) == r.text
        ]
