"""D-013: confirmations and rejections live beside the pack, never inside it."""

import hashlib
import io
import shutil

import yaml

from transcript_normalizer import find_annotations, load_pack, read_caption
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.runs import learned_file

from .conftest import CAPTION, PACK

CONFIRMED_SEMIGA = (
    "version: 1\n"
    "confirmed:\n"
    "  CEMIG:\n"
    "    - variant: semiga\n"
    "      date: '2026-09-20'\n"
    "rejected: []\n"
)
REJECTED_PRECO_DELA = (
    "version: 1\n"
    "confirmed: {}\n"
    "rejected:\n"
    "  - text: preço dela\n"
    "    term: preço teto\n"
    "    date: '2026-09-20'\n"
)


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

    layer = tmp_path / "learned.yaml"
    layer.write_text(CONFIRMED_SEMIGA, "utf-8")
    pack = load_pack(path, learned_from=layer)
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

    layer = tmp_path / "learned.yaml"
    layer.write_text(REJECTED_PRECO_DELA, "utf-8")
    pack = load_pack(path, learned_from=layer)
    assert pack.is_rejected("preco dela", "preço teto")

    after = find_annotations(transcript, pack)
    assert not [a for a in after if a.original == "preço dela"]


def test_confirm_run_writes_the_learned_file_and_never_the_pack(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    path = pack_copy(tmp_path)
    digest_before = hashlib.sha256(path.read_bytes()).hexdigest()
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    # One `y`, one `n`, then end of input, which the loop treats as skip.
    monkeypatch.setattr("sys.stdin", io.StringIO("y\nn\n"))
    assert main([str(caption), "--pack", str(path), "--confirm"]) == 0

    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest_before

    # D-015: the learned layer lives under runs/, not beside the pack.
    layer = learned_file(path)
    assert layer == tmp_path / "runs" / "learned" / "pack.learned.yaml"
    assert layer.exists()
    assert not (tmp_path / "pack.learned.yaml").exists()

    learned = load_learned(layer)
    assert learned.confirmed, "the `y` answer should have confirmed a term"
    assert learned.rejected, "the `n` answer should have recorded a rejection"
    for confirmations in learned.confirmed.values():
        assert all(c.decided for c in confirmations)
    assert all(r.decided for r in learned.rejected)

    out = capsys.readouterr().out
    assert "to confirm:" in out
    assert str(layer) in out


def test_a_second_run_honours_what_the_first_one_learned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = pack_copy(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)

    monkeypatch.setattr("sys.stdin", io.StringIO("n\n"))
    main([str(caption), "--pack", str(path), "--confirm"])

    rejected = load_learned(learned_file(path)).rejected
    assert rejected
    transcript = read_caption(caption)
    annotations = find_annotations(transcript, load_pack(path))
    for r in rejected:
        assert not [
            a for a in annotations if a.term == r.term and " ".join(a.original.split()) == r.text
        ]
