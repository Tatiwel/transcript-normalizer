# transcript-normalizer

Domain-term normalization for ASR transcripts and auto-captions.

## The problem

Automatic captions and speech recognition systematically garble domain vocabulary: company names, acronyms, indicators, units. In a Brazilian finance video, `CEMIG` came out as `SEMIG`, `SEMIC`, `CIC`, `sem amig`, `esse amigo`; `EBITDA` came out as `Ebítida`, `web ebita`, `bicho`; `Geração Dividendos` (the channel's own name) came out as `Geração de Dentes`.

Spell checkers do not help. Half of these errors are valid words. `Word` is a perfectly spelled word; the speaker said `Ward`, the name of a tool.

## The approach

The tool never asks "does this word exist?". It asks "does this stretch of text resemble a term I know?".

- The user declares a **domain pack**: a list of terms, each with aliases, observed misrecognitions (*variants*), and collocations. The tool never infers the domain.
- Only text that resembles a pack term is ever touched. Everything else is left alone, so a finance pack cannot damage a biology transcript.
- Correction is **stand-off**: the original text and timestamps are never modified. Normalization is a separate layer pointing at offsets, recording which rule fired and which dictionary version was used.
- Every confirmed correction is added to the pack's observed variants, so the next transcript benefits.

## Usage

```
transcript-normalizer <legenda.txt> --pack <pack.yaml> [--gold-draft] [--confirm]
```

Every output goes under `runs/` in the current directory, never beside the input:

- `runs/<input-stem>/annotations.json` — the stand-off layer, every proposal with its band.
- `runs/<input-stem>/report.txt` — the same text the command prints.
- `runs/<input-stem>/gold-draft.csv` — with `--gold-draft`, the applied annotations as the starting point for a new gold file.
- `runs/learned/<pack-name>.learned.yaml` — with `--confirm`, what you confirmed and what you turned down.

`--out DIR` writes a run somewhere else, `--learned PATH` points at a different learned layer. `runs/` is gitignored. The pack file is never written to.

## Status

Experimental, but the engine is a package with a regression test.

- `fixtures/R2Qgz8tFWVI/`: one Brazilian Portuguese finance video (31 min). `legenda.txt` is the raw platform caption, `gold.csv` is a hand-checked gold list of 168 domain-term errors plus 2 lines that must not be touched, `pack.yaml` is the first domain pack.
- `experiments/`: throwaway scripts that measured how far naive approaches go against that fixture. Results are in `docs/DECISIONS.md`.

Measured on the fixture, with RapidFuzz plus a hand-curated variant list, a unit rule, and a disciplined threshold: 156 of 168 hits, 9 false positives in ~1000 caption lines, zero changes to the lines that had to stay untouched.

## Test content

Code, docs and API are in English. Test fixtures are Brazilian Portuguese finance videos, because that is the problem this was built to solve. Contributions of fixtures in other languages and domains are welcome.

## Related work this builds on

RapidFuzz (string similarity), SymSpell LookupCompound (word boundary errors), Whisper `initial_prompt` (vocabulary biasing before transcription), memoQ-style term base ranking (layer conflicts), W3C PROV (provenance), NFC normalization on input.

## License

MIT.
