"""D-090: a term with `match: exact` matches only by equality with its own forms."""

import pytest
import yaml

from transcript_normalizer import find_annotations, load_pack, merge, parse_caption, resolve_overlaps
from transcript_normalizer.core.fit import fitting_terms
from transcript_normalizer.core.pack import Learned
from transcript_normalizer.core.standoff import BAND_ASK, BAND_HIGH

HEAD = """\
language: pt-BR
version: test
classes: [companhia, farmaco, indicador]
phonetic_classes: [companhia, pessoa, farmaco]
terms:
"""


def pack_file(tmp_path, terms, name="pack.yaml"):
    path = tmp_path / name
    path.write_text(HEAD + terms, encoding="utf-8")
    return path


def found(path, caption, learned=None):
    pack = load_pack(path, learned=learned or Learned())
    return [(a.original, a.term, a.rule, a.band)
            for a in resolve_overlaps(find_annotations(parse_caption(caption), pack))]


def both(tmp_path, term, caption):
    """What a caption finds without the field, and with it."""
    plain = pack_file(tmp_path, term, "plain.yaml")
    exact = pack_file(tmp_path, term + "    match: exact\n", "exact.yaml")
    return found(plain, caption), found(exact, caption)


# ------------------------------------------------------------------ the paths it turns off


def test_no_fuzzy(tmp_path):
    before, after = both(tmp_path, "  - term: Paracetamol\n    class: farmaco\n", "0:01 tomei paracetamou ontem\n")
    assert before == [("paracetamou", "Paracetamol", "term:fuzzy", "medium")]
    assert after == []


def test_no_phonetic(tmp_path):
    before, after = both(tmp_path, "  - term: Partners\n    class: companhia\n", "0:01 eu tenho Paratenaras na carteira\n")
    assert before == [("Paratenaras", "Partners", "term:phonetic", BAND_ASK)]
    assert after == []


def test_no_inflection(tmp_path):
    before, after = both(tmp_path, "  - term: debênture\n    class: indicador\n", "0:01 as debêntures subiram\n")
    assert before == [("debêntures", "debênture", "term:alias", BAND_HIGH)]
    assert after == []


def test_no_number_words(tmp_path):
    before, after = both(tmp_path, "  - term: BOVA11\n    class: companhia\n", "0:01 comprei BOVA onze e BOVA11\n")
    assert [o for o, *_ in before] == ["BOVA onze", "BOVA11"]
    assert after == [("BOVA11", "BOVA11", "term:exact", BAND_HIGH)]


def test_name_alias_and_variant_still_match_ignoring_case_and_accents(tmp_path):
    path = pack_file(tmp_path, (
        "  - term: Paracetamol\n    class: farmaco\n    match: exact\n"
        "    aliases: [acetaminofeno]\n    variants: [para setamol]\n"
    ))
    caption = "0:01 o PARACETAMOL e o Acetaminofêno\n0:05 tomei para Setamol\n"
    assert found(path, caption) == [
        ("PARACETAMOL", "Paracetamol", "term:exact", BAND_HIGH),
        ("Acetaminofêno", "Paracetamol", "term:alias", BAND_HIGH),
        ("para Setamol", "Paracetamol", "term:variant", BAND_HIGH),
    ]


# ------------------------------------------------------------------ case_sensitive

CASED = (
    "  - term: Vale\n    class: companhia\n    match: exact\n"
    "    aliases: [Companhia Vale]\n    variants: [Valle]\n"
    "    case_sensitive: [Vale, Valle]\n"
    "  - term: Léo\n    class: pessoa\n    match: exact\n    case_sensitive: [Léo]\n"
)


def test_case_sensitive_matches_its_own_case_and_accents(tmp_path):
    path = pack_file(tmp_path, CASED)
    assert found(path, "0:01 a Vale lucrou e a Valle caiu, disse Léo\n") == [
        ("Vale", "Vale", "term:exact", BAND_HIGH),
        ("Valle", "Vale", "term:variant", BAND_HIGH),
        ("Léo", "Léo", "term:exact", BAND_HIGH),
    ]


def test_case_sensitive_does_not_match_another_case_or_accent(tmp_path):
    path = pack_file(tmp_path, CASED)
    assert found(path, "0:01 vale a pena, VALE, valle e Leo e léo\n") == []


def test_a_form_not_listed_stays_case_insensitive(tmp_path):
    path = pack_file(tmp_path, CASED)
    assert found(path, "0:01 a companhia vale lucrou\n") == [
        ("companhia vale", "Vale", "term:alias", BAND_HIGH)
    ]


# ------------------------------------------------------------------ the learned layer


def test_learned_variants_and_aliases_still_match(tmp_path):
    path = pack_file(tmp_path, "  - term: Paracetamol\n    class: farmaco\n    match: exact\n")
    learned = Learned().confirm("Paracetamol", "parace tamol").alias("Paracetamol", "paracetamól genérico")
    assert found(path, "0:01 tomei Parace Tamol\n0:05 e paracetamol genérico\n", learned) == [
        ("Parace Tamol", "Paracetamol", "term:variant", BAND_HIGH),
        ("paracetamol genérico", "Paracetamol", "term:alias", BAND_HIGH),
    ]


# ------------------------------------------------------------------ the guards read the exact forms


def test_an_exact_name_still_suppresses_a_shorter_correction(tmp_path):
    """D-040: `Dividend` inside `Dividend Yield` is not dividendo; with a
    case-sensitive name, only where the name is written as the pack writes it."""
    path = pack_file(tmp_path, (
        "  - term: Dividend Yield\n    class: indicador\n    match: exact\n    case_sensitive: [Dividend Yield]\n"
        "  - term: dividendo\n    class: indicador\n    variants: [dividend]\n"
    ))
    assert found(path, "0:01 o Dividend Yield subiu\n") == [
        ("Dividend Yield", "Dividend Yield", "term:exact", BAND_HIGH)
    ]
    assert found(path, "0:01 o dividend yield subiu\n") == [
        ("dividend", "dividendo", "term:variant", BAND_HIGH)
    ]


# ------------------------------------------------------------------ pack fit and context


def test_pack_fit_counts_an_exact_recognition(tmp_path):
    path = pack_file(tmp_path, (
        "  - term: Vale\n    class: companhia\n    match: exact\n    case_sensitive: [Vale]\n"
        "  - term: Petrobras\n    class: companhia\n    match: exact\n"
        "  - term: OPEX\n    class: indicador\n    match: exact\n    variants: [Ox]\n    context: {Ox: [CAPEX]}\n"
        "  - term: CAPEX\n    class: indicador\n"
    ))
    pack = load_pack(path, learned=Learned())

    def terms(caption):
        return fitting_terms(resolve_overlaps(find_annotations(parse_caption(caption), pack)))

    assert terms("0:01 a Vale e a PETROBRAS\n") == {"Vale", "Petrobras"}
    assert terms("0:01 vale a pena, Ox\n") == set()  # no context for Ox, and `vale` is not Vale


def test_an_exact_term_as_context_respects_case_sensitive(tmp_path):
    path = pack_file(tmp_path, (
        "  - term: OPEX\n    class: indicador\n    variants: [Ox]\n    context: {Ox: [CAPEX]}\n"
        "  - term: CAPEX\n    class: indicador\n    match: exact\n    case_sensitive: [CAPEX]\n"
    ))

    def ox(caption):
        return [(o, b) for o, t, _, b in found(path, caption) if o == "Ox"]

    assert ox("0:01 o capex subiu\n0:10 o Capex caiu\n0:20 o Ox subiu\n") == []
    assert ox("0:01 o CAPEX subiu\n0:10 o CAPEX caiu\n0:20 o Ox subiu\n") == [("Ox", BAND_HIGH)]


# ------------------------------------------------------------------ the loader


@pytest.mark.parametrize("term, message", [
    ("    match: fuzzy\n", "`match:` can only be `exact` (got 'fuzzy')"),
    ("    case_sensitive: [Vale]\n", "`case_sensitive:` needs `match: exact` on the same term"),
    ("    match: exact\n    case_sensitive: Vale\n", "`case_sensitive:` must be a list of the term's forms"),
    ("    match: exact\n    case_sensitive: [vale]\n", "`case_sensitive:` names 'vale', which is not its name"),
    ("    match: exact\n    case_sensitive: [Valle]\n", "`case_sensitive:` names 'Valle', which is not its name"),
])
def test_loader_errors(tmp_path, term, message):
    path = pack_file(tmp_path, "  - term: Vale\n    class: companhia\n    aliases: [VALE3]\n" + term)
    with pytest.raises(ValueError) as error:
        load_pack(path, learned=Learned())
    assert str(path) in str(error.value) and "term 'Vale'" in str(error.value)
    assert message in str(error.value)


def test_case_sensitive_may_name_an_alias_or_a_variant(tmp_path):
    path = pack_file(tmp_path, (
        "  - term: Vale\n    class: companhia\n    match: exact\n"
        "    aliases: [VALE3]\n    variants: [Valle]\n    case_sensitive: [VALE3, Valle]\n"
    ))
    assert load_pack(path, learned=Learned()).terms[0].case_sensitive == ("VALE3", "Valle")


# ------------------------------------------------------------------ the merge (D-069)


def t(term, **fields):
    return {"term": term, "class": "companhia", **fields}


def merged(base, up, mine):
    data = lambda terms: {"language": "pt-BR", "version": "0.1.0", "terms": terms}  # noqa: E731
    m = merge.Merge("p", data(base), data(up), data(mine), Learned()).run()
    m.case_sensitive_forms()
    return {x["term"]: x for x in m.result.values()}, m.summary.notices


def test_merge_keeps_the_fields_and_combines_case_sensitive_by_spelling():
    base = [t("Vale", match="exact", variants=["Valle"])]
    up = [t("Vale", match="exact", variants=["Valle"], case_sensitive=["Vale"])]
    mine = [t("Vale", match="exact", variants=["Valle"], case_sensitive=["Valle"])]
    got, _ = merged(base, up, mine)
    assert got["Vale"]["match"] == "exact"
    assert got["Vale"]["case_sensitive"] == ["Vale", "Valle"]


def test_merge_drops_case_sensitive_forms_that_no_longer_load():
    base = [t("Vale", match="exact", variants=["Valle"], case_sensitive=["Vale", "Valle"])]
    up = [t("Vale", match="exact", case_sensitive=["Vale", "Valle"])]  # upstream removed the variant
    mine = [t("Vale", match="exact", variants=["Valle"], case_sensitive=["Vale", "Valle"])]
    got, notices = merged(base, up, mine)
    assert got["Vale"]["case_sensitive"] == ["Vale"]
    assert "Vale: case_sensitive 'Valle' dropped, the form is gone" in notices

    base = [t("Vale", match="exact")]
    up = [t("Vale")]  # upstream no longer exact; I had listed a case-sensitive form
    got, notices = merged(base, up, [t("Vale", match="exact", case_sensitive=["Vale"])])
    assert "match" not in got["Vale"] and "case_sensitive" not in got["Vale"]
    assert any("no longer `match: exact`" in n for n in notices)


def test_a_merged_pack_with_the_fields_loads(tmp_path):
    base = [t("Vale", match="exact", case_sensitive=["Vale"])]
    got, _ = merged(base, base, base)
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump({"language": "pt-BR", "version": "0.1.0", "terms": list(got.values())}),
                    encoding="utf-8")
    assert load_pack(path, learned=Learned()).terms[0].exact
