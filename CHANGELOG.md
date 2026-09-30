# Changelog

## 0.3.0

- Matching runs against a pack the user declares, never against the language: text that resembles no term is never touched (D-001, D-002, D-003); word-boundary splitting and phonetic matching are deferred, and a mis-assigned variant is fixed in the pack, not the matcher (D-009, D-010, D-014).
- Corrections are stand-off annotations: the caption and its timestamps are never modified, and matching runs over the joined text, across caption breaks (D-004, D-007, D-012).
- Short strings match exactly and units are regex rules applied first; unit terms never go fuzzy (D-005, D-006, D-028).
- Three confidence bands: apply, apply and ask, or only mark, with thresholds 80 and 70 (D-011, D-029).
- The confirmation loop asks per variant, saves after every answer and writes to a personal learned layer, never into the pack; rejections suppress by containment (D-013, D-019, D-027, D-037).
- Two kinds of annotation: corrections are substituted, aliases and canonical mentions are recognized and left as said (D-020, D-025, D-041).
- Guards against over-reach: whole-word "already spelled out", inflections count as the term, no n-grams across sentences, and an exact name beats any guess or shorter correction overlapping it (D-024, D-030, D-031, D-034, D-040).
- Language-specific rules live in language modules, and packs curate ordinary words out (D-021, D-032, D-033).
- Outputs go to `runs/<video-id>/` with `meta.yaml`, `normalized.txt` and `needs-review/`; `fetch` takes a url or a local file, falling back from platform captions to faster-whisper (D-015 to D-018, D-022, D-023, D-036, D-038).
- Three regression fixtures scored by one gold rule; the finance pack (0.2.4) ships inside the package and is the default when no `./packs/financas-ptbr.yaml` is present; a manter row forbids corrections, not recognitions (D-008, D-026, D-039, D-042, D-043).
