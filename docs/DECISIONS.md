# Decisions

Append-only, numbered. A decision is superseded by a later one, never edited.

## D-001 Match against known terms, not against the language

The normalizer never checks whether a word exists. It checks whether a stretch of text resembles a term in a loaded domain pack. Text that resembles nothing in the pack is never touched.

Why: half of the errors in the fixture are valid words (`Word`, `bicho`, `geração de dentes`, `bit`). Existence checks cannot see them and produce false positives on everything else.

## D-002 The user declares the domain pack; the tool never infers it

Domain and language are inputs, not detections. Loading two packs at once resolves conflicts by explicit rank (memoQ model), never by guessing context.

Why: inferring "is EBITDA valid in biology?" requires a biology vocabulary anyway, and the inference is the fragile part. Whoever downloads a video knows what it is about.

## D-003 The dictionary unit is the term, not the error→correction pair

Each entry is a canonical term with aliases, observed variants, and collocations. Matching runs against all of them. Confirmed corrections are appended to observed variants.

Why: CEMIG alone has 14 distinct misrecognitions in one video. Measured: fuzzy matching against term and aliases only found 77/172; adding observed variants found 141/172 (exp1).

## D-004 Correction is stand-off

The original text and its timestamps are never modified. Normalization is a separate layer of `(offset_start, offset_end, original, replacement, term, rule, confidence, pack_version)`.

Why: the timestamp is the provenance of every claim extracted downstream. A corrected string whose audio says something else breaks that. Inherited from the research consolidation of 2026-09-06.

## D-005 Short strings match by exact equality only; fuzzy needs 6+ characters and similar length

Fuzzy similarity is applied only when both the candidate and the text span have at least 6 characters and their lengths differ by at most 2. Anything shorter matches only on exact (normalized) equality.

Why, measured (exp2): without this rule, 64 false positives, including `dívida → dividendo` 34 times and `ainda → Engie` 14 times, and one of the two must-not-touch lines was corrupted. With it, 10 false positives and both lines intact, at a cost of one true hit (152 vs 153).

## D-006 Unit patterns are rules, applied before the dictionary

`number + (B | bit | bi | be)` → `bi` and `bilhões deais` → `bilhões de reais` are regex rules in a deterministic layer that runs before term matching. They belong to inverse text normalization, not to the domain pack.

Why, measured: 14 of the 32 misses of exp1 were units. One regex closed 12 of them.

## D-007 Normalize over the whole text, not caption line by caption line

Platform captions break lines mid-phrase. Matching must run over the joined text with an offset map back to lines and timestamps.

Why: `ser MIG` (→ CEMIG) is split across two caption lines at 24:48 / 24:51 and cannot be found line by line.

## D-008 Case-only differences are not corrections

`tir` → `TIR`, `rap` → `RAP` are not errors of the transcript and are not counted in the gabarito (status `so_caixa`). Casing of acronyms is a display concern of the output layer, not a normalization.

Effect on the fixture: 168 in-scope rows instead of 172; hits stay at 152, misses drop to 16.

## D-009 Word-boundary errors are handled by observed variants only, for now

Glued words (`SEMigd`, `autocapex`, `aoonista`) and split words (`Geração de Dentes`) are covered by listing them as multi-word variants of the term. SymSpell LookupCompound is not adopted yet.

Why: 6 cases in 168. The variant list covers them after the first sighting. SymSpell is revisited if a second fixture shows the category is larger than it looks here.

## D-010 Phonetic matching is deferred to experiment 3

No phonetic layer (metaphone-ptbr, Epitran) enters the package before the base library exists and the regression test is in place. Experiment 3 will measure, against the same gabarito, whether phonetics recovers the remaining misses (`mississões`, `BBI`, `serig`) without adding false positives.

Why: 7 cases in 168, and no pt-BR benchmark exists for either tool. Decide on measurement, not on reputation.

## D-011 Three confidence bands decide whether to apply, ask, or only mark

| Band | Trigger | Behaviour |
|---|---|---|
| High | listed variant, alias, or unit rule | apply, log in report |
| Medium | fuzzy match at or above the apply threshold, never confirmed | apply flagged `to_confirm`; ask in batch, grouped by term; on confirmation, promote to listed variant |
| Low | fuzzy match between the mark threshold and the apply threshold | do not apply, do not ask; passive mark in the annotation file |

Initial thresholds: apply 80, mark 60. Both are to be calibrated against the gabarito, not fixed.

## D-012 Whole-text matching (D-007) is accepted at 155 hits / 11 false positives

Matching over the joined text instead of caption lines found three line-straddling errors (`ser MIG`, `Geração de Dentes`, `9.3 bilhões deais`) and introduced one false positive (`preço dela` → `preço teto`, fuzz 85). New regression bounds: hits >= 155, false positives <= 11, in scope 168. The ten other false positives are identical to exp2.

## D-013 Confirmations and rejections go to a separate learned layer, never into the pack

User decisions from the confirmation loop are written to `<pack>.learned.yaml` next to the pack file (`pack.learned.yaml` for `pack.yaml`). Schema: `version`, `confirmed: {term: [variant, ...]}`, `rejected: [{text, term}]`, each entry with the date it was decided. The loader merges pack and learned layer; learned variants are matched as `term:variant` (high band). Rejected pairs are never proposed again.

Why: the pack is curated and shareable; the learned layer is personal and unreviewed. Mixing them would ship unreviewed variants to other users and gives rejections nowhere to live.

## D-014 `SEMigd` belongs to `Cemig D`, not to CEMIG

`SEMigd` was listed as a variant of CEMIG while the gold file has it at 5:13 as `Cemig D`. It is now a variant of a `Cemig D` term entry of its own (class `companhia`); `Cemig D` stays an alias of CEMIG as well. A curation fix to the fixture pack, not a change to the matcher.

Effect, measured: the 5:13 row becomes a hit and the two `SEMigd` → CEMIG false positives disappear. New regression bounds: hits >= 156, false positives <= 9, in scope 168. Nothing else in the per-term table moves, and the remaining nine false positives are the ones D-012 already recorded.

## D-015 User outputs live in `runs/<id>/`

User outputs live in runs/<id>/, gitignored; the package never writes beside its inputs or into fixtures/.

A run writes `annotations.json`, `report.txt` and, when asked, `gold-draft.csv` into `runs/<input-stem>/` under the current directory (`--out DIR` overrides). The learned layer of D-013 moves with them, to `runs/learned/<pack-name>.learned.yaml` (`--learned PATH` overrides).

Why: the first version wrote `legenda.annotations.json` next to its input, which meant a run against the fixture dirtied `fixtures/`. Outputs are disposable and regenerable; inputs are not.

## D-016 Rendered outputs

Rendered outputs. runs/<id>/normalized.txt is the original caption with applied annotations substituted, one line per caption line as `m:ss  text`, timestamps preserved. It is a view over the stand-off layer (D-004); the original legenda.txt is kept beside it. runs/<id>/review/ holds files that need the user: gold-draft.csv and to-confirm.txt (the medium band, grouped by term, same text the --confirm prompt shows). A speaker-aware variant normalized.speakers.txt is reserved for when diarization exists.

`annotations.json` and `report.txt` stay at the top of the run directory: they describe the run, they are not something to hand to a person. A rendered file carries no provenance header, which is why the raw caption is copied in beside it.

## D-017 `packs/` is the user's knowledge directory

packs/ is the user's knowledge directory; fixtures/ packs are frozen test copies.

`packs/financas-ptbr.yaml` is the first one, copied from the fixture pack, and it is what `--pack` falls back to. The learned layer of a pack moves here too, to `packs/<name>.learned.yaml`, superseding the `runs/learned/` location of D-015: what the user confirmed belongs with the pack it is about, not with a disposable run. The learned file is gitignored; the pack is not.

Why: `fixtures/R2Qgz8tFWVI/pack.yaml` is an input to the regression test and has to stay frozen, so it cannot also be the pack people edit as they work.

## D-018 The run id comes from the video, not from the file name

`runs/<id>/` is derived in this order: if the input is already inside a `runs/<id>/`, that directory is the run directory; else if the caption header has a `# URL:` line with a recognizable video id, `runs/<id>/`; else the input's stem. `--out` still overrides all three.

Why: `fetch` names every caption `legenda.txt` (D-016), so deriving the run id from the input stem sent every video to `runs/legenda/` and each run silently overwrote the last. The first rule also makes normalizing a fetched caption write back into the directory it was fetched into, instead of forking a second one.

A recognizable id is the eleven-character platform id, read from the `youtu.be/<id>`, `?v=<id>` and `/shorts|embed|live|v/<id>` shapes. An unrecognized url is treated as no url: the stem is a poor id, but inventing one from an arbitrary url would be worse.

## D-019 Confirmation is per variant, not per term group

Confirmation is per variant, not per term group. In a real run (wxgFO_fyfXg) the group `ser mais, dos 10, sem mig, que caiu, esse mig -> CEMIG` was accepted with one `y`; only two of the five were CEMIG. A term-level answer cannot express a mixed group. The prompt shows the term once, then asks for each variant separately, with that variant's own example lines (up to 3), `[y]es / [n]o / [s]kip / [a]ll-yes / [r]est-no`. `a` and `r` apply to the remaining variants of the current term only.

`review/to-confirm.txt` keeps the grouped view and lists each variant under its term with its own examples and its own question, so the file still shows what the loop will ask.

## D-020 Two kinds of annotation: correction and alias

Two kinds of annotation. `correction`: the caption misrecognized the term; the span is substituted in normalized.txt. `alias`: the text is a legitimate other name of the term (ticker CPFE for CPFL, plural `preços teto`, spoken `CEMIG 4` for CMIG4); the span is annotated with the term but never substituted. Pack `aliases` produce alias annotations; pack `variants` produce corrections. Inflection is alias, not variant. The learned layer gains an `aliases` section beside `confirmed` and `rejected`; --confirm gains the answer `[l]ias` = 'it is this term, but the speaker said it that way'. Measured on wxgFO_fyfXg: 42 of 228 gold rows are aliases; substituting them rewrites what the speaker said.

An alias annotation comes only from an exact match against an alias; a fuzzy match near one is still a guess that the text is garbled, so it stays a correction. It is high band and its `replacement` is the original text. In `annotations.json` the `kind` field carries the difference, and the report lists aliases under "recognized (not changed)". The prompt shows the answer as `a[l]ias`, since `a` is taken by all-yes. A given text is either a confirmed variant or an alias of a term, never both: recording one removes the other.

## D-021 Eight classes, a closed list

Eight classes, closed list: companhia (has ticker and balance sheet), indicador (a number per company or asset), conceito (idea, method, strategy), unidade, pessoa, organizacao (not a listed company: regulator, fund manager, channel, series), ferramenta, sigla (sector or regulatory abbreviation). Migration: indice→indicador; instrumento, tributario, estrangeirismo→conceito; periodo→unidade; gestora, canal, serie do canal→organizacao; sigla setorial→sigla. Class is a label for consumers; it does not affect matching.

Applied to `packs/financas-ptbr.yaml`, both fixture packs and `fixtures/R2Qgz8tFWVI/gold.csv`; `fixtures/wxgFO_fyfXg/gold.csv` already used the eight, and the legacy copy is left as it was. The loader refuses a class that is not on the list. Two cases the migration did not name: `operacao` (emissão, diluição; three gold rows) became `conceito`, the nearest of the eight and where `instrumento` went; `numero` appears only on out-of-scope rows with no term, where the class column is a free note like `fala comum`, so it stays. One in-scope gold row has no class at all (18:38 `aoonista` -> acionista) and is left blank: a blank means unlabelled, not a ninth class.

The eight `CPFE -> CPFL` rows of `fixtures/R2Qgz8tFWVI/gold.csv` are now status `alias` with `correct` equal to `wrong`, the same speaker habit as wxgFO_fyfXg. Measured: that fixture moves from 156 hits / 9 false positives to 148 / 17. The frozen pack still lists CPFE as a variant, so all eight are substituted, and each counts as a miss and as a false positive. New bounds: hits >= 148, false positives <= 17, in scope 168.

## D-022 One run directory per video, described by meta.yaml

Run directory is runs/<video-id>/ (unique, stable, filesystem-safe). fetch writes runs/<id>/meta.yaml with title, channel, url, published, fetched_at. `transcript-normalizer list` prints id, date, title for every run.

The id is derived as D-018 says; for a caption with no recognizable url the fallback is still the file stem. `published` is stored as an ISO date (`2026-08-25`, not the platform's `20260825`) and `fetched_at` as a timestamp with its offset. The date `list` prints is the video's publication date, since that is what tells one episode of a channel from another. A run without meta.yaml, from before this decision or from normalizing a local file, is described from the provenance header of its caption; a directory holding neither is not a run and is not listed.

## D-023 Files that need the user live in needs-review/

Files that need the user live in runs/<id>/needs-review/: corrections.csv (was review/gold-draft.csv; same columns; status draft) and pending.txt (was to-confirm.txt), which lists each unanswered variant grouped by term, tagged [never asked] when the run had no --confirm and [skipped] when the user answered s.

This supersedes the `review/` directory of D-016. `--gold-draft` is renamed `--corrections`; the old flag still works for one release, hidden from `--help`, and says so on stderr. corrections.csv keeps its alias rows, with `correct` equal to `wrong`, because a gold file needs them. pending.txt is written with every variant `[never asked]` when the report is produced, then rewritten after a `--confirm` loop from its answers: a variant that got `y`, `n` or `l` leaves it, one that got `s` (or that the input ran out before) stays as `[skipped]`, and the file is removed when nothing is left, so a stale list never outlives its answers.

## D-024 Word n-grams stop at strong punctuation

Word n-grams do not cross strong punctuation (. ? ! ;). Measured: `Warn Buffet. Tem` was proposed as one variant of Warren Buffett in wxgFO_fyfXg.

The tokenizer marks each token followed by `.`, `?`, `!` or `;`, and no n-gram runs across the mark. A `.` inside a token is a decimal point (`6.7`) and does not count, a comma does not count, and a caption break is not punctuation, so D-007's `ser` / `MIG` still joins. The unit rules are regexes over the text and are unaffected.

Measured: R2Qgz8tFWVI loses the false positive `preço. Então` -> preço teto (17 -> 16) and no hit. wxgFO_fyfXg loses one hit, 36:41 `Warn Buffet` -> Warren Buffett (103 -> 102). That hit was credited only to the span `Warn Buffet. Tem`; the caption line ends `do Warn Buffet.`, and nothing in the frozen pack reaches `Warn Buffet` without crossing the full stop. Its bound moves to hits >= 102. The first fixture's bounds stay as they were, since it lost no hit.

## D-025 Aliases and learned variants match exactly

Fuzzy matching runs only against the canonical term and the curated pack variants. Aliases and learned variants match by exact normalized equality only. Measured: alias `bilhões` fuzzy-matched `milhões` at 85.7, medium band, applied: 24 false positives on wxgFO_fyfXg and millions rewritten as billions in normalized.txt for any user of the default pack. Aliases are legitimate spellings, not misrecognitions; fuzzy is for finding misrecognitions. This also closes open question (a): learned confirmations no longer widen fuzzy reach.

Measured after: wxgFO_fyfXg against pack 0.2.0 drops from 53 to 32 false positives with no hit lost; neither fixture moves against its frozen pack. The hazard is not fully closed, because the canonical term is still fuzzy. `milhões` scores 61.5 against `bilhão` and is only a low-band mark now (neither applied nor rendered), but `milhão` scores 83 against it, medium band, and is still applied: three times on wxgFO_fyfXg. Both are held as strict expected failures in `tests/test_exact_only.py`, so the suite goes red if either is fixed without being promoted to a real test.

## D-026 Gold status is provenance; scoring is one rule

In gold.csv, certo and conferido record who wrote the row (tool-proposed and human-checked vs human-added). Scoring does not distinguish them: every row with correct != wrong expects that correction; hit if an applied correction produces it on that line, miss otherwise. alias expects an alias annotation and no substitution; manter expects no applied annotation; rows with empty term are out of scope. Both fixtures use this one rule.

This replaces the two gold conventions of the first version of the evaluator, under which `conferido` was always a miss in wxgFO_fyfXg and scored like `certo` in R2Qgz8tFWVI. "Produces it" means an applied correction for the row's term that covers the row's text on that line; the rendered text is not compared with `correct`, which people write with more context than the span (`Tanto as emissões`) and with their own decimal separator (`4,6 bi`). `correct != wrong` is compared on normalized text, so D-008 still holds: the three `CPFe -> CPFE` alias rows stay aliases, and 15:57 `Etaú -> ETAU`, a `conferido` row differing only by case and accent, is out of scope.

Measured: R2Qgz8tFWVI does not move (167 in scope, 147 hits, 16 false positives), since it already scored the two alike. wxgFO_fyfXg goes to 225 in scope with 107 hits and 57 false positives: the frozen pack finds none of its conferido rows. Against pack 0.2.0 the same fixture goes from 149 to 188 hits, the 39 conferido rows that pack now finds.

## D-027 Rejection by containment

A rejected pair (text, term) suppresses any proposal for that term whose normalized span contains the rejected text as whole words. Measured: rejecting `divide → dividendo` did not suppress `divide a → dividendo` at 15:54 in wxgFO_fyfXg, violating a manter row.

Whole words means `divide` rules out `divide a` and `ele divide a` but not `dividida` or `subdivide`, and a rejection for one term says nothing about another. Measured with the user's learned layer and pack 0.2.0 on wxgFO_fyfXg: the manter row goes clean, false positives go from 18 to 17, and no hit is lost. The regression bounds do not move, since the fixtures are scored with no learned layer. This closes the open question on rejection by exact text.

## D-028 Unit terms never enter fuzzy matching

Terms of class unidade never enter fuzzy matching. They are matched by the unit rules (D-006) and by exact normalized equality of the term, its aliases and its variants. Measured: with fuzzy on, the canonical `bilhão` matched `milhão` at 83 (applied, 3 rewrites of millions as billions on wxgFO_fyfXg) and the alias `bilhões` matched `milhões` at 85.7. One-letter differences between real words cannot be separated by a threshold.

This supersedes D-021's "it does not affect matching" for one class: `unidade` is the only class the matcher reads. Measured after: wxgFO_fyfXg against pack 0.2.0 goes from 32 to 29 false positives with no hit lost, and `milhões` is not even marked; neither fixture moves against its frozen pack.

## D-029 Low band lower threshold is 70

Low band lower threshold is 70. Measured at 60: 499 and 579 passive marks per fixture; at 70: 113 and 91. Marks are never applied, so the threshold only governs noise in annotations.json.

This supersedes the initial mark threshold of D-011 (60); the apply threshold stays 80. Counted after overlap resolution with the frozen packs, R2Qgz8tFWVI then wxgFO_fyfXg. No bound moves, since marks are never applied.

## D-030 "Already spelled out" means as whole words

The guard that skips a span because the term (or one of its aliases) is already spelled out in it now tests whole-word containment, the rule of D-027, instead of raw substring containment. Measured: `dec` was found inside `deck` and `enterprise value` inside `enterprise valuey`, so both listed variants could never match.

Measured: R2Qgz8tFWVI gains three hits (`autocapex`, `Sabespe`, `segundo trio`) and wxgFO_fyfXg against pack 0.2.0 gains four (`deck` three times, `Enterprise Valuey`). The cost: the substring guard had also been blocking real words that contain the term, and they now come through. The term's own plural is fuzzily corrected to the singular (`dividendos` -> dividendo at 94, eight times on R2Qgz8tFWVI and nine on wxgFO_fyfXg; `valuations` -> valuation three times), which D-020 says is an alias, never a correction; and the TIR variant `tira`, also an everyday word, applies (three times). R2Qgz8tFWVI goes from 147 / 16 to 150 / 26; wxgFO_fyfXg from 107 / 57 to 107 / 70. The plural case is held as a strict expected failure in `tests/test_whole_word_guard.py`.

## D-031 Inflection is the term spelled out; exact beats fuzzy

(a) A word that is an inflection of a term or alias, as the pack's language module defines inflection (D-033), is that term already spelled out: it produces an alias annotation and is never a correction. For pt-BR, `languages/pt_br.py` defines the plural inflections -s, -es, -ão→-ões, -al→-ais, -el→-eis. Measured after D-030: `dividendos → dividendo` ×8 and `valuations → valuation` were applied as corrections, violating D-020. (b) A span that contains an exact match (term, alias, variant, or inflected form) of any term cannot be a fuzzy proposal for another term. Measured: `dividendos e → dividend yield` ×5 over the exact word `dividendos`.

The language module maps a single normalized word to its base forms; a word whose base form is a single-word term or alias is annotated as that alias: exact-only by D-025, and part of D-030's "already spelled out" guard. A word that some term already lists explicitly belongs to that term. (Amended with D-033: the inflection list moved from the core to the pt-BR module; the rule and its measurements are unchanged.) (b) applies to fuzzy proposals only and to other terms only, as worded.

Measured: R2Qgz8tFWVI goes from 150 / 26 to 150 / 18, wxgFO_fyfXg from 107 / 70 to 107 / 58, and wxgFO_fyfXg against pack 0.2.1 from 42 to 25 false positives with no hit lost. All three D-030 hits are kept. Neither fixture gets back to its pre-D-030 false positives (16 and 57): the difference is exactly the variant `tira -> TIR` (twice and once), which is not an inflection. The frozen fixture packs keep it, so D-032's removal of it from packs/ does not reach those numbers. The inflection open question is closed.

## D-032 An ordinary word is not a variant

Curation rule: a variant that is an ordinary Portuguese word does not enter the pack, even if the caption used it for the term. Exact matching on ordinary words is wrong more often than right (`tira → TIR`, `rápido → RAP`, `divide → dividendo`). Such cases wait for a collocation layer (open).

Pack 0.2.2 removes `tira` from TIR, `rápido` from RAP and `valorist` from valuation, and adds the term `market cap` (indicador; aliases `marketcap`, `valor de mercado`). Measured, wxgFO_fyfXg against 0.2.2: false positives go from 25 to 20 and one hit is lost, 15:54 `rápido -> RAP`, the one row the removed variant existed for; `valorist` is still reached fuzzily through `valoristo`. `market -> market share` (three times, in `market cap`) remains: the exact form is the two-word term, which D-031 (b) does not see from inside the one-word span. The frozen fixture packs keep `tira`.

## D-033 Language modules

The core is language-agnostic. Everything language-specific lives in src/transcript_normalizer/languages/<code>.py implementing one protocol: normalize(text) (case, accent folding), inflections(word) -> set of base forms (D-031a), unit_rules() -> list of (pattern, replacement, term) (D-006), sentence_boundaries -> set of punctuation (D-024). A pack declares `language: pt-BR`; the loader selects the module and fails with a clear message if none exists. Adding a language means adding one module and one pack; the core does not change.

`languages/pt_br.py` holds what the core used to know: accent folding to `[a-z0-9$ ]`, the plural inflections of D-031a (now word -> base form, the inverse of the old generation of plurals), the three unit rules of D-006, and `. ? ! ;`. `languages/generic.py` has no inflections and no unit rules, keeps letters of any script, and uses `. ? ! ;`; it is used only when `--allow-generic` is passed for a pack whose language has no module. A pack that declares no language is refused too (D-002). A code maps to a module by name (`pt-BR` -> `pt_br`); a module kept elsewhere is made known with `languages.register`. Each unit rule is a `UnitRule(pattern, replacement, term)` with one optional field, `owns`: the words only that rule may match for its term, which is how `bit` stays EBITDA's everywhere except after a number (D-028). The learned layer has no language, so it compares its own entries by case and spacing only; the pack's language normalizes them when they are loaded.

Measured: every annotation of both fixtures, and of wxgFO_fyfXg against pack 0.2.2 with and without a rejection, is identical field for field before and after. Declaring `language: pt-BR` in the three packs is not a curation change and no bound moves. `tests/test_language_xx.py` runs the core on an invented language, with the generic module and with a module of its own.

## D-034 D-031(b) is overlap, not containment

D-031(b) is overlap, not containment: a fuzzy proposal is dropped when its span overlaps, in either direction, an exact-match span of a different term. Measured: `market` → market share ×3 survived D-031(b) because the fuzzy span sits inside the exact span `market cap`.

Overlap means sharing any token: the fuzzy span inside the exact one, around it, or across part of it. Exact-match spans are found before any fuzzy guess, whether or not they produce an annotation themselves: `market cap` spelled out produces none and still counts. Measured: neither fixture moves against its frozen pack; wxgFO_fyfXg against pack 0.2.2 goes from 20 to 17 false positives with no hit lost. On these fixtures "overlap" and "containment either way" score the same: every proposal whose removal changed a number was inside another term's exact span (`market` in `market cap`, `de Dentes` in `Geração de Dentes`). Overlap drops five more raw proposals that share only part of their span (`o market`, `Valuey, aí`, `o dividend`, `de dividend` twice), each either a low mark or one that overlap resolution already discarded.

## D-035 Out-of-domain silence test

Out-of-domain silence test. Pack financas-ptbr 0.3.3 on a 16-minute street prank video (BIrASod49XY, Tá Gravando, platform caption pt-orig, 463 lines, outdoor noise, overlapping informal speech): 2 applied corrections, both false positives (`Ox` → OPEX, the Northeastern interjection 'oxe'), 1 wrong recognition (`tir uma` → TIR, recognition only, text unchanged), 0 medium-band questions, 27 passive marks. The run is not kept as a fixture (no domain terms to grade).

The number was reserved on 2026-09-29 for this test and is used for it now, on 2026-10-06. The recognition's span is `tir` alone, on the 3:47 line, which reads `tir uma`. It is the canonical name spelled out (D-041), so the text is unchanged. The two corrections are at 2:08 and 2:12 (`Ox, entende nada`). Pack 0.3.4 removes `Ox` from OPEX's variants (D-032: an ordinary word, and the Northeastern `oxe` is common in Brazilian speech). It predates D-005 and keeps `O PX`. Two other short variants from before D-005 remain in the pack, `TR` (the unit tri) and `Lu` (Leo); each should be checked against a silence run before the next pack release (CONTRIBUTING 2.4).

The removal has a cost in domain, measured against the bundled pack (hits / false positives, 0.3.3 → 0.3.4). R2Qgz8tFWVI goes from 145 / 16 to 142 / 16: its three `Ox` → OPEX rows (10:59, 11:03, 11:20) are real, because there the speaker spells the term out ("Ox. O PX. O editor vai escrever aí"). 4tTmY8Buask (108 / 4), 4wCtn8BWR4o (44 / 2) and wxgFO_fyfXg (211 / 10) do not move, and no frozen bound moves. Three hits in domain are traded for two false positives out of it, because out of domain the text is someone else's speech being rewritten. Like `dividendio` and `bicho` (D-046), `Ox` is a garble whose meaning only its context gives, and the collocation layer (open) would have to decide it. With 0.3.4 the silence run applies nothing: the one remaining annotation is the `tir` recognition.

A second measurement, on a clean silence run. The video is yJxxTf0IQC8 (Ciência Todo Dia, on prions): platform caption pt-orig, 428 lines, a single narrator, scripted science speech. Pack fit (D-054) finds 1 term with confidence and applies nothing, which is the intended answer out of domain. With `--force` and pack 0.3.4, the run applied 41 annotations, all false positives. 40 were `proteínas`, `proteína priônica` and `proteína se` → BR Partners, all from the phonetic source (D-050): skeleton `prtns` against `prtnrs`, 91, medium band, applied. One was `trio` → tri, an ordinary word ("trio de irmãs estranhas"). After D-060 (phonetic matches only ask) and pack 0.3.5 (`trio` only in `primeiro/segundo/terceiro/quarto trio`), the forced run applies 0: the 40 phonetic forms are questions in needs-review, and the text is unchanged. The prank run with 0.3.5 and `--force` applies only the `tir` recognition. Neither run is kept as a fixture.

## D-036 The fetch strategy chain

fetch resolves its source in a fixed chain and records which step produced the caption in the legenda.txt header and in meta.yaml: (1) platform caption; on HTTP 429 retry up to 3 times with exponential backoff; (2) if no caption exists or (1) fails after retries, download audio and transcribe locally with faster-whisper; (3) error only if both fail. --caption-only stops after (1); --whisper skips (1). yt-dlp already covers most platforms (TikTok, Instagram, Vimeo, X, Twitch); the tool never depends on third-party converter sites.

"Up to 3" is three attempts in all, the first and two retries, waiting 2s and then 4s: three 429s in a row fall through to step 2. Any failure of step 1 falls through, but only a 429 is retried. Reading the video's metadata comes before both steps and is retried the same way; if it fails, there is nothing to fall through to. The header gains a line `# Etapa: 1, legenda da plataforma` (with the retries, when there were any) or `# Etapa: 2, reconhecimento de fala local (<why>)`, in the header's Portuguese; meta.yaml gains `step`, `step_name`, `retries` and, for step 2, `fallback_reason`. With curl_cffi installed (the ingest extra), yt-dlp is asked to impersonate a browser (`--impersonate chrome`), which is what avoids most 429s; without it yt-dlp runs as before. On a terminal the stages, the transcription progress (by seconds of audio) and the retry countdown are drawn with rich; anywhere else they are plain lines. The model download shows faster-whisper's own progress, announced by a line before it starts.

## D-038 fetch takes a local audio or video file

`transcript-normalizer fetch <path>` accepts a local audio or video file as well as a url. A file has no platform caption, so the D-036 chain starts at step 2: it is transcribed locally with faster-whisper, where it sits, without being copied, and needs faster-whisper but not yt-dlp. The run directory is `runs/<file-stem>/`, D-018's third rule. meta.yaml records `source: file` and the file's absolute path, with `url: null`, and a url run now records `source: url`. The legenda.txt header has `# Arquivo: <file name>` where a video's has `# URL:`, and `# Etapa: 2, reconhecimento de fala local (arquivo local)`. `--caption-only` with a file is an error, since there is no caption to take; so is a path that is neither an existing file nor a url, rather than handing it to yt-dlp.

## D-037 The confirm loop saves as it goes

The confirmation loop writes the learned layer after every answer (atomic write: temp file then rename), so an interrupted session keeps its answers and a rerun only asks what is still pending. Measured: a Ctrl+C during the third fixture's first --confirm run lost every answer given.

Every `y`, `n` and `l` is written before the next question; a skip changes nothing and writes nothing. The temporary file sits beside the learned file, so the rename stays on one filesystem; a failed write removes it and leaves the previous file whole. Ctrl+C ends the loop, pending.txt is rewritten from the answers so far (a variant the loop never reached is `[never asked]`, one skipped is `[skipped]`), the run prints how many answers it kept, and it exits with 130. A finished session still ends with "learned layer written to". A rerun asks nothing already answered, because a confirmed variant now matches exactly, a rejected pair is never proposed, and an alias is recognized.

## D-039 The design is stable for pt-BR finance

Third fixture (4wCtn8BWR4o) changed only the speaker and the recognizer (Whisper medium instead of platform captions) while keeping the vocabulary. Result with pack 0.2.3 and the user's learned layer: 37 applied, 4 asked (1 confirmed, 3 rejected), no new design rule required; every gap was pack data (evitida, dividendio, preço alvo, dívida alíquida). CEMIG misrecognitions (Semig, semiga) appeared with a different speaker and recognizer, so the variants are properties of the recognizers, not of one speaker. The design is considered stable for pt-BR finance: from here, new videos are expected to change packs, not code. Amended by D-040: one matcher gap (exact-over-exact overlap) was found in this fixture.

The four answers are the 2026-09-29 entries of the learned layer: `evitida` → EBITDA confirmed; `saber se` → Sabesp, `dividendio` → dividendo and `preço alto` → preço teto rejected. The two gold rows at 0:19 are status alias (`Dividend Yield`, both words, is in the caption line).

Measured against the frozen pack 0.2.3, no learned layer: 40 in scope, 35 hits, 5 misses, 7 false positives, 13 aliases recognized, 2 wrongly substituted. CEMIG is 21/21. New regression bounds: hits >= 35, false positives <= 7, in scope 40. With the learned layer, false positives drop to 2 and no hit moves. Against packs/ 0.2.4, no learned layer: 38 hits, 2 misses, 6 false positives. `preço alto` → preço alvo is a hit reached fuzzily, not through a variant, and the new term brings one false positive (`preço, você` → preço alvo). R2Qgz8tFWVI (147 / 22) and wxgFO_fyfXg (214 / 18) do not move from 0.2.3 to 0.2.4.

One gap is not in the list: at 0:19 the exact variant `dividend` of dividendo substitutes `Dividend` inside the term `Dividend Yield` spelled out. That is two false positives, two aliases wrongly substituted and two alias misses, with every pack measured. D-034 drops fuzzy proposals that overlap an exact span of another term. It does not drop exact ones.

## D-040 An exact name suppresses a shorter correction overlapping it

An exact term or alias span suppresses any shorter correction of another term that overlaps it, the way D-034 suppresses fuzzy proposals. Measured: at 4wCtn8BWR4o 0:19 the exact variant `dividend` of dividendo substituted `Dividend` inside `Dividend Yield`, twice. That is the gap D-039 names. D-034's check ran only on fuzzy proposals, so an exact variant got through.

A name is the canonical term, an alias (curated or learned), or D-031a's inflection of either. A variant is not a name, so a longer variant does not suppress anything here. "Shorter" counts tokens: the correction's span has fewer words than the name's. An equal or longer one is still left to `resolve_overlaps`. A name of the same term suppresses nothing, since D-030's spelled-out guard already covers that. Unit rules (D-006) run before the dictionary and are unaffected. `dividend` on its own is still corrected.

Measured: 4wCtn8BWR4o against its frozen pack 0.2.3 goes from 35 hits / 7 false positives / 2 aliases wrongly substituted to 35 / 5 / 0. Against packs/ 0.2.4 it goes from 38 / 6 / 2 to 38 / 4 / 0. Its bound moves to false positives <= 5. R2Qgz8tFWVI and wxgFO_fyfXg do not move, against their frozen packs or against 0.2.4. The two 0:19 alias rows are still misses. The term's canonical name spelled out produces no annotation, while an alias row expects an alias annotation.

## D-041 Canonical mentions are recognized

An exact occurrence of a term's canonical name (or its inflected form) produces a recognition annotation (kind alias, rule term:exact) like an alias does; nothing is substituted. Downstream consumers need every mention of a term, not only the misspelled ones. Measured: the two `Dividend Yield` rows at 0:19 in 4wCtn8BWR4o were counted as misses because a correctly spelled term produced no annotation.

The inflected form already produced a recognition under D-031a, and its rule stays `term:alias`. The new annotation is the exact canonical name, compared folded (case and accent), so `Léo` is the name `Leo`. The report lists these under "recognized (not changed)". normalized.txt does not change.

Measured, after overlap resolution, `term:exact` annotations per fixture (frozen pack / packs/ 0.2.4): 4wCtn8BWR4o 43 / 48, R2Qgz8tFWVI 61 / 76, wxgFO_fyfXg 105 / 125. Against the frozen packs, 4wCtn8BWR4o goes from 35 to 37 hits and from 13 to 15 aliases recognized: the two 0:19 rows. Its misses go from 5 to 3 and its false positives stay at 5. Its bound moves to hits >= 37. R2Qgz8tFWVI and wxgFO_fyfXg do not move in hits, false positives or aliases, against either pack. Against 0.2.4, 4wCtn8BWR4o has 40 hits, 0 misses and 4 false positives. One `manter` row of R2Qgz8tFWVI now carries an applied annotation: 7:30 `Léo ruim` is recognized as the term Leo. The gold note says the speaker said "Leo, ruim?". The text is not substituted, but D-026 counts any applied annotation on a manter row, so that fixture's bound allows one touched row. Amended by D-042: recognitions do not touch a manter row, and the bound is back to zero.

## D-042 A manter row forbids corrections, not recognitions

Amends D-026. A manter row forbids an applied correction on its span, not a recognition annotation; recognitions never change text. Measured: `Léo ruim` at 7:30 in R2Qgz8tFWVI was counted as touched once canonical mentions were recognized (D-041).

The evaluator's touched list for a manter row now holds applied corrections only, of any term. Recognitions (kind alias) are not in it. Measured: R2Qgz8tFWVI goes back to no touched manter row, and its bound is zero again. wxgFO_fyfXg keeps its one touched row, 15:54 `divide a`, which is a correction. No fixture moves in hits, misses, false positives or aliases.

## D-043 The curated pack ships in the package

The curated pack ships inside the package at transcript_normalizer/packs/ and is the default when no ./packs/financas-ptbr.yaml exists in the working directory (supersedes the error case of D-017). The root packs/ directory holds only user files: learned layers and user-authored packs.

The root `packs/financas-ptbr.yaml` is no longer a link to the bundled copy. It is gone, so the sdist carries no symlink. Run in the repo, the default is therefore the bundled pack, while the learned layer still sits at `./packs/<pack-name>.learned.yaml`. Tests and `scripts/measure.py` read the bundled path. `packs/README.md` says what the directory is for.

## D-045 fetch prefers the original automatic caption

YouTube publishes the original automatic caption as `<lang>-orig` and an auto-translated track as `<lang>`. fetch must prefer `<lang>-orig`, then a manual `<lang>`, then automatic `<lang>`, and record which track it took in the header and meta.yaml. Measured: for 4tTmY8Buask the `pt` track was a translation (`BTG Pacific`, `Portfólio de canais`, `Ofertas públicas iniciais (IPOs)`), useless as a normalization source.

Within each of the three, an exact code comes before a regional variant (`pt-BR-orig` for `--lang pt`), with the existing warning when there are several. Another language's `-orig` (`en-orig`) says nothing about `pt`, so an automatic `pt` is still taken. It is a translation then, but the chain has no better caption to offer, and the header names the track. The header keeps its line `# Origem da legenda: <source> (<track>)`. The source is `manual`, `automatica` or the new `automatica original`, so a caption from `pt-orig` reads `automatica original (pt-orig)`. meta.yaml gains `caption_track` and `caption_source` when step 1 produced the text. Tested with a fake track list shaped like 4tTmY8Buask's (`pt-orig` alongside translations into `de`, `en`, `es`, `fr`, `pt`, `zh-Hans`). Existing headers are unchanged, since a video without `-orig` takes the same track as before.

## D-044 pt-BR n-grams stop at a comma

Add comma to the pt-BR sentence boundaries (D-024). Measured: the proposals `preço, valor`, `preço, não` and `isso, Amigo` crossed a comma in 4tTmY8Buask.

This supersedes D-024's "a comma does not count" for pt-BR only. The generic language module keeps `. ? ! ;`. A comma inside a token is still part of it, so a decimal comma (`11,5%`) and a decimal point (`6.7`) are both unaffected. A caption break is still not punctuation (D-007). No term, alias or variant in any pack contains a comma.

Measured on the 4tTmY8Buask run with the bundled pack 0.2.4, no learned layer: eight proposals crossed a comma. Three were medium band and applied (`preço, valor` and `preço, não` → preço alvo at 85 and 84, `isso, Amigo` → CEMIG at 80), and five were low marks. None is left. Applied annotations go from 46 to 43 and corrections from 7 to 4. That run's caption is the translated `pt` track (`automatica (pt)`) D-045 is about, fetched before D-045. The fixtures do not move against their frozen packs, so no bound changes. Against 0.2.4, 4wCtn8BWR4o goes from 4 to 3 false positives (`preço, você` → preço alvo is gone), and R2Qgz8tFWVI and wxgFO_fyfXg do not move. No hit is lost anywhere.

## D-046 Fourth fixture: a new sector, and one misrecognition with two meanings

Fourth fixture, new sector (investment bank), same speaker as the third. With pack 0.2.4 the tool found 4 of 81 expected corrections and produced 8 false positives; the 77 misses were all missing pack data, dominated by one company name in 18 misrecognitions. First case of one misrecognition meaning two different terms by context (`dividendio`: dividend yield in 4wCtn8BWR4o, dividendo mínimo in 4tTmY8Buask), recorded as the concrete motivation for the collocation layer (open).

The caption is the platform's `pt-orig` track (D-045). The gold has 121 rows: 79 conferido, 36 alias, 4 certo, 2 manter. 83 rows expect a correction, and two of those have no term (`realo`, `portas` → pelo menos), so 81 are in scope with the 36 alias rows: 117. The 40 hits are the 36 alias rows plus 4 corrections (`dividendield`, `freeat` twice, `SEMIG`). The company is BR Partners: 50 rows, 18 distinct forms after folding. Among the misses, "pack data" includes data that was there but wrong: `dividend` was a variant of dividendo, while this gold has it as dividend yield. Also counted are five forms D-005 and D-032 keep out of any pack (`RO`, `sel`, `Port`, `porta`, `portas`). The touched manter row is 19:46 `bicho`, then an EBITDA variant. Bounds against the frozen pack 0.2.4: in scope 117, hits >= 40, false positives <= 8, one touched manter row.

Pack 0.3.0 adds the conferido terms of the gold: BR Partners, drawdown, small cap, Décio Bazin, M&A, IPO, Benchimol, BTG Pactual, Adapta Valuer, Auren, securitizadora and commodities. It also adds payout, LPA, DPA, P/VP (alias P/B) and partnership, and `Selica` for Selic. It removes `bicho` from EBITDA and `dividend` from dividendo (D-032). `dividendio` stays on dividend yield, with the ambiguity noted in the pack. Two variants of the gold stay out under D-032: `apos`, which folds to `após`, and `Portes`, the plural of `porte`.

Measured against 0.3.0, no learned layer (hits / misses / false positives):

| fixture | 0.2.4 | 0.3.0 |
|---|---|---|
| 4tTmY8Buask | 40 / 77 / 8 | 103 / 14 / 10 |
| 4wCtn8BWR4o | 40 / 0 / 3 | 40 / 0 / 15 |
| R2Qgz8tFWVI | 147 / 20 / 22 | 146 / 21 / 28 |
| wxgFO_fyfXg | 214 / 11 / 18 | 211 / 14 / 19 |

The removals cost four hits elsewhere. R2Qgz8tFWVI 28:44 `sobre bicho` is EBITDA there, a second context-dependent misrecognition. wxgFO_fyfXg 33:17, 33:25 and 39:32 have gold rows `dividend` → dividendo, inside spans the same gold also marks `dividend y` → dividend yield.

Most of the new false positives are curated variants reaching ordinary words fuzzily at 80 to 86. `Portizar` reaches `aportar` (×5) and `amortizar`. `Portess` reaches `por essa`, `por esse` and `por três`, `Portudo` reaches `oportuno`, and `Portinas` reaches `portas`. `Selica` reaches `eólica`, `securizadora` reaches `seguradora`, `Dio Bazin` reaches `do bazinho`, and `adapta Vala` reaches `adaptar a`. `commodit` corrects the singular `commodity` (×2) to the plural. Seven of 4wCtn8BWR4o's twelve new false positives are spellings of the channel's tool (`AdaptaValor`, `adaptavala`, `DAPTA Valdre`), likely gaps in that fixture's gold, not checked. Only the frozen packs are bounds, so none of this blocks.

## D-047 Fuzzy from a curated variant needs 85

A fuzzy match reached from a curated variant is applied only at 85 or above. A match reached from the canonical term keeps D-011's 80. Below its threshold a variant's match is a low mark: it keeps its real score and is never applied. Measured on D-046: the variants of 0.3.0 reached ordinary words at 80 to 84 (`Portizar` → `aportar`, `Portess` → `por essa`, `Selica` → `eólica`).

Two rules were measured on all four fixtures with the bundled pack 0.3.0, before anything changed. A: curated variants match by exact equality only, so fuzzy runs from the canonical term alone. C: fuzzy from a variant requires 85. Hits / false positives:

| fixture | 0.3.0 | A | C |
|---|---|---|---|
| 4tTmY8Buask | 103 / 10 | 98 / 8 | 103 / 7 |
| 4wCtn8BWR4o | 40 / 15 | 40 / 7 | 40 / 9 |
| R2Qgz8tFWVI | 146 / 28 | 146 / 14 | 146 / 17 |
| wxgFO_fyfXg | 211 / 19 | 206 / 8 | 211 / 9 |
| total | 500 / 72 | 490 / 37 | 500 / 42 |

The same, after the gold fixes below:

| fixture | 0.3.0 | A | C |
|---|---|---|---|
| 4tTmY8Buask | 103 / 10 | 98 / 8 | 103 / 7 |
| 4wCtn8BWR4o | 45 / 7 | 42 / 4 | 44 / 4 |
| R2Qgz8tFWVI | 146 / 28 | 146 / 14 | 146 / 17 |
| wxgFO_fyfXg | 211 / 19 | 206 / 8 | 211 / 9 |
| total | 505 / 64 | 492 / 34 | 504 / 37 |

C is adopted. It removes 27 false positives for one hit, while A removes 30 for thirteen, so the two are not close. A loses hits that only a variant reaches fuzzily: `Waren Buff`, `esse mig`, `sem mig`, `ebítica`, `valorist`, `freeat` twice, `Adaptavalda`, `adaptavala` and `adaptar a válvula`, plus three more on 4tTmY8Buask. C loses one hit, 4wCtn8BWR4o 4:54 `adaptar a válvula`, reached at 80 from `adapta Vala`. Ranking is by the demoted score, so a variant's match under 85 does not win a span from a better proposal. Two tests now hold the old threshold on purpose: the confirmation-loop tests script answers against R2Qgz8tFWVI's four-variant CEMIG group, and C leaves two of those four.

Gold fixes, authorized. In wxgFO_fyfXg the rows `dividend` → dividendo at 33:17, 33:25 and 39:32 are dropped. Those spans are dividend yield, and the dividend yield rows stay. In 4wCtn8BWR4o there are five conferido rows for the channel's tool, Adapta Valuer, each checked on its line: 1:04 `Adaptavalda`, 4:54 `adaptar a válvula` ("pra você que tem acesso [à Adapta Valuer], temos agora essa nova aba"), 5:03 `DAPTA Valdre`, 18:16 `AdaptaValor`, 18:42 `adaptavala`. Against the frozen pack, wxgFO_fyfXg goes from 107 / 58 to 104 / 67 from the gold alone. The evaluator scores proposals before overlap resolution, so each dropped row's `dividend` correction also brings its overlapping `o dividend`, `de dividend` and `dividend y`. C then takes it to 104 / 59.

Pack 0.3.1 adds `commodity` as an alias of commodities: the singular is not an error. 4wCtn8BWR4o loses its two `commodity` → commodities false positives.

Bounds, frozen packs (hits / false positives): R2Qgz8tFWVI 150 / 14 (was 18), 4wCtn8BWR4o 37 / 4 with 45 in scope (was 37 / 5 with 40), wxgFO_fyfXg 104 / 59 with 222 in scope (was 107 / 58 with 225, the gold change). 4tTmY8Buask does not move. Bundled 0.3.1: 4tTmY8Buask 103 / 7, 4wCtn8BWR4o 44 / 2, R2Qgz8tFWVI 146 / 17, wxgFO_fyfXg 211 / 9.

## D-048 The evaluator scores what is applied

The evaluator scores only the annotations that survive `resolve_overlaps`, exactly the set rendered into normalized.txt. Before, it scored every proposal, so a proposal that lost its span to a longer or better one counted as a false positive, though it never reached the output. Measured: wxgFO_fyfXg went from 58 to 67 false positives when D-047 dropped three gold rows. Each dropped row's `dividend` correction also brought its overlapping `o dividend`, `de dividend` and `dividend y`.

The rule applies everywhere `evaluate` is called: the regression test, `scripts/measure.py`, and the manter check, which now sees only the resolved set too. A proposal that loses its span is neither a hit nor a false positive. This replaces the "as exp2 did" scoring that `evaluate_fixture` and the regression test had kept. Matching and its numbers are unchanged.

Measured, hits / false positives, before → after:

| fixture | frozen | bundled 0.3.1 |
|---|---|---|
| 4tTmY8Buask | 40 / 8 → 40 / 6 | 103 / 7 → 102 / 6 |
| 4wCtn8BWR4o | 37 / 4 → 37 / 4 | 44 / 2 → 44 / 2 |
| R2Qgz8tFWVI | 150 / 14 → 150 / 14 | 146 / 17 → 146 / 15 |
| wxgFO_fyfXg | 104 / 59 → 104 / 53 | 211 / 9 → 211 / 9 |

What went out: `de dividend` → dividendo ×2 on 4tTmY8Buask (both packs), `bit` → EBITDA ×2 on R2Qgz8tFWVI with 0.3.1, and on wxgFO_fyfXg (frozen) `dividend y` ×3, `de dividend` ×2 and `o dividend`. 4tTmY8Buask with 0.3.1 loses one hit, which the output never had: at 3:34 the rendered annotation is `dividend` → dividendo (94, from the canonical term), which wins the span from the proposal for dividend yield. That annotation is now the false positive. No manter count moves. New bounds: 4tTmY8Buask false positives <= 6, wxgFO_fyfXg <= 53.

## D-049 The spelled-out guard means covered, not contained

D-030's guard skips a candidate when an exact name of its term (canonical, alias, or D-031a's inflection of either) is spelled out in the span. It now skips only when that exact span covers the whole window, equal or larger. A window that is longer and merely contains the name stays eligible, and the longer span wins in overlap resolution. Measured: in wxgFO_fyfXg the alias `dividend` (0.3.2) blocked the variant `dividend y` → dividend yield three times.

"Covers" is positional, over the exact-name spans D-040 already records: the window's tokens lie inside an exact name of the same term. A window shorter than a name is now skipped too (`Value` inside `Enterprise Value`). Before, it was not, because it does not contain the whole name. A longer fuzzy window around a name (`o Enterprise Value`, 94) becomes a proposal again. It loses its span to the name's own recognition (100, D-041) in overlap resolution, so neither normalized.txt nor the scores (D-048) see it.

Measured with the old gold, before → after (hits / false positives). With the bundled 0.3.2, wxgFO_fyfXg goes from 208 / 9 to 211 / 9: the three `dividend y` and `dividend y build` rows. 4tTmY8Buask goes from 102 / 4 to 104 / 4, through variants that contain an alias: `Dio Bazin` (alias `Bazin`) and `B Partners` (alias `Partners`). R2Qgz8tFWVI and 4wCtn8BWR4o do not move, and no fixture moves against its frozen pack. The strict expected failure of 0.3.2 in tests/test_inflection.py is a test again.

Gold, authorized, fixtures/4tTmY8Buask/gold.csv. The rows 3:34 and 9:19 `dividend` are now alias rows of dividend yield, with `correct` equal to `wrong`: the speaker's short form, and the text stays. Two conferido rows for BR Partners are added, each checked on its line: 7:48 `A Partens` ("A Partens, em 2025, ano passado, ela terminou o ano") and 11:39 `partner` ("eu tenho partner e é minha segunda maior posição de small caps"). After the gold change: frozen 0.2.4 has 119 in scope, 40 hits and 6 false positives, and its bound moves to 119 in scope. Bundled 0.3.2 has 106 hits and 4 false positives, with 38 aliases recognized.

## D-050 A phonetic skeleton is the fourth matching source, for names

A pt-BR consonant-skeleton similarity (drop vowels, collapse doubles, s/c/ç→s, g/j→j, l/u before consonant→u) runs as a fourth matching source, only for terms of class companhia and pessoa, only on spans the exact and fuzzy sources did not resolve, threshold 85 on rapidfuzz ratio of skeletons, always medium band (applied flagged, asked in --confirm), never high. Measured on a BR Partners hold-out (exp3): recovers 6 of 18 misrecognized forms and 25 of 50 rows for 4 false positives across four fixtures, two of which were real mentions missing from the gold. Epitran por-Latn recovered nothing beyond the baseline (vowel differences dominate IPA distance). Closes D-010.

The rule is `term:phonetic`. The skeleton lives in `languages/pt_br.py` as `skeleton(text)`, part of the language protocol (D-033): a module sets it to a function or to `None`. The generic module sets `None`, so the source is off there. The vocalized l/u is written `w`, so the vowel pass that follows keeps it. The source compares 1- and 2-word windows, within sentences (D-024, D-044), against the canonical names and aliases of companhia and pessoa terms whose skeleton has 4 letters or more. A window is skipped if any applied annotation of the other sources overlaps it, after overlap resolution. A rejected pair is not proposed. One addition to exp3: a 2-word window is proposed only if it scores higher than each of its words alone. Otherwise a word that adds nothing to the skeleton rides along and is replaced with the name: `a Portness`, or `Portinas caiu` (`caiu` folds into the trailing `s`). The fixture numbers are the same with and without it.

Measured, hits / false positives, before → after:

| fixture | frozen | bundled 0.3.2 |
|---|---|---|
| 4tTmY8Buask | 40 / 6 → 40 / 6 | 106 / 4 → 108 / 4 |
| 4wCtn8BWR4o | 37 / 4 → 37 / 4 | 44 / 2 → 44 / 2 |
| R2Qgz8tFWVI | 150 / 14 → 150 / 15 | 145 / 15 → 145 / 16 |
| wxgFO_fyfXg | 104 / 53 → 105 / 55 | 211 / 9 → 211 / 10 |

Gained: 4tTmY8Buask 7:48 `A Partens` and 11:39 `partner e` → BR Partners (90), the two rows D-049 added. wxgFO_fyfXg 36:41 `Warn Buffet` → Warren Buffett (100) with the frozen pack, the hit D-024 lost. Added false positives: `para três` (R2Qgz8tFWVI) and `por três` (wxgFO_fyfXg) → BR Partners with 0.3.2 (`prtrs` against `prtnrs`, 90). With the frozen packs, `como gestão` (R2Qgz8tFWVI) and `mesmo jeito` ×2 (wxgFO_fyfXg) → CEMIG (88). Both go through the alias `Cemig GT`, whose skeleton is four letters (`smjt`). The frozen bounds move with the measurement: R2Qgz8tFWVI false positives <= 15, wxgFO_fyfXg hits >= 105 and false positives <= 55. Three tests account for the new medium-band proposals. The confirmation-loop tests turn the source off, as they hold D-047's threshold, to keep their scripted group.

Amended: the minimum skeleton length is 5, not 4. A name, alias or window whose skeleton has fewer than 5 letters is skipped. Measured: the three CEMIG false positives with the frozen packs (`como gestão` in R2Qgz8tFWVI, `mesmo jeito` ×2 in wxgFO_fyfXg) all went through the alias `Cemig GT`, whose skeleton `smjt` has four letters. At 5 they disappear and no gain is lost. `Warn Buffet` stays (frozen wxgFO_fyfXg). `Partens` and `partner` stay with 0.3.2, at 108 / 4, the pack where the phonetic source produced them; since 0.3.3 they are variants. Hits / false positives at 4 → 5: frozen R2Qgz8tFWVI 150 / 15 → 150 / 14 and wxgFO_fyfXg 105 / 55 → 105 / 53. Nothing else moves, frozen or with the bundled 0.3.3 (4tTmY8Buask 108 / 4, 4wCtn8BWR4o 44 / 2, R2Qgz8tFWVI 145 / 16, wxgFO_fyfXg 211 / 10). The bounds go back to false positives <= 14 and <= 53. With 0.3.3 the source's two remaining false positives are `para três` and `por três` → BR Partners (`prtrs`, five letters).

## D-051 Interactive mode

Running `transcript-normalizer` with no arguments on a TTY opens an interactive menu; every menu action calls the same functions the subcommands call, so nothing is reachable only through the menu, and scripted use (subcommands, non-TTY) is unchanged. Built with rich only; no new dependency.

The menu, in `interactive.py`, runs each action through `cli.main` with the argument list a person would type:

1. Fetch: `fetch <path>` for a local file. For a url, `fetch <url> --caption-only` first, and if that fails, the question "run with local speech recognition? [y/n]", then `fetch <url> --whisper`. On the command line the chain falls through on its own (D-036). The menu asks first, because the next step downloads the audio and can take minutes.
2. Normalize a run: the `list` table, numbered, then `<run>/legenda.txt`, then "review pending now?" if needs-review/pending.txt exists.
3. Review pending: `normalize <run>/legenda.txt --confirm`.
4. Show a run's outputs: the run's files and the first 20 lines of normalized.txt.
5. List runs: `list`.
6. Help: one paragraph, pointing to docs/GUIDE.md.
7. `q` quits.

After each action the menu comes back. `q`, end of input or Ctrl+C at the menu quits. An error, an exit code other than 0, or an exception in an action is printed in the menu, never as a traceback. "TTY" means both stdin and stdout are terminals. Without them, no arguments is argparse's usage error, exit 2, as before. rich is optional here as it is for fetch: without it the menu is plain text. Tested with scripted stdin and the fake yt-dlp and transcriber: fetch, normalize, review; a bad url; no caption, then local speech recognition; show, list, help; an unexpected exception; `q`, and end of input.

Amended: menu and help layout. Each menu item shows a one-line description beside it, aligned, inside the panel. A blank line and a dim rule come between an action's output and the next menu. Help is one text in sections, like `gh help`: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE. It has one entry per line, aligned, and plain text. `transcript-normalizer help`, the top-level `--help` and `-h`, and menu item 6 all print it, and menu item 6 runs `help` through `cli.main` like every other action. A command's own `--help` stays argparse's list of options. The MENU section gives each action its equivalent command, in backticks, on a line under its description. In the menu, `?` and a number prints that action's entry alone. Help, show and `?N` wrap at the terminal width with a margin of 2. A wrapped line stays under its column: a description under its description, a caption line under its text after the timestamp. A backticked command is never split. The help lives in `helptext.py`, which also holds the menu's items, so the two cannot drift apart.

## D-052 Distribution tiers and the user data directory

Two artefacts from one codebase. (1) The Python package: `pip install transcript-normalizer` (core: rapidfuzz, pyyaml; a few MB) for programs such as valuation-simulator, plus the [ingest] extra for fetch. (2) A standalone executable per platform, built with PyInstaller on each tag by GitHub Actions and attached to the GitHub Release, for people who will not use pip; it opens the interactive menu. The executable is never a dependency of anything. Two builds: `lite` (fetch with platform captions only, ~30 MB) and `full` (local speech recognition included, several hundred MB). When running frozen (PyInstaller), the working directory is not the executable's folder: runs/ and packs/ live under the user's documents directory (`~/Documents/transcript-normalizer/` or the platform equivalent via platformdirs), created on first run, and the menu prints that path on its first screen.

`runs.base_dir()` is the one place that decides. Outside the executable it is the current directory, as D-015 and D-017 say, and nothing is created. Frozen (`sys.frozen`, which PyInstaller sets), it is `platformdirs.user_documents_dir()/transcript-normalizer/`, with `runs/` and `packs/` created on first use. `TRANSCRIPT_NORMALIZER_HOME` moves it, for the tests and for a portable copy. `runs_root()` and `packs_root()` build on it, so fetch, normalize, list, the learned layer and the menu all follow without further change. The default pack is still the bundled one (D-043), unless the data directory's `packs/` holds a `financas-ptbr.yaml`. platformdirs joins the core dependencies: it is small and pure Python. The menu's first line is `your files: <path>` when frozen, and `working in: <path>` otherwise.

Amended: no ffmpeg is bundled. Nothing in the project invokes an ffmpeg binary. `fetch` keeps the audio as it was downloaded, and faster-whisper decodes it through PyAV, which carries its own FFmpeg libraries. The release workflow no longer downloads an LGPL ffmpeg build. `packaging/entry.py` no longer puts the bundle on PATH. docs/THIRD_PARTY.md keeps only the Python packages the executables carry, and the note that the model weights are not bundled.

## D-053 A prompts adapter, and a menu with less friction

Interactive input (arrow-key lists, multi-select) lives behind a prompts adapter with two implementations: questionary when installed and stdout is a TTY, plain numbered/lettered text otherwise. The core never imports either. Tests drive the plain implementation; a few tests patch questionary's ask functions.

The adapter, `prompts.py`, asks four kinds of question: `select`, `multi_select`, `confirm` and `text`. Each shows a hint and a key legend. Empty input or Esc goes back, and `?` explains each option and asks again. On `text`, `?` explains only as the whole answer, since URLs contain `?`. On `confirm`, empty input takes the default rather than going back. In plain text a select option can carry its own key (`q` for Quit), and a multi-select takes letters, with `-` for none. rich and questionary form the `[menu]` extra. `[captions]` includes it, so `[ingest]` and both executables do too.

The menu opens with the version, where the files are, the typical flow and the keys. Runs are picked from a list (id, date, title). Each step offers the next as "Next: …?", with yes as the default. It still runs everything through `cli.main`, using two new options of `normalize` that the command line has too. `--summary` prints three counters instead of the report (report.txt is unchanged). `--review` is the review one term per screen: a multi-select of the doubtful forms (selected forms are confirmed, the rest rejected), then a second multi-select of which of those are aliases. Esc leaves the term pending. The learned layer is written after each term (D-037). `--confirm` keeps the per-form loop of D-019. Colour goes through rich, one colour per meaning (yellow: needs you; green: done; red: errors; blue: paths and terms; dim: hints; bold: titles and counters), and only on a terminal. In the `lite` executable, a fetch that would need local speech recognition says that this build cannot transcribe audio and points to the full build, instead of giving pip advice. The `?N` of D-051's amendment is gone: `?` on any question does its job. Built and run locally as a `lite` executable on Linux: the arrow-key menu, the version and the colours all show up frozen.

## D-054 A pack applies only where it fits

Before anything is applied, normalize counts the distinct terms with at least one high-band annotation, after overlap resolution. Fewer than 3, and it prints "pack <name> does not seem to fit this transcript (N terms found); nothing applied. Use --force to apply anyway.", writes a normalized.txt identical to the input and an empty annotations.json, and asks nothing. `--force` applies anyway. The silence run of D-035 is the reason: a pack applied to someone else's speech finds the odd short form, and every correction it makes there is a false positive.

Unit rules do not count: numbers and units turn up in any field. Recognitions count as well as corrections: a term spelled right is as much evidence that the video is about the domain as a term garbled. The check is in `core/fit.py`; the regression test and the evaluator do not go through it, so no bound moves. The menu asks "What is this video about?" before it normalizes: a list of the installed packs (bundled, then packs/, D-055) and "none / another area", which normalizes nothing and says so. A review started from the menu uses the one installed pack, or asks which.

Measured, distinct high-band terms per caption (`scripts/measure.py runs/BIrASod49XY/legenda.txt`):

| caption | frozen pack | bundled 0.3.4 | fits |
|---|---|---|---|
| 4tTmY8Buask | 6 | 23 | yes |
| 4wCtn8BWR4o | 11 | 15 | yes |
| R2Qgz8tFWVI | 29 | 35 | yes |
| wxgFO_fyfXg | 18 | 44 | yes |
| BIrASod49XY (prank, D-035) | - | 1 | no |

The prank's one term is the `tir` recognition of D-035. The closest fixture is 4tTmY8Buask against its frozen 0.2.4 at 6; with the pack users run, the lowest is 15. Counting corrections only would also separate them (bundled: 15, 4, 26, 28 against 0), but 4wCtn8BWR4o, a video in the domain whose terms are mostly spelled right, would sit at 4, one away from the threshold. The threshold of 3 is not calibrated beyond these five captions; a short clip in the domain can fall under it, which is what `--force` is for.

## D-055 Packs live in their own repository

Domain packs live in github.com/Tatiwel/transcript-normalizer-packs, one directory per pack with `pack.yaml`, `README.md` and `MAINTAINERS`. The maintainers of a pack review its pull requests; the engine repository never edits pack content. An `index.json` at the root names every pack: name, version, language, description, path and the sha256 of its file. The bundled financas-ptbr stays as the offline default (D-043), a copy taken from that repository at a released version.

`transcript-normalizer pack list` reads the index from https://raw.githubusercontent.com/Tatiwel/transcript-normalizer-packs/main/index.json. `pack install <name>` downloads the pack into the user's `packs/` as `<name>.yaml` and writes it only if its sha256 matches the index. `pack update` installs a newer version of each pack installed that way. urllib only, so no new dependency. `--index URL` or `TRANSCRIPT_NORMALIZER_PACKS_INDEX` points elsewhere, and a `file://` index works the same, which is what the tests use (tests/test_registry.py).

`packs/installed.json` records the version and sha256 of what install wrote. A `packs/<name>.yaml` that does not match it was edited here or written by the user: `update` leaves it alone, and `install` replaces it only with `--force`. A pack name must be lowercase letters, digits and hyphens, so an index cannot make install write outside packs/. An installed pack is in `packs/`, so it wins over the bundled one of the same name (`default_pack`, D-017), it is offered by the menu's "What is this video about?" (D-054), and its learned layer is the same `packs/<name>.learned.yaml` as before.

## D-056 Contributing what the review taught

`transcript-normalizer pack propose [--pack name]` reads the learned layer of the pack (the default pack without `--pack`) and keeps what the pack does not already have: confirmed variants and learned aliases whose form the term does not list, and every rejection, since a pack has no place for "never this" and its maintainers may still want to know. It prints them as a diff, one line per entry: term, form and decision (`+ variant`, `+ alias`, `- rejected`), never the transcript or a timestamp. It asks to confirm, default no. On a yes it writes `contributions/<pack>-<date>.yaml` (the pack, its version, the engine version, the date, the entries) under the working directory, or the data directory in the executable (D-052), and opens a prefilled issue on the packs repository (D-055) with that file's content, through `webbrowser.open`. Where there is no browser it prints the link. A file too long for a link (8000 characters) gets an issue that asks for the file to be attached. In the menu, after a review, "Contribute what you taught the tool? [y/N]" runs it, if the learned layer has anything to give.

The tool sends nothing itself: the user reads the issue in the browser and submits it, under their own GitHub account. A one-click push, where the tool submits for the user, needs a server-side endpoint that holds a GitHub token, because a token in the executable is a token anyone can extract. That is deferred. The maintainers of the pack decide what enters it, by CONTRIBUTING 2.4's curation rules, which the learned layer does not apply (2.6).

## D-057 yt-dlp runs in-process

yt-dlp is called in-process through its Python API (yt_dlp.YoutubeDL), never as a subprocess, so the same code runs in the repository and inside a frozen executable. Error messages from step 1 are shown verbatim before any fallback message; the lite-build notice appears only when step 2 is actually needed.

The bug: fetch ran `sys.executable -m yt_dlp`. In a PyInstaller build `sys.executable` is the executable itself, so the command re-entered this CLI with `-m yt_dlp`, and argparse failed with `invalid choice: 'yt_dlp'`. It was seen on a real Windows machine with 0.4.1-windows-lite, and reproduced on Linux with a lite build of 0.4.2. The chain then fell to step 2, and the menu printed the lite-build notice in place of the cause.

`fetch.youtube_dl(params)` is now the one place yt-dlp is opened. The old command line maps onto YoutubeDL options:
- `--dump-single-json` is `extract_info(url, download=False)`;
- `--write-subs` and `--write-auto-subs` are `writesubtitles` and `writeautomaticsub`;
- `--skip-download`, `--sub-langs` and `--output` are `skip_download`, `subtitleslangs` and `outtmpl`;
- the audio's `-f` and `--no-part` are `format` and `nopart`;
- `--impersonate chrome` is `impersonate`, when curl_cffi is installed.

A silent logger keeps yt-dlp from printing its own copy of an error. The error comes back as an exception, whose message is shown as it is, and whose `HTTP Error 429` triggers the retries of D-036. In the lite build, step 2 raises the lite notice before anything else, and only when the chain reaches step 2. The menu no longer runs `--caption-only` there and guesses from the exit code: it runs the plain chain, so step 1's own error comes first. The test fake is shaped like the API (`open(params)` returning an object with `extract_info` and `download`), and a test fails if fetch starts a subprocess.

`fetch --check` prints yt-dlp, curl_cffi and faster-whisper, each with its version or "not installed", and exits 0. The versions are read from the modules, since a frozen build may lack the package metadata. The release workflow's smoke test runs it: yt-dlp must be there in both flavors, faster-whisper only in `full`. Then it runs `fetch --list https://youtu.be/4wCtn8BWR4o`. A track list or an HTTP 429 passes, and so does YouTube's bot check: datacenter runners get it, and it still comes from yt-dlp. A traceback or an argparse error fails. Checked locally against a lite executable built from this code: `fetch --check`, `fetch --list` and a full caption download (`pt-orig`, 511 lines) all work, where the 0.4.2 build failed with `invalid choice: 'yt_dlp'`.

## D-058 Executables are built from the lock

The release workflow builds each executable from uv.lock (`uv sync --locked --no-dev --no-editable --extra <extra>`, then PyInstaller on top), never from a fresh resolve. pyproject.toml gives faster-whisper and av upper bounds, so a fresh resolve cannot pair them wrongly either. The full executable proves, before release, that it can decode audio.

The bug: in 0.4.3's full build, step 2 failed with `TypeError: open() got an unexpected keyword argument 'metadata_errors'`. It was seen by a fresh Windows user. The workflow installed with `uv pip install ".[ingest]"`, which ignores the lock and took the newest of everything. That paired faster-whisper 1.2.1, which calls `av.open(..., metadata_errors=...)`, with av 19.0.1, which no longer accepts the argument. The lock has av 18.1.0. Reproduced locally on Linux, building as the 0.4.3 workflow did: the full executable failed the same way transcribing a two-second WAV with the `tiny` model. Built from the lock as the workflow now does, the same executable decodes it, `fetch --selftest-audio` reports 32000 samples, and the transcription finishes.

The bounds are `faster-whisper>=1.0,<1.3` and `av>=11,<19`. A hidden `fetch --selftest-audio FILE` decodes FILE with faster-whisper's `decode_audio` and prints the sample count: no model, no network. The release workflow runs it inside each full executable on `tests/data/two-seconds.wav` (a 440 Hz tone, 16 kHz, 2 s) and expects 32000.

Field fixes in the same release, from the same user:
- `?` on a menu question prints each option's help entry, with its command (help's MENU section). It used to print the one-line descriptions the menu already showed, which looked like a re-render. Tested against real questionary through prompt_toolkit's pipe input, not only the fake.
- Step 1's failure on the menu's path is said in plain words, with no flags named: "YouTube is limiting downloads right now (HTTP 429).", "This video has no caption.", or yt-dlp's own message for anything else. The question about local speech recognition follows. When the menu moves on to step 2, the second fetch skips the title, channel and duration (a hidden `--no-video-info`).
- The backoff of D-036 waited, but the rich countdown was transient: only "retrying now" stayed on screen, which read as three attempts back to back. The countdown now stays ("retrying in 4 s", then "waited 4 s, retrying"). A fake-clock test checks that the attempts start at 0, 2 and 6 s.
- Hugging Face is silenced before the model loads: `HF_HUB_DISABLE_SYMLINKS_WARNING=1`, `HF_HUB_VERBOSITY=error`, and its UserWarnings filtered. A model not yet in the cache is downloaded by fetch itself, with one line of its own, "downloading the speech model (about 1.5 GB, first time only)…", and a rich progress bar on a terminal (none in a pipe). faster-whisper's own download shows nothing.

## D-059 A failed attempt does not break the next one

A run directory left by a failed attempt must not break the next one. Before step 2's audio download, fetch deletes any `audio.*` and `*.part` in the run directory and passes yt-dlp `continuedl: False`. If a download still answers HTTP 416, it deletes the partial files and retries once from zero. If fetch fails at both steps, it removes the files it created in this attempt; meta.yaml stays only if it existed before. Seen on Windows: an `audio.m4a.part` left by the 0.4.3 crash made every 0.4.4 retry fail with "HTTP Error 416: Requested range not satisfiable".

"Created in this attempt" is measured. fetch notes what the run directory held before it starts, and on failure removes everything that was not there. If the attempt created the directory and it is left empty, the directory goes too. The same applies when `--caption-only` fails. A failure inside step 2 other than a FetchError is now reported in the list of failures and taken back the same way, instead of escaping as a traceback. That was what 0.4.3's `TypeError` from the decoder did. The test fake can leave a `.part` file and answer 416, and the tests cover a stale `.part`, one 416, two 416s, both steps failing next to an earlier meta.yaml, and a transcription crash.

In the same release, the executable's entry point reconfigures stdout and stderr to UTF-8. yt-dlp's messages carry curly quotes ("you’re"). Written in cp1252 through a pipe on Windows and read back as UTF-8, as GitHub's log did, they showed as a replacement character. A Windows console already receives Unicode from Python, so nothing changes there.

## D-060 Phonetic proposals ask, never apply

Phonetic matches are proposals only: they go to the confirm queue and are never substituted until the user confirms the form (which makes it an exact variant). Amends D-050. Measured: three independent runs produced phonetic false positives (`para três` → BR Partners in R2Qgz8tFWVI and `por três` → BR Partners in wxgFO_fyfXg, both with the bundled pack; `proteínas` → BR Partners ×40 in a forced out-of-domain run, D-035), while every phonetic hit in the fixtures is now covered by a curated variant.

The phonetic source's annotations now carry a band of their own, `ask` (`BAND_ASK`). It is not one of the applied bands, so nothing is substituted in normalized.txt and nothing counts as a hit or a false positive. It is one of the question bands (`QUESTION_BANDS`, with medium), so the report lists it under "to confirm", needs-review/pending.txt lists it, and `--confirm`, `--review` and the menu ask about it. A confirmed form is a learned variant, and from then on it is matched exactly, in the high band (D-013). A rejected form is never proposed again. Pack fit (D-054) counted only the high band already, so it does not move.

Measured, hits / false positives before → after, against the bundled pack 0.3.4: R2Qgz8tFWVI 142 / 16 → 142 / 15 (`para três` is gone), wxgFO_fyfXg 211 / 10 → 211 / 9 (`por três` is gone), 4tTmY8Buask 108 / 4 and 4wCtn8BWR4o 44 / 2 unchanged. Against the frozen packs, one hit is lost: wxgFO_fyfXg 36:41 `Warn Buffet` → Warren Buffett, which the frozen 0.1.0 pack does not list and only the phonetic source reached (105 → 104). The bundled pack lists `Warn Buffet` as a variant, so it is still a hit there, and that bound moves to hits >= 104. No other fixture, frozen or bundled, loses a hit. "Every phonetic hit is covered by a curated variant" holds for the bundled pack; for the frozen ones it is that single row.

Pack 0.3.5 in the same release replaces the variant `trio` of tri with `primeiro trio`, `segundo trio`, `terceiro trio` and `quarto trio`. The garble of the unit of time matches only in its phrase, because alone `trio` is an ordinary word (D-032). R2Qgz8tFWVI 8:24 `segundo trio` → tri is still a hit, and no fixture moves.

## D-061 Menu structure: settings, Back, stages

The menu (the `[menu]` extra) gets a Settings screen, a Back option in every list, and a visible structure. Nothing under core/ changes, and no dependency is added.

Settings writes `config.toml` in `platformdirs.user_config_dir("transcript-normalizer")`, with two keys: `data_dir`, the folder runs/ and packs/ go in, and `pack`, the pack offered first. `runs.base_dir()` now resolves in this order: `TRANSCRIPT_NORMALIZER_HOME` (for scripts, in every mode now, not only in the executable); `data_dir`; then the current directory for a pip install, or the documents folder for the executable (D-052). A folder other than the current directory is created with runs/ and packs/ on first use. The folder is chosen with `tkinter.filedialog.askdirectory`, which ships with Python; where tkinter is missing or there is no display (`TclError`), the menu asks for a typed path. Files already saved are not moved. A file that cannot be read counts as no settings. The menu's one setting a script cannot reach through a command is the pack offered first, which only orders a menu question; the folder is `TRANSCRIPT_NORMALIZER_HOME`, so D-051 holds.

Every `prompts.select` ends with "← Back" (`b` in plain text) unless the caller says otherwise; the main menu has Quit instead. Back returns None, like Esc and empty input, so every caller already handled it. Where a question follows another inside one action, Back returns to the earlier question: the pack question to the run list in "Normalize a run" and "Review pending". In a chain from an earlier step (fetch, then normalize), Back returns to the menu, since the previous question was a yes or no. Multi-selects (the review) keep Esc and empty input; a Back checkbox would read as an answer.

The structure: `prompts.stage` prints a dim rule and `◆ <Stage>` before each block, `prompts.field` prints `── paste below ──` or `── type a path ──` above each text field, and `prompts.detail` and `Output.detail` print label and value (label dim, value white, paths blue, numbers bold). questionary gets `◇` as its question mark, `»` as its pointer and a cyan style; its checkbox already uses ● and ○. In plain text the marks are ASCII (`-`, `*`, `>`, `<- Back`, `[*]`), because the plain adapter is what pipes, tests and narrow code pages see. The first screen adds a line under the version from whether `faster_whisper` can be found (`find_spec`, without importing it).

From the first Windows run of 0.4.6: the menu prints no exit codes; "Review pending" on a run with nothing pending, or whose last normalize was refused for D-054, says "nothing to review for this run" and returns before asking for a pack, and does not offer the folder, since nothing was done. normalize has a hidden `--menu`, which the menu passes, so the D-054 refusal names what the menu has ("Pick another pack in Settings, or install one with pack install.") instead of `--force`, which the command line keeps.

The executables are built with `--collect-submodules tkinter --hidden-import tkinter.filedialog`. A hidden `help --check-picker` imports `tkinter.filedialog` and starts a Tcl interpreter (no window, so no display), printing the Tcl version; the release workflow runs it in every executable. Checked locally on Linux with a lite build from uv's Python 3.12: `tkinter 9.0.4, filedialog tkinter.filedialog`.

The Linux build needs a Python with Tk (0.5.1). In 0.5.0's release, setup-uv's `python-version: 3.12` took the Ubuntu runner's `/usr/bin/python3.12`, which has no tkinter, so `help --check-picker` failed in both Linux executables with `No module named 'tkinter'` and the release was not published; Windows and macOS passed. On Linux the workflow now runs `uv python install 3.12` and builds the venv with `--python 3.12 --python-preference only-managed`, a uv-managed Python that ships tkinter and its Tcl/Tk libraries, and stops at once if `import tkinter` fails. It also installs `python3-tk` and `tk` with apt first, so the system's libtk and libtcl are there too. `--collect-all tkinter` was not needed. The check stays strict on all three systems. Checked locally by building lite the same way: `tkinter 9.0.4, filedialog tkinter.filedialog`.

## Open, not yet decided

- Calibration of the two thresholds of D-011.
- Multi-word term fuzzy matching (`preço dela` → `preço teto`): whether each word of a multi-word term must match its counterpart individually.
- A collocation layer (D-032): matching a term by the words around it, for misrecognitions that are ordinary words (`tira`, `rápido`, `divide`) and cannot be exact variants.
