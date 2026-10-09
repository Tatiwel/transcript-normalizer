# transcript-normalizer

Domain-term normalization for ASR transcripts and auto-captions.

- **Just want to use it:** download the program for your system from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases) and double-click it; your files go to `Documents/transcript-normalizer/`.
- **Use Python:** `pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.6.3"`.
- **Want to contribute:** `git clone https://github.com/Tatiwel/transcript-normalizer`, `uv sync --extra ingest`, then [CONTRIBUTING.md](CONTRIBUTING.md).

**New here?** Read the guide: [docs/GUIDE.md](docs/GUIDE.md) (English) or [docs/GUIDE.pt-BR.md](docs/GUIDE.pt-BR.md) (português). It covers installing, a first run, reading the outputs, reviewing what the tool was unsure about and writing a pack for your own field.

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
transcript-normalizer <legenda.txt | file.srt | file.vtt> [--pack <pack.yaml>] [--corrections] [--review | --confirm] [--summary] [--force]
transcript-normalizer list
transcript-normalizer pack list [--installed] | install <name> | update | propose
transcript-normalizer pack create --template <field> --name <n> --lang <l> | import <file> | remove <name>
transcript-normalizer pack copy | add-term | edit-term | remove-term | show | export   # editing your packs
transcript-normalizer pack propose --whole <name>                                      # a whole pack, as an issue
transcript-normalizer pack merge <name> [--dry-run]                                    # a newer upstream into your copy
transcript-normalizer            # on a terminal, with no arguments: an interactive menu (D-051)
```

`fetch` takes the platform's own caption with yt-dlp, retrying rate limits; if there is none, or it cannot be had, it transcribes the audio locally with faster-whisper (D-036). It writes `runs/<video-id>/legenda.txt` and `meta.yaml`, both recording which of the two produced the text. `--caption-only` never falls back; `--whisper` goes straight to local transcription. A local audio or video file works too: it goes straight to local transcription, into `runs/<file-stem>/` (D-038). It needs the optional extra: `uv sync --extra ingest`. No ffmpeg is needed: WebVTT is converted in Python, and faster-whisper decodes audio itself. Speech recognition is not the same as asking an AI provider to transcribe: it maps audio to text and does not fill a gap with something plausible.

Normalizing reads `packs/financas-ptbr.yaml` in the current directory unless `--pack` names another; with no such file it uses the copy that ships in the package. A pack that names fewer than three of its terms with confidence does not fit the transcript, and nothing is applied unless `--force` (D-054). Packs live in [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs): `pack list` shows them, `pack install <name>` puts one in `packs/` after checking its sha256, `pack update` keeps them current (D-055), and `pack propose` offers what your reviews taught the tool back to that repository as a prefilled issue (D-056). For a field with no pack yet, `pack create` starts one from one of ten field templates, which gives it the field's classes (D-064, D-065); `pack import` checks a pack file and copies it into `packs/`, `pack remove` deletes one, and `pack list --installed` shows what this machine has. `pack add-term`, `edit-term` and `remove-term` edit a pack of your own (`pack copy` makes a bundled one yours), each change checked and saved with the next patch version (D-066); `pack export` writes `<name>-<version>.yaml`, and `pack propose --whole` proposes a whole pack to the packs repository (D-067). The menu's Packs item does all of these, and after normalizing it offers to add a term you noticed in the run. A copy remembers its base, and `pack merge` brings a newer upstream version into it three-way, asking about each conflict (D-069). Languages: pt-BR and English (D-068). Every output goes under `runs/<id>/` in the current directory, never beside the input:

- `annotations.json` — the stand-off layer: every proposal with its band and its kind, `correction` or `alias` (D-020).
- `normalized.txt` — the caption with the corrections substituted; aliases are left as they were said.
- `legenda.txt` — the raw caption, kept beside what was rendered from it.
- `report.txt` — the same text the command prints.
- `meta.yaml` — title, channel, url, publication date and when it was fetched, from `fetch`.
- `needs-review/corrections.csv` — with `--corrections`, the applied annotations as the starting point for a new gold file.
- `needs-review/pending.txt` — every medium-band variant, and every `ask`-band name found by sound (never applied, D-060), still unanswered, tagged `[never asked]` or `[skipped]`.

`--confirm` asks about each medium-band and ask-band variant in turn and records the answers in `packs/<pack-name>.learned.yaml`. `transcript-normalizer list` prints the id, date and title of every run. `--out DIR` writes a run somewhere else, `--learned PATH` points at a different learned layer. The pack file is never written to.

## Where things are

```
src/transcript_normalizer/
  core/          the engine: pack, rules, text, matcher, stand-off, render; no language in it
  languages/     one module per language: normalization, inflection, units, sentences (D-033)
  ingest/        fetching captions; optional, needs the `ingest` extra
  packs/         the curated packs, shipped in the wheel; financas-ptbr.yaml is the default (D-043)
packs/           your own packs and learned layers (D-017, D-043)
fixtures/        frozen test material; the regression test reads it, nothing writes it
experiments/     the throwaway scripts that measured the decisions, kept as record
runs/            everything a command produces, gitignored (D-015)
  <video-id>/    annotations.json, normalized.txt, legenda.txt, report.txt, meta.yaml (D-022)
    needs-review/  what needs a person: corrections.csv, pending.txt (D-023)
```

The run id is the video id, read from the caption header when the input did not come from `fetch`; a caption with no recognizable url falls back to its file stem (D-018). `packs/` is yours to edit; the pack under `fixtures/` is a frozen copy that the regression test depends on. `runs/` and `packs/*.learned.yaml` are disposable and gitignored.

## Status

Experimental, but the engine is a package with a regression test.

- `fixtures/R2Qgz8tFWVI/`: one Brazilian Portuguese finance video (31 min). `legenda.txt` is the raw platform caption, `gold.csv` is a hand-checked gold list of 196 rows: 167 domain-term errors in scope, plus aliases, case-only rows and 2 lines that must not be touched, `pack.yaml` is the first domain pack.
- `fixtures/wxgFO_fyfXg/`: a second video from the same channel (40 min, CEMIG vs CPFL), with a 225-row gold file whose statuses separate corrections the tool made (`certo`), legitimate other names of a term (`alias`), and errors a person had to add (`conferido`). The meanings are in `src/transcript_normalizer/evaluate.py`.

`uv run python scripts/measure.py` prints every fixture's numbers side by side; the regression test holds each one to its own bounds.
- `experiments/`: throwaway scripts that measured how far naive approaches go against that fixture. Results are in `docs/DECISIONS.md`.

Measured on the first fixture with its frozen pack (RapidFuzz plus a hand-curated variant list, unit rules and disciplined thresholds): 150 of 167 hits and 14 false positives in ~1000 caption lines; with the bundled pack 0.3.7, 142 hits and 15 false positives. `scripts/measure.py` is the source of these numbers: if they disagree with it, it is right.

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) has the three procedures for adding a language, building a domain pack, and building a fixture that measures them. This repository is the engine; domain content (the packs) lives in [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), where each pack's maintainers review its changes.

## Test content

Code, docs and API are in English. Test fixtures are Brazilian Portuguese finance videos, because that is the problem this was built to solve. Contributions of fixtures in other languages and domains are welcome.

## Related work this builds on

RapidFuzz (string similarity), SymSpell LookupCompound (word boundary errors), Whisper `initial_prompt` (vocabulary biasing before transcription), memoQ-style term base ranking (layer conflicts), W3C PROV (provenance), NFC normalization on input.

## License

MIT.
