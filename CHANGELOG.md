# Changelog

## 0.4.0

- An interactive menu: `transcript-normalizer` with no arguments, on a terminal. Every item runs a subcommand, so nothing is reachable only through the menu. `help`, `--help` and `?` print one sectioned reference, and `?N` prints one item's entry (D-051).
- A fourth matching source: a pt-BR consonant skeleton for names (companhia, pessoa), at 85 and always medium band. It closes the phonetics question (D-010) that experiment 3 measured (D-050).
- Fuzzy matches reached from a curated variant need 85, while the canonical term keeps 80 (D-047). The evaluator scores only what reaches normalized.txt (D-048). A name blocks a candidate only when it covers the whole candidate (D-049).
- A fourth fixture, 4tTmY8Buask: a new sector with the same speaker as the third. It is the first garble that means two terms depending on context (`dividendio`, D-046). Gold fixes in three fixtures (D-047, D-049).
- Pack 0.3.3: BR Partners and the other terms of the fourth fixture, `commodity` as an alias, `dividend` as an alias of dividend yield, and no more `bicho` or `dividend` as variants of other terms.
- Extras: `[captions]` gives fetch with platform captions only; `[ingest]` adds local speech recognition. platformdirs joins the core dependencies.
- The standalone executable keeps runs/ and packs/ in `Documents/transcript-normalizer/` (D-052).
- A release workflow builds the wheel, the sdist and the `lite` and `full` executables for Windows, Linux and macOS on each tag, with checksums. CI runs the tests on all three systems. No ffmpeg is bundled (D-052, amended).

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
