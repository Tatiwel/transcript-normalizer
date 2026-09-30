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
transcript-normalizer fetch <url | file> [--caption-only | --whisper]
transcript-normalizer <legenda.txt> [--pack <pack.yaml>] [--corrections] [--confirm]
transcript-normalizer list
```

`fetch` takes the platform's own caption with yt-dlp, retrying rate limits; if there is none, or it cannot be had, it transcribes the audio locally with faster-whisper (D-036). It writes `runs/<video-id>/legenda.txt` and `meta.yaml`, both recording which of the two produced the text. `--caption-only` never falls back; `--whisper` goes straight to local transcription. A local audio or video file works too: it goes straight to local transcription, into `runs/<file-stem>/` (D-038). It needs the optional extra: `uv sync --extra ingest`. WebVTT is converted in Python, so the caption path needs no ffmpeg; only `--whisper` does. Speech recognition is not the same as asking an AI provider to transcribe: it maps audio to text and does not fill a gap with something plausible.

Normalizing reads `packs/financas-ptbr.yaml` in the current directory unless `--pack` names another; with no such file it uses the copy that ships in the package. Every output goes under `runs/<id>/` in the current directory, never beside the input:

- `annotations.json` — the stand-off layer: every proposal with its band and its kind, `correction` or `alias` (D-020).
- `normalized.txt` — the caption with the corrections substituted; aliases are left as they were said.
- `legenda.txt` — the raw caption, kept beside what was rendered from it.
- `report.txt` — the same text the command prints.
- `meta.yaml` — title, channel, url, publication date and when it was fetched, from `fetch`.
- `needs-review/corrections.csv` — with `--corrections`, the applied annotations as the starting point for a new gold file.
- `needs-review/pending.txt` — every medium-band variant still unanswered, tagged `[never asked]` or `[skipped]`.

`--confirm` asks about each medium-band variant in turn and records the answers in `packs/<pack-name>.learned.yaml`. `transcript-normalizer list` prints the id, date and title of every run. `--out DIR` writes a run somewhere else, `--learned PATH` points at a different learned layer. The pack file is never written to.

## Where things are

```
src/transcript_normalizer/
  core/          the engine: pack, rules, text, matcher, stand-off, render; no language in it
  languages/     one module per language: normalization, inflection, units, sentences (D-033)
  ingest/        fetching captions; optional, needs the `ingest` extra
packs/           your domain packs, and the learned layer beside each (D-017)
fixtures/        frozen test material; the regression test reads it, nothing writes it
experiments/     the throwaway scripts that measured the decisions, kept as record
runs/            everything a command produces, gitignored (D-015)
  <video-id>/    annotations.json, normalized.txt, legenda.txt, report.txt, meta.yaml (D-022)
    needs-review/  what needs a person: corrections.csv, pending.txt (D-023)
```

The run id is the video id, read from the caption header when the input did not come from `fetch`; a caption with no recognizable url falls back to its file stem (D-018). `packs/` is yours to edit; the pack under `fixtures/` is a frozen copy that the regression test depends on. `runs/` and `packs/*.learned.yaml` are disposable and gitignored.

## Status

Experimental, but the engine is a package with a regression test.

- `fixtures/R2Qgz8tFWVI/`: one Brazilian Portuguese finance video (31 min). `legenda.txt` is the raw platform caption, `gold.csv` is a hand-checked gold list of 168 domain-term errors plus 2 lines that must not be touched, `pack.yaml` is the first domain pack.
- `fixtures/wxgFO_fyfXg/`: a second video from the same channel (40 min, CEMIG vs CPFL), with a 228-row gold file whose statuses separate corrections the tool made (`certo`), legitimate other names of a term (`alias`), and errors a person had to add (`conferido`). The meanings are in `src/transcript_normalizer/evaluate.py`.

`uv run python scripts/measure.py` prints every fixture's numbers side by side; the regression test holds each one to its own bounds.
- `experiments/`: throwaway scripts that measured how far naive approaches go against that fixture. Results are in `docs/DECISIONS.md`.

Measured on the fixture, with RapidFuzz plus a hand-curated variant list, a unit rule, and a disciplined threshold: 156 of 168 hits, 9 false positives in ~1000 caption lines, zero changes to the lines that had to stay untouched.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) has the three procedures for adding a language, building a domain pack, and building a fixture that measures them.

## Test content

Code, docs and API are in English. Test fixtures are Brazilian Portuguese finance videos, because that is the problem this was built to solve. Contributions of fixtures in other languages and domains are welcome.

## Related work this builds on

RapidFuzz (string similarity), SymSpell LookupCompound (word boundary errors), Whisper `initial_prompt` (vocabulary biasing before transcription), memoQ-style term base ranking (layer conflicts), W3C PROV (provenance), NFC normalization on input.

## License

MIT.
