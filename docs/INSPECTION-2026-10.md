# Codebase inspection, 2026-10-08

Read-only inspection of `main` at `50e3c5c` (0.6.3 + Unreleased). The only file written is this report. Tools ran ad hoc via `uvx` and `uv run --with`, with nothing added to pyproject. Mutation checks ran in a scratch copy (`git archive HEAD`), never in the tree.

Machine: Linux, 12 cores, Python 3.12.14 (the project venv). All timings are wall-clock, best of 3 unless noted.

---

## 1. Inventory

### Core: the matching engine; `import transcript_normalizer` loads only this

| module | lines | role |
|---|---:|---|
| `__init__.py` | 29 | public API |
| `core/matcher.py` | 470 | windows, scoring, guards, phonetic source, overlap resolution |
| `core/pack.py` | 422 | pack and learned-layer loading and saving |
| `core/standoff.py` | 104 | `Annotation`, bands, JSON |
| `core/text.py` | 88 | caption → joined text with offset map |
| `core/render.py` | 54 | `normalized.txt` view |
| `core/rules.py` | 33 | unit-rule hits |
| `core/fit.py` | 24 | D-054 pack fit |
| `core/__init__.py` | 5 | docstring only |
| `languages/` (5 files) | 346 | `base`, `generic`, `pt_br`, `en`, registry |
| `runs.py` | 288 | paths: run dir, data dir, learned file, portable mode (imported by `core.pack` for `learned_file`) |
| **core total** | **1,863** | |

### Product layer

| module | lines | role |
|---|---:|---|
| `interactive.py` | 1,203 | the menu |
| `ingest/fetch.py` | 913 | yt-dlp / faster-whisper fetch chain |
| `cli.py` | 827 | argparse, normalize, confirm/review loops |
| `merge.py` | 800 | D-069 three-way pack merge |
| `prompts.py` | 501 | questionary/rich adapter and plain fallback |
| `packedit.py` | 445 | D-066 pack editing |
| `packfiles.py` | 351 | pack list/install/create |
| `contribute.py` | 339 | D-056/D-067 proposals |
| `evaluate.py` | 297 | gold scoring (dev tooling, also used by tests and measure.py) |
| `registry.py` | 296 | packs index |
| `helptext.py` | 206 | help screen |
| `ingest/` (rest) | 362 | `header`, `subtitles`, `console`, `__init__` |
| `catalog.py` | 90 | `meta.yaml` |
| **product total** | **6,630** | |

Outside `src/`: tests 6,356 lines in 49 files; `scripts/measure.py` 112; `scripts/exp3/` 207; `experiments/` (2 scripts and their results, kept as a record per the README); `packaging/` (entry point, `portable_zip.py`, `.iss`).

### The core imports no extra (confirmed)

`python -X importtime -c "import transcript_normalizer"` loads 189 modules, cumulative **45.5 ms**. None of `rich`, `questionary`, `prompt_toolkit`, `yt_dlp`, `faster_whisper`, `tkinter` or `curl_cffi` is among them, and `sys.modules` agrees after the import:

```
wall 44.7 ms extras loaded: []
```

The largest cumulative entries are `core.matcher` 45.3 ms (it pulls in the rest), `core.pack` 22.1 ms (4.5 ms self, mostly dataclass creation), `yaml` 9.8 ms (`yaml.reader` 4.7 ms self), `rapidfuzz` 8.3 ms, `dataclasses` 7.5 ms and `inspect` 6.4 ms. `platformdirs` is imported lazily inside `runs.py` functions, not at import time.

Layering note: `core/pack.py` imports `..runs` (for `learned_file`) and `..languages`. Both have only stdlib imports at module level, so the boundary holds. `runs.py` does sit across it: it is half core (paths) and half product (config, portable mode, `platformdirs`).

---

## 2. Findings

Severity: **high** means wrong behaviour or a measurable cost to users; **medium** means maintenance cost; **low** means style.

| # | file:line | category | evidence | sev. | conf. | recommended action |
|---|---|---|---|---|---|---|
| F1 | README.md:6, docs/GUIDE.md:7,23, docs/GUIDE.pt-BR.md:7,23 | doc drift | The Python install line pins `@v0.4.2`. pyproject is 0.6.3. v0.4.2 has no `pack create/edit/merge/export`, no English, and its `ingest` extra lacks D-058's `av<19` / `faster-whisper<1.3` bounds, so a fresh resolve can produce the audio breakage D-058 fixed. | high | high | Point it at the latest tag, or drop the pin (`@main`) and say so. |
| F2 | core/matcher.py:429 (and :413) | performance | The phonetic source checks every window against **every** applied span (`any(... for s, e in taken)`), so it is quadratic in caption length. Measured on wxgFO_fyfXg concatenated: phonetic 0.38 s at 1×, 1.33 s at 2×, **5.29 s at 4×** (×3.5, ×4.0). | high (long captions only) | high | Sort `taken` and bisect, or mark taken token indices in a boolean array. Cost becomes linear. |
| F3 | core/matcher.py:313-328 | performance | Every window is scored against every candidate in Python: 21.7k windows × 255 candidates = **5.5 M `_score` calls**, 60–75 % of normalize time on every fixture (§3). Most calls are length mismatches that fall through to `span == candidate`. The cost is linear, but grows with pack size × caption length. | medium | high | Bucket fuzzy candidates by length (only lengths within ±2 can score), and look up exact-only candidates in a dict. Expect normalize to drop from ~2.3 s to well under 1 s on wxgFO_fyfXg. Verify with the regression bounds unchanged. |
| F4 | core/matcher.py:282-286, 373-374 | dead code (logic) | Mutant M1 (`inside_a_longer_name` → `False`) passes all 516 tests and changes **no resolved annotation** in any of the 8 fixture × {frozen, bundled} runs. The longer exact name always has score 100, high band and the longer span, so `resolve_overlaps` already drops the shorter correction. | medium | medium | Leave as is until someone constructs a case where it matters (e.g. the longer name is itself rejected). If none exists, remove it with a note in D-040. In either case add a pre-resolution test that pins it. |
| F5 | core/matcher.py:278-280, 361-362 | dead code (logic) | The same applies to `covered_by_its_own_name` (D-049): mutant M9 passes all tests, and no fixture output changes. The test that names D-049 asserts only post-resolution output, which overlap resolution produces anyway. | medium | medium | Same as F4. |
| F6 | core/matcher.py:317-322 | test quality | Mutant M3 removes D-047's **ranking** demotion (`rank = APPLY_THRESHOLD - 1`). All 516 tests pass, yet it **changes output**: on 4wCtn8BWR4o with the bundled pack, `Adapta Valuer` at 4878–4892 goes from medium to low. The D-047 tests in test_bands.py pass because `band_for(..., from_variant=True)` marks such matches low by itself; nothing tests which candidate wins. | medium | high | Add a test where a variant at 80–84 and the term at ≥80 compete for one span. |
| F7 | core/matcher.py:118-120 | dead code | `contains_words` has no caller in `src/`. Its last use was replaced in `a94af64` (D-049). It survives only through `test_containment_is_by_whole_words` (6 parametrised cases), which therefore tests nothing that runs. `Pack.is_rejected` (core/pack.py:284) does its own whole-word containment. | medium | high | Delete the function and its parametrised test. Keep the four behavioural tests in that file. |
| F8 | core/fit.py:23-24 | dead code | `fits()` is never called (vulture 60 %, confirmed by grep). cli.py and measure.py compare `fitting_terms(...)` with `MIN_FIT_TERMS` inline. | low | high | Use `fits()` at cli.py:566 and measure.py:95, or delete it. |
| F9 | evaluate.py:122, 239, 265 | dead code / doc drift | `Result.unlisted_aliases` is computed but never read: not by `as_row`, `render`, measure.py or any test. The comment at :239 says an unlisted alias "is reported". It is not. | low | high | Either report it in `render()` or remove the field and fix the comment. |
| F10 | catalog.py:19 | dead code | `META_FIELDS` is never referenced. The keys are written literally at catalog.py:43-46. | low | high | Delete, or use it to order the dict. |
| F11 | runs.py:40 | dead code (deliberate) | `NORMALIZED_SPEAKERS_FILE` is unused, but D-016 (DECISIONS.md:101) reserves the name "for when diarization exists". | low | high | Leave as is; it is documented as reserved. |
| F12 | evaluate.py:54-61 | duplication | `is_correction(a)` / `is_alias(a)` just return `a.is_correction` / `a.is_alias` (standoff.py:52-57). Used at evaluate.py:158-159 and 195. | low | high | Inline them; or leave as is, since they are harmless. |
| F13 | packedit.py:50 | (false positive) | vulture 100 %: `indentless` unused. It is a PyYAML override signature that deliberately ignores the argument. | — | high | Leave as is. |
| F14 | prompts.py:359,364 | (false positive) | vulture: two functions named `_` unused. They are prompt_toolkit key-binding handlers registered by decorator. | — | high | Leave as is. |
| F15 | core/matcher.py:315,319; merge.py:520 | (checked, fine) | ruff B023: a closure uses a loop variable. `ranked` and the merge lambda are called within the same iteration and never stored, so this is not the late-binding bug. | — | high | Leave as is. Optionally pass the variable as a parameter to silence the rule. |
| F16 | docs/GUIDE.md:323-330 (+ pt-BR) | doc drift | The §8 table says "the pack that ships (0.3.4)" with wrong changes 16 / 10 for R2Qgz8tFWVI / wxgFO_fyfXg. The bundled pack is 0.3.7, and measure.py prints 15 / 9. | medium | high | Regenerate the table from measure.py. |
| F17 | CONTRIBUTING.md:108; core/pack.py:26-27 | doc drift | Both say phonetic proposals go to `companhia` and `pessoa`. Since D-068 it is `pack.phonetic_classes` (matcher.py:404-408), with a different default. The paragraph right after it (CONTRIBUTING.md:110) is correct and contradicts it. | medium | high | Rewrite the sentence to point to the next paragraph, and fix the comment. |
| F18 | README.md:76-82 | doc drift | "168 domain-term errors" (measure: 167 in scope). "228-row gold file" (225 rows parsed). "156 of 168 hits, 9 false positives" is D-014-era; the frozen result now is 150/167 hits with 14 false positives. | low | high | Update, or point to measure.py instead of quoting numbers. |
| F19 | GUIDE.md:136,350; README.md:50 | doc drift | Docs list the bands high/medium/low. The code has a fourth, `ask` (standoff.py, matcher.py:97-98, D-060), written to annotations.json and queued in pending.txt. | medium | high | Document `ask`. |
| F20 | cli.py:701-704; DECISIONS D-023 | stale flag | `--gold-draft`, "kept hidden for one release" (D-023), is still in 0.6.3. | low | high | Remove it and add a CHANGELOG line, or amend D-023 to say it stays. |
| F21 | GUIDE.md:281 (+ pt-BR) | doc drift | The merge backup is documented as `.bak-<date>`. merge.py:740 writes `.bak-%Y%m%d-%H%M%S`; D-069 and CHANGELOG say `<timestamp>` correctly. | low | high | Change it to `<timestamp>`. |
| F22 | runs.py:3, :200 | doc drift | Docstrings say runs and packs are in the current directory. `base_dir()` (runs.py:160-182) resolves the env var, then portable mode, then Settings, then Documents. | low | high | Fix the docstrings. |
| F23 | packfiles.py:28-29 | doc drift | The comment credits the 3 s wait to D-064 (it is D-065/D-067), and says the table appears "without the update column". packfiles.py:190 adds the column whenever a copy exists (D-069). | low | high | Fix the comment. |
| F24 | packaging/release-header.md:6,11 | doc drift | The row `transcript-normalizer-VERSION-<system>-full` implies a plain Windows full file. Since D-070, Windows full ships only as `-setup.exe` and `-portable.zip`. | low | high | Say "macOS, Linux" in that row. |
| F25 | GUIDE.md:50,90,187 (+ pt-BR) | doc drift | Sample output shows 0.5.0, pack 0.3.4 and 0.3.6. | low | high | Refresh it when convenient; leaving it is harmless. |
| F26 | core/matcher.py:1-5 | doc drift | The module docstring says it is a port of exp2 "with one deliberate difference". Thirty-odd decisions later, exp2 is history, not the reference behaviour. | low | high | Reword it as "started as a port of exp2". |
| F27 | merge.py:740; interactive.py:92 → merge.offers → packfiles.index_within | performance | With a pack copy installed, every menu start waits for the packs index. The first screen took 0.18 s with no copy and 0.34–0.52 s with a copy and GitHub reachable. With the index host **unreachable (packets dropped)** it took **3.21 s every start** (the full `INDEX_WAIT_SECONDS = 3`). | medium | high | Fetch in a background thread and show the merge offer when it arrives, or cache the index for a day in the data dir. |
| F28 | core/matcher.py:467; core/text.py:43-48, 55 | performance | `resolve_overlaps` scans all kept annotations for each one, `Transcript.line_at` rebuilds `_starts()` on every call, and `spans` scans all lines. All three are quadratic, but small: resolve 8 → 135 ms and render 7 → 115 ms from 1× to 4×. | low | high | Leave as is for now. If F2/F3 are done, cache `_starts` (frozen dataclass, so a `cached_property` or a field) and sort-and-sweep in `resolve_overlaps`. |
| F29 | tests/conftest.py:44-64; tests/test_confirm_resume.py, test_learned_layer.py, test_pending.py | test quality / performance | `medium_order()` reruns the full matcher on R2Qgz8tFWVI (~1.7 s) on every call. `answers_for()` calls it again, with 12 call sites. These tests dominate the slowest list: 2–4 s each without coverage, 13–27 s each under coverage. | medium | high | Cache `medium_order()` (`functools.cache`; the pack and caption are fixed files). Most of the slowest 15 would drop by about 1.7 s each. F3 would cut it further. |
| F30 | tests/test_whole_word_guard.py:14, test_pack_v2.py:27, test_exact_only.py:19, test_inflection.py:16 | test quality (duplication) | The same fixture `v2` (`load_pack(PACK_V2, learned=Learned())`) is defined 4 times. Helpers are copied under the same name: `annotate` ×4, `applied` ×3, `fetched` ×4, `publish` ×3, `pack_text` ×2, `home` ×2 (packedit, packfiles). | low | high | Move `v2` and the one-line `annotate`/`applied` into conftest. Leave `fetched`/`publish` as is: their signatures differ per file on purpose. |
| F31 | tests/test_contribute.py:13, test_field_fixes.py:10, test_pack_fit.py:21 | test residue | ruff F401: `fetch_fakes.URL` is imported and unused. Eight RUF059 hits are unused unpacked variables in tests. | low | high | `ruff --fix` for F401; leave the rest. |
| F32 | core/matcher.py:153 (`find_annotations`, CC 46, radon F); evaluate.py:142 (E 35); merge.py `run_merge`/`Merge.run` (D 26) | complexity | radon cc: one F, two E (one is `scripts/exp3`), 12 D. The average is A (4.55). `find_annotations` is a 237-line function holding five closures and three passes over the windows. | medium | high | Split `find_annotations` into named passes (unit hits, exact maps, main loop, phonetic) when F3 is done, not before. Leave merge.py: it is long but each method is one D-069 rule, and it is 92 % covered. |
| F33 | interactive.py, merge.py | complexity | radon mi gives both MI 0.00 (rank C). This is mostly a size effect (1,203 and 800 lines), not tangled code; per-function CC is mostly A/B. | low | medium | Leave as is. |
| F34 | src/transcript_normalizer/ingest/fetch.py:498-502 | dependency | It imports `huggingface_hub` and `tqdm`, which are not declared. Both are transitive dependencies of `faster-whisper`, imported only on the `ingest` path. | low | high | Leave as is; optionally add a comment naming where they come from. |
| F35 | uv.lock / pyproject | dependency | `uv lock --check` resolves 42 packages with no change. The core declares exactly what it imports (`rapidfuzz`, `pyyaml`, `platformdirs`). | — | high | Fine as is. |
| F36 | sdist | packaging | The sdist (410 KB) ships tests, fixtures, experiments, scripts and `.github`. The wheel (128 KB, 47 files) ships only the package and its data, as it should. | low | high | Leave as is: this is useful for downstream packagers who run the tests. |
| F37 | ruff ALL | style | 7,000+ hits are dominated by rules the project does not follow (ANN, D, S101, E501, T201). The substantive remainder: 8 × `B905` (zip without `strict=`; packfiles.py:192,202,205, prompts.py:266,283,291, registry.py:187), 8 × `BLE001` (all are deliberate "show it in the menu" catches), `F541` at contribute.py:148, 3 × `RUF100` (stale `noqa`s), `ARG001` at cli.py:634, contribute.py:214, generic.py:30 (signature conformance). | low | high | `zip(strict=True)` where the lengths must match (packfiles.py:202,205 look like they must). Remove the stale `noqa`s. Leave the rest. |

---

## 3. Measurements

### Core import

| | |
|---|---|
| `import transcript_normalizer`, wall | 44.7–45.4 ms (3 runs) |
| importtime cumulative | 45.5 ms, 189 modules |
| allocations during import (tracemalloc) | peak 5.0 MB |
| process max RSS after import | 28 MB (the bare interpreter in the same venv is also 28 MB; the difference is in the noise) |

### Normalize per fixture (bundled pack 0.3.7, in process, `find_annotations` + `resolve_overlaps` + render)

| fixture | lines | annotations | load_pack | normalize | peak alloc | CLI end to end (incl. startup) |
|---|---:|---:|---:|---:|---:|---:|
| 4wCtn8BWR4o | 239 | 179 | 22 ms | 0.76 s | 1.6 MB | 0.87 s, RSS 31 MB |
| 4tTmY8Buask | 743 | 300 | 24 ms | 1.15 s | 2.6 MB | 1.27 s, RSS 33 MB |
| R2Qgz8tFWVI (31 min) | 1,018 | 407 | 21 ms | 1.74 s | 3.4 MB | 1.87 s, RSS 34 MB |
| wxgFO_fyfXg (40 min) | 1,259 | 530 | 21 ms | 2.29 s | 4.3 MB | 2.38 s, RSS 35 MB |

Top 5 by cumulative time (cProfile). The order is the same on all four fixtures, and only the totals scale:

| wxgFO_fyfXg (8.27 s under the profiler) | cumulative |
|---|---:|
| `matcher.find_annotations` | 8.24 s |
| `builtins.max` (over the candidate generator, matcher.py:325) | 6.07 s |
| `matcher.py:326 <genexpr>` (5.56 M calls) | 5.30 s |
| `matcher.ranked` (5.54 M calls) | 4.13 s |
| `matcher._score` (5.54 M calls) | 2.72 s |
| *(next: `phonetic_proposals` 1.29 s)* | |

On the other fixtures `find_annotations` and `max` took 4.71 s and 3.72 s (4tTmY8Buask), 2.78 s and 2.26 s (4wCtn8BWR4o), and 6.50 s and 5.01 s (R2Qgz8tFWVI), with `<genexpr>`, `ranked` and `_score` next in the same order.

### Quadratic check: wxgFO_fyfXg concatenated 1×, 2×, 4×

| | 1× | 2× | 4× | growth 1×→4× |
|---|---:|---:|---:|---|
| caption lines / tokens | 1,259 / 9,063 | 2,518 / 18,126 | 5,036 / 36,252 | |
| `find_annotations` total | 2.29 s | 5.12 s | 13.03 s | ×5.7 |
| of which `phonetic_proposals` | 0.38 s | 1.33 s | 5.29 s | **×13.9: quadratic (F2)** |
| of which everything else | 1.91 s | 3.79 s | 7.74 s | ×4.05: linear |
| `resolve_overlaps` | 8 ms | 31 ms | 135 ms | ×17: quadratic, small (F28) |
| `render_normalized` | 7 ms | 26 ms | 115 ms | ×16: quadratic, small (F28) |
| `write_pending`, `report` | ≤1 ms | ≤1 ms | ≤1 ms | flat |

So a 2.5–3-hour video spends about 40 % of its 13 s in the quadratic phonetic pass. At 40 minutes it is 17 %.

### Menu first screen (pty, time until "What would you like to do?")

| situation | first output | menu question |
|---|---:|---:|
| no pack copy (index not read) | 0.10 s | 0.18 s |
| one pack copy, GitHub reachable | 0.09–0.11 s | 0.34–0.52 s |
| one pack copy, index host unreachable | 0.10 s | **3.21 s** (F27) |

Importing the menu (`transcript_normalizer.interactive` + `prompts` + rich + questionary) takes 54–57 ms.

---

## 4. Tests

**Total: 516 tests, all passing.** The suite takes 82.5 s without coverage, 484 s with `pytest-cov`, and 20–23 s with `pytest-xdist -n 12` (used for the mutation runs). Line coverage is **93 %** (4,687 statements, 331 missed). The lowest modules are `ingest/console.py` 80 %, `interactive.py` 88 %, `registry.py` 88 % and `prompts.py` 89 %. The core sits at 97–100 %, except `fit.py` at 86 %, where the uncovered line is the dead `fits()` (F8).

### Slowest 15 (without coverage)

```
3.98s test_confirm_resume.py::test_a_rerun_only_asks_what_is_still_pending
2.95s test_learned_layer.py::test_all_yes_stops_at_the_end_of_its_term
2.32s test_pack_fit.py::test_every_fixture_fits_its_pack[bundled-wxgFO_fyfXg]
2.10s test_learned_layer.py::test_a_rejected_pair_is_never_proposed_again
2.09s test_learned_layer.py::test_a_second_run_honours_what_the_first_one_learned
2.09s test_learned_layer.py::test_a_mixed_group_is_answered_one_variant_at_a_time
2.08s test_learned_layer.py::test_confirmed_variant_is_matched_as_a_high_band_variant
2.05s test_pending.py::test_nothing_pending_leaves_no_file_behind
2.05s test_learned_layer.py::test_rest_no_takes_the_current_variant_and_the_ones_after_it
2.01s test_confirm_resume.py::test_an_interrupted_session_keeps_the_answers_it_was_given
2.01s test_confirm_resume.py::test_pending_after_an_interrupt_tells_asked_from_never_asked
1.99s test_corrections.py::test_draft_holds_exactly_the_applied_annotations
1.96s test_confirm_resume.py::test_a_finished_session_still_says_where_it_wrote
1.83s test_run_outputs.py::test_out_overrides_the_run_directory
1.79s test_packs.py::test_pack_defaults_to_the_packs_directory
```

Every one of these runs the full matcher on a real fixture, once or more (F29, and F3 underneath). Under coverage the same tests take 12–27 s each.

### Mutation spot-check (13 targets; each mutant was run against its own test file first, then the full suite if it survived)

| mutant | own tests | full suite |
|---|---|---|
| M1 `inside_a_longer_name` → False (D-040) | survived (2 passed) | **survived (516 passed)**: no behavioural effect on fixtures (F4) |
| M2 n-grams cross sentence ends (D-024) | killed (6 failed) | |
| M3 no variant rank demotion 80–84 (D-047) | survived (6 passed) | **survived (516 passed)**: changes fixture output (F6) |
| M4 never refuse an unfit pack (D-054) | killed (3 failed) | |
| M5 `is_rejected` → False (D-013) | killed (5 failed) | |
| M6 `Transcript.spans` → () (D-007) | killed (1 failed) | |
| M7 render ignores annotations (D-016) | survived (test_render.py, 6 passed) | killed (3 failed elsewhere) |
| M8 pt-BR `inflections` → ∅ (D-031a) | killed (7 failed) | |
| M9 `covered_by_its_own_name` → False (D-049) | survived (10 passed) | **survived (516 passed)**: no behavioural effect on fixtures (F5) |
| M10 `MIN_SKELETON_LEN` 5 → 4 (D-050) | survived (test_phonetic.py, 17 passed) | killed (1 failed) |
| M11 `portable_dir` → None (D-070) | killed (3 failed) | |
| M12 `keep_original` copies nothing (D-016) | killed (1 failed) | |
| M13 evaluate: no nested-FP exemption | survived (test_evaluate.py, 7 passed) | killed (3 failed, regression bounds) |

The suite catches 10 of 13 mutants. Three survive everything: two because the guarded behaviour appears to be redundant with overlap resolution (F4, F5), and one because a real behaviour is untested (F6). Three more survive only their own file (M7, M10, M13): the named test file doesn't pin its rule, but the regression or integration tests do. That is acceptable, though `test_render.py` not noticing that render ignores annotations is worth a one-line assertion.

**A test of nothing that runs:** `test_whole_word_guard.py::test_containment_is_by_whole_words` (6 cases) tests `contains_words`, which production no longer calls (F7).

### Duplicated fixtures and helpers

See F30. The `v2` fixture is defined 4 times and the one-line `annotate`/`applied` helpers 3–4 times. `pack` appears twice with different meanings (conftest: the R2Qgz8tFWVI frozen pack; test_rejection.py: a local one), which is legitimate shadowing, not duplication. `scored` is the same: two different fixtures that share a name.

---

## 5. What is good: leave it alone

- **The core/product boundary.** The core imports nothing from the extras, the `core/__init__` docstring's promise holds, and import costs 45 ms. Extras are imported at their point of use throughout. This is the D-052/D-053 design and it is intact.
- **Coverage of the core**: 97–100 % per module, and the decisions are pinned by name. Ten of 13 mutants are killed, most of them by the test file named after their decision.
- **Regression bounds** (`tests/test_regression_fixture.py`) catch a broad class of matcher changes even when a unit test misses them (M10, M13). measure.py prints them reproducibly.
- **`languages/`**: small, 100 % covered, a clean protocol (the `generic.py` `ARG001` is signature conformance, not residue).
- **`core/standoff.py`, `core/text.py`, `core/render.py`, `core/rules.py`**: small, clear, fully covered. The quadratic bits (F28) are cheap at real sizes.
- **`merge.py`**: long, and radon dislikes it, but it maps one-to-one onto D-069's rules and is 92 % covered. Rewriting it would buy nothing.
- **Dependencies**: the lock is in sync and the extras match their docs. The D-058 upper bounds are in place in pyproject (just not in the install line the docs give, F1).
- **The release workflow and packaging**: the wheel contents are minimal and correct, and the smoke tests in release.yml exercise the built executables, not the source tree.
- **The docs, mostly**: the doc-drift pass checked every threshold, CLI flag, environment variable, run file name, menu entry and template against the code, and they match. The drift that exists (F1, F16–F26) is in numbers and version strings that went stale, not in described behaviour, except for F19 (`ask` band).
- **Residue is scarce.** After three weeks of agent sessions, the confirmed dead code is 4 symbols (F7–F10), 1 stale flag (F20), 3 unused test imports and 3 stale `noqa`s. There are no commented-out blocks (ruff ERA: 0 in `src`) and no duplicated helpers in `src` beyond F12.

---

## 6. Proposed cleanup plan (nothing executed)

### Risk: none (docs and comments only)

| item | gain |
|---|---|
| F1: fix the install pin in README and both GUIDEs | Users who install with pip get 0.6.x and the D-058 bounds, instead of a 0.4.2 that lacks half the documented commands. **Do this first.** |
| F16, F18, F19, F21, F24, F25: refresh the numbers, document the `ask` band, timestamp backup name, release-header row | The docs match what users see. |
| F17, F22, F23, F26, F9's comment: fix code comments and docstrings | Contributors are not misled about phonetic classes, paths, or which decision says what. |

### Risk: low (delete or inline, covered by tests)

| item | gain |
|---|---|
| F7: delete `contains_words` and its 6-case test | −1 function and −6 tests that test nothing that runs. |
| F8, F10: use or delete `fits()` and `META_FIELDS` | −2 dead symbols. |
| F9: report `unlisted_aliases` in `evaluate.render`, or remove it | The comment becomes true. |
| F12: inline `evaluate.is_correction`/`is_alias` | Cosmetic. |
| F20: drop `--gold-draft` (+ CHANGELOG Unreleased line), or amend D-023 | Keeps the promise D-023 made. |
| F31, F37 subset: remove unused imports and stale `noqa`s; add `zip(strict=True)` at packfiles.py:202,205 | A latent length mismatch would raise instead of silently truncating. |
| F29: `functools.cache` on `conftest.medium_order()` | About 1.7 s off each of roughly 12 slow tests: suite ≈ 82 → ~65 s, and far more under coverage. |
| F30: move `v2`, `annotate` and `applied` to conftest | −~25 lines of copied test code. |

### Risk: medium (behaviour-preserving changes to the matcher; gate on regression bounds and measure.py output being identical)

| item | gain |
|---|---|
| F6: add a test for D-047's ranking demotion **first** | Closes the one real behavioural gap the mutants found. A prerequisite for touching the matcher. |
| F4, F5: add pre-resolution tests for D-040/D-049, then decide | Either they find a case where the guards matter (keep them, now tested), or the guards go with a DECISIONS amendment. Either way it is −2 untested code paths. |
| F2: linear `taken` check in `phonetic_proposals` | 4× captions: 5.3 s → ~1.3 s. Normalizing a 3-hour video gets ~40 % faster; no change below about an hour. |
| F3: length-bucketed fuzzy candidates and exact dict lookup | Expected normalize ~2.3 s → <1 s on wxgFO_fyfXg. The test suite gets faster in proportion (most of its time is the matcher). This also stops pack growth from multiplying normalize time. |
| F28: cache `Transcript._starts`, sort-sweep `resolve_overlaps` | ~250 ms off 4× captions; negligible otherwise. Do it only alongside F2/F3. |

### Risk: medium (product behaviour)

| item | gain |
|---|---|
| F27: read the packs index in the background, or cache it daily | Menu start with a copy and a dead network: 3.2 s → 0.2 s. Needs a decision on how the merge offer appears late. |

### Not recommended

- Splitting `interactive.py` or `merge.py` for their MI scores (F33). The size is honest, and the tests are organised around the current structure.
- Turning on the ruff ANN/D/E501 families. That is 3,000+ changes for no behavioural gain.
- Refactoring `find_annotations` (F32) on its own. Do it as part of F3, when the loop is being rewritten anyway and the regression bounds are watching.
