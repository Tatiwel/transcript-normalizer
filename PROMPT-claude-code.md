# Prompt for Claude Code (run inside the cloned repo, after unzipping the bundle into it)

You are working in the repository `transcript-normalizer`. The folders `fixtures/`, `experiments/`, `docs/` and the `README.md` were just added and must not be rewritten, only read. Read `README.md` and `docs/DECISIONS.md` first; every decision there is binding.

Task: turn the throwaway experiment into a minimal, tested Python package. Do not add features beyond what is listed.

1. Create `pyproject.toml` with a `src/` layout, package name `transcript_normalizer`, Python >= 3.11, dependencies `rapidfuzz` and `pyyaml`, dev dependency `pytest`. Use `uv` if available, otherwise plain pip. License MIT.

2. Implement in `src/transcript_normalizer/`:
   - `pack.py`: load a domain pack from YAML (`fixtures/R2Qgz8tFWVI/termos.yaml` is the schema by example: `termos[]` with `termo`, `classe`, optional `apelidos`, `variantes`, `colocacoes`; `regras_de_unidade[]`). Normalize every string with NFC, lowercase, strip accents for matching, keep the original for display.
   - `rules.py`: the unit rules of D-006 as regexes.
   - `matcher.py`: the matching of D-001, D-003, D-005 over word n-grams of size 1 to 3, using `rapidfuzz.fuzz.ratio` with threshold 80. Port the logic of `experiments/exp2_units_and_threshold.py`; it is the reference behaviour.
   - `standoff.py`: the output type of D-004, a list of annotations with `start`, `end`, `original`, `replacement`, `term`, `rule` (`unit` or `term:<variant|alias|fuzzy>`), `score`, `pack_version`. Nothing in the package may return a modified transcript string; only annotations.
   - `text.py`: read a `legenda.txt` (skip `#` header lines, each line is `m:ss text`), join into one text, and keep an offset map from character offset to `(line_index, timestamp)`, per D-007.
   - `cli.py`: `transcript-normalizer <legenda.txt> --pack <termos.yaml>` prints a report grouped by term: `SEMIG, semig, SEMIC (41 occurrences) -> CEMIG` plus the unit corrections, and writes `<legenda>.annotations.json` next to the input. Exit code 0.

3. Tests in `tests/`, run with pytest, all against `fixtures/R2Qgz8tFWVI/`:
   - `test_regression_fixture.py`: replay the evaluation of `experiments/exp2_units_and_threshold.py` against `gabarito.csv` and assert: hits >= 152 (of 168 in scope), false positives <= 10, and the two rows with `status == manter` receive zero annotations. Print the per-term table on failure. Any change in these numbers must be a conscious commit that also updates this test and `docs/DECISIONS.md`.
   - `test_standoff.py`: the original text is byte-identical after normalization; every annotation's `start:end` slice of the original equals its `original` field.
   - `test_short_variants.py`: `tri` does not match `dívida`; `End` does not match `ainda`; `Ward` matches `Word` only because it is a listed variant.
   - `test_cross_line.py`: `ser MIG` split across the lines at 24:48 and 24:51 is found as one annotation for `CEMIG`. This test is expected to FAIL against a straight port of exp2, because exp2 works line by line; make it pass by implementing D-007 in `text.py`.

4. Do not touch `fixtures/`. Do not delete `experiments/`; they are the historical record.

5. When done, paste the literal output of `pytest -q` and the literal output of the CLI run against the fixture. Do not summarize them. If any number differs from the ones in `docs/DECISIONS.md`, say so and stop; do not adjust thresholds to make tests pass.
