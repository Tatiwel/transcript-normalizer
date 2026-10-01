"""D-013: confirmations and rejections live beside the pack, never inside it."""

import hashlib
import io
import shutil

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, read_caption
from transcript_normalizer.cli import main
from transcript_normalizer.core import matcher
from transcript_normalizer.core.pack import load_learned
from transcript_normalizer.runs import learned_file

from .conftest import CAPTION, PACK, answers_for, medium_order


@pytest.fixture(autouse=True)
def mixed_group_as_designed(monkeypatch):
    """These tests are about the confirmation loop (D-013, D-019), not matching.

    They script answers against the fixture's CEMIG group of four variants.
    D-047 demoted `dos 10` and `nesse ramo` (fuzzy from a variant, under 85) to
    marks, which leaves two, too few for y/n/y/s or rest-no to mean anything,
    so the variant threshold is held at the canonical one here.
    """
    monkeypatch.setattr(matcher, "VARIANT_APPLY_THRESHOLD", matcher.APPLY_THRESHOLD)

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


def confirm_run(tmp_path, monkeypatch, answers):
    """A --confirm run in tmp_path, driven by `answers`, one per line."""
    monkeypatch.chdir(tmp_path)
    path = pack_copy(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{a}\n" for a in answers)))
    assert main([str(caption), "--pack", str(path), "--confirm"]) == 0
    return load_learned(learned_file(path))


def confirmed_pairs(learned):
    return sorted(
        (term, c.variant) for term, cs in learned.confirmed.items() for c in cs
    )


def rejected_pairs(learned):
    return sorted((r.term, r.text) for r in learned.rejected)


# The fixture's mixed medium-band group, in the order the loop asks it: the
# whole point of D-019. Where it falls among the groups is derived, not assumed.
CEMIG_VARIANTS = ["dos 10", "e caiu", "mês caiu", "nesse ramo"]


def test_the_mixed_group_is_the_one_these_tests_expect():
    assert [v for t, v in medium_order() if t == "CEMIG"] == CEMIG_VARIANTS


def test_a_mixed_group_is_answered_one_variant_at_a_time(tmp_path, monkeypatch):
    # yes, no, yes, skip -- then end of input, so no later term is touched.
    learned = confirm_run(tmp_path, monkeypatch, answers_for("CEMIG", ["y", "n", "y", "s"]))

    assert confirmed_pairs(learned) == [("CEMIG", "dos 10"), ("CEMIG", "mês caiu")]
    assert rejected_pairs(learned) == [("CEMIG", "e caiu")]


def test_all_yes_stops_at_the_end_of_its_term(tmp_path, monkeypatch):
    # `a` on CEMIG's first variant takes all four; the next term asks again.
    learned = confirm_run(tmp_path, monkeypatch, answers_for("CEMIG", ["a", "n"]))

    assert confirmed_pairs(learned) == [("CEMIG", v) for v in CEMIG_VARIANTS]
    # Only the one variant the `n` answered: the first of the next term's.
    order = medium_order()
    after = next(pair for pair in order[order.index(("CEMIG", CEMIG_VARIANTS[-1])) + 1 :])
    assert rejected_pairs(learned) == [after]


def test_rest_no_takes_the_current_variant_and_the_ones_after_it(tmp_path, monkeypatch):
    learned = confirm_run(tmp_path, monkeypatch, answers_for("CEMIG", ["y", "r"]))

    assert confirmed_pairs(learned) == [("CEMIG", "dos 10")]
    assert rejected_pairs(learned) == [
        ("CEMIG", v) for v in CEMIG_VARIANTS if v != "dos 10"
    ]


def test_each_variant_is_asked_with_its_own_examples(tmp_path, monkeypatch, capsys):
    confirm_run(tmp_path, monkeypatch, ["s"])
    out = capsys.readouterr().out

    heading = out.index("CEMIG  (5 occurrences)")
    for variant in CEMIG_VARIANTS:
        assert f"  {variant}  (" in out
        assert f"{variant} -> CEMIG? [y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no:" in out
    # The term is named once, above its variants.
    assert out.count("CEMIG  (5 occurrences)") == 1
    assert out.index("    0:37  Neste mês caiu") > heading


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

    # D-017: the learned layer lives under packs/, not beside the pack file
    # (which here is a copy in tmp_path, so the two are distinguishable).
    layer = learned_file(path)
    assert layer == tmp_path / "packs" / "pack.learned.yaml"
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
