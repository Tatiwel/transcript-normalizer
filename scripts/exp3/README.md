# Experiment 3: phonetics on held-out names

This experiment asks the question D-010 deferred: does a phonetic layer recover misrecognized names that the matcher misses, and what does it cost? Nothing here is part of the package. The matcher is unchanged, and `pyproject.toml` gains no dependency.

```
uv pip install epitran                      # ad hoc, into the project venv
uv run --no-sync python scripts/exp3/exp3.py
```

`--no-sync` matters: a plain `uv run` syncs the venv to the lock file and removes epitran again.

Libraries installed ad hoc for this run: `epitran 1.35.2`, which pulled in `panphon 0.22.2`, `marisa-trie 1.4.1`, `regex 2026.9.29`, `unicodecsv 0.14.1`, `jamo 0.4.1`, `munkres 1.1.4`, `editdistance 0.8.1`, `numpy 2.5.3`, `requests 2.34.2` and `setuptools 84.0.0`.

## Design

- **Hold-out.** `pack-holdout.yaml` is the bundled pack (0.3.2) with BR Partners reduced to its canonical name and the aliases `BRBI11` and `Partners`, with no variants. `exp3.py` regenerates it. Against `fixtures/4tTmY8Buask` the target is BR Partners' 50 gold rows: 18 distinct forms after folding.
- **Where a method runs.** Only on 1- and 2-word spans that no applied annotation of the current matcher covers. Spans do not cross pt-BR sentence boundaries, commas included (D-024, D-044).
- **What it matches against.** Only the canonical names and aliases of terms of class `companhia` or `pessoa`. An encoded span or name shorter than 4 characters is skipped.
- **Scoring.** A proposal is a medium-band correction. Proposals are scored with the matcher's own annotations after overlap resolution (D-048), with the same gold as the regression. "FP added" is a fixture's false positives minus the baseline's.
- **Recall.** A form counts as recovered when at least one of its rows is a hit.

Methods:

- **baseline**: the current matcher on the hold-out pack.
- **M1, metaphone-ptbr: skipped.** It is not on PyPI. `metaphone-ptbr`, `metaphone_ptbr`, `metaphoneptbr`, `pymetaphone-ptbr` and `metaphone-pt-br` all return 404. `metaphone` exists but is the English Double Metaphone, which is not the method asked for.
- **M2, epitran.** Spans and names go to IPA, then rapidfuzz `ratio` is taken on the IPA strings, at 80 and at 85. epitran has no pt-BR map: `por-Latn-BR` fails with "Add an appropriately-named mapping". `por-Latn` was used, and it is European in places, for example a final `s` becomes `ʃ`.
- **M3, consonant skeleton.** Text is folded as the pack folds it (case, accents), and spaces are dropped. Then `ç`/`c`/`s` become `s`, `g`/`j` become `j`, and `l` or `u` before a consonant becomes `w`. Vowels are dropped and doubled letters collapse. rapidfuzz `ratio` runs on the skeletons, at 80 and at 85.

## Results

BR Partners held out: 18 distinct forms, 50 gold rows in 4tTmY8Buask.

| method | forms recovered (of 18) | rows hit (of 50) | FP added 4tTmY8Buask | FP added 4wCtn8BWR4o | FP added R2Qgz8tFWVI | FP added wxgFO_fyfXg |
|---|---|---|---|---|---|---|
| baseline | 2 | 8 | 0 | 0 | 0 | 0 |
| M1 metaphone-ptbr | not on PyPI | | | | | |
| M2 epitran 80 | 2 | 8 | 9 | 11 | 14 | 8 |
| M2 epitran 85 | 2 | 8 | 1 | 0 | 0 | 0 |
| M3 skeleton 80 | 9 | 39 | 9 | 7 | 10 | 12 |
| M3 skeleton 85 | 6 | 33 | 2 | 0 | 1 | 1 |

Hits gained over the baseline, any term:

| method | 4tTmY8Buask | 4wCtn8BWR4o | R2Qgz8tFWVI | wxgFO_fyfXg |
|---|---|---|---|---|
| M2 epitran 80 | 0 | 0 | 1 | 0 |
| M2 epitran 85 | 0 | 0 | 0 | 0 |
| M3 skeleton 80 | 31 | 0 | 0 | 0 |
| M3 skeleton 85 | 25 | 0 | 0 | 0 |

The baseline's two forms are `BR Portness` and `Portness`. The canonical name reaches them fuzzily at 81.

### Examples

M2 epitran 80:
- Hits: `serig` → CEMIG (80, R2Qgz8tFWVI), one of the three misses D-010 named. No other hit.
- FPs: `casa` → Copasa (80, R2Qgz8tFWVI and wxgFO_fyfXg), `sabe` → Sabesp (80, R2Qgz8tFWVI).

M2 epitran 85:
- Hits: none.
- FPs: `partner` → BR Partners (93, 4tTmY8Buask 11:39). This is probably a real mention the gold lacks (see below). It is the method's only proposal.

M3 skeleton 80:
- Hits: `a Portness` → BR Partners (90), `Berry Portene` → BR Partners (85), `Portess` → BR Partners (80).
- FPs: `aportar` → BR Partners (80, R2Qgz8tFWVI), `presta atenção` → BR Partners (83, 4tTmY8Buask), `a partir` → BR Partners (80, 4wCtn8BWR4o).

M3 skeleton 85:
- Hits: `a Portness` → BR Partners (90), `Berry Portene` → BR Partners (85), `Portness` → BR Partners (90).
- FPs: `A Partens` → BR Partners (90, 4tTmY8Buask 7:48), `partner e` → BR Partners (90, 4tTmY8Buask 11:39), `para três` → BR Partners (90, R2Qgz8tFWVI).

## What it says

- **M2 does not capture what M3 captures; it is the other way round.** At both thresholds every form M2 recovers is one the baseline already had. M3 adds seven forms at 80 (`berry portene`, `br portance`, `portance`, `portas`, `portes`, `portess`, `portinas`) and four at 85. In `por-Latn` IPA, `Portness` and `Partners` score 75, because the vowel symbols differ (`o`/`ɐ`, `s`/`ɾ`). Dropping vowels removes exactly that difference.
- **M3 at 85 is the only setting worth a second look.** It recovers 25 more rows of the held-out company, and adds 2, 0, 1 and 1 false positives. Two of the 4tTmY8Buask false positives are probably not false. 7:48 "A Partens, em…" and 11:39 "eu tenho partner e é minha segunda maior" read as mentions of BR Partners that the gold does not list. The gold was not changed.
- **Phonetics does not reach these forms:** `b partners`, `br port`, `pornet`, `port`, `porta`, `portizar`, `portou`, `portudo`, `wortness`. Of these, `port`, `porta` and `br port` are short or ordinary words that D-005 and D-032 keep out anyway.
- **This is one company and one speaker.** The hold-out measures recall on a single name with many forms. Under the pack, the same forms are listed variants. Whether a phonetic layer earns a place before the first sighting of a name is the open question. This run suggests a skeleton fold at 85 restricted to name classes, not IPA.
