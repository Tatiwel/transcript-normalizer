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

Why: `fixtures/fixture0001/pack.yaml` is an input to the regression test and has to stay frozen, so it cannot also be the pack people edit as they work.

## D-018 The run id comes from the video, not from the file name

`runs/<id>/` is derived in this order: if the input is already inside a `runs/<id>/`, that directory is the run directory; else if the caption header has a `# URL:` line with a recognizable video id, `runs/<id>/`; else the input's stem. `--out` still overrides all three.

Why: `fetch` names every caption `legenda.txt` (D-016), so deriving the run id from the input stem sent every video to `runs/legenda/` and each run silently overwrote the last. The first rule also makes normalizing a fetched caption write back into the directory it was fetched into, instead of forking a second one.

A recognizable id is the eleven-character platform id, read from the `youtu.be/<id>`, `?v=<id>` and `/shorts|embed|live|v/<id>` shapes. An unrecognized url is treated as no url: the stem is a poor id, but inventing one from an arbitrary url would be worse.

## D-019 Confirmation is per variant, not per term group

Confirmation is per variant, not per term group. In a real run (fixture0002) the group `ser mais, dos 10, sem mig, que caiu, esse mig -> CEMIG` was accepted with one `y`; only two of the five were CEMIG. A term-level answer cannot express a mixed group. The prompt shows the term once, then asks for each variant separately, with that variant's own example lines (up to 3), `[y]es / [n]o / [s]kip / [a]ll-yes / [r]est-no`. `a` and `r` apply to the remaining variants of the current term only.

`review/to-confirm.txt` keeps the grouped view and lists each variant under its term with its own examples and its own question, so the file still shows what the loop will ask.

## D-020 Two kinds of annotation: correction and alias

Two kinds of annotation. `correction`: the caption misrecognized the term; the span is substituted in normalized.txt. `alias`: the text is a legitimate other name of the term (ticker CPFE for CPFL, plural `preços teto`, spoken `CEMIG 4` for CMIG4); the span is annotated with the term but never substituted. Pack `aliases` produce alias annotations; pack `variants` produce corrections. Inflection is alias, not variant. The learned layer gains an `aliases` section beside `confirmed` and `rejected`; --confirm gains the answer `[l]ias` = 'it is this term, but the speaker said it that way'. Measured on fixture0002: 42 of 228 gold rows are aliases; substituting them rewrites what the speaker said.

An alias annotation comes only from an exact match against an alias; a fuzzy match near one is still a guess that the text is garbled, so it stays a correction. It is high band and its `replacement` is the original text. In `annotations.json` the `kind` field carries the difference, and the report lists aliases under "recognized (not changed)". The prompt shows the answer as `a[l]ias`, since `a` is taken by all-yes. A given text is either a confirmed variant or an alias of a term, never both: recording one removes the other.

## D-021 Eight classes, a closed list

Eight classes, closed list: companhia (has ticker and balance sheet), indicador (a number per company or asset), conceito (idea, method, strategy), unidade, pessoa, organizacao (not a listed company: regulator, fund manager, channel, series), ferramenta, sigla (sector or regulatory abbreviation). Migration: indice→indicador; instrumento, tributario, estrangeirismo→conceito; periodo→unidade; gestora, canal, serie do canal→organizacao; sigla setorial→sigla. Class is a label for consumers; it does not affect matching.

Applied to `packs/financas-ptbr.yaml`, both fixture packs and `fixtures/fixture0001/gold.csv`; `fixtures/fixture0002/gold.csv` already used the eight, and the legacy copy is left as it was. The loader refuses a class that is not on the list. Two cases the migration did not name: `operacao` (emissão, diluição; three gold rows) became `conceito`, the nearest of the eight and where `instrumento` went; `numero` appears only on out-of-scope rows with no term, where the class column is a free note like `fala comum`, so it stays. One in-scope gold row has no class at all (18:38 `aoonista` -> acionista) and is left blank: a blank means unlabelled, not a ninth class.

The eight `CPFE -> CPFL` rows of `fixtures/fixture0001/gold.csv` are now status `alias` with `correct` equal to `wrong`, the same speaker habit as fixture0002. Measured: that fixture moves from 156 hits / 9 false positives to 148 / 17. The frozen pack still lists CPFE as a variant, so all eight are substituted, and each counts as a miss and as a false positive. New bounds: hits >= 148, false positives <= 17, in scope 168.

Amended by D-064: a pack now declares its own classes; these eight are what a pack without a `classes:` line keeps, and what financas-ptbr declares.

## D-022 One run directory per video, described by meta.yaml

Run directory is runs/<video-id>/ (unique, stable, filesystem-safe). fetch writes runs/<id>/meta.yaml with title, channel, url, published, fetched_at. `transcript-normalizer list` prints id, date, title for every run.

The id is derived as D-018 says; for a caption with no recognizable url the fallback is still the file stem. `published` is stored as an ISO date (`2026-08-25`, not the platform's `20260825`) and `fetched_at` as a timestamp with its offset. The date `list` prints is the video's publication date, since that is what tells one episode of a channel from another. A run without meta.yaml, from before this decision or from normalizing a local file, is described from the provenance header of its caption; a directory holding neither is not a run and is not listed.

## D-023 Files that need the user live in needs-review/

Files that need the user live in runs/<id>/needs-review/: corrections.csv (was review/gold-draft.csv; same columns; status draft) and pending.txt (was to-confirm.txt), which lists each unanswered variant grouped by term, tagged [never asked] when the run had no --confirm and [skipped] when the user answered s.

This supersedes the `review/` directory of D-016. `--gold-draft` is renamed `--corrections`; the old flag still works for one release, hidden from `--help`, and says so on stderr. corrections.csv keeps its alias rows, with `correct` equal to `wrong`, because a gold file needs them. pending.txt is written with every variant `[never asked]` when the report is produced, then rewritten after a `--confirm` loop from its answers: a variant that got `y`, `n` or `l` leaves it, one that got `s` (or that the input ran out before) stays as `[skipped]`, and the file is removed when nothing is left, so a stale list never outlives its answers.

Amended: `--gold-draft` is removed (2026-10, after 0.6.3). It was kept for one release and stayed for many; `--corrections` is the only name, and the old flag is now an unknown argument.

## D-024 Word n-grams stop at strong punctuation

Word n-grams do not cross strong punctuation (. ? ! ;). Measured: `Warn Buffet. Tem` was proposed as one variant of Warren Buffett in fixture0002.

The tokenizer marks each token followed by `.`, `?`, `!` or `;`, and no n-gram runs across the mark. A `.` inside a token is a decimal point (`6.7`) and does not count, a comma does not count, and a caption break is not punctuation, so D-007's `ser` / `MIG` still joins. The unit rules are regexes over the text and are unaffected.

Measured: fixture0001 loses the false positive `preço. Então` -> preço teto (17 -> 16) and no hit. fixture0002 loses one hit, 36:41 `Warn Buffet` -> Warren Buffett (103 -> 102). That hit was credited only to the span `Warn Buffet. Tem`; the caption line ends `do Warn Buffet.`, and nothing in the frozen pack reaches `Warn Buffet` without crossing the full stop. Its bound moves to hits >= 102. The first fixture's bounds stay as they were, since it lost no hit.

## D-025 Aliases and learned variants match exactly

Fuzzy matching runs only against the canonical term and the curated pack variants. Aliases and learned variants match by exact normalized equality only. Measured: alias `bilhões` fuzzy-matched `milhões` at 85.7, medium band, applied: 24 false positives on fixture0002 and millions rewritten as billions in normalized.txt for any user of the default pack. Aliases are legitimate spellings, not misrecognitions; fuzzy is for finding misrecognitions. This also closes open question (a): learned confirmations no longer widen fuzzy reach.

Measured after: fixture0002 against pack 0.2.0 drops from 53 to 32 false positives with no hit lost; neither fixture moves against its frozen pack. The hazard is not fully closed, because the canonical term is still fuzzy. `milhões` scores 61.5 against `bilhão` and is only a low-band mark now (neither applied nor rendered), but `milhão` scores 83 against it, medium band, and is still applied: three times on fixture0002. Both are held as strict expected failures in `tests/test_exact_only.py`, so the suite goes red if either is fixed without being promoted to a real test.

## D-026 Gold status is provenance; scoring is one rule

In gold.csv, certo and conferido record who wrote the row (tool-proposed and human-checked vs human-added). Scoring does not distinguish them: every row with correct != wrong expects that correction; hit if an applied correction produces it on that line, miss otherwise. alias expects an alias annotation and no substitution; manter expects no applied annotation; rows with empty term are out of scope. Both fixtures use this one rule.

This replaces the two gold conventions of the first version of the evaluator, under which `conferido` was always a miss in fixture0002 and scored like `certo` in fixture0001. "Produces it" means an applied correction for the row's term that covers the row's text on that line; the rendered text is not compared with `correct`, which people write with more context than the span (`Tanto as emissões`) and with their own decimal separator (`4,6 bi`). `correct != wrong` is compared on normalized text, so D-008 still holds: the three `CPFe -> CPFE` alias rows stay aliases, and 15:57 `Etaú -> ETAU`, a `conferido` row differing only by case and accent, is out of scope.

Measured: fixture0001 does not move (167 in scope, 147 hits, 16 false positives), since it already scored the two alike. fixture0002 goes to 225 in scope with 107 hits and 57 false positives: the frozen pack finds none of its conferido rows. Against pack 0.2.0 the same fixture goes from 149 to 188 hits, the 39 conferido rows that pack now finds.

## D-027 Rejection by containment

A rejected pair (text, term) suppresses any proposal for that term whose normalized span contains the rejected text as whole words. Measured: rejecting `divide → dividendo` did not suppress `divide a → dividendo` at 15:54 in fixture0002, violating a manter row.

Whole words means `divide` rules out `divide a` and `ele divide a` but not `dividida` or `subdivide`, and a rejection for one term says nothing about another. Measured with the user's learned layer and pack 0.2.0 on fixture0002: the manter row goes clean, false positives go from 18 to 17, and no hit is lost. The regression bounds do not move, since the fixtures are scored with no learned layer. This closes the open question on rejection by exact text.

## D-028 Unit terms never enter fuzzy matching

Terms of class unidade never enter fuzzy matching. They are matched by the unit rules (D-006) and by exact normalized equality of the term, its aliases and its variants. Measured: with fuzzy on, the canonical `bilhão` matched `milhão` at 83 (applied, 3 rewrites of millions as billions on fixture0002) and the alias `bilhões` matched `milhões` at 85.7. One-letter differences between real words cannot be separated by a threshold.

This supersedes D-021's "it does not affect matching" for one class: `unidade` is the only class the matcher reads. Measured after: fixture0002 against pack 0.2.0 goes from 32 to 29 false positives with no hit lost, and `milhões` is not even marked; neither fixture moves against its frozen pack.

## D-029 Low band lower threshold is 70

Low band lower threshold is 70. Measured at 60: 499 and 579 passive marks per fixture; at 70: 113 and 91. Marks are never applied, so the threshold only governs noise in annotations.json.

This supersedes the initial mark threshold of D-011 (60); the apply threshold stays 80. Counted after overlap resolution with the frozen packs, fixture0001 then fixture0002. No bound moves, since marks are never applied.

## D-030 "Already spelled out" means as whole words

The guard that skips a span because the term (or one of its aliases) is already spelled out in it now tests whole-word containment, the rule of D-027, instead of raw substring containment. Measured: `dec` was found inside `deck` and `enterprise value` inside `enterprise valuey`, so both listed variants could never match.

Measured: fixture0001 gains three hits (`autocapex`, `Sabespe`, `segundo trio`) and fixture0002 against pack 0.2.0 gains four (`deck` three times, `Enterprise Valuey`). The cost: the substring guard had also been blocking real words that contain the term, and they now come through. The term's own plural is fuzzily corrected to the singular (`dividendos` -> dividendo at 94, eight times on fixture0001 and nine on fixture0002; `valuations` -> valuation three times), which D-020 says is an alias, never a correction; and the TIR variant `tira`, also an everyday word, applies (three times). fixture0001 goes from 147 / 16 to 150 / 26; fixture0002 from 107 / 57 to 107 / 70. The plural case is held as a strict expected failure in `tests/test_whole_word_guard.py`.

## D-031 Inflection is the term spelled out; exact beats fuzzy

(a) A word that is an inflection of a term or alias, as the pack's language module defines inflection (D-033), is that term already spelled out: it produces an alias annotation and is never a correction. For pt-BR, `languages/pt_br.py` defines the plural inflections -s, -es, -ão→-ões, -al→-ais, -el→-eis. Measured after D-030: `dividendos → dividendo` ×8 and `valuations → valuation` were applied as corrections, violating D-020. (b) A span that contains an exact match (term, alias, variant, or inflected form) of any term cannot be a fuzzy proposal for another term. Measured: `dividendos e → dividend yield` ×5 over the exact word `dividendos`.

The language module maps a single normalized word to its base forms; a word whose base form is a single-word term or alias is annotated as that alias: exact-only by D-025, and part of D-030's "already spelled out" guard. A word that some term already lists explicitly belongs to that term. (Amended with D-033: the inflection list moved from the core to the pt-BR module; the rule and its measurements are unchanged.) (b) applies to fuzzy proposals only and to other terms only, as worded.

Measured: fixture0001 goes from 150 / 26 to 150 / 18, fixture0002 from 107 / 70 to 107 / 58, and fixture0002 against pack 0.2.1 from 42 to 25 false positives with no hit lost. All three D-030 hits are kept. Neither fixture gets back to its pre-D-030 false positives (16 and 57): the difference is exactly the variant `tira -> TIR` (twice and once), which is not an inflection. The frozen fixture packs keep it, so D-032's removal of it from packs/ does not reach those numbers. The inflection open question is closed.

## D-032 An ordinary word is not a variant

Curation rule: a variant that is an ordinary Portuguese word does not enter the pack, even if the caption used it for the term. Exact matching on ordinary words is wrong more often than right (`tira → TIR`, `rápido → RAP`, `divide → dividendo`). Such cases wait for a collocation layer (open).

Pack 0.2.2 removes `tira` from TIR, `rápido` from RAP and `valorist` from valuation, and adds the term `market cap` (indicador; aliases `marketcap`, `valor de mercado`). Measured, fixture0002 against 0.2.2: false positives go from 25 to 20 and one hit is lost, 15:54 `rápido -> RAP`, the one row the removed variant existed for; `valorist` is still reached fuzzily through `valoristo`. `market -> market share` (three times, in `market cap`) remains: the exact form is the two-word term, which D-031 (b) does not see from inside the one-word span. The frozen fixture packs keep `tira`.

## D-033 Language modules

The core is language-agnostic. Everything language-specific lives in src/transcript_normalizer/languages/<code>.py implementing one protocol: normalize(text) (case, accent folding), inflections(word) -> set of base forms (D-031a), unit_rules() -> list of (pattern, replacement, term) (D-006), sentence_boundaries -> set of punctuation (D-024). A pack declares `language: pt-BR`; the loader selects the module and fails with a clear message if none exists. Adding a language means adding one module and one pack; the core does not change.

`languages/pt_br.py` holds what the core used to know: accent folding to `[a-z0-9$ ]`, the plural inflections of D-031a (now word -> base form, the inverse of the old generation of plurals), the three unit rules of D-006, and `. ? ! ;`. `languages/generic.py` has no inflections and no unit rules, keeps letters of any script, and uses `. ? ! ;`; it is used only when `--allow-generic` is passed for a pack whose language has no module. A pack that declares no language is refused too (D-002). A code maps to a module by name (`pt-BR` -> `pt_br`); a module kept elsewhere is made known with `languages.register`. Each unit rule is a `UnitRule(pattern, replacement, term)` with one optional field, `owns`: the words only that rule may match for its term, which is how `bit` stays EBITDA's everywhere except after a number (D-028). The learned layer has no language, so it compares its own entries by case and spacing only; the pack's language normalizes them when they are loaded.

Measured: every annotation of both fixtures, and of fixture0002 against pack 0.2.2 with and without a rejection, is identical field for field before and after. Declaring `language: pt-BR` in the three packs is not a curation change and no bound moves. `tests/test_language_xx.py` runs the core on an invented language, with the generic module and with a module of its own.

## D-034 D-031(b) is overlap, not containment

D-031(b) is overlap, not containment: a fuzzy proposal is dropped when its span overlaps, in either direction, an exact-match span of a different term. Measured: `market` → market share ×3 survived D-031(b) because the fuzzy span sits inside the exact span `market cap`.

Overlap means sharing any token: the fuzzy span inside the exact one, around it, or across part of it. Exact-match spans are found before any fuzzy guess, whether or not they produce an annotation themselves: `market cap` spelled out produces none and still counts. Measured: neither fixture moves against its frozen pack; fixture0002 against pack 0.2.2 goes from 20 to 17 false positives with no hit lost. On these fixtures "overlap" and "containment either way" score the same: every proposal whose removal changed a number was inside another term's exact span (`market` in `market cap`, `de Dentes` in `Geração de Dentes`). Overlap drops five more raw proposals that share only part of their span (`o market`, `Valuey, aí`, `o dividend`, `de dividend` twice), each either a low mark or one that overlap resolution already discarded.

## D-035 Out-of-domain silence test

Out-of-domain silence test. Pack financas-ptbr 0.3.3 on a 16-minute street prank video (BIrASod49XY, Tá Gravando, platform caption pt-orig, 463 lines, outdoor noise, overlapping informal speech): 2 applied corrections, both false positives (`Ox` → OPEX, the Northeastern interjection 'oxe'), 1 wrong recognition (`tir uma` → TIR, recognition only, text unchanged), 0 medium-band questions, 27 passive marks. The run is not kept as a fixture (no domain terms to grade).

The number was reserved on 2026-09-29 for this test and is used for it now, on 2026-10-06. The recognition's span is `tir` alone, on the 3:47 line, which reads `tir uma`. It is the canonical name spelled out (D-041), so the text is unchanged. The two corrections are at 2:08 and 2:12 (`Ox, entende nada`). Pack 0.3.4 removes `Ox` from OPEX's variants (D-032: an ordinary word, and the Northeastern `oxe` is common in Brazilian speech). It predates D-005 and keeps `O PX`. Two other short variants from before D-005 remain in the pack, `TR` (the unit tri) and `Lu` (Leo); each should be checked against a silence run before the next pack release (CONTRIBUTING 2.4).

The removal has a cost in domain, measured against the bundled pack (hits / false positives, 0.3.3 → 0.3.4). fixture0001 goes from 145 / 16 to 142 / 16: its three `Ox` → OPEX rows (10:59, 11:03, 11:20) are real, because there the speaker spells the term out ("Ox. O PX. O editor vai escrever aí"). fixture0003 (108 / 4), fixture0004 (44 / 2) and fixture0002 (211 / 10) do not move, and no frozen bound moves. Three hits in domain are traded for two false positives out of it, because out of domain the text is someone else's speech being rewritten. Like `dividendio` and `bicho` (D-046), `Ox` is a garble whose meaning only its context gives, and the collocation layer (open) would have to decide it. With 0.3.4 the silence run applies nothing: the one remaining annotation is the `tir` recognition.

A second measurement, on a clean silence run. The video is yJxxTf0IQC8 (Ciência Todo Dia, on prions): platform caption pt-orig, 428 lines, a single narrator, scripted science speech. Pack fit (D-054) finds 1 term with confidence and applies nothing, which is the intended answer out of domain. With `--force` and pack 0.3.4, the run applied 41 annotations, all false positives. 40 were `proteínas`, `proteína priônica` and `proteína se` → BR Partners, all from the phonetic source (D-050): skeleton `prtns` against `prtnrs`, 91, medium band, applied. One was `trio` → tri, an ordinary word ("trio de irmãs estranhas"). After D-060 (phonetic matches only ask) and pack 0.3.5 (`trio` only in `primeiro/segundo/terceiro/quarto trio`), the forced run applies 0: the 40 phonetic forms are questions in needs-review, and the text is unchanged. The prank run with 0.3.5 and `--force` applies only the `tir` recognition. Neither run is kept as a fixture.

## D-036 The fetch strategy chain

fetch resolves its source in a fixed chain and records which step produced the caption in the legenda.txt header and in meta.yaml: (1) platform caption; on HTTP 429 retry up to 3 times with exponential backoff; (2) if no caption exists or (1) fails after retries, download audio and transcribe locally with faster-whisper; (3) error only if both fail. --caption-only stops after (1); --whisper skips (1). yt-dlp already covers most platforms (TikTok, Instagram, Vimeo, X, Twitch); the tool never depends on third-party converter sites.

"Up to 3" is three attempts in all, the first and two retries, waiting 2s and then 4s: three 429s in a row fall through to step 2. Any failure of step 1 falls through, but only a 429 is retried. Reading the video's metadata comes before both steps and is retried the same way; if it fails, there is nothing to fall through to. The header gains a line `# Etapa: 1, legenda da plataforma` (with the retries, when there were any) or `# Etapa: 2, reconhecimento de fala local (<why>)`, in the header's Portuguese; meta.yaml gains `step`, `step_name`, `retries` and, for step 2, `fallback_reason`. With curl_cffi installed (the ingest extra), yt-dlp is asked to impersonate a browser (`--impersonate chrome`), which is what avoids most 429s; without it yt-dlp runs as before. On a terminal the stages, the transcription progress (by seconds of audio) and the retry countdown are drawn with rich; anywhere else they are plain lines. The model download shows faster-whisper's own progress, announced by a line before it starts.

## D-037 The confirm loop saves as it goes

The confirmation loop writes the learned layer after every answer (atomic write: temp file then rename), so an interrupted session keeps its answers and a rerun only asks what is still pending. Measured: a Ctrl+C during the third fixture's first --confirm run lost every answer given.

Every `y`, `n` and `l` is written before the next question; a skip changes nothing and writes nothing. The temporary file sits beside the learned file, so the rename stays on one filesystem; a failed write removes it and leaves the previous file whole. Ctrl+C ends the loop, pending.txt is rewritten from the answers so far (a variant the loop never reached is `[never asked]`, one skipped is `[skipped]`), the run prints how many answers it kept, and it exits with 130. A finished session still ends with "learned layer written to". A rerun asks nothing already answered, because a confirmed variant now matches exactly, a rejected pair is never proposed, and an alias is recognized.

## D-038 fetch takes a local audio or video file

`transcript-normalizer fetch <path>` accepts a local audio or video file as well as a url. A file has no platform caption, so the D-036 chain starts at step 2: it is transcribed locally with faster-whisper, where it sits, without being copied, and needs faster-whisper but not yt-dlp. The run directory is `runs/<file-stem>/`, D-018's third rule. meta.yaml records `source: file` and the file's absolute path, with `url: null`, and a url run now records `source: url`. The legenda.txt header has `# Arquivo: <file name>` where a video's has `# URL:`, and `# Etapa: 2, reconhecimento de fala local (arquivo local)`. `--caption-only` with a file is an error, since there is no caption to take; so is a path that is neither an existing file nor a url, rather than handing it to yt-dlp.

## D-039 The design is stable for pt-BR finance

Third fixture (fixture0004) changed only the speaker and the recognizer (Whisper medium instead of platform captions) while keeping the vocabulary. Result with pack 0.2.3 and the user's learned layer: 37 applied, 4 asked (1 confirmed, 3 rejected), no new design rule required; every gap was pack data (evitida, dividendio, preço alvo, dívida alíquida). CEMIG misrecognitions (Semig, semiga) appeared with a different speaker and recognizer, so the variants are properties of the recognizers, not of one speaker. The design is considered stable for pt-BR finance: from here, new videos are expected to change packs, not code. Amended by D-040: one matcher gap (exact-over-exact overlap) was found in this fixture.

The four answers are the 2026-09-29 entries of the learned layer: `evitida` → EBITDA confirmed; `saber se` → Sabesp, `dividendio` → dividendo and `preço alto` → preço teto rejected. The two gold rows at 0:19 are status alias (`Dividend Yield`, both words, is in the caption line).

Measured against the frozen pack 0.2.3, no learned layer: 40 in scope, 35 hits, 5 misses, 7 false positives, 13 aliases recognized, 2 wrongly substituted. CEMIG is 21/21. New regression bounds: hits >= 35, false positives <= 7, in scope 40. With the learned layer, false positives drop to 2 and no hit moves. Against packs/ 0.2.4, no learned layer: 38 hits, 2 misses, 6 false positives. `preço alto` → preço alvo is a hit reached fuzzily, not through a variant, and the new term brings one false positive (`preço, você` → preço alvo). fixture0001 (147 / 22) and fixture0002 (214 / 18) do not move from 0.2.3 to 0.2.4.

One gap is not in the list: at 0:19 the exact variant `dividend` of dividendo substitutes `Dividend` inside the term `Dividend Yield` spelled out. That is two false positives, two aliases wrongly substituted and two alias misses, with every pack measured. D-034 drops fuzzy proposals that overlap an exact span of another term. It does not drop exact ones.

## D-040 An exact name suppresses a shorter correction overlapping it

An exact term or alias span suppresses any shorter correction of another term that overlaps it, the way D-034 suppresses fuzzy proposals. Measured: at fixture0004 0:19 the exact variant `dividend` of dividendo substituted `Dividend` inside `Dividend Yield`, twice. That is the gap D-039 names. D-034's check ran only on fuzzy proposals, so an exact variant got through.

A name is the canonical term, an alias (curated or learned), or D-031a's inflection of either. A variant is not a name, so a longer variant does not suppress anything here. "Shorter" counts tokens: the correction's span has fewer words than the name's. An equal or longer one is still left to `resolve_overlaps`. A name of the same term suppresses nothing, since D-030's spelled-out guard already covers that. Unit rules (D-006) run before the dictionary and are unaffected. `dividend` on its own is still corrected.

Measured: fixture0004 against its frozen pack 0.2.3 goes from 35 hits / 7 false positives / 2 aliases wrongly substituted to 35 / 5 / 0. Against packs/ 0.2.4 it goes from 38 / 6 / 2 to 38 / 4 / 0. Its bound moves to false positives <= 5. fixture0001 and fixture0002 do not move, against their frozen packs or against 0.2.4. The two 0:19 alias rows are still misses. The term's canonical name spelled out produces no annotation, while an alias row expects an alias annotation.

## D-041 Canonical mentions are recognized

An exact occurrence of a term's canonical name (or its inflected form) produces a recognition annotation (kind alias, rule term:exact) like an alias does; nothing is substituted. Downstream consumers need every mention of a term, not only the misspelled ones. Measured: the two `Dividend Yield` rows at 0:19 in fixture0004 were counted as misses because a correctly spelled term produced no annotation.

The inflected form already produced a recognition under D-031a, and its rule stays `term:alias`. The new annotation is the exact canonical name, compared folded (case and accent), so `Léo` is the name `Leo`. The report lists these under "recognized (not changed)". normalized.txt does not change.

Measured, after overlap resolution, `term:exact` annotations per fixture (frozen pack / packs/ 0.2.4): fixture0004 43 / 48, fixture0001 61 / 76, fixture0002 105 / 125. Against the frozen packs, fixture0004 goes from 35 to 37 hits and from 13 to 15 aliases recognized: the two 0:19 rows. Its misses go from 5 to 3 and its false positives stay at 5. Its bound moves to hits >= 37. fixture0001 and fixture0002 do not move in hits, false positives or aliases, against either pack. Against 0.2.4, fixture0004 has 40 hits, 0 misses and 4 false positives. One `manter` row of fixture0001 now carries an applied annotation: 7:30 `Léo ruim` is recognized as the term Leo. The gold note says the speaker said "Leo, ruim?". The text is not substituted, but D-026 counts any applied annotation on a manter row, so that fixture's bound allows one touched row. Amended by D-042: recognitions do not touch a manter row, and the bound is back to zero.

## D-042 A manter row forbids corrections, not recognitions

Amends D-026. A manter row forbids an applied correction on its span, not a recognition annotation; recognitions never change text. Measured: `Léo ruim` at 7:30 in fixture0001 was counted as touched once canonical mentions were recognized (D-041).

The evaluator's touched list for a manter row now holds applied corrections only, of any term. Recognitions (kind alias) are not in it. Measured: fixture0001 goes back to no touched manter row, and its bound is zero again. fixture0002 keeps its one touched row, 15:54 `divide a`, which is a correction. No fixture moves in hits, misses, false positives or aliases.

## D-043 The curated pack ships in the package

The curated pack ships inside the package at transcript_normalizer/packs/ and is the default when no ./packs/financas-ptbr.yaml exists in the working directory (supersedes the error case of D-017). The root packs/ directory holds only user files: learned layers and user-authored packs.

The root `packs/financas-ptbr.yaml` is no longer a link to the bundled copy. It is gone, so the sdist carries no symlink. Run in the repo, the default is therefore the bundled pack, while the learned layer still sits at `./packs/<pack-name>.learned.yaml`. Tests and `scripts/measure.py` read the bundled path. `packs/README.md` says what the directory is for.

## D-044 pt-BR n-grams stop at a comma

Add comma to the pt-BR sentence boundaries (D-024). Measured: the proposals `preço, valor`, `preço, não` and `isso, Amigo` crossed a comma in fixture0003.

This supersedes D-024's "a comma does not count" for pt-BR only. The generic language module keeps `. ? ! ;`. A comma inside a token is still part of it, so a decimal comma (`11,5%`) and a decimal point (`6.7`) are both unaffected. A caption break is still not punctuation (D-007). No term, alias or variant in any pack contains a comma.

Measured on the fixture0003 run with the bundled pack 0.2.4, no learned layer: eight proposals crossed a comma. Three were medium band and applied (`preço, valor` and `preço, não` → preço alvo at 85 and 84, `isso, Amigo` → CEMIG at 80), and five were low marks. None is left. Applied annotations go from 46 to 43 and corrections from 7 to 4. That run's caption is the translated `pt` track (`automatica (pt)`) D-045 is about, fetched before D-045. The fixtures do not move against their frozen packs, so no bound changes. Against 0.2.4, fixture0004 goes from 4 to 3 false positives (`preço, você` → preço alvo is gone), and fixture0001 and fixture0002 do not move. No hit is lost anywhere.

## D-045 fetch prefers the original automatic caption

YouTube publishes the original automatic caption as `<lang>-orig` and an auto-translated track as `<lang>`. fetch must prefer `<lang>-orig`, then a manual `<lang>`, then automatic `<lang>`, and record which track it took in the header and meta.yaml. Measured: for fixture0003 the `pt` track was a translation (`BTG Pacific`, `Portfólio de canais`, `Ofertas públicas iniciais (IPOs)`), useless as a normalization source.

Within each of the three, an exact code comes before a regional variant (`pt-BR-orig` for `--lang pt`), with the existing warning when there are several. Another language's `-orig` (`en-orig`) says nothing about `pt`, so an automatic `pt` is still taken. It is a translation then, but the chain has no better caption to offer, and the header names the track. The header keeps its line `# Origem da legenda: <source> (<track>)`. The source is `manual`, `automatica` or the new `automatica original`, so a caption from `pt-orig` reads `automatica original (pt-orig)`. meta.yaml gains `caption_track` and `caption_source` when step 1 produced the text. Tested with a fake track list shaped like fixture0003's (`pt-orig` alongside translations into `de`, `en`, `es`, `fr`, `pt`, `zh-Hans`). Existing headers are unchanged, since a video without `-orig` takes the same track as before.

## D-046 Fourth fixture: a new sector, and one misrecognition with two meanings

Fourth fixture, new sector (investment bank), same speaker as the third. With pack 0.2.4 the tool found 4 of 81 expected corrections and produced 8 false positives; the 77 misses were all missing pack data, dominated by one company name in 18 misrecognitions. First case of one misrecognition meaning two different terms by context (`dividendio`: dividend yield in fixture0004, dividendo mínimo in fixture0003), recorded as the concrete motivation for the collocation layer (open).

The caption is the platform's `pt-orig` track (D-045). The gold has 121 rows: 79 conferido, 36 alias, 4 certo, 2 manter. 83 rows expect a correction, and two of those have no term (`realo`, `portas` → pelo menos), so 81 are in scope with the 36 alias rows: 117. The 40 hits are the 36 alias rows plus 4 corrections (`dividendield`, `freeat` twice, `SEMIG`). The company is BR Partners: 50 rows, 18 distinct forms after folding. Among the misses, "pack data" includes data that was there but wrong: `dividend` was a variant of dividendo, while this gold has it as dividend yield. Also counted are five forms D-005 and D-032 keep out of any pack (`RO`, `sel`, `Port`, `porta`, `portas`). The touched manter row is 19:46 `bicho`, then an EBITDA variant. Bounds against the frozen pack 0.2.4: in scope 117, hits >= 40, false positives <= 8, one touched manter row.

Pack 0.3.0 adds the conferido terms of the gold: BR Partners, drawdown, small cap, Décio Bazin, M&A, IPO, Benchimol, BTG Pactual, Adapta Valuer, Auren, securitizadora and commodities. It also adds payout, LPA, DPA, P/VP (alias P/B) and partnership, and `Selica` for Selic. It removes `bicho` from EBITDA and `dividend` from dividendo (D-032). `dividendio` stays on dividend yield, with the ambiguity noted in the pack. Two variants of the gold stay out under D-032: `apos`, which folds to `após`, and `Portes`, the plural of `porte`.

Measured against 0.3.0, no learned layer (hits / misses / false positives):

| fixture | 0.2.4 | 0.3.0 |
|---|---|---|
| fixture0003 | 40 / 77 / 8 | 103 / 14 / 10 |
| fixture0004 | 40 / 0 / 3 | 40 / 0 / 15 |
| fixture0001 | 147 / 20 / 22 | 146 / 21 / 28 |
| fixture0002 | 214 / 11 / 18 | 211 / 14 / 19 |

The removals cost four hits elsewhere. fixture0001 28:44 `sobre bicho` is EBITDA there, a second context-dependent misrecognition. fixture0002 33:17, 33:25 and 39:32 have gold rows `dividend` → dividendo, inside spans the same gold also marks `dividend y` → dividend yield.

Most of the new false positives are curated variants reaching ordinary words fuzzily at 80 to 86. `Portizar` reaches `aportar` (×5) and `amortizar`. `Portess` reaches `por essa`, `por esse` and `por três`, `Portudo` reaches `oportuno`, and `Portinas` reaches `portas`. `Selica` reaches `eólica`, `securizadora` reaches `seguradora`, `Dio Bazin` reaches `do bazinho`, and `adapta Vala` reaches `adaptar a`. `commodit` corrects the singular `commodity` (×2) to the plural. Seven of fixture0004's twelve new false positives are spellings of the channel's tool (`AdaptaValor`, `adaptavala`, `DAPTA Valdre`), likely gaps in that fixture's gold, not checked. Only the frozen packs are bounds, so none of this blocks.

## D-047 Fuzzy from a curated variant needs 85

A fuzzy match reached from a curated variant is applied only at 85 or above. A match reached from the canonical term keeps D-011's 80. Below its threshold a variant's match is a low mark: it keeps its real score and is never applied. Measured on D-046: the variants of 0.3.0 reached ordinary words at 80 to 84 (`Portizar` → `aportar`, `Portess` → `por essa`, `Selica` → `eólica`).

Two rules were measured on all four fixtures with the bundled pack 0.3.0, before anything changed. A: curated variants match by exact equality only, so fuzzy runs from the canonical term alone. C: fuzzy from a variant requires 85. Hits / false positives:

| fixture | 0.3.0 | A | C |
|---|---|---|---|
| fixture0003 | 103 / 10 | 98 / 8 | 103 / 7 |
| fixture0004 | 40 / 15 | 40 / 7 | 40 / 9 |
| fixture0001 | 146 / 28 | 146 / 14 | 146 / 17 |
| fixture0002 | 211 / 19 | 206 / 8 | 211 / 9 |
| total | 500 / 72 | 490 / 37 | 500 / 42 |

The same, after the gold fixes below:

| fixture | 0.3.0 | A | C |
|---|---|---|---|
| fixture0003 | 103 / 10 | 98 / 8 | 103 / 7 |
| fixture0004 | 45 / 7 | 42 / 4 | 44 / 4 |
| fixture0001 | 146 / 28 | 146 / 14 | 146 / 17 |
| fixture0002 | 211 / 19 | 206 / 8 | 211 / 9 |
| total | 505 / 64 | 492 / 34 | 504 / 37 |

C is adopted. It removes 27 false positives for one hit, while A removes 30 for thirteen, so the two are not close. A loses hits that only a variant reaches fuzzily: `Waren Buff`, `esse mig`, `sem mig`, `ebítica`, `valorist`, `freeat` twice, `Adaptavalda`, `adaptavala` and `adaptar a válvula`, plus three more on fixture0003. C loses one hit, fixture0004 4:54 `adaptar a válvula`, reached at 80 from `adapta Vala`. Ranking is by the demoted score, so a variant's match under 85 does not win a span from a better proposal. Two tests now hold the old threshold on purpose: the confirmation-loop tests script answers against fixture0001's four-variant CEMIG group, and C leaves two of those four.

Gold fixes, authorized. In fixture0002 the rows `dividend` → dividendo at 33:17, 33:25 and 39:32 are dropped. Those spans are dividend yield, and the dividend yield rows stay. In fixture0004 there are five conferido rows for the channel's tool, Adapta Valuer, each checked on its line: 1:04 `Adaptavalda`, 4:54 `adaptar a válvula` ("pra você que tem acesso [à Adapta Valuer], temos agora essa nova aba"), 5:03 `DAPTA Valdre`, 18:16 `AdaptaValor`, 18:42 `adaptavala`. Against the frozen pack, fixture0002 goes from 107 / 58 to 104 / 67 from the gold alone. The evaluator scores proposals before overlap resolution, so each dropped row's `dividend` correction also brings its overlapping `o dividend`, `de dividend` and `dividend y`. C then takes it to 104 / 59.

Pack 0.3.1 adds `commodity` as an alias of commodities: the singular is not an error. fixture0004 loses its two `commodity` → commodities false positives.

Bounds, frozen packs (hits / false positives): fixture0001 150 / 14 (was 18), fixture0004 37 / 4 with 45 in scope (was 37 / 5 with 40), fixture0002 104 / 59 with 222 in scope (was 107 / 58 with 225, the gold change). fixture0003 does not move. Bundled 0.3.1: fixture0003 103 / 7, fixture0004 44 / 2, fixture0001 146 / 17, fixture0002 211 / 9.

## D-048 The evaluator scores what is applied

The evaluator scores only the annotations that survive `resolve_overlaps`, exactly the set rendered into normalized.txt. Before, it scored every proposal, so a proposal that lost its span to a longer or better one counted as a false positive, though it never reached the output. Measured: fixture0002 went from 58 to 67 false positives when D-047 dropped three gold rows. Each dropped row's `dividend` correction also brought its overlapping `o dividend`, `de dividend` and `dividend y`.

The rule applies everywhere `evaluate` is called: the regression test, `scripts/measure.py`, and the manter check, which now sees only the resolved set too. A proposal that loses its span is neither a hit nor a false positive. This replaces the "as exp2 did" scoring that `evaluate_fixture` and the regression test had kept. Matching and its numbers are unchanged.

Measured, hits / false positives, before → after:

| fixture | frozen | bundled 0.3.1 |
|---|---|---|
| fixture0003 | 40 / 8 → 40 / 6 | 103 / 7 → 102 / 6 |
| fixture0004 | 37 / 4 → 37 / 4 | 44 / 2 → 44 / 2 |
| fixture0001 | 150 / 14 → 150 / 14 | 146 / 17 → 146 / 15 |
| fixture0002 | 104 / 59 → 104 / 53 | 211 / 9 → 211 / 9 |

What went out: `de dividend` → dividendo ×2 on fixture0003 (both packs), `bit` → EBITDA ×2 on fixture0001 with 0.3.1, and on fixture0002 (frozen) `dividend y` ×3, `de dividend` ×2 and `o dividend`. fixture0003 with 0.3.1 loses one hit, which the output never had: at 3:34 the rendered annotation is `dividend` → dividendo (94, from the canonical term), which wins the span from the proposal for dividend yield. That annotation is now the false positive. No manter count moves. New bounds: fixture0003 false positives <= 6, fixture0002 <= 53.

## D-049 The spelled-out guard means covered, not contained

D-030's guard skips a candidate when an exact name of its term (canonical, alias, or D-031a's inflection of either) is spelled out in the span. It now skips only when that exact span covers the whole window, equal or larger. A window that is longer and merely contains the name stays eligible, and the longer span wins in overlap resolution. Measured: in fixture0002 the alias `dividend` (0.3.2) blocked the variant `dividend y` → dividend yield three times.

"Covers" is positional, over the exact-name spans D-040 already records: the window's tokens lie inside an exact name of the same term. A window shorter than a name is now skipped too (`Value` inside `Enterprise Value`). Before, it was not, because it does not contain the whole name. A longer fuzzy window around a name (`o Enterprise Value`, 94) becomes a proposal again. It loses its span to the name's own recognition (100, D-041) in overlap resolution, so neither normalized.txt nor the scores (D-048) see it.

Measured with the old gold, before → after (hits / false positives). With the bundled 0.3.2, fixture0002 goes from 208 / 9 to 211 / 9: the three `dividend y` and `dividend y build` rows. fixture0003 goes from 102 / 4 to 104 / 4, through variants that contain an alias: `Dio Bazin` (alias `Bazin`) and `B Partners` (alias `Partners`). fixture0001 and fixture0004 do not move, and no fixture moves against its frozen pack. The strict expected failure of 0.3.2 in tests/test_inflection.py is a test again.

Gold, authorized, fixtures/fixture0003/gold.csv. The rows 3:34 and 9:19 `dividend` are now alias rows of dividend yield, with `correct` equal to `wrong`: the speaker's short form, and the text stays. Two conferido rows for BR Partners are added, each checked on its line: 7:48 `A Partens` ("A Partens, em 2025, ano passado, ela terminou o ano") and 11:39 `partner` ("eu tenho partner e é minha segunda maior posição de small caps"). After the gold change: frozen 0.2.4 has 119 in scope, 40 hits and 6 false positives, and its bound moves to 119 in scope. Bundled 0.3.2 has 106 hits and 4 false positives, with 38 aliases recognized.

## D-050 A phonetic skeleton is the fourth matching source, for names

A pt-BR consonant-skeleton similarity (drop vowels, collapse doubles, s/c/ç→s, g/j→j, l/u before consonant→u) runs as a fourth matching source, only for terms of class companhia and pessoa, only on spans the exact and fuzzy sources did not resolve, threshold 85 on rapidfuzz ratio of skeletons, always medium band (applied flagged, asked in --confirm), never high. Measured on a BR Partners hold-out (exp3): recovers 6 of 18 misrecognized forms and 25 of 50 rows for 4 false positives across four fixtures, two of which were real mentions missing from the gold. Epitran por-Latn recovered nothing beyond the baseline (vowel differences dominate IPA distance). Closes D-010.

The rule is `term:phonetic`. The skeleton lives in `languages/pt_br.py` as `skeleton(text)`, part of the language protocol (D-033): a module sets it to a function or to `None`. The generic module sets `None`, so the source is off there. The vocalized l/u is written `w`, so the vowel pass that follows keeps it. The source compares 1- and 2-word windows, within sentences (D-024, D-044), against the canonical names and aliases of companhia and pessoa terms whose skeleton has 4 letters or more. A window is skipped if any applied annotation of the other sources overlaps it, after overlap resolution. A rejected pair is not proposed. One addition to exp3: a 2-word window is proposed only if it scores higher than each of its words alone. Otherwise a word that adds nothing to the skeleton rides along and is replaced with the name: `a Portness`, or `Portinas caiu` (`caiu` folds into the trailing `s`). The fixture numbers are the same with and without it.

Measured, hits / false positives, before → after:

| fixture | frozen | bundled 0.3.2 |
|---|---|---|
| fixture0003 | 40 / 6 → 40 / 6 | 106 / 4 → 108 / 4 |
| fixture0004 | 37 / 4 → 37 / 4 | 44 / 2 → 44 / 2 |
| fixture0001 | 150 / 14 → 150 / 15 | 145 / 15 → 145 / 16 |
| fixture0002 | 104 / 53 → 105 / 55 | 211 / 9 → 211 / 10 |

Gained: fixture0003 7:48 `A Partens` and 11:39 `partner e` → BR Partners (90), the two rows D-049 added. fixture0002 36:41 `Warn Buffet` → Warren Buffett (100) with the frozen pack, the hit D-024 lost. Added false positives: `para três` (fixture0001) and `por três` (fixture0002) → BR Partners with 0.3.2 (`prtrs` against `prtnrs`, 90). With the frozen packs, `como gestão` (fixture0001) and `mesmo jeito` ×2 (fixture0002) → CEMIG (88). Both go through the alias `Cemig GT`, whose skeleton is four letters (`smjt`). The frozen bounds move with the measurement: fixture0001 false positives <= 15, fixture0002 hits >= 105 and false positives <= 55. Three tests account for the new medium-band proposals. The confirmation-loop tests turn the source off, as they hold D-047's threshold, to keep their scripted group.

Amended: the minimum skeleton length is 5, not 4. A name, alias or window whose skeleton has fewer than 5 letters is skipped. Measured: the three CEMIG false positives with the frozen packs (`como gestão` in fixture0001, `mesmo jeito` ×2 in fixture0002) all went through the alias `Cemig GT`, whose skeleton `smjt` has four letters. At 5 they disappear and no gain is lost. `Warn Buffet` stays (frozen fixture0002). `Partens` and `partner` stay with 0.3.2, at 108 / 4, the pack where the phonetic source produced them; since 0.3.3 they are variants. Hits / false positives at 4 → 5: frozen fixture0001 150 / 15 → 150 / 14 and fixture0002 105 / 55 → 105 / 53. Nothing else moves, frozen or with the bundled 0.3.3 (fixture0003 108 / 4, fixture0004 44 / 2, fixture0001 145 / 16, fixture0002 211 / 10). The bounds go back to false positives <= 14 and <= 53. With 0.3.3 the source's two remaining false positives are `para três` and `por três` → BR Partners (`prtrs`, five letters).

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
| fixture0003 | 6 | 23 | yes |
| fixture0004 | 11 | 15 | yes |
| fixture0001 | 29 | 35 | yes |
| fixture0002 | 18 | 44 | yes |
| BIrASod49XY (prank, D-035) | - | 1 | no |

The prank's one term is the `tir` recognition of D-035. The closest fixture is fixture0003 against its frozen 0.2.4 at 6; with the pack users run, the lowest is 15. Counting corrections only would also separate them (bundled: 15, 4, 26, 28 against 0), but fixture0004, a video in the domain whose terms are mostly spelled right, would sit at 4, one away from the threshold. The threshold of 3 is not calibrated beyond these five captions; a short clip in the domain can fall under it, which is what `--force` is for.

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

`fetch --check` prints yt-dlp, curl_cffi and faster-whisper, each with its version or "not installed", and exits 0. The versions are read from the modules, since a frozen build may lack the package metadata. The release workflow's smoke test runs it: yt-dlp must be there in both flavors, faster-whisper only in `full`. Then it runs `fetch --list https://youtu.be/fixture0004`. A track list or an HTTP 429 passes, and so does YouTube's bot check: datacenter runners get it, and it still comes from yt-dlp. A traceback or an argparse error fails. Checked locally against a lite executable built from this code: `fetch --check`, `fetch --list` and a full caption download (`pt-orig`, 511 lines) all work, where the 0.4.2 build failed with `invalid choice: 'yt_dlp'`.

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

Phonetic matches are proposals only: they go to the confirm queue and are never substituted until the user confirms the form (which makes it an exact variant). Amends D-050. Measured: three independent runs produced phonetic false positives (`para três` → BR Partners in fixture0001 and `por três` → BR Partners in fixture0002, both with the bundled pack; `proteínas` → BR Partners ×40 in a forced out-of-domain run, D-035), while every phonetic hit in the fixtures is now covered by a curated variant.

The phonetic source's annotations now carry a band of their own, `ask` (`BAND_ASK`). It is not one of the applied bands, so nothing is substituted in normalized.txt and nothing counts as a hit or a false positive. It is one of the question bands (`QUESTION_BANDS`, with medium), so the report lists it under "to confirm", needs-review/pending.txt lists it, and `--confirm`, `--review` and the menu ask about it. A confirmed form is a learned variant, and from then on it is matched exactly, in the high band (D-013). A rejected form is never proposed again. Pack fit (D-054) counted only the high band already, so it does not move.

Measured, hits / false positives before → after, against the bundled pack 0.3.4: fixture0001 142 / 16 → 142 / 15 (`para três` is gone), fixture0002 211 / 10 → 211 / 9 (`por três` is gone), fixture0003 108 / 4 and fixture0004 44 / 2 unchanged. Against the frozen packs, one hit is lost: fixture0002 36:41 `Warn Buffet` → Warren Buffett, which the frozen 0.1.0 pack does not list and only the phonetic source reached (105 → 104). The bundled pack lists `Warn Buffet` as a variant, so it is still a hit there, and that bound moves to hits >= 104. No other fixture, frozen or bundled, loses a hit. "Every phonetic hit is covered by a curated variant" holds for the bundled pack; for the frozen ones it is that single row.

Pack 0.3.5 in the same release replaces the variant `trio` of tri with `primeiro trio`, `segundo trio`, `terceiro trio` and `quarto trio`. The garble of the unit of time matches only in its phrase, because alone `trio` is an ordinary word (D-032). fixture0001 8:24 `segundo trio` → tri is still a hit, and no fixture moves.

## D-061 Menu structure: settings, Back, stages

The menu (the `[menu]` extra) gets a Settings screen, a Back option in every list, and a visible structure. Nothing under core/ changes, and no dependency is added.

Settings writes `config.toml` in `platformdirs.user_config_dir("transcript-normalizer")`, with two keys: `data_dir`, the folder runs/ and packs/ go in, and `pack`, the pack offered first. `runs.base_dir()` now resolves in this order: `TRANSCRIPT_NORMALIZER_HOME` (for scripts, in every mode now, not only in the executable); `data_dir`; then the current directory for a pip install, or the documents folder for the executable (D-052). A folder other than the current directory is created with runs/ and packs/ on first use. The folder is chosen with `tkinter.filedialog.askdirectory`, which ships with Python; where tkinter is missing or there is no display (`TclError`), the menu asks for a typed path. Files already saved are not moved. A file that cannot be read counts as no settings. The menu's one setting a script cannot reach through a command is the pack offered first, which only orders a menu question; the folder is `TRANSCRIPT_NORMALIZER_HOME`, so D-051 holds.

Every `prompts.select` ends with "← Back" (`b` in plain text) unless the caller says otherwise; the main menu has Quit instead. Back returns None, like Esc and empty input, so every caller already handled it. Where a question follows another inside one action, Back returns to the earlier question: the pack question to the run list in "Normalize a run" and "Review pending". In a chain from an earlier step (fetch, then normalize), Back returns to the menu, since the previous question was a yes or no. Multi-selects (the review) keep Esc and empty input; a Back checkbox would read as an answer.

The structure: `prompts.stage` prints a dim rule and `◆ <Stage>` before each block, `prompts.field` prints `── paste below ──` or `── type a path ──` above each text field, and `prompts.detail` and `Output.detail` print label and value (label dim, value white, paths blue, numbers bold). questionary gets `◇` as its question mark, `»` as its pointer and a cyan style; its checkbox already uses ● and ○. In plain text the marks are ASCII (`-`, `*`, `>`, `<- Back`, `[*]`), because the plain adapter is what pipes, tests and narrow code pages see. The first screen adds a line under the version from whether `faster_whisper` can be found (`find_spec`, without importing it).

From the first Windows run of 0.4.6: the menu prints no exit codes; "Review pending" on a run with nothing pending, or whose last normalize was refused for D-054, says "nothing to review for this run" and returns before asking for a pack, and does not offer the folder, since nothing was done. normalize has a hidden `--menu`, which the menu passes, so the D-054 refusal names what the menu has ("Pick another pack in Settings, or install one with pack install.") instead of `--force`, which the command line keeps.

The executables are built with `--collect-submodules tkinter --hidden-import tkinter.filedialog`. A hidden `help --check-picker` imports `tkinter.filedialog` and starts a Tcl interpreter (no window, so no display), printing the Tcl version; the release workflow runs it in every executable. Checked locally on Linux with a lite build from uv's Python 3.12: `tkinter 9.0.4, filedialog tkinter.filedialog`.

The Linux build needs a Python with Tk (0.5.1). In 0.5.0's release, setup-uv's `python-version: 3.12` took the Ubuntu runner's `/usr/bin/python3.12`, which has no tkinter, so `help --check-picker` failed in both Linux executables with `No module named 'tkinter'` and the release was not published; Windows and macOS passed. On Linux the workflow now runs `uv python install 3.12` and builds the venv with `--python 3.12 --python-preference only-managed`, a uv-managed Python that ships tkinter and its Tcl/Tk libraries, and stops at once if `import tkinter` fails. It also installs `python3-tk` and `tk` with apt first, so the system's libtk and libtcl are there too. `--collect-all tkinter` was not needed. The check stays strict on all three systems. Checked locally by building lite the same way: `tkinter 9.0.4, filedialog tkinter.filedialog`.

## D-062 The fetch flow: where, which track, caption or transcription

"Fetch a video or file" asks three things, each with Back: "Where is it?" (a link, a file on this computer); for a link, "Use the platform's caption, or transcribe the audio on this computer?"; for the caption, which track. Then the existing "Next: normalize this run now?". Nothing under core/ changes.

A file is chosen with `tkinter.filedialog.askopenfilename` (filters: audio or video, mp3 m4a wav ogg opus mp4 mkv webm mov; captions, srt vtt txt; all files), in the same dialog wrapper as D-061's folder picker, and typed where there is no dialog. A caption file goes to the Normalize stage directly (`normalize <file>`, which converts a .srt or .vtt); there is nothing to fetch. An audio or video file runs `fetch <file>`, which transcribes it (D-038).

For a link, the menu reads the video itself (`fetch.read_metadata`, the function fetch uses) and shows its title, channel, date and duration, because the questions depend on what tracks exist. It then runs `fetch <url> --track <code> --caption-only --no-video-info` or `fetch <url> --whisper --no-video-info`, so every choice is a command a script can type (D-051). That reads the video twice, as the menu's step-1-then-step-2 path did before. If the caption download fails, the menu still offers transcription when the build has it.

The tracks (`fetch.tracks`) are listed by name in D-045's order: the original-audio tracks (`<lang>-orig`, "Portuguese, original audio (automatic)"), then the manual ones ("Portuguese (written by the channel)"), then the automatic translations under one entry, "Other languages (automatic translations)…", which opens their list ("English (automatic translation)"). When a video has no original-audio track, its plain automatic tracks are not translations, so they are listed directly as "(automatic)". A code that has a manual track is listed once, as manual. Names come from a table of nine languages (pt en es fr de it ja ko zh); a regional code keeps its code (`Portuguese (pt-BR)`), and an unknown one is its code. The default is the original-audio track, or what `--lang` would choose when there is none, so Enter does what the menu did before. A video with one track names it and does not ask.

`prompts.select` takes a `default`: questionary starts the cursor there, and in plain text enter alone takes it (only `b` goes back, and the key legend says so). An Option can be `disabled` with a reason: questionary shows it greyed with the reason, plain text shows it with `-` for a key and refuses it. The transcription option is disabled with "full build only" in the lite executable and "needs the ingest extra" in a pip install without faster-whisper.

`fetch --track <code>` takes exactly that track, as `--list` names it; for a code with both a manual and an automatic track, the manual one. A track that does not exist is a NoCaption that names it ("there is no caption track 'fr' for this video", with the tracks there are), also under `--caption-only`, where "This video has no caption." would be wrong. Without `--track`, `--lang` chooses as before.

In the same release, Settings prints its hint ("saved in your user settings…") once, not again each time its list comes back after a change; seen on Windows. A test starts the executable afresh with a saved folder and finds it on the first screen.

## D-063 Packaging: a folder for full, Linux on 22.04

Only the release workflow and packaging/ change for the executables; the menu gets four small fixes.

The full build on Windows and macOS is built with PyInstaller `--onedir` and shipped as `transcript-normalizer-<version>-<os>-full.zip`, a zip of the folder `transcript-normalizer-<version>-<os>-full/` with `transcript-normalizer.exe` (`transcript-normalizer` on macOS) inside. A `--onefile` executable is an archive that unpacks itself into a temporary folder on every start; for full that is about 100 MB (the speech stack of D-052), and on Windows, where Defender scans what is unpacked, the 0.5.2 full build was slow to open. A folder is unpacked once, by the user. The program is built as `transcript-normalizer` and its folder renamed, so the name users open is the same in every version and the folder says which one it is. lite is small and stays one file, because one file is simpler to download and keep. Linux full stays one file too: it is started from a terminal, and the start-up cost is the one thing 0.5.3 changes on Windows and macOS. The smoke tests run the executable inside the unpacked folder; the workflow names it once, as `EXE`. The release header and both guides say "full: unzip, then open transcript-normalizer.exe inside the folder", and that the folder must stay together.

To measure the change, the Windows full job times `help` with PowerShell's `Measure-Command`, three runs each, for the new folder build and for 0.5.2's one-file `transcript-normalizer-0.5.2-windows-full.exe` (downloaded from that release with `gh`), and writes both to the job summary. 0.5.2 is the last one-file full build, so it stays the baseline. The step is `continue-on-error`: a measurement never stops a release. The numbers are in the summary of the v0.5.3 release run.

The Linux executables are built on `ubuntu-22.04`, not `ubuntu-latest`. PyInstaller's bootloader and the manylinux wheels ask little of glibc, but what it collects from the runner (the uv-managed Python stays, D-061, and the system's libtk and libtcl beside it) is linked against the runner's glibc, so the oldest glibc the executables run on is the build runner's. 22.04 has glibc 2.35, which covers 22.04-based systems such as Zorin 17; the job writes `ldd --version` to its summary. The check, package and release jobs make no executable and stay on `ubuntu-latest`, which moves to 26.04 after 2026-10-19. When GitHub retires 22.04 runners, the oldest available one takes its place.

From the last Windows run: the file dialog's first filter, its default, is "All supported (audio, video, captions)", the media and caption patterns together; "Audio or video", "Captions" and "All files" follow. In the track list, the automatic translations carry "(translations are rate-limited more often)", on "Other languages (automatic translations)…" and on each language in its list: YouTube answers HTTP 429 to a translated track more often than to the original. questionary printed a chosen option's whole line, label and description, as the answer; its choices now show the line in the list and only the label once answered (questionary reads `Choice.title` for both, so the title follows the question's `is_answered`). D-054 already wrote normalized.txt from the input with no annotation, so every line, stamp and text, is the input's, in normalized.txt's layout (no header, the two-space gap); a test checks it line for line.

Measured on the v0.5.3 release run (GitHub's `windows-latest` and `ubuntu-22.04` runners, 2026-10-08), from its job summaries:

| windows-full, `help`, `Measure-Command` | run 1 | run 2 | run 3 |
|---|---|---|---|
| onefile, 0.5.2 | 5.78 s | 5.59 s | 5.13 s |
| onedir, 0.5.3 | 0.30 s | 0.29 s | 0.28 s |

About 19 times faster to start (5.50 s against 0.29 s on average): the onefile time is the unpacking, every time. The Linux runner: `ldd (Ubuntu GLIBC 2.35-0ubuntu3.15) 2.35`.

## D-064 Classes are declared by the pack (amends D-021)

A pack declares `classes: [..]`, the classes its terms may use. Four are common and always allowed, whatever the pack declares: `pessoa`, `organizacao`, `sigla`, `unidade`; any field has people, organizations, abbreviations and units. A pack adds its own: a medicine pack has `farmaco` and `doenca`, which D-021's eight, written for finance, could only call `conceito`. D-021's closed list served one field; with packs for other fields (D-055, D-065) a closed list would either grow without end or squeeze every field into finance's words.

The check stays at load, as D-021 had it: a term with a class that is neither declared nor common is a ValueError that names the file, the term, the class and the classes allowed, and says to add it to `classes:`. `classes:` that is not a list of names is an error too. `Pack.classes` keeps the allowed list (common first, then the pack's, without repeats), for the editor and for consumers.

A pack with no `classes:` line is a pack from before this decision (the frozen fixture packs, packs already in the packs repository, anyone's own) and keeps D-021's eight, so nothing that loaded before is refused now. financas-ptbr declares its eight explicitly (pack 0.3.6; no term changes).

Matching still does not read class (D-021 stands on that), with the two exceptions it already had: a `unidade` is never matched by similarity (D-028), and `companhia` and `pessoa` get phonetic proposals (D-050, which only ask, D-060). Both read common or finance names: a medicine pack's names are `pessoa` and get phonetic proposals; its `farmaco` terms do not. Whether a pack should be able to say which of its classes are names is left open until a pack needs it. (Decided in D-068: `phonetic_classes:`.)

## D-065 Field templates and the Packs menu

**Templates.** `src/transcript_normalizer/templates/<field>.yaml` holds ten field templates, data only: a pack with zero terms, `name: NAME` and `language: LANG` as placeholders, a `description` with one line in English (`en`) and one in Portuguese (`pt-BR`), and the field's classes (the common four of D-064 come with every pack):

| template | classes |
|---|---|
| financas | companhia, indicador, conceito, ferramenta |
| medicina | doenca, farmaco, procedimento, anatomia, exame |
| direito | lei, instituicao, instrumento, conceito |
| tecnologia | linguagem, biblioteca, protocolo, produto, conceito |
| engenharia | material, componente, norma, processo |
| educacao-ciencias | conceito, metodo, grandeza |
| esportes | time, competicao, posicao, regra |
| politica-governo | orgao, cargo, programa, lei |
| agro | cultura, insumo, praga, tecnica |
| geral | conceito, produto, lugar |

Class names are lowercase and without accents, like D-021's. The templates ship in the package and in the executables (`--collect-data transcript_normalizer`). The menu lists them in this order, geral last.

**Commands.** In `packfiles.py`, beside registry.py's repository commands; every check is `load_pack`'s own, with `allow_generic`, so a file accepted here is a file normalize accepts:

- `pack list --installed`: name, version, language, terms, size (KB) and source: `bundled`, `repository` (packs/ holds the file `pack install` wrote, by installed.json's sha256) or `mine` (created, imported, or edited). It reads the repository's index in a thread and waits at most 3 seconds, since urllib's timeout does not cover a name lookup; with the index, an `update` column marks `↑ update (<version>)` where the index has a later version (numeric comparison) of a bundled or repository pack, never of `mine`. Without it, the column is absent and a line says the repository was not reached.
- `pack create --template <field> --name <n> --lang <l>` writes `packs/<n>.yaml`: the template's name, description, classes and no terms, version 0.1.0. It refuses a name that is not a pack name (registry's: lowercase, digits, hyphens), the name of a bundled pack (an empty pack in packs/ would hide it, D-017), a file already there, and a language that is not a code. A language with no module is created, and the command says normalize needs `--allow-generic` for it (D-033).
- `pack import <file>` checks the file and copies it, byte for byte, to `packs/<stem>.yaml`; the file name is the pack's name. A file already there needs `--force`. Importing a bundled pack's name is allowed, and said: the copy is used instead (D-017).
- `pack remove <name>` deletes `packs/<name>.yaml` and its installed.json record. It refuses a bundled pack. The learned layer is kept and named: it holds the user's review answers, and a pack installed again finds them.

**The menu.** "Packs" is menu item 6; Settings stays 7 and holds only the folder, and Help moves to 8. Packs lists: Installed packs, Get a pack, Create a pack, Import a pack file, Remove a pack, The pack offered first (moved from Settings; the config key is unchanged), and Back. Each runs its command through `cli.main`: Get reads the index (up to 10 seconds) to offer the list, then runs `pack install <name>`; Create asks for a template, a name and a language, runs `pack create`, and on a yes saves the new pack as the one offered first; Import opens the file dialog of D-062 on `*.yaml`, or asks for a typed path; Remove shows the file and asks twice (both default no) before `pack remove`, and for a bundled pack runs `pack remove` at once, which says why not. The D-054 refusal in the menu now says "Pick another pack, or get or create one in Packs."

## D-066 Editing a pack, and adding a term from a run

**Editing.** `packedit.py` adds `pack copy`, `add-term`, `edit-term`, `remove-term`, `show` and `export`, and the menu's Packs → Edit a pack runs them. Only a pack of the user's own (`mine`, D-065) is edited. A bundled pack or one installed from the repository is read-only, and the menu offers "make my own copy" first: `pack copy <name>` copies a bundled pack into packs/ under the same name, which is then used instead (D-017), or, for a repository pack, drops its installed.json record, so `pack update` leaves it alone. The name stays, so the learned layer (`<name>.learned.yaml`) and the pack offered first still apply.

`add-term <pack> <term>` adds a term (`--class`, `--alias`, `--variant`, repeatable); when the term is already in the pack, by its name or an alias, it adds the forms to it instead, which is what "Add a term you noticed" needs. `edit-term` renames, changes the class, and adds or removes aliases and variants; `remove-term` removes a term. A form that already belongs to another term is refused (one form, one term); one already in this term is skipped and said.

Every write is checked before the file is replaced: the changed pack is written to a trial file beside it and loaded with `load_pack` (classes, D-064; phonetic classes, D-068), and the forms being added are checked against the curation rules. A variant under 3 letters, after folding, is refused with the reason (D-005: it matches too much, even exactly). A variant made only of words in the language module's `common_words` is saved with a warning (D-032): only the user has seen the caption, and the warning says what the cost is. These checks apply to what is being added, not to what the pack already holds, so financas-ptbr's `TR` and `Lu` (CONTRIBUTING 2.4) do not block an edit of a copy. Each saved change bumps the patch version (0.1.0 → 0.1.1; a version that is not three numbers becomes 0.1.0).

The pack is written again from its data, YAML with lists of strings in flow style and the terms indented under `terms:`. The comment block at the top of the file is kept, since that is where packs record their history (CONTRIBUTING 2.7); comments further down are lost on the first save. A copy of financas-ptbr loses four such comment lines. Keeping them would need a round-trip YAML library, a new dependency, for three comments.

`common_words` is new and optional in the language protocol: pt-BR lists 105 ordinary words (articles, prepositions, pronouns, common verbs, and the D-032 cases: `tira`, `rápido`, `divide`, `trio`, `oxe`), English 117, and the generic module none. `register` does not require it.

Show terms pages through `pack show --page <n>` (20 a page) and searches with `pack show --search <text>` (any form of a term containing the text, folded). Edit and Remove ask for part of a term, then list the matches (at most 20).

**Adding a term from a run.** After normalizing (also when the pack did not fit, D-054, since a missing term may be why), after a review, and after "Show a run's outputs", the menu asks "Add a term you noticed?" (default no). It asks for "the wrong form you saw" and shows the run's caption lines containing it as whole words (folded), at most five and how many there are, then asks whether that is the form; a form not in the caption is said and asked again. Then "what it should be". If the pack has that term (by name or alias), it asks whether the form is a mishearing (a variant) or the term said that way (an alias); otherwise it asks for a class and creates the term with the form as a variant (no variant when the two fold the same). Both are `pack add-term`. Then "Normalize <run> again with it?" runs the normalize step with that pack, without asking the pack question again. A run shown with no pack in mind asks which pack first, or takes the one installed.

The question adds one prompt after every normalize in the menu; the existing menu tests answer it.

## D-067 Contributing a whole pack

`pack propose --whole <name>` (menu: Packs → Contribute a pack) proposes a whole pack, where D-056's `pack propose` proposes learned entries. D-056 holds: nothing leaves the machine without the user seeing it, and the tool sends nothing itself.

It prints the summary: name, version and language; field (the `field:` key, which `pack create` now writes, with the description's English line; "(not recorded)" otherwise); classes; number of terms; the first five terms with their forms, and how many more. It says the whole file is sent, never a transcript, and asks "Propose this pack?" (default no). On a yes it writes the file, byte for byte, to `contributions/<name>-<version>.yaml` and opens a prefilled issue on the packs repository titled "New pack: <name>", or "Update: <name>" when the repository has a pack of that name. That comes from the index within 3 seconds, as `pack list --installed` reads it, or, offline, from where the pack came from: bundled and repository packs are updates. The issue body has the summary and the file inside a collapsed `<details>` block. When the link would be longer than D-056's 8000 characters (financas-ptbr is), the body asks for the written file to be attached instead. Without a browser the link is printed.

`pack export <name> [--to <path>]` (menu: Export a pack file, with the folder dialog of D-061 or a typed path) copies the pack to `<name>-<version>.yaml` in the data folder, in the folder given, or to the `.yaml` path given. Any installed pack can be exported, bundled ones too.

## D-068 An English module, and phonetic classes per pack

**English.** `languages/en.py` closes the first limit 0.6.0 recorded: an English pack needed `--allow-generic`, and the menu did not pass it. `normalize` lowercases, folds accents and flattens everything but letters, digits and `$`, as pt-BR does. `inflections` gives the singulars of -ies (→ -y), -es and -s, never for a word in -ss and never a one-letter base. The unit rules turn `bn` and `B` after a number (with or without a space) into `billion`, and `mn` and `M` into `million`; each owns its words, which elsewhere are left to the dictionary. The sentence boundaries are `. ? ! ;` and the comma (D-044). There is no phonetic skeleton yet (`skeleton = None`), so the phonetic source is off for English. A test runs a 10-line English caption against a small pack: a variant corrected twice, three unit rules, a plural recognized as the term, and a two-word term that does not run across a full stop.

For a pack whose language still has no module, the menu now passes `--allow-generic` to normalize and to the review, and says once, before running, that it is matching with the generic module (no inflections, no unit rules). The command line keeps the explicit flag (D-033).

**Phonetic classes.** This closes the second limit: D-050 compared only `companhia` and `pessoa`, finance's names, so a medicine pack's drugs were never compared by sound. A pack may declare `phonetic_classes: [..]`, each one of its classes (an unknown one is an error at load). Without the line, a pack that declares `classes:` gets `pessoa` and `organizacao`, plus `companhia` when it declares it; a pack with no `classes:` line, from before D-064, keeps D-050's two, so the frozen fixture packs match exactly as measured. `Pack.phonetic_classes` replaces the matcher's constant. financas-ptbr declares `[companhia, pessoa]` (pack 0.3.7), D-050's measured pair: adding `organizacao` to it would add questions no fixture has measured. The templates set their lists: medicina `farmaco, doenca, pessoa, organizacao`; tecnologia `produto, biblioteca, linguagem, pessoa, organizacao`; esportes `time, pessoa, competicao`; the others take the default. The phonetic source still only asks (D-060): a test shows a `farmaco` term proposed in the ask band, never applied, only when the pack names `farmaco`.

## D-069 Three-way pack merge

A copy of a bundled or repository pack (D-066) used to drift: when upstream released a new version, the copy kept the old terms and the user's edits, with nothing to bring the two together. `pack merge <name>` does that, by canonical term, and asks where it cannot decide.

**Provenance.** `pack copy` (also the menu's automatic copy before editing or adding a term) writes `based_on: <name>@<version>` and `local_edits: 0` after the copy's `version:` line, leaving the rest of the file as it was. It also keeps the upstream file it copied in `packs/.bases/<name>@<version>.yaml`. A three-way merge needs the base's content, and neither the bundled pack (only the current version ships) nor the repository index (only the latest is listed) can give an old version back. Every saved edit increments `local_edits`. A copy made before 0.6.2 has no `based_on`; it merges two-way, and the merge writes `based_on` (the new upstream version) and its snapshot, so the next merge is three-way. A copy whose snapshot is missing also merges two-way, and says so.

**Detection.** On the menu's first screen, in Installed packs (an `↑ merge available (<version>)` mark), and in `pack update`, each copy is compared with its upstream: the newer, by version, of the bundled pack of that name and the repository's (the index within 3 seconds). A copy is a pack of the user's own that has `based_on`, or that has the name of a bundled pack. When upstream is newer than `based_on` (or, without one, than the copy's version), it says "financas-ptbr 0.4.0 is available; your copy is based on 0.3.7 with 3 local edits." and the menu asks "Merge?" (default no). `pack update` asks only on a terminal, and otherwise prints the command. Nothing is merged without being asked for. `pack merge <name>` takes `--dry-run`, `--yes-theirs` and `--yes-mine` (every conflict answered one way), and `--force` (merge even when upstream is not newer).

**Merging.** Terms are matched by their canonical name, folded by the pack's language (case and accents). Lists are aliases, variants and collocations within a term, and the pack's classes and phonetic_classes: both sides' additions, minus what either side removed from the base. Mine's spelling of a form wins when the two differ only in folding. Other pack keys come from upstream, except the copy's own `name`, `field`, `based_on` and `local_edits`.

Three-way (with a base):

| base | upstream | mine | result |
|---|---|---|---|
| - | has it | - | added from upstream |
| - | - | has it | kept (mine) |
| - | has it | has it | combined as two-way (both added the same term) |
| has it | same as base | same as base | unchanged |
| has it | changed | same as base | upstream's version |
| has it | same as base | changed | mine |
| has it | changed | changed | combined field by field: one side's change is taken, lists are combined; a class changed on both sides is a conflict |
| has it | removed | same as base | removed |
| has it | removed | changed | kept, with a notice |
| has it | renamed (a new term holding its name or forms) | same as base | upstream's renamed term |
| has it | renamed | changed | conflict |
| has it | any | removed | left out, with a notice when upstream changed it |

Each upstream removal of an alias or variant that is still in mine gets a notice. Two-way (no base): a term on one side only is added or kept; a term on both is the union of its forms, with no removals, since without a base nothing can be told apart from an addition. A class that differs is a conflict, and so is a form that is an alias on one side and a variant on the other.

**Conflicts**, asked one at a time, each with the term's versions (base, mine, theirs) and up to three caption lines from the user's runs where one of its forms occurs:

| conflict | keep mine | take theirs | keep both | decide later |
|---|---|---|---|---|
| class changed on both sides (two-way: differs) | my class | their class | - | my class |
| a form is an alias in one, a variant in the other (two-way) | my kind | their kind | - | my kind |
| the same form is a variant of two terms | removed from theirs | removed from mine | - | both stay |
| my variant is upstream's alias of another term | removed from theirs | removed from mine | - | both stay |
| my variant is upstream's canonical name of another term | (not possible) | removed from mine | - | both stay |
| a form I confirmed in the learned layer was removed upstream | kept in the pack | removed (the learned layer still corrects it for me) | - | kept |
| a form I rejected in the learned layer was added upstream | not added | added | - | not added |
| my new term looks like a new upstream term (folded, rapidfuzz ratio ≥ 90) | mine only | theirs only | both, when no form collides | mine only |
| upstream renamed a term I had added forms to | my term, old name | the renamed term, with my added forms | - | my term |

The answers have fixed keys in plain text: `m` keep mine, `t` take theirs, `k` keep both, `l` decide later. Empty input or Esc decides later. "Decide later" leaves the term as mine and records the conflict in `packs/<name>.merge-pending.yaml`, which `installed_packs` does not list as a pack. `--yes-mine` decides later where keeping mine is not possible. Form conflicts and learned-layer conflicts are found after the term-level answers, on the merged terms.

**Safety.** The result is loaded as normalize loads it (D-064, D-068), and a variant under 3 letters that upstream does not itself have is refused (D-005). Only then is the copy backed up as `<name>.yaml.bak-<timestamp>` beside it and replaced. The new upstream file becomes the base snapshot. The written pack has `based_on: <name>@<upstream version>`, `local_edits` set to the number of terms where it now differs from upstream, and as version upstream's, or upstream's next patch when anything of mine was kept. The summary prints terms added from upstream, updated from upstream, kept of mine, combined and removed; conflicts resolved and pending; the notices; and where the learned layer now repeats the pack (redundant) or contradicts it, though the learned layer itself is never changed. `--dry-run` prints the summary and the conflicts that would be asked, and writes nothing.

**Contribution against the base.** `pack propose --whole <name>` for a copy with a base (and its snapshot) proposes the changes since that base, never the whole file: new terms, added aliases and variants, removed terms and forms, class changes. It shows them, asks, writes `contributions/<name>-<version>-diff.yaml`, and opens an issue titled "<name>: N additions from <user>" (with ", M removals" when there are any). <user> is the computer's login name, shown in the title before the question. A pack without a base is still proposed whole (D-067). `pack propose` without `--whole` still proposes learned entries (D-056).

Tested with a synthetic base, upstream and mine that has one term per row of both tables, in both directions (`--yes-theirs`, `--yes-mine`, every conflict decided later), two-way mode, a backup, a dry run, detection in the menu, the table and `pack update`, and the diff-only contribution.

Amended (2026-10): the menu no longer waits for the index, nor asks at startup. With a copy installed and the index unreachable (packets dropped rather than refused), every menu start took 3.2 s, the full wait (docs/INSPECTION-2026-10.md, F27). The look now runs in a background thread with the same 3-second wait, and the index it reads is kept for 24 hours in `packs/.index-cache.json` under the data directory (so a portable install keeps it inside its folder), keyed by the index's url; a cache that cannot be written is ignored. The copies are found before the thread starts, in the menu's own directory. When the look finds an update, the next time the main menu is drawn it prints one line, "financas-ptbr 0.4.0 is available; your copy is based on 0.3.7 with 3 local edits. Packs → Merge an update merges it.", once per session. Packs prints the same line and offers "Merge an update" as its first entry, which runs `pack merge` as before. Measured offline with a copy: the first screen in 0.19 s instead of 3.21 s. `pack list --installed` and `pack update` still read the index themselves, since the user asked for them.

## D-070 A Windows installer with a folder choice, and a portable build

No change under core/; packaging and the product layer only.

**The installer.** The Windows full build ships as `transcript-normalizer-<version>-windows-full-setup.exe`, made by Inno Setup 6 from `packaging/windows-installer.iss`. It installs per user by default (`PrivilegesRequired=lowest`, into `%LOCALAPPDATA%\Programs\transcript-normalizer`), so no administrator is needed, and its first page offers "install for all users" instead. The "choose install location" page is shown (`DisableDirPage=no`). It adds a Start menu shortcut, and a desktop shortcut when that box is ticked. Its uninstaller is in "Add or remove programs". A fixed AppId lets a new version install over an old one, and `[InstallDelete]` empties the old `_internal` first, so the program folder is replaced rather than mixed.

The uninstaller never deletes user data. It removes what the installer put in the program folder, and the folder once it is empty; the user's files are not there (runs/ and packs/ are in Documents or the Settings folder, D-052, D-061, and config.toml is in the user settings folder). Its last page says so: "Your files were kept: runs/ and packs/ … and the Settings folder."

The release runner installs it silently into a folder with a space in its name (`/VERYSILENT /CURRENTUSER /DIR=…`), checks the Start menu shortcut, runs `help` and `fetch --check` from there (faster-whisper must be listed), uninstalls silently, and waits up to 90 seconds for the folder and the shortcut to be gone.

**The portable build.** `transcript-normalizer-<version>-windows-full-portable.zip` holds the onedir folder, `portable.txt` (one line saying what it does) and an empty `data/` folder. The zip is written with Python's zipfile (`packaging/portable_zip.py`), because PowerShell's Compress-Archive drops empty folders. The plain windows-full zip of D-063 is no longer published; lite stays a single .exe, and macOS and Linux are unchanged.

**Portable mode** keeps every byte inside its folder. It is on when `portable.txt` is beside the executable (`sys.executable` when frozen, `sys.argv[0]` otherwise), so any build becomes portable by adding the file, lite included. Then, under `<program folder>/data`:

| what | normally | portable |
|---|---|---|
| runs/ and packs/ (`base_dir`) | Documents, or the Settings folder | `data/` |
| config.toml | the user settings folder | `data/config.toml` |
| the speech model (`HF_HOME`) | `~/.cache/huggingface` | `data/models` |
| yt-dlp's cache (`cachedir`) | `~/.cache/yt-dlp` | `data/cache` |
| what yt-dlp's JavaScript runtime writes (a `deno.lock`) | the working directory | `data/cache`, yt-dlp's working directory while it runs |

`HF_HOME` is set at the start of `cli.main`, before anything imports huggingface_hub. Portable wins over a folder chosen in Settings, since the data lives with the program, and Settings says "portable mode: everything stays in <folder>" with no folder dialog; the first screen says it too. `TRANSCRIPT_NORMALIZER_HOME` still wins over both, for scripts. yt-dlp runs in-process (D-057), so its working directory is changed for the call and restored after, and only in portable mode, where a relative path typed by the user is not involved (fetch's paths are absolute by then).

A test makes a program folder with `portable.txt`, a temporary home (HOME, USERPROFILE, APPDATA, LOCALAPPDATA and the XDG folders) and a current directory of its own, runs a fake fetch and a normalize, writes the settings, and finds every file under the program folder and none in the home (settings, documents, ~/.cache) or the current directory. Another proves yt-dlp ran inside data/cache and the working directory came back. On the runner, the unzipped portable build normalizes a fixture with no TRANSCRIPT_NORMALIZER_HOME, and the run is in its data/ and nothing is in Documents, the settings folder or the working directory.

## D-071 YouTube's bot check, said plainly; the sign-in as cookies yt-dlp reads

No change under core/; the product layer only.

**What happened.** A Windows user got yt-dlp's "Sign in to confirm you're not a bot. Use --cookies-from-browser or --cookies for the authentication" at the metadata read, and the menu printed it as it came: flags they could not use from the menu, and nothing to do next. YouTube asks this of a connection, not of a video (a VPN, a shared network, many requests from one address).

**Said plainly.** `ytdlp()` recognises YouTube's checks by pieces of yt-dlp's message, lowercased, curly apostrophe folded: "not a bot" is the bot check; "confirm your age", "age-restricted", "inappropriate for some users", "login details are needed", "only available for registered users", "members-only", "join this channel" and yt-dlp's "--cookies-from-browser or --cookies" are a sign-in wall. It raises `SignInRequired` with "YouTube asked to confirm you are not a bot. This depends on your connection, not on the video." or "YouTube asks for a signed-in account to show this video (an age check, or members only).", and keeps yt-dlp's text in `.raw`. Neither is retried like a 429. `fetch` prints the plain line and the ways out (`--cookies-from-browser firefox`, `--cookies cookies.txt`, Settings, later; not for the menu's own calls, `--no-video-info`), and exits 3, a code of its own so the menu can tell it from other failures. At step 1 it stops instead of falling through to the audio, which would meet the same check, and takes the attempt back (D-059).

**The menu** offers, at the metadata read or after a fetch that exited 3: "Use your browser's YouTube sign-in (cookies)", "Try again later" (back to the main menu), "Use a file from this computer" (the file flow of D-062), and Back. A sign-in chosen there is saved as in Settings, and the read or the fetch runs again.

**The sign-in is cookies, named, never held.** Settings has "YouTube sign-in": a browser (Firefox first, "works best"; Chrome, Edge and Brave carry "on Windows usually cannot be read", since Chromium browsers there encrypt cookies with a key only the browser can use, and lock the file while open; Safari on macOS), "A cookies.txt file…" (the file dialog, or a typed path), or "None". config.toml keeps `youtube_cookies = "firefox"` or the file's absolute path, never what is in it. yt-dlp gets `cookiesfrombrowser = (browser, None, None, None)` or `cookiefile`, for the metadata read and every download, and reads them itself in this process (D-057). In order: `fetch --cookies-from-browser <browser>` or `--cookies <file>` (mutually exclusive), then Settings, then, in portable mode (D-070), a `cookies.txt` in `data/`. A cookies.txt that is not there is said before yt-dlp runs ("There is no cookies file at …"), since yt-dlp would carry on without it. A browser that cannot be read (yt-dlp's CookieLoadError) is said with its name and cause, "Could not read the YouTube sign-in from Chrome (…)", then "On Windows, Chrome's cookies usually cannot be read." where that applies, and "Try Firefox, or a cookies.txt file."

**Privacy.** Nothing the tool writes holds a cookie: not runs/ (legenda.txt, meta.yaml, the audio), report.txt, needs-review/, the learned layer, contributions, nor config.toml. A test puts a fake cookie jar in Settings, fetches through both steps (the fake yt-dlp reads the jar, as the real one would), normalizes, and finds none of its values in any file under the test's folder, and only the path in config.toml. yt-dlp itself writes the jar back to a cookies.txt it was given when it closes, as its own `--cookies` does; that file is the user's, outside runs/.

Help has a section "YOUTUBE SAYS I'M A BOT", and both guides one under section 3, with how to export a cookies.txt.

## D-072 The review is one stop per form, in the order of the video, and Enter decides nothing

**What happened.** A user reviewed fixture0003 in the menu. The review was one screen per term, a multi-select (D-053): the forms selected were confirmed and the ones left unselected were **rejected**. He pressed Enter with nothing selected to move on, believing he was skipping, and rejected every form of two terms, which the tool then never proposed again. Nothing on the screen said Enter rejects; the hint said "the others are rejected", under a list he did not mean to answer.

**The review now** (the menu and `normalize --review`) stops once at each pending form: one stop per (term, form) in the ask bands, ordered by the form's first occurrence. A form taken as a term (yes, only here, or said that way) is not asked again for another term, and its later occurrences take the same answer, since an answer is per form. A form answered "No" for one term can still be asked about another.

**Each stop shows** the caption line before, the line with the form in «guillemets» and the line after, with their timestamps (all of them when the form straddles a break); the other timestamps where the same form occurs ("also at"); and where to watch it: for YouTube (`watch?v=`, `youtu.be/`, `shorts/`, `live/`, `embed/`) `https://youtu.be/<id>?t=<seconds>`; for another platform its URL and "at m:ss", since not every platform takes a time in the link; for a local file nothing beyond the timestamp. The URL is the caption header's.

**One question, single choice**, "Is «form» term?": "Yes: this is <term> (fix it from now on)" (confirmed in the learned layer), "Yes, but only in this video" (D-073), "This is <term>, said that way (recognise it, keep the text)" (an alias, D-020), "No: this is not <term>" (rejected), and "Decide later", the default, which Enter takes. **Nothing is rejected unless "No" was chosen.** Back (b, Esc) or Ctrl+C ends the stops; the rest is left for later.

**Nothing is written until the summary.** After the last stop, "will remember: X → term (and aliases, `X (as said) = term`); rejected: Y is not term; only in this video: Z → term; left for later: N", then "Save these answers? [Y/n]". Yes writes the learned layer once and the run's local decisions; no discards every answer of that review and writes nothing (pending.txt then lists them as skipped). When every answer was "Decide later" there is nothing to save and the question is not asked. This amends D-037 for the review: it no longer saves per term; a Ctrl+C at the summary's question keeps nothing and exits 130. `--confirm` is unchanged (D-019, D-037: per answer, saved as it goes), and gains `o` for "only in this video".

The multi-select of D-053 is gone from the review; `prompts.multi_select` stays for other questions. Tests drive the plain prompts: Enter on every stop writes neither the learned layer nor a local file; of the five answers only "No" produces a rejection; the summary appears and "n" discards; stops follow the timeline, a repeated form is one stop that lists its other timestamps; the link for YouTube, another platform and no URL.

## D-073 "Only in this video": a decision kept beside the run

Some forms are right for one video only: a guest's name the recognizer garbled into a word that, elsewhere, is a real word. Confirming them would correct every video from then on; rejecting them leaves this one wrong.

"Yes, but only in this video" (in the review, and `o` in `--confirm`) is written to `runs/<id>/local-decisions.yaml`, a list of `{form, term}` with a comment saying what it is, merged with what is already there. When that run is normalized, after overlaps are resolved, every annotation of that term whose form matches, and that is not already high, becomes a high-band correction with rule `local` in annotations.json (stand-off, D-004): applied in normalized.txt, counted as corrected, never asked again in that run. It is never written to the learned layer, so `pack propose` (which reads only the learned layer) never includes it, and `pack merge` never reads runs. Another run with the same words is not affected. A test reviews one form as local, normalizes again, finds the `local` annotation applied and the form no longer pending, finds it pending and not local in another run, and finds the learned layer empty and nothing to propose.

## D-074 Dubbed caption tracks: the video's own language is the original

YouTube now dubs some videos automatically, and each dubbed audio brings its own automatic caption with the `-orig` suffix: fixture0003, in Portuguese, listed `en-US-orig`, `es-US-orig` and `pt-orig`. D-045 took any `-orig` track as the original audio's, so the menu listed three "original audio" tracks, sorted by code, and English came first.

The original is now the `-orig` track in the video's language as yt-dlp's `language` field reports it (exact code first, then by base language). The other `-orig` tracks are dubbed (source `automatica dublada`, in the header and meta.yaml) and named "<language>, dubbed audio (automatic)". The track list goes by language: the original language first (its original-audio track, then the channel's own), then English, then the rest, each in D-045's order within. `choose_language` (`--lang`) ranks a dub after a manual track of that language and before an automatic translation. `fetch --list` prints the dubs on a line of their own, `dubbed:`. When yt-dlp names no language, or one with no `-orig` track, every `-orig` track is original, as before.

The menu's default is the original. With questionary the default was passed as questionary's `default`, which also paints that row as chosen, and it stayed painted after the pointer moved, so two rows looked selected. The pointer now starts on the default and nothing else is painted.

## D-075 No decision numbers in what the program says

Decision numbers are for whoever reads the code and the docs; in a message or a help line they read as noise ("Instead of Settings (D-071)"). They are removed from every user-facing string: the help, argparse help and descriptions (two were taken from docstrings, and are now their own text), menu prompts, errors and warnings. They stay in code comments, docstrings, these decisions, the guides and the changelog. The comment block written at the top of a new pack file, and the field templates, keep theirs: they are file comments, read like the code's own. A test reads every string literal in the package (but docstrings and that comment block) and finds no `D-0nn`; others check `help`, each command's `--help` and a walk through the menu.

## D-076 Linux full is a folder too

The Linux full executable was one file (D-063 kept it so, since it is started from a terminal). As one file it unpacks its whole speech stack to a temporary folder on every start, which is what made the Windows one slow. It is now built `--onedir`, like Windows and macOS full, and shipped as `transcript-normalizer-<version>-linux-full.tar.gz` holding the folder `transcript-normalizer-<version>-linux-full/` with `transcript-normalizer` inside. The release runner's smoke tests run the program inside the folder; the release page says to extract it and run it from inside. Linux lite stays one file in a tar.gz.

## D-077 After a review, only the questions that make sense; the sign-in list shows what is installed

Two findings from a user test of the menu.

**After the review's summary.** "learned layer written to …" was printed whenever a learned layer existed, even when every answer was "only in this video" (D-073) or "decide later"; the file was rewritten too. "Contribute what you taught the tool?" was asked whenever the layer held anything the pack lacked, from any earlier review. Now the CLI writes and announces the learned layer only when this session changed it (`--confirm` too), and the menu snapshots the layer before the review and offers to contribute only when it is different afterwards. Then "Add a term you noticed?" and "Open the folder?", once each, in that order. When adding a term leads to normalizing the run again, that second pass does not ask them again (`normalize_run(..., followups=False)`, and its review likewise).

**The YouTube sign-in list** (Settings, and the ways out when fetch meets YouTube's check: the same list) is built from what is on this computer. The system comes from `sys.platform`, never a question. A browser is listed when its profile folder exists where yt-dlp reads it (yt_dlp/cookies.py: `_firefox_browser_dirs`, `_get_chromium_based_browser_settings`): on Linux that includes Firefox under `$XDG_CONFIG_HOME/mozilla/firefox`, `~/.mozilla/firefox`, flatpak (`~/.var/app/org.mozilla.firefox/…`) and snap (`~/snap/firefox/common/.mozilla/firefox`). A test compares the folders with yt-dlp's own on the system the tests run on. Safari is offered on macOS only (part of the system). Whale, which yt-dlp also reads, is left out.

The rows: Firefox ("works best"); one row "Chromium-based browser" whose description names the ones found (Chrome, Edge, Brave, Opera, Vivaldi, Chromium), which opens a sub-list when there are two or more and goes straight to the browser when there is one; Safari; "A cookies.txt file…"; "None"; "How does this work?", which prints a four-line explanation (why YouTube asks, what signing in borrows, why Chromium-based browsers on Windows lock their login, that the login never leaves the computer or the program's files) and shows the list again; Back. "on Windows usually cannot be read" is shown beside the Chromium-based browsers only on Windows; D-071 showed it on every system, where on Linux and macOS they usually work. With no browser found, the list is the cookies.txt row, None and the help row. `fetch --cookies-from-browser` still takes any browser yt-dlp knows.

Tests fake the system, the environment and the home folder (`cookies.system`, `environ`, `home`); by default every test sees a Linux with an empty home, so the developer's browsers never shape a test.

## D-078 Other sites: the sign-in for any site, their login walls, no captions, the audio, a quick check

No change under core/; the product layer only. From a discussion with a user who fetches from sites other than YouTube.

**The sign-in is for every site.** "YouTube sign-in" is now "Sign-in (your browser's login)" in Settings, the ways out of fetch, the help and the guides. It was already passed to yt-dlp for every call, whatever the site; only its name said YouTube. config.toml's key is now `sign_in`; the old `youtube_cookies` is still read when `sign_in` is absent, and saving writes `sign_in` and removes the old key, so it cannot win later. The program does not check whether the chosen browser is signed in to a site: it cannot know without asking the site, and the site's answer is the check.

**Login walls on any site.** Besides YouTube's checks (D-071), a message is a login wall when it has one of yt-dlp's own words for it. `raise_login_required`, which every extractor uses, appends a hint in one of three wordings, all starting "Use --cookies" (`--cookies-from-browser or --cookies`, `--cookies, --cookies-from-browser, …`, `--cookies for the authentication`); and the extractors' own messages, collected from yt-dlp's Instagram, Facebook, TikTok, Twitter and Vimeo extractors (there is no Kwai extractor): "login required", "rate-limit reached", "requires authentication", "authentication may be needed", "need to log in", "log into an account", "who follow this account", "accessing posts anonymously", "without being logged-in", "account is private", "videos are private", "protected tweet", "not authorized to view", "do not have permission to view", "only works when logged-in", "fresh cookies", "private video", "granted access to this video". The site is named from the extractor in yt-dlp's message (`[Instagram]`, `[twitter]`, before any `:`) or the info's `extractor_key`, else from the link's host, through a short table (YouTube, Instagram, Facebook, TikTok, X (Twitter), Vimeo, Kwai, Twitch, …); an unknown site is called by its host. Plainly: "<Site> asked you to sign in for this video." (YouTube keeps D-071's age-check wording). With a sign-in already set: "The browser you chose (<name>) may not be signed in to <Site>. Sign in there, or pick another browser in Settings." (for a cookies.txt, to export it again while signed in). Exit 3 and the menu's ways out, as for YouTube.

**No captions.** Most sites other than YouTube have none. When a link has no caption track, the full build's menu says "<Site> doesn't provide captions for this video." and asks straight away whether to transcribe; it never offers the platform caption. The lite build says "<Site> doesn't provide captions for this video. The full build can transcribe its audio on this computer." and returns, in the menu and in `fetch`, without the "could not get a text" list or the menu's "fetch did not finish". `--caption-only` says the first sentence (D-062's plain words, now with the site).

**The audio.** Until now the downloaded audio stayed in the run folder as `audio.<ext>` after transcription, never deleted, with a line saying it could be. The user asked for "Keep the audio after transcribing", off by default, and chose, when told the audio was never deleted, that off deletes it. So: once the text is written, the audio is deleted ("the audio was deleted; --keep-audio, or Settings, keeps it"); with Settings → "Keep the audio after transcribing" (`keep_audio = "yes"` in config.toml) or `fetch --keep-audio`, it stays in the run folder as `<video id>.<ext>`. A failed attempt still takes back what it wrote (D-059). A local file (D-038) is never touched. Portable mode is unaffected: the run folder is already inside it.

**`fetch --list <url>` checks a link**, without downloading: the site, title, channel, date, duration, then the caption tracks as before (D-045, D-074) or "captions: none (<Site> doesn't provide captions for this video.)", whether there is audio ("audio only (m4a)", "with the video", or "none offered", from yt-dlp's formats), and "login: not asked". When the site asks for a login, it prints the site and "login: asked: …" and exits 3. It is for trying other platforms by hand.

Tests use a fake yt-dlp for a site with no captions and an audio-only format (Vimeo) and for Instagram's login wall: the full build goes to transcription, the lite build prints its line; the wall with no sign-in, with a browser from the flag and from Settings; the old key read and replaced; the audio deleted, kept with `--keep-audio` and with Settings; `--list` for Vimeo, for Instagram's wall and for YouTube.

## D-079 Unsupported sites, unknown durations, and one no-caption sentence

Three findings from a real Instagram test.

**Unsupported sites.** yt-dlp answers a link it has no extractor for with "Unsupported URL: <link>" (its UnsupportedError, raised by the generic extractor). That was printed raw, after "could not read the video:" and, in the menu, as an error. It now raises `UnsupportedSite` and says only "This site isn't supported. Download the video another way and use 'A file on this computer'.": on stderr with exit 1 for `fetch` (also `--list`), as a plain line in the menu, which then returns. Kwai is one such site (D-078).

**Unknown duration.** A site that gives no duration (Instagram) showed "0min00s". The details and `fetch --list` now say "duration: unknown". When step 2 runs, the decoder's length of the audio (faster-whisper's `info.duration`), rounded to the second, becomes the duration: printed as "duration: 0min50s (measured from the audio)" and written to meta.yaml. meta.yaml now records `duration` (seconds) whenever it is known, with `duration_from: audio` when it was measured; a site's own duration is never replaced. A local file (D-038) gets its measured duration the same way.

**One no-caption sentence.** On the command line, a site with no captions at all still printed step 1's "there is no caption in 'pt' for this video (manual: none; automatic: none)", in the warning and in the failure list. It now prints the menu's sentence, "<Site> doesn't provide captions for this video.". The detailed line stays when the site has captions but none in the language asked, or not the `--track` named; for that case `--caption-only` now prints the detailed line too, where D-078 had wrongly said the site had no captions, and the lite build goes on to D-057's notice as before D-078.

## D-080 The default caption language is the video's own

From Marco's test. `fetch` without `--lang` asked for `pt` whatever the video spoke, so an English video with an `en-orig` track came out as YouTube's machine translation into Portuguese, or as nothing.

`--lang` has no fixed default now. Without it, the language is yt-dlp's `language` field, spelt as its `-orig` track spells it when there is one (D-074), and its base code (`pt`) when it is regional (`pt-BR`) and only the base language has tracks. When yt-dlp names no language, a fixed order, never a guess between tracks: the only `-orig` track, when there is exactly one; else the only manual track, when there is exactly one; else `pt` (the old default), with one line: "the video's language is unknown: using 'pt' (--lang chooses another)". Several `-orig` tracks (dubs) with no language named is not resolved by picking one. `--lang` given wins, as before; `--track` wins over both (D-062). The menu's default track, when there is no original-audio track, is what fetch without `--lang` would take. Local speech recognition gets the base code (faster-whisper knows `en`, not `en-US`); a local file (D-038) has no site to ask, and keeps `pt`.

## D-081 In the original language, the channel's caption before the automatic one (provisional, amends D-045)

From Marco's test of 3S4vuHxGh7c (English): it has a manual `en` written by the channel beside `en-orig`, and the tool took `en-orig`. D-045 put the original automatic caption first because its measured alternative was a machine translation (fixture0003's `pt`), never a manual track; no fixture or run had shown a manual track in the original language until this one.

The order is now: a manual track in the original language, then the original audio's automatic one (`-orig`), then manual tracks of other languages, then automatic ones (dubs, D-074, and translations). `choose_language` (`--lang`, and fetch without it, D-080) tries the manual `<lang>` first; the menu's list puts, within each language group of D-074, manual before automatic, and its default is the first track in the original language, so the channel's own when there is one. The manual one is named "(written by the channel)", as since D-062. `--track` still takes exactly the track named.

Provisional: it rests on one observed video, 3S4vuHxGh7c. A channel's manual track can be worse than YouTube's recognition (a summary, or out of sync); if one turns up, this is revisited.

Nothing changes on the four fixtures: `fetch --list` on 2026-10-12 shows no manual track at all on any of them (fixture0003 and fixture0004: `pt-orig` and two dubs; fixture0001 and fixture0002: `pt-orig`), so the choice for each is the same track as before, and `scripts/measure.py` does not move.

## D-082 "Applied, please confirm", not "to confirm"

Wording only, from Marco's test: "to confirm 6" read as six changes waiting for a yes, when the medium band (D-011) is already applied in normalized.txt. The summary's counter is now "applied, please confirm N" and the report's section "applied, please confirm:"; the help (menu item 3 and `--review`) and both guides say the close guesses are already in normalized.txt and that the review confirms or undoes them. The counts are unchanged: the same forms, medium and ask band (D-060) as before; an ask-band name, never applied, is still counted there, as it was under "to confirm".

## D-083 A fuzzy match never takes in an ordinary word the term does not have

From Marco's test: `impressora que` was applied as `impressora 3D` (fuzzy, 81, medium band), and "comprei uma impressora que imprime peças" became "comprei uma impressora 3D imprime peças". The window is the term's first word plus an ordinary word that happens to be about as long as the rest.

When a fuzzy candidate's window holds a token that is one of the language module's `common_words` (D-032, D-066) and is not a word of the term (its canonical name or the form it was reached from), the fuzzy match is rejected, in every band. `impressora que` vs `impressora 3D`: `que` is ordinary and not in the term, rejected. `BR Portness` vs `BR Partners`: no ordinary word, allowed. `fluxo de caixo` vs `fluxo de caixa`: `de` is ordinary but is in the term, allowed. Exact, alias, inflection, unit and phonetic matches are not touched: a listed variant made of ordinary words is the pack editor's warning to give (D-066), not this guard's. English's list applies to English packs; the generic module has none, so nothing changes there. `COMMON_WORD_GUARD` in the matcher turns it off, for the tests of the confirmation loop and the pending list, which script answers against forms it now rejects (as D-047's tests hold the variant threshold).

Gate: annotations.json for the eight fixture × pack runs (frozen and bundled 0.3.7, no learned layer), before and after. None is byte-identical; every difference, with its gold verdict:

- No gold hit is lost. fixture0004, bundled, 5:03: `a DAPTA Valdre` (fuzzy 81) gave way to `DAPTA Valdre` (fuzzy 80), which is exactly the gold row's `wrong`; still a hit for the same row, and the speaker's `a` now stays ("a Adapta Valuer").
- Seven false positives fewer (applied, medium band): fixture0001, frozen and bundled, 19:36 `preço dela` → preço teto (85) and 29:16 `e caiu` → CEMIG (92); fixture0002, frozen, 15:54 `divide` → dividendo (85), which also leaves the manter row `15:54 divide a` untouched without D-027's rejection; fixture0002, frozen and bundled, 33:27 `preço até` → preço teto (84).
- Low marks (never applied, never scored) go, all of them windows with an ordinary word (`meu amigo` → CEMIG, `de venda` → dividendo, `projeção de` → preço teto, `de Minas` → M&A …), and six low marks take a shorter or neighbouring span instead: `dentre` → debêntures (fixture0003 3:59; fixture0004 5:29 and 5:40), `preço-alvo` → preço teto (fixture0004 15:02), `dívida` → dividendo (fixture0001 5:38), `preciso` → preço teto (fixture0002 20:57).

| fixture | false positives, frozen | false positives, bundled 0.3.7 | low marks at 70 | at 60 |
|---|---|---|---|---|
| fixture0003 | 6 → 6 | 4 → 4 | 106 → 84 | 456 → 291 |
| fixture0004 | 4 → 4 | 2 → 2 | 74 → 49 | 302 → 180 |
| fixture0001 | 14 → 12 | 15 → 13 | 110 → 80 | 466 → 245 |
| fixture0002 | 53 → 51 | 9 → 8 | 89 → 52 | 554 → 250 |

Hits, misses, aliases recognized and aliases wrongly substituted do not move anywhere, nor does pack fit. The regression test's bounds hold unchanged.

## D-084 Number words fold to digits, for matching only

From Marco's test: a speaker says tickers as words ("BOVA onze"), and the recognizer writes them so; the pack has `BOVA11`. Both language modules now fold the words for 2 to 20 to digits inside `normalize` (pt-BR: `dois`/`duas` … `vinte`, with `catorze`/`quatorze` and the pt-PT `dezasseis`, `dezassete`, `dezanove`; English: `two` … `twenty`). 1 is left out: `um`, `uma` and `one` are articles and pronouns far more often than numbers. A number word one space after a word ending in a letter joins it, as a ticker is written (`bova onze` → `bova11`), unless that word is itself a number word or one of the module's `common_words` (`de onze` → `de 11`). The spacing is otherwise kept, so no fuzzy score of a window without number words changes. It is folding: what normalized.txt shows is never rewritten from it, and an exact match of the term's own name stays a recognition (D-041), so "BOVA onze" is found as BOVA11 and left as said. The generic module does not fold.

Measured, eight fixture × pack runs: hits, misses, false positives, aliases, pack fit and the low marks at 70 do not move. annotations.json is byte-identical for six runs; for fixture0001 and fixture0002 with the bundled 0.3.7, one ask-band proposal each is gone, `para três` and `por três` → BR Partners (phonetic, 90, never applied, not scored): `três` is now `3`, and its skeleton no longer sounds like the name. The diagnostic count of low marks at 60 moves by one or two (fixture0003 291 → 289, fixture0001 245 → 244, fixture0002 250 → 251).

## D-085 Applied and suggested are counted apart (amends D-082)

D-082's "applied, please confirm N" counted the ask band (D-060) with the medium band, though an ask-band proposal (a name found by sound) is never in normalized.txt. The count now holds only the medium-band corrections, which are applied, one per form of each term as before. The ask-band proposals get their own line, "suggested, not applied M" ("(names that sound like a pack name)"), in the summary that `--summary` and the menu print, shown when M is not 0; report.txt has the matching section, "suggested, not applied:", after "applied, please confirm:". What the review asks, pending.txt and "Next: review the N uncertain one(s) now?" still cover both bands. Help and both guides say which is which. Tested with one of each: `fluxo de caixo` (fuzzy, medium) and `Berry Portene` (phonetic, ask).

## D-086 Context-conditioned forms (amends D-032)

D-032 keeps out of a pack any variant that is also an ordinary word or a common string, since a variant is corrected wherever it appears (`Ox` for OPEX is also an ox, and the start of Oxford). Some of those are the recognizer's usual error for a term in one kind of video and a plain word in every other. A form may now say when it is the term.

**Schema.** A term may have `context:` and `unless_near:`, each a mapping from one of its forms, its canonical name or a variant, to canonical names of terms of the same pack: `context: {Ox: [CAPEX]}`, `unless_near: {Ox: [pecuária]}`. The canonical name may carry them too, for a name that is an ordinary word (`Vale`). Aliases do not. The `variants:` list stays a list of strings.

**Detection.** A context term appears where the run holds one of its forms exactly, folded: its name, an alias, a curated or learned variant, an inflection (D-031a). Never by fuzzy or phonetic similarity: `a gente` is close to `agente` and must not stand for it. Its distinct occurrences (overlapping windows counted once, longest first) are counted over the whole run, all the form's context terms together.

**The rule**, only for a form that declares `context`, and for whatever matches through it (exactly, by inflection, or fuzzily from it): no occurrence, the form is not proposed at all; exactly one, it is asked (ask band, not applied); two or more, it matches as it would without a context. Then an occurrence with an `unless_near` term within 90 seconds, by caption timestamp (200 tokens when a timestamp cannot be read), is asked. A low mark stays a low mark. A phonetic proposal for a term follows its canonical name's condition. Forms without `context` behave exactly as before.

Gate: with no `context` in any pack, annotations.json for the eight fixture × pack runs is byte-identical before and after.

**Checked on load.** Every `context` and `unless_near` entry must be the canonical name of a term of the same pack (the error names the file, the term and the entry), and not one of the language's `common_words` ("context must be a specific term, not an ordinary word"): a context that is itself an ordinary word would be found in every video. A `context:` key must be the term's name or one of its variants.

**Writing it.** `pack add-term <pack> <term> --variant <form> --context <term,term> [--unless-near <term,term>]` writes the mapping for the command's variants, or for the term's own name when it adds none; entries may be given by any name of the term and are written as canonical names. A variant added with a context is exempt from D-005's three-letter refusal and from D-066's ordinary-word warning: the context is the answer to both (`Ox`). The menu, after each variant typed in Add a term, Edit a term → Add variants and Add a term you noticed, asks once "Is '<form>' also an ordinary word? If so, pick the pack terms that appear in a video when it means <term>", a multi-select over the pack's terms (ordinary-word terms left out); Enter skips.

**From the review.** After "Yes, but only in this video" (D-073), one question: "Save it for every video, but only when one of these terms appears?", with up to five terms found in this run at high band, most frequent first. Picking any saves the form as a learned variant with that context (the learned file's entry gains `context:`), instead of a local decision; Enter keeps it local. `pack propose` carries the context with the variant, so a conditional form is never proposed as an unconditional one.

**Why the whole run, by simulation.** The design was validated by simulation before it was written. A window of words around each occurrence fails, because the context word is said once and the garble thirty times: window-based context had 1 of 30 in recall. Context counted over the whole run had 27 of 30. Detecting context by free string or fuzzy similarity creates context that is not there (`a gente` ≈ `agente`), and weak context words destroy unrelated videos: 20 false positives. The rule above, whole-run positive context from pack terms plus a local negative check, made 0 false positives on the pure and the mixed runs, with the ambiguous occurrences asked.

**First real case: `Ox` → OPEX, financas-ptbr 0.3.8.** D-035 took `Ox` out of OPEX (0.3.4): the Northeastern `oxe` in a street-prank video (BIrASod49XY) became OPEX twice, at the cost of three gold hits in fixture0001, where the speaker spells the term out ("Ox. O PX. O editor vai escrever aí"). 0.3.8 puts it back with `context: {Ox: [CAPEX]}` and `unless_near: {Ox: []}`. Measured, no learned layer:

- fixture0001 against the bundled pack: 142 → 145 hits, 25 → 22 misses, false positives 13 → 13. The three gold rows come back (10:59, 11:03, 11:20), and a fourth `Ox` on the 11:03 line ("Ox é") is applied too, scored as the same row. CAPEX is found there 18 times. No other annotation of any fixture changes beyond the pack version; the frozen numbers do not move.
- The silence runs, forced: BIrASod49XY (pt-orig, 481 lines, fetched again 2026-10-17), whose two `Ox` lines (2:08, 2:12) were D-035's false positives: CAPEX never appears, so `Ox` is neither applied nor proposed. yJxxTf0IQC8 (its new manual pt track, and its pt-orig): no `Ox`, no OPEX, nothing applied.
- A synthetic mixed caption (tests/data/context-mixed.txt with tests/data/context-ia.yaml): Claude in the first half, cloud infrastructure in the second, and one sentence with both. `cloud` → Claude is applied three times, asked in the sentence with AWS and twice near AWS and Kubernetes; the infrastructure half alone proposes nothing.

## D-087 A pack may say which engine it needs (`min_engine`)

D-086 gave packs something an older engine does not know. An engine up to 0.6.5 reads a pack with `context: {Ox: [CAPEX]}`, ignores the key, and corrects `Ox` everywhere: checked, 0.6.5 with financas-ptbr 0.3.8 on BIrASod49XY applies `Ox` → OPEX at 2:08 and 2:12, D-035's false positives back. The packs repository was left at 0.3.7 for that reason. Nothing said which engine a pack was written for, and `pack install`/`pack update` installed whatever the index named.

**The field.** An index entry may have `min_engine`, the oldest engine version that understands the pack, as plain numbers (`"0.7.0"`). It is optional: an entry without it is read as before. A pack file may carry the same top-level `min_engine:`. Versions compare as numbers, padded with zeros (`0.7` = `0.7.0`, `0.10.0` > `0.7.0`); the engine's own version counts by its leading numbers, so a `0.7.0.dev1` build of the next release has its features. A `min_engine` that is not plain numbers cannot be checked and counts as too new: refused, not guessed. An engine whose own version is unknown (a source checkout never installed) is let through.

**Several versions of one name.** Every released engine with the registry (0.4.2 to 0.6.5, checked at each tag) reads `index.json` into a dict by name, so the last entry of a name wins, and ignores keys it does not know. So `min_engine` alone protects only engines from this one on; an old engine would still install 0.3.8. The index may therefore list a pack more than once, one entry per version, each at its own path: the newest first with its `min_engine`, the one for older engines last without it. An engine from this one on takes, for each name, the newest version it can use (numbers, not text: 0.3.10 after 0.3.9; the later entry on a tie, as before), and keeps the newest one it cannot as `held`, to say so. An old engine takes the last entry, the safe one. When no version of a name is usable, the newest is kept, marked, so it is still listed with the reason.

**What each command does** with a version this engine cannot use:

- `pack list`: the usable version in the table, or the entry with "needs 0.7.0+" beside its status; under the table, "financas-ptbr 0.3.8 needs transcript-normalizer 0.7.0 or later (this is 0.6.5); 0.3.7 is the newest for this version" (or "it cannot be installed with this version"), and where newer releases are.
- `pack install`: installs the usable version and says what was held back; with none, refuses, exit 1, even with `--force`, nothing written. `install()` itself refuses an entry that is too new, so no other way in (the menu, `pack update`) can write one.
- `pack update`: never updates past the newest usable version; "0.3.7 is the latest for this version; financas-ptbr 0.3.8 needs …", or "… 0.3.7 is kept".
- `pack list --installed`: no "↑ update" for a version that cannot be had; a line under the table says which.
- Merges (D-069), and so the menu's background look: an upstream entry this engine cannot use is no upstream; no offer is made for it, and `pack merge` says it was left out. Get a pack shows such a pack, not choosable, with the reason; when nothing is installable it says so and asks nothing.
- The menu's index cache keeps every entry, so the choice is made again on reading it.

**A pack file copied by hand.** `load_pack` refuses a file whose `min_engine:` is newer than the engine: "<file>: this pack (0.3.8) needs transcript-normalizer 0.7.0 or later (this is 0.6.5); it uses what an older version would ignore …". It is an `EngineTooOld`, a `ValueError`, so `normalize` prints it and exits 2, and the pack checks (`pack import`, the pack lists, the editor) refuse the file as they refuse a malformed one. This protects only engines from this one on: 0.6.5 and earlier ignore the key. No per-feature check was added (an engine finding `context:` refusing the pack): every engine that would run such a check already knows `context:`; the check for what comes later is `min_engine`, declared by whoever adds the later feature to a pack.

**Not done.** Packs are not refused for unknown keys: user packs written by hand may carry their own, and a strict schema is a larger change than this. The bundled financas-ptbr does not carry `min_engine`: it ships with the engine that understands it, and the version in pyproject (0.6.5 until the release) would make the engine refuse its own default.

Amended in 0.8.0: the included financas-ptbr now carries `min_engine`. It is a byte-for-byte copy of the packs repository's file, and 0.4.0 uses `match: exact`, so it says `min_engine: "0.8.0"` (D-090). The engine accepts its own included pack because it ships with the version the pack asks for: 0.8.0 includes 0.4.0. The check is the same as for any other pack file, so the included pack's `min_engine` must not be newer than the version in pyproject. A commit that brings in such a pack before the version bump fails its own tests: the engine refuses its default (it happened in 4ed1ce0, the pack commit of 0.8.0, at 0.7.0).

**Publishing financas-ptbr 0.3.8.** Once an engine with D-086 and this decision is released as 0.7.0: keep 0.3.7's file at a path of its own (e.g. `financas-ptbr/0.3.7/pack.yaml`, its sha256 unchanged), put 0.3.8 at `financas-ptbr/pack.yaml` with `min_engine: "0.7.0"` in the file, and list both in `index.json`, 0.3.8 first with `"min_engine": "0.7.0"`, 0.3.7 last. Engines up to 0.6.5 then keep 0.3.7; 0.7.0 and later get 0.3.8. Tested in tests/test_min_engine.py, with the running engine pinned at 0.6.5 and 0.7.0.

## D-088 The bundled pack is included, not installed

Until now financas-ptbr, shipped inside the package (D-043), was every user's pack from the first run: the menu listed it as installed, offered it first, and normalized with it unless told otherwise. The product is a transcript normalizer for any field; a finance pack active by default made it a finance tool by default, and someone with a medicine lecture met the wrong pack first. The pack ships inside the program for one reason: to work offline.

**Included, not installed.** A pack in the program's own `packs/` is *included*: available offline, never active until the user installs it. A fresh data folder has no pack installed. Installing an included pack copies it into the user's `packs/` and writes the same `installed.json` record a download writes (version and sha256 of the file), so `pack update`, the "edited here" check and `pack merge` treat it exactly as a pack from the repository. `pack install <name>` for an included pack waits at most 3 seconds for the index and takes the repository's version only when it is newer and this engine can use it; otherwise, and offline, the included copy. `--included` never reads the repository (the menu uses it when the version shown is the included one). `pack update` installs a newer included version too, offline, after a program upgrade. `packs/installed.json` does not say where a pack came from; `pack list --installed` calls it `included` when its record matches the included file's sha256.

**The menu.** "What is this video about?" lists, in this order: the installed packs (the pack offered first on top); the included packs not installed, "(included, not installed)"; the repository's packs not installed, "(from the packs repository)", when its index is had (the day's cache, else 3 seconds; when it is not reached it is not asked again for 10 minutes); "Create your own from a template…"; "None / another area"; Back. A pack in both the program and the repository is listed once, as included. Picking a pack not installed installs it (`pack install`, one line) and goes on normalizing; still one pack per run. A pack made from a template has no terms, so the menu says to add them and normalize again rather than normalizing with it. Packs → Installed packs lists only installed ones; Get a pack lists the included and repository packs together, included first. "The pack offered first" is offered only when a pack is installed, and with exactly one it is that one without asking. The first screen says "Pack offered first: <name>", or, with none installed, "No pack installed yet: you will be asked what the video is about."

**What does not change.** A user with a pack in `packs/` (installed, or a copy, D-066) sees no change: it is installed. `normalize --pack` keeps its default (D-017): `packs/financas-ptbr.yaml` when there is one, else the included file, so scripts, fixtures, `scripts/measure.py` and the tests keep using the bundled file directly. `pack copy` still works on an included pack that is not installed. `pack remove` of an installed included pack deletes it from `packs/` and says it can be installed again; the included file is never touched.

Tested in tests/test_included.py; the tests of the repository's behaviour (test_registry.py, test_min_engine.py) run with nothing included.

## D-089 `TRANSCRIPT_NORMALIZER_HOME` moves config.toml too (amends D-061)

D-061 put config.toml in `platformdirs.user_config_dir("transcript-normalizer")` whatever else was set, and made `TRANSCRIPT_NORMALIZER_HOME` move only runs/ and packs/. So a script, or a measurement run with its own folder, still read and wrote the user's real settings: the sign-in, the pack offered first, keep_audio, all from `~/.config`, shared with every other run on the computer. The variable exists to put a run somewhere of its own (D-052: "for the tests and for a portable copy"); half of it stayed behind.

With the variable set, `runs.config_file()` is `<variable's folder>/config.toml`, and every read and write of the settings happens there; the user configuration directory is neither read nor written. The file sits at the folder's root, beside runs/ and packs/, the same place the portable folder keeps it (`data/config.toml`, D-070), so the two ways of keeping everything in one folder lay it out the same. The order is base_dir's: the variable, then portable, then the user configuration directory. A `data_dir` key in that file is read but changes nothing, since the variable already wins over Settings (D-061). Without the variable nothing changes.

Tested in tests/test_home_config.py, with the platform's configuration directory redirected to a temporary folder: a write with the variable set lands only in the variable's folder, and the other stays empty.

## D-090 A term may match only exactly

Some terms are short codes or names that every similarity source reaches by accident: a ticker one letter from a word, a name whose plural or number word is something else. A term may now say that it matches only by equality with its own forms.

**Schema.** A term may have `match: exact`, the only value; anything else is refused on load. Without the key a term matches exactly as before. A term with `match: exact` may also have `case_sensitive: [..]`, forms of its own (its canonical name, an alias or a curated variant), written exactly as the pack writes them; each listed form matches only with that case and those accents. A `case_sensitive:` without `match: exact` on the same term, one that is not a list, or one that names something not among the term's forms (`vale` when the term is `Vale`) is refused, with the file, the term and the reason.

**What it turns off, for that term only.** Fuzzy matching (D-011, D-025, with D-005's length rule and D-047's variant threshold): the canonical name and the curated variants are no longer compared by similarity. The phonetic source (D-050, D-060, D-068), even when the term's class is phonetic. D-031a's inflection: a plural of the term or of an alias is not the term spelled out. D-084's number words: the term's forms and the text are compared in the language module's new optional `fold`, which is `normalize` without number words (pt-BR and English; a module without it uses `normalize`, as the generic one does, which folds no numbers). So `BOVA onze` is not `BOVA11` for such a term, while `BOVA11` is.

**What stays.** The name, the aliases and the variants, curated and learned (D-013, D-020), match by equality after that fold: case and accents ignored, and whatever else the language flattens (`P/VP` is `P VP`), unless the form is listed in `case_sensitive`. A case-sensitive form is compared as written, word by word, so `Vale` is the company and `vale a pena` is not; this restricts D-041's folded comparison for the forms listed, and is not a case-only correction (D-008): it decides whether a form is found, never rewrites case. The guards that read exact forms keep reading the term's: D-030 as D-049 amends it, D-031b as D-034 amends it, and D-040; for this term they see its exact forms only, with no inflection and with its case-sensitive forms only where they match. Rejections (D-027), local decisions (D-073) and the unit rules (D-006) are unchanged.

**Pack fit and context.** Nothing changes in D-054: a recognized exact term is a high-band annotation and counts like any other, and a form with `context:` and none in the run is not proposed, so it does not count. As a context term (D-086) an exact term is found only by its exact forms, with no inflection, no number words, and its case-sensitive forms only in their case. An exact term may itself declare a `context:`.

**Merging (D-069).** `match` is a scalar and merges as one. `case_sensitive` is a list merged like aliases and variants (both sides' additions, minus what either side removed), but by exact spelling, since its forms differ from the term's others only in case. After the conflicts are answered, a case-sensitive form whose form the merge took away is dropped, and so is the whole list on a term that is no longer `match: exact`, each with a notice, so the result still loads.

**Older engines.** An engine without this decision ignores both keys and matches the term fuzzily, by inflection and by sound, which is what the pack meant to stop. A pack that uses `match:` therefore declares `min_engine:` (D-087) equal to the first released engine that has this decision, in the file and in its index entry, and bumps its minor version (CONTRIBUTING 2.7: a new key). As D-087 decided, the loader does not check this for the pack author: the engine that would run such a check already knows the key.

Gate: with no `match:` in any pack, annotations.json is byte-identical before and after for thirteen runs: the four fixtures against their frozen pack and against the bundled 0.3.8, fixture0002 with tests/data/fixture0002.learned.yaml, fixture0001 and fixture0004 with a learned layer of confirmed variants, an alias and a context-conditioned variant, tests/data/context-mixed.txt with context-ia.yaml, and tests/data/xx with the generic module. Tested in tests/test_match_exact.py and tests/test_context.py.

## D-091 A legenda.txt is never replaced unasked

A run's `legenda.txt` is the provenance of everything taken from it: a project cites its lines by their timestamps, as D-022's header says. Three commands wrote it without looking at what was there: `fetch` of a link (D-059 takes back only a failed attempt), `fetch` of a local file, and `normalize` of a `.srt` or `.vtt` (D-038's conversion). Running any of them again, with another model, track or file, changed the text under every citation already made, and said nothing. A project that cites these files asked for this to stop.

**Before any work.** Each of the three reads the `legenda.txt` already in the folder it would write to, if any, before downloading or transcribing anything. Its header says where it came from: the kind (platform caption, local transcription, converted file, by the header's first line), the link (`# URL:`), the file (`# Arquivo:`), the model (`# Modelo:`) and the track (`# Origem da legenda:`).

**The same source: used as it is.** For a link, the same video (the same link, or one with the same video id), and nothing asked that the text there does not have: `--whisper` needs a local transcription, `--caption-only` or `--track` a platform caption (that track), and a local transcription counts only with the same `--model`. For a local file, a local transcription of a file with that name, with the same model. For a subtitle, a `legenda.txt` with the same lines, whatever its header says (another day's, or fetch's). Then nothing is written, the command says the text is already there, and it exits 0. Re-running the same command is therefore safe, and a script that fetches every time gets the same file back.

**Another source: refused.** The command writes nothing, says what is there and why it stopped, and exits with 4 (`caption_guard.EXIT_CAPTION_EXISTS`; 1, 2 and 3 are taken). It names the two ways on: `--out <folder>`, to keep both, and `--replace-caption`.

**Replacing.** `--replace-caption`, on `fetch` and `normalize`, moves the `legenda.txt`, its `meta.yaml`, and what was made from it (annotations.json, normalized.txt, normalized.speakers.txt, report.txt, local-decisions.yaml, needs-review/) into `replaced-<YYYY-MM-DDTHH-MM-SS>/` inside the run, `-2`, `-3` when the second is taken; nothing is deleted. The kept audio (D-078) and a kept subtitle (`--keep-raw`) are sources, not derived from the text, and stay. For a link, the move happens before the download, and a failure puts everything back where it was, after D-059 has taken back what the attempt wrote. For a local file and a subtitle, the move happens once the new text is ready.

**The menu asks.** When fetch stops for this, the menu asks "The run folder already has a text. What now?": "Keep the one there" (the default: nothing is downloaded, and it is the one normalized next) or "Replace it" (the command again, with `--replace-caption`). A subtitle picked as "A file on this computer" is asked the same. After a fetch that used the text there, "normalize this run now?" is about that run, not the one written last.

**A subtitle in a run folder belongs to that run.** `normalize runs/<id>/<file>.vtt` (a subtitle `--keep-raw` left there) converts into `runs/<id>/`, not `runs/<file>/`, so it meets the text fetch made from it, with the same lines.

Tested in tests/test_caption_guard.py. One existing test changed: test_track_on_the_command_line_takes_that_exact_track fetched three times into the same folder, expecting each to write; it now writes each into a folder of its own with `--out`.

## D-092 Passages a local transcription wrote twice are found and shown

Measured on a 2h40 lesson transcribed whole with faster-whisper medium (D-036's step 2): around 44:29, a passage of 24 words said at 44:06 and 44:24 came out a second time, and what was said there was lost; and within the stretch compared, the timestamps after it were about 7 seconds off. The same model, on a clip of 44:02 to 44:33 of the same file, had it right. That 7 seconds was seen only in comparing the long file with that clip, and says nothing of the rest of the lesson: a measurement made by the project that uses this library (2026-11-22), aligning each block of another transcription with its own clock against the same word in `legenda.txt`, gave a median difference of 0 s, with a precision of about 1 s, before 44:00 and after 44:40, and in each stretch of the lesson after it. Within 44:00 to 44:40 nothing was measured. What was lost was said between 44:02 and 44:06, before the first copy. With the VAD on or off, and the volume normal (mean -25.9 dB, peak -2.6 dB), so the cause is how the long file was cut into windows, not the model, the VAD or the audio. A larger model was not tried as a fix: nothing says it is cut differently.

The text cannot show what is missing, but it can show what came out twice, which is where to listen. After a local transcription, fetch compares the transcription's words, folded (lowercase, accents off, punctuation out), six at a time. A run of them that repeats one whose first copy began less than 60 seconds earlier, without overlapping it, is a repeated passage; runs that touch are one passage. Its first copies are kept apart when they are apart in the text (the lesson's passage repeated two stretches, said at 44:06 and at 44:24, back to back), and each is named, so a report never covers words between them that were not repeated. A passage counts from 15 words up, counting only the words outside its own first copies: a refrain sung four times in a row overlaps itself and is not a passage written twice. The threshold is that lesson's: its second longest repetition within a minute was 13 words, and was said; 15 keeps the one passage that was lost, and only it. It is calibrated on one case, and the decision says so: a speaker who repeats 15 words within a minute is flagged too, and listening settles it.

A language other than the text's is another source too: `--lang en` where a `pt` caption or transcription is stops (D-091). An attempt stopped by Ctrl+C takes back what it wrote and puts a replaced text back, as a failed one does. A local file's transcription looks again for a text in its folder once it is done, since another run of the same file may have written one meanwhile; that narrows the window, it does not lock the folder.

What a passage gives: a line fetch prints ("1 passage(s) came out twice, at 44:29: listen there before citing"); `needs-review/repeats.txt` (D-023), each passage with the time of its first copy, its length and its lines as written; and lines in the header of `legenda.txt`, so the warning travels with the file: `# Trecho repetido: 1. Ouca o audio antes de citar estes trechos:` and `#   44:29 a 44:33 repete 44:06 e 44:24 a 44:29 (24 palavras); a fala real ali pode ter se perdido.` With none, the header says `# Trecho repetido: nenhum encontrado. Isto nao garante que nada faltou.` The header's limitations become three, the third being this one. The text is never changed: no line is removed, no timestamp moved.

Only local transcription is searched. A platform caption rolls (subtitles.py) and is not cut into windows the same way, and nothing like this was measured on one; the four fixtures, which are platform captions, have no passage at 15 words.

Not done: transcribing a second time with windows shifted by half, to recover what was lost. It doubles the time, and is left for later.

Tested in tests/test_caption_guard.py.

## D-093 The header says which moment of a line the timestamp is

A line of a platform caption, or of a converted `.srt` or `.vtt`, is stamped with the end of its cue (subtitles.cues_to_lines); a line of a local transcription with the start of its segment (fetch.transcribe). The header said only "Cada linha comeca com o timestamp mm:ss", and a project reading these files wrote that every timestamp is the end, which for a transcription is wrong by the length of the segment.

The three headers now say it. A caption and a converted file: `# Cada linha comeca com o timestamp mm:ss do FIM do trecho: o` / `# instante em que a legenda sai da tela. A fala comeca antes dele.` A transcription: `# Cada linha comeca com o timestamp mm:ss do INICIO do trecho: o` / `# instante em que a fala comeca.` The rest of the paragraph is unchanged. The converter and the transcriber are not changed: the same moments as before, now named.

A `legenda.txt` written before this decision keeps its header; its kind (the first line) still says which convention it has. The fixtures keep theirs, since they were fetched before it: test_header_writer_reproduces_the_fixture_header now checks that the writer gives the fixture's header with this one paragraph replaced, and tests/data/rolling.legenda.txt, the converter's expected output, has the new paragraph.

## D-094 The fixtures name no channel, video or link

The four fixtures were folders named after the videos' ids, and each caption's header (and meta.yaml) kept the video's title, channel, publication date and link, as fetch wrote them. The repository is public; the owner asked that it carry the terms only, with no tie to the channels the captions came from.

**Renamed.** The folders and every reference to them (tests, scripts, experiments, guides, CONTRIBUTING, this file, the CHANGELOG, the frozen packs' comments) use `fixture0001` to `fixture0004`. Which video each was is not written anywhere in the repository. Eleven characters, so the run id is still read from the header (D-018).

**The headers.** `# Titulo:` is the fixture's name, `# Canal:` and `# Publicado:` say `omitido`, and `# URL:` is `https://example.invalid/watch?v=<fixture name>`: a reserved domain that never resolves, with the fixture's name where the video id was, so a caption still normalizes into `runs/<fixture name>/` and the tests of D-018 keep their input. meta.yaml in fixture0003 and fixture0004 the same. Nothing below the header changes: the caption's lines, gold.csv and the frozen packs' terms are byte for byte what they were, and `scripts/measure.py` prints the same numbers, only in the new names' order.

**Tests.** The header writer's test describes the fixture's video with these values, and the catalog's test, which read a publication date from the fixture's header, now writes one into its copy, since the fixture has none.

**Not done here.** The included financas-ptbr.yaml names the old ids in its comments; it is a copy of the packs repository's file at a released version, so its next version there renames them, and this copy follows when it is included. The release workflow's check that fetch reaches YouTube (`fetch --list`) used one of the fixtures' videos; it now uses another public video the owner chose, from a channel none of the fixtures came from, which `fetch --list` shows with an `original: pt-orig` track, as the check requires. The text the speakers said is still in the captions, and the git history still has the old names and headers: changing history was not asked for.

## D-095 An edited pack keeps its generated part

financas-ptbr 0.4.0 has 282 companies written by the packs repository's tools/gerar_termos.py, between two comment lines inside `terms:` (`  # >>> início da parte gerada`, with the generator's notes after it, and `  # <<< fim da parte gerada`); the generator finds its part by those lines to write it again. Saving a pack after an edit (D-066's add-term, edit-term, remove-term, and D-069's merge) loads the YAML and dumps it, so every comment below the top was lost, the markers with them, and a new term went to the end of `terms:`, after the generated ones. An edited copy, exported or proposed whole (D-067), could no longer be regenerated, and its hand-written and generated terms were mixed.

When the pack being saved has such a part (a comment line starting `# >>>` inside the file, comment lines after it, and later one starting `# <<<`), the terms it held, by name (read as YAML, so an entry whose `term:` is not its first key counts too), are written last in `terms:`, in their order, between the same marker lines, written as they were. Every other term, a new one included, goes before the part. A generated term renamed by hand is no longer the generator's, and leaves the part. With every generated term removed, the markers stay, with nothing between them. A merge takes the part from upstream, which regenerated it, and from the copy when upstream has none.

Not changed: the other comments inside `terms:` are still lost on save, as before (the ones at the top are kept by D-066). Keeping every comment needs a YAML library that round-trips them, a new dependency for the executables; not done for this.

Tested in tests/test_pack_upkeep.py; test_copy_of_the_bundled_pack_is_used_instead_and_editable now expects the added term before the generated part.

## D-096 `pack import` takes the pack's name, not the export's file name

A pack has no name inside the file: it is the file's name (D-017). `pack import` took the file's stem, so a file written by `pack export`, `<name>-<version>.yaml`, was imported as a pack called `financas-ptbr-0.4.1`, beside `financas-ptbr`, and a pack from the packs repository, `<name>/pack.yaml`, as a pack called `pack`.

Now the name is taken as the files that hold packs are named: a stem ending in `-<the pack's own version>` loses it (`med-ptbr-0.1.3.yaml` with `version: 0.1.3` is `med-ptbr`; `med-ptbr-2.yaml` stays `med-ptbr-2`); `pack.yaml` takes its folder's name, or the folder above when its folder is a version (`financas-ptbr/0.3.9/pack.yaml`), from the file's absolute path, so `pack import pack.yaml` from inside its folder works; anything else is the stem, as before. `--name` chooses the name instead. When the name is not the stem, import says where it came from. A name that is not a pack name is refused as before, with both ways out (rename the file, or `--name`). A pack of that name already in `packs/` still needs `--force`.

Tested in tests/test_pack_upkeep.py.

## D-097 The menu updates an installed pack that was not edited

`pack update` installs the newest version of every pack installed with `pack install` and not edited here, from the repository or, after a program upgrade, included in the program (D-088). The menu had no way to it: Packs offered "Merge an update" only for a copy of the user's (D-069), so a pack installed as it was stayed at its old version until the command was typed, and normalize kept using it (D-017).

Packs now has "Update packs", which runs `pack update`, whenever a pack is installed. Its description names what this program includes that is newer ("financas-ptbr 0.4.0 → 0.4.1 (included)"), and otherwise says what it does. When this program includes a newer version of an installed pack not edited here, the first screen and Packs say so in a line: "financas-ptbr 0.4.1 is included in this version (installed: 0.4.0). Packs → Update packs installs it." That look reads only files, so the first screen never waits; a newer version only in the repository is found when Update packs runs, as the command does. Nothing is updated unless asked. The option is last in Packs, so the numbers of the others do not change.

Tested in tests/test_pack_upkeep.py.

## D-098 The included financas-ptbr is 0.4.1

The copy of financas-ptbr inside the program (D-088) is the packs repository's 0.4.1, byte for byte (sha256 `0c5bcdb14977865daf0febe3f1fbced742372851df3dee5b49b345644a767de6`, as its index publishes). Two changes from 0.4.0, measured and decided there:

- BR Partners has `match: exact` (D-090): only its name, aliases and listed variants count. On a 2h40 lesson transcribed locally, 0.4.0 applied `aportes` and `portas` as BR Partners 10 times and asked about 5 more; 0.4.1 does none of it. Its cost is fixture0003's two hits that came fuzzily from ordinary words (`portas`, `Portes`), with one false positive fewer. The owner accepted the drop.
- Four curated terms tied to channels rather than to the market go: a channel's name, a presenter's, a product and a course. Their gold rows stay in the fixtures and are now misses: 4 in fixture0001, 2 in fixture0003, 4 in fixture0004.

So the included pack is no longer a superset of every term in the fixtures' frozen packs and gold files (D-017's "nothing is dropped"): those four are the exception, named once in tests/conftest.py (`TAKEN_OUT_IN_0_4_1`), and the tests check the rest is still there and those four are not. The bundled-pack numbers in GUIDE section 8 follow `scripts/measure.py`: fixture0001 119 of 167, fixture0002 168 of 222, fixture0003 101 of 119, fixture0004 40 of 45. The frozen fixture packs, and so the regression bounds, do not change.

An installed 0.4.0 that was not edited is offered 0.4.1 by the menu and by `pack update` (D-097); one that was edited is offered a merge (D-069).

## D-099 A local file is the same file by its content

D-091 told a local file transcribed again from another one by its name only, the `# Arquivo:` line of the header, which has no folder. Two courses each with an `aula1.mp4` go to the same `runs/aula1/`, so the second one was taken for the first, and its transcription was the first one's text, with exit 0 and "already here, from the same source".

A transcription of a local file now writes a line after `# Arquivo:`, `# Impressao digital: sha256 <hex>, <n> bytes`, the file's SHA-256 and size, read before transcribing. Fetching a local file again compares that: other content is another source, and the command stops with exit 4 (D-091) and says the file "has other content"; the same content is the same source whatever its folder or name, and the text there is used. The comparison is made before transcribing and again before writing, as D-091's. The file is read again after transcribing: if it changed meanwhile, nothing is written and the command exits 1, so the line always names the content that was transcribed. A file that cannot be read stops the command the same way.

A `legenda.txt` written before 0.8.3 has no such line, and the name decides, as it did: the program cannot know which file it came from. Transcribing it again with `--replace-caption`, or deleting the run folder, writes one with the line. A converted `.srt` or `.vtt` is unchanged: it was already compared by its lines.

## D-100 Learned entries for a term the pack no longer has are said

The learned layer (D-013) is read by the pack's term names. An entry for a term the pack no longer has (D-098 took four out) stayed in the file and was skipped, with nothing said: its variants stopped being corrected without a word.

`normalize` now says it, on standard error, before normalizing: how many entries, for which terms, that they stay in the file and are not used, and how to use them again (`pack copy`, then `pack add-term` with the term). Nothing is removed from the learned file and nothing is changed in the pack: putting the term back is a choice of the person whose layer it is. The exit status is unchanged.

## D-101 The stretch around a passage written twice is transcribed again on its own

D-092 finds where a long transcription wrote a passage twice, but cannot say what was lost there, and the person who listens starts from nothing. Yet the same model, on a clip of that stretch alone, got it right. So after a local transcription, each passage's stretch is cut from the same file and transcribed again on its own, with the same model, language and options (the VAD on, as always), and written to `needs-review/repeats/<m-ss>.txt`, named after the second copy's time.

**The stretch.** From 15 seconds before the earliest first copy to 10 seconds after the line where the second copy ends. It starts before the first copy because what was lost may have been said before the passage the transcription repeated: in D-092's lesson it was between 44:02 and 44:06, and the first copy is at 44:06. That lesson's stretch is 43:51 to 44:43, which holds the clip that came out right. Only the stretch is decoded, from the nearest keyframe before it, mono at 16 kHz, as faster-whisper decodes a file. Times count from the audio stream's own start, as a whole file's transcription does from its first sample, even when a file starts its audio after the container's start. The stretch's times are added to its start, so they read as `legenda.txt`'s do, the start of each segment (D-093).

**What it is.** Help for listening (D-102 dropped "never a source"). `legenda.txt` is not changed. Each file says so, which stretch it is, of which file (its name and fingerprint, D-099, or the url of the downloaded audio), with which model, and how the file is known to be the one `legenda.txt` came from. A loss that wrote nothing twice is still not found, and the header still says that no passage found does not mean nothing was lost. A stretch that fails, or a file that cannot be written, is said and skipped; the text is already written by then, and nothing here can undo it. Two passages that start on the same line get two files, `44-29.txt` and `44-29-2.txt`. A local file is read again once its stretches are done, as after a transcription (D-099): if it changed meanwhile, the stretches are not kept, and `--recheck` exits 1. What a program does with a stretch's text is that program's business (D-102).

**A text already there.** `fetch FILE --recheck` does the same for the `legenda.txt` in FILE's run folder (or `--out`): it finds the passages in it and transcribes each stretch again from FILE, with the model and language the header names, in seconds rather than the hours of the whole file, and writes `repeats.txt` too, which a text before 0.8.2 lacks. `legenda.txt` and `meta.yaml` are not touched, and `needs-review/repeats/` is written anew. FILE is checked against the header's fingerprint: other content stops with exit 4 (the text there is of another source, D-091) and writes nothing. A text written before 0.8.3 has no fingerprint, and is refused (exit 1) unless `--unverified-source` is given; then FILE must still have the name the header gives, and each stretch's file says it was not checked. Only a local transcription that names its model is rechecked; a platform caption or a converted subtitle has no audio to go back to. A url is refused: the audio downloaded for it is deleted after transcribing, unless kept with `--keep-audio`, and a kept audio is a local file.

## D-102 The library carries no rule of a program that uses it

The header of a `legenda.txt` said two things that were rules of one program that imports this library, not facts about the text: "NAO E CONHECIMENTO AUTORADO. Nao carregue isto em conhecimento/." (`conhecimento/` is that program's folder) and "O timestamp e a procedencia de qualquer afirmacao extraida daqui" (that program's rule of provenance, which it has since dropped for knowledge taken from transcriptions). Both lines are gone from the three headers (D-022, D-038, D-087). What a program does with the text, and whether it records where the text came from, is that program's business.

Advice that said "before citing" says "before using" (the header's limitations, D-092's warning, `repeats.txt`), and D-101's stretch file no longer says it is "not a source" to cite from: it is help for listening, and `legenda.txt` was not changed.

What stays has a use of its own: the timestamp on each line and the moment it marks (D-093), to find the stretch in the audio; the fingerprint (D-099), for D-091's check; the warning of a passage written twice (D-092) and its stretch (D-101); the three measured limitations; and whether a person or an AI wrote the text. D-091's protection stays, for its own reason: `normalized.txt`, the review lists in `needs-review/` and any note taken by timestamps are made from that text, and changing it unasked would leave them out of step without a word. D-005's reason is the same: a correction keeps the line's timestamp so the stretch can still be found in the audio.

A `legenda.txt` written before 0.8.5 keeps the old lines; nothing reads them, and D-091's check reads the header's fields, not these lines.

## D-103 A timestamp from 1 hour on is written as a video player shows it

A line's timestamp was always `m:ss`, with minutes past 59: `74:14` where a video player shows `1:14:14`. Finding the moment in the player meant converting it by hand. From 0.8.6 a timestamp is `m:ss` before 1 hour, as it was (`44:29`), and `h:mm:ss` from 1 hour on (`1:14:14`), in the three kinds of text (D-022, D-038, D-087), in D-092's warning and `repeats.txt`, and in D-101's stretch files, whose name follows (`1-14-29.txt`). The header says so in one line: `# Antes de 1 hora, m:ss (44:29); depois, h:mm:ss (1:14:14).` One function writes every timestamp (`stamps.clock`), and one reads both forms (`stamps.seconds`); the matcher and the review already read `h:mm:ss`, D-092's search now does too. Nothing is slower: it is how a number is written.

**Texts written before.** They keep `74:14`, and every reader takes it. D-091's check of a converted `.srt` or `.vtt` compares lines by the moment they name, so a subtitle converted before is still the same subtitle, not exit 4. `restamp <run folder or legenda.txt>` rewrites an old text the new way: the timestamp at the start of each line; every timestamp in the lines the program itself wrote about passages written twice (the header's `repete` lines, `repeats.txt`, the stretch files, renamed too); and the header's line that named the form `mm:ss`, followed by the new line above. No word changes, and a time said in the speech ("às 10:30", or `74:00` inside a line) is left as it is: only the leading stamp of a line of speech is a timestamp. What it changes is kept first in `replaced-<date and time>/` (D-091's archive), and so is what `normalize` made from the old text, which names the old timestamps and is to be made again; `meta.yaml` and what has nothing to rewrite come back as they were. A failure puts the run back as it was, a half-written file included. Two stretches that would end up under one name (an old `74-29.txt` beside a `1-14-29.txt`) stop it before anything is moved. Run on a text already the new way, it says so and writes nothing. The header's fields D-091 reads (model, language, file, fingerprint) do not change, so the same source is still the same source.

## Open, not yet decided

- Calibration of the two thresholds of D-011.
- Multi-word term fuzzy matching (`preço dela` → `preço teto`): whether each word of a multi-word term must match its counterpart individually. D-083 rejects that example, since `dela` is an ordinary word; the question stands for windows without one.
- A collocation layer (D-032): matching a term by the words around it, for misrecognitions that are ordinary words (`tira`, `rápido`, `divide`) and cannot be exact variants.
