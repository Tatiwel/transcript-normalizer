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

## Open, not yet decided

- Calibration of the two thresholds of D-011.
- Whether the confirmation loop of D-011 writes to the pack file directly or to a separate user layer (the layered-dictionary question from the research consolidation).
- Multi-word term fuzzy matching (`preço dela` → `preço teto`): whether each word of a multi-word term must match its counterpart individually.
