# Contributing

Three things people outside the project add: a language, a domain pack, and a fixture that measures them. Each has a procedure below that you can follow without reading the code.

**This repository is the engine; domain content lives in the packs repository.** Packs are proposed, reviewed and versioned in [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), one directory per pack, each with a `MAINTAINERS` file naming who reviews its changes (D-055). A change to a pack's terms goes there, not here; this repository never edits pack content. It keeps two kinds of copies: `src/transcript_normalizer/packs/financas-ptbr.yaml`, the offline default, taken from the packs repository at a released version, and the frozen `pack.yaml` of each fixture, which only a measurement changes. Section 2 below is how to build and curate a pack wherever it will live; the packs repository's README says how to propose one. A user's reviews reach the packs repository through `transcript-normalizer pack propose` (D-056). `docs/DECISIONS.md` is the reason behind every rule here; decision numbers (D-0xx) point into it.

## Contents

1. [Adding a language](#1-adding-a-language)
2. [Building a domain pack](#2-building-a-domain-pack)
3. [Building a fixture and measuring](#3-building-a-fixture-and-measuring)
4. [Dependencies](#4-dependencies)

Set up once with `uv sync`. Its `dev` dependency group includes `transcript-normalizer[ingest]` (which carries `[captions]` and `[menu]`) and pytest, so every extra is installed, and a later plain `uv sync` keeps them instead of removing them. Run the tests with `uv run pytest -q`.

---

## 1. Adding a language

The core knows no language (D-033). Everything language-specific lives in one module that implements four things. A pack says which language it is in, and the loader picks the module.

**1.1 Create the module.** For the language code `xx-YY`, create `src/transcript_normalizer/languages/xx_yy.py` (lowercase, `-` becomes `_`). Start from `tests/lang_xx.py`, which is a complete working module for an invented language.

**1.2 Implement the protocol.** The module provides these four names:

- `normalize(text) -> str` — the form text is compared in: lowercase, accents folded, and whatever else your language needs flattened. Every term, alias, variant and caption span passes through it.

  ```python
  normalize("Preço Teto!")   # pt-BR
  # -> "preco teto"
  ```

- `inflections(word) -> set[str]` — the base forms a single normalized word may be an inflection of (D-031a). A word whose base form is a term or alias is treated as that term spelled out: it is recognized, never corrected. Return `set()` for anything that is not inflected, and for multi-word input.

  ```python
  inflections("dividendos")   # pt-BR: -s
  # -> {"dividendo"}
  ```

- `unit_rules() -> list[UnitRule]` — the deterministic unit layer, which runs before the dictionary (D-006). Each `UnitRule(pattern, replacement, term)` holds a compiled regex, a `re.Match.expand` template, and the rule's own name for the unit. The optional fourth field, `owns`, lists words that only this rule may match for that unit: `bit` after a number is the unit, and anywhere else it is left to the dictionary. Rules apply in order, and a match overlapping an earlier rule's match is dropped. Return `[]` if your language needs none.

  ```python
  UnitRule(re.compile(r"(\d[\d.,]*)\s+(B|bit|be)\b(?![\w])"), r"\1 bi", "bi", owns=("B", "bit", "be"))
  # "31 bit" -> annotated as the pack term that names "bi", replaced by "31 bi"
  ```

- `sentence_boundaries` — a set of punctuation characters that no word n-gram runs across (D-024). A `.` inside a token (`6.7`) is a decimal point, not a boundary.

  ```python
  sentence_boundaries = frozenset(".?!;")
  # "Warn Buffet. Tem" is never matched as one span
  ```

**1.3 Register it.** Usually there is nothing to do: a module at `languages/<code>.py` is found by its name when a pack declares that `language:`. A module kept anywhere else (a plugin, a test) is made known with `transcript_normalizer.languages.register("xx-YY", module)`, which also checks that it keeps the protocol.

**1.4 Test it.** Copy the `xx` tests as a template:

- `tests/data/xx/legenda.txt` — a short caption (20 lines) in your language;
- `tests/data/xx/pack.yaml` — a pack with a few terms, declaring `language:`;
- `tests/test_language_xx.py` — proves that the core runs on it end to end, that your inflections and unit rules are honoured, and that a pack in a language with no module is refused.

A pack in a language with no module is an error. `--allow-generic` runs it with `languages/generic.py` instead: case and accent folding, `. ? ! ;`, and no inflections or unit rules. That is a way to try a pack out, not a substitute for a module.

---

## 2. Building a domain pack

A pack is the list of terms the tool is allowed to touch (D-001, D-002). Nothing outside it is ever changed. The curated one, used by default, is `src/transcript_normalizer/packs/financas-ptbr.yaml` and ships in the package; `packs/` at the root is for your learned layers and your own packs (D-043).

**2.1 The schema.**

```yaml
language: pt-BR          # required; selects the language module (D-033)
version: 0.2.3           # see 2.7
terms:
  - term: CPFL           # the canonical name, as it should be written
    class: companhia     # one of the eight classes, 2.2
    aliases: [CPFE, CPFE3, CPFL Energia]   # other correct names (2.3)
    variants: [CPFS, CPF]                  # observed misrecognitions (2.3)
    collocations: []     # reserved: read, not used for matching yet (D-032)
```

`term` and `class` are required; the rest are optional lists. A `unit_rules:` block at the end of a pack is descriptive only: the rules that run are the language module's (1.2).

**2.2 Classes (D-021).** A closed list; the loader refuses any other value. Class is a label for consumers, and matching reads only `unidade` (D-028).

| class | what it is |
|---|---|
| `companhia` | a listed company: has a ticker and a balance sheet |
| `indicador` | a number per company or asset (EBITDA, ROE, IPCA) |
| `conceito` | an idea, method or strategy (valuation, buy and hold) |
| `unidade` | a unit (bilhão, tri) |
| `pessoa` | a person |
| `organizacao` | not a listed company: a regulator, fund manager, channel or series |
| `ferramenta` | a tool or product used by the speaker |
| `sigla` | a sector or regulatory abbreviation (RAP, DEC) |

**2.3 Aliases and variants (D-020).** The one distinction that matters most:

- An **alias** is a legitimate other name for the term, spelled the way the speaker really said it. It is recognized and annotated, and the text is **never** changed.
  - `CPFE` for CPFL (the ticker);
  - `preços teto` for preço teto (the plural; inflection is always an alias).
- A **variant** is a misrecognition: the caption garbled the term. It is **corrected** in `normalized.txt`.
  - `SEMIG` for CEMIG;
  - `presteto` for preço teto.

If a speaker actually said it, it is an alias. If it is the caption's mistake, it is a variant. Aliases match exactly only; variants are also the base of fuzzy matching (D-025).

**2.4 Curation rules.**

- **Short strings match exactly, and one- and two-letter strings stay out** (D-005). Fuzzy matching needs at least 6 characters on both sides and lengths within 2, so anything shorter matches only if it is identical. Single letters and two-letter strings (`R`, `TI`, `EB`) match too much ordinary text even exactly, so new ones do not enter the pack. Two from the first version predate the rule: `TR` (a variant of the unit tri) and `Lu` (of Leo). Check each against a silence run (below) before the next pack release, and remove it if it fires. `Ox` was the third: it was removed in 0.3.4 after the silence run of D-035 found it was the Northeastern interjection `oxe`.
- **Silence run** (D-035). Normalize a video from a different field with the pack, and count what it applies. Any applied correction there is a false positive by definition. Run it before a pack release.
- **Ordinary words stay out** (D-032). A variant that is an ordinary word of the language (`tira`, `rápido`, `divide`) does not enter the pack, even if the caption used it for the term: exact matching on ordinary words is wrong more often than right. Such cases wait for the collocation layer. Also check that a new variant does not fuzzily reach an ordinary word: `presteto` reaches `preste` (0:24 on wxgFO_fyfXg).
- **Units are class `unidade`** (D-028). A unit term never enters fuzzy matching (`milhão` and `bilhão` are one letter apart). Its rules live in the language module (1.2), and the pack names the term the rules resolve to: `bilhão` with alias `bi`.

**2.5 The learned layer.** `transcript-normalizer <legenda.txt> --confirm` asks about each medium-band proposal, one variant at a time (D-019). Your answers go to `packs/<pack-name>.learned.yaml`, never into the pack itself (D-013, D-017):

- `y` — a real misrecognition; it is corrected from now on (`confirmed`);
- `n` — not this term; that text, and any longer span containing it as whole words, is never proposed for the term again (`rejected`, D-027);
- `l` — it is this term, said that way; it is recognized from now on and never changed (`aliases`, D-020);
- `s` skips; `a` answers yes, and `r` no, for this variant and every remaining variant of the same term.

Learned entries match exactly only (D-025), so one confirmation never widens what fuzzy matching reaches. The file is personal and gitignored.

**2.6 Promoting learned entries into the pack.** When a learned entry has proven itself, make it curated. For a pack from the packs repository, `transcript-normalizer pack propose --pack <name>` opens an issue there with your learned entries, and the pack's maintainers do the steps below. For your own pack:

1. Move it from `packs/<name>.learned.yaml` into the pack: a `confirmed` variant into the term's `variants`, a learned alias into its `aliases`.
2. Apply the curation rules in 2.4 before you move it; the learned layer does not.
3. Delete it from the learned file, so the same entry does not live in both.
4. Bump the pack's version (2.7) and re-measure (3.6).

A rejection stays in the learned layer: the pack has no place for "never this".

**2.7 Versioning.** Bump the **patch** number (`0.2.2` → `0.2.3`) for data: adding, removing or moving a term, alias or variant. Bump the **minor** number (`0.2.x` → `0.3.0`) for a change someone reading the file would notice in its shape: a new key, a changed meaning of a key, a class change. Say in the comment at the top of the pack what each version added. Every annotation records the pack version that produced it (D-004).

---

## 3. Building a fixture and measuring

A fixture is a video whose caption has been checked by hand against the tool's output. It is how a pack or a matcher change is measured instead of guessed at. Fixtures live in `fixtures/<video-id>/` and are frozen once recorded.

**3.1 Fetch the caption.**

```
transcript-normalizer fetch <url>
```

This writes `runs/<video-id>/legenda.txt` (the platform's caption, with a provenance header) and `meta.yaml`. If the platform has no caption, or it cannot be had after retrying rate limits, the audio is transcribed locally instead; the header's `# Etapa:` line and meta.yaml say which happened (D-036). `--caption-only` never falls back, and `--whisper` always transcribes.

For a recording you have as a file, pass its path instead of a url:

```
transcript-normalizer fetch path/to/entrevista.mp4
```

A file has no platform caption, so it is transcribed locally into `runs/<file-stem>/` (`runs/entrevista/` here). Its header records the file name where a video's records the url, and meta.yaml records `source: file` and the file's absolute path (D-038).

**3.2 Normalize, asking for the corrections draft.**

```
transcript-normalizer runs/<video-id>/legenda.txt --corrections
```

This writes `normalized.txt` (the caption with the corrections applied) and `needs-review/corrections.csv`. The CSV has one row per applied annotation, with the columns `timestamp, wrong, correct, term, class, status`, and every status set to `draft`.

**3.3 Hand-check every row of corrections.csv.** Set each row's `status` to one of these:

- `certo` — the tool proposed this correction and it is right.
- `alias` — the text is a legitimate other name of the term (a ticker, a plural, a spoken form). Set `correct` equal to `wrong`.
- `manter` — the tool touched text that must stay exactly as it is. Nothing may be proposed there.
- `conferido` — a person added this row: an error the tool missed (3.4).
- `so_caixa` — the difference is case only (`tir` → `TIR`). It is not a correction and is not scored (D-008).

`fala comum` is **not** a status. It goes in the `class` column of a row with an empty `term`, to record ordinary speech that caught your eye. Rows with an empty term are out of scope and are never scored. Delete any row where the tool was simply wrong (not a domain term, or the wrong term): leaving it out of the gold is what makes it count as a false positive.

The status records who wrote the row. Scoring treats `certo` and `conferido` alike (D-026).

**3.4 Add the misses.** Read `normalized.txt` against the audio or the video, and find the domain terms the tool left garbled. For each one, add a row with status `conferido`. Its `timestamp` is the caption line the text is on. For a stretch that runs across a line break, use the line it starts on.

**The `wrong` column must be the raw caption text, copied from `legenda.txt`, never the text from `normalized.txt`.** Scoring looks for `wrong` in the caption, because the caption is what the tool reads. A `wrong` taken from the normalized view describes text that is not in the caption: it can never be matched, it is a miss under any pack forever, and nothing tells you so. Read `normalized.txt` to find the misses, then copy the words from `legenda.txt`. This happened in wxgFO_fyfXg: five rows recorded `CEMIG 4`, the normalized text, where the caption said `SEMIG 4`, and they were unscorable until fixed.

**3.5 Save the fixture.** Create `fixtures/<video-id>/` holding three files:

- `legenda.txt` — copied from the run;
- `gold.csv` — your checked file, saved as UTF-8;
- `pack.yaml` — a copy of the pack as it is today. This copy is frozen: later pack changes are measured separately (3.6), so the fixture's numbers stay comparable.

**3.6 Measure, record, and write it down.**

1. Run `uv run pytest -q tests/test_regression_fixture.py`. A fixture without bounds fails on purpose (`test_every_fixture_has_bounds`).
2. Run `uv run python scripts/measure.py`, which prints every fixture's in-scope rows, hits, misses, false positives, aliases recognized and aliases wrongly substituted, and a non-blocking run of each fixture against the current curated pack.
3. Add the fixture to `BOUNDS` in `tests/test_regression_fixture.py` with the numbers **as measured**, not tuned: `in_scope`, `min_hits`, `max_false_positives`, and `max_manter_touched` if a `manter` row is touched. Write a comment saying what the numbers are and where they came from.
4. Append a decision to `docs/DECISIONS.md` recording the fixture and its measured bounds. Decisions are append-only: from then on, any change that moves a bound gets a commit that updates the table, and a decision that says why.

---

## 4. Dependencies

The core, what `pip install transcript-normalizer` brings, stays minimal: rapidfuzz, PyYAML and platformdirs. A new dependency goes into an extra, `[menu]`, `[captions]`, `[ingest]` or a new one, unless the matcher itself needs it.

The reason: programs such as valuation-simulator import the core to normalize text. They must not inherit dependencies for an interface (rich, questionary) or for downloading and transcribing (yt-dlp, faster-whisper). Code that needs an extra imports it where it is used, never at the top of a core module, so the core still imports without it. See D-052 (the two artefacts and the extras) and D-053 (the `[menu]` extra and the prompts adapter).
