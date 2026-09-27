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

## Open, not yet decided

- Calibration of the two thresholds of D-011.
- Multi-word term fuzzy matching (`preço dela` → `preço teto`): whether each word of a multi-word term must match its counterpart individually.
- Inflection of the term itself (D-030): whether a span that is the term plus a plural ending (`dividendos`, `valuations`) counts as the term spelled out, which would block all of D-030's new false positives from plurals and keep all its gains.
