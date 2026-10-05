# transcript-normalizer: the guide

For three readers at once: you want cleaner transcripts and nothing else; you study another field and want to teach the tool your vocabulary (biomedicine is the running example); you are a developer. Each section is short. Decision numbers like (D-020) point into [DECISIONS.md](DECISIONS.md), where the reasons and the measurements live. A Brazilian Portuguese version is in [GUIDE.pt-BR.md](GUIDE.pt-BR.md).

**Start here** (section 2 has the details):
- *I just want to use it:* download the program for your system from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases) and double-click it.
- *I use Python:* `pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.0"`.
- *I want to contribute:* `git clone https://github.com/Tatiwel/transcript-normalizer`, then [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. What it does, and what it does not

Automatic captions and speech recognition mishear the vocabulary of a field. A finance video gets `SEMIG` for CEMIG and `evitida` for EBITDA; a pharmacology lecture gets `metiformina` for metformina. The tool knows the terms you give it, a **pack**, and finds the places where the transcript got one of them wrong. Text that resembles nothing in the pack is never touched, so a finance pack cannot damage a biology lecture (D-001).

It never changes what the speaker said; it fixes what the recognizer heard. That is the difference between a **correction** (the caption garbled the term: `SEMIG` becomes `CEMIG`) and an **alias** (the speaker really said it another way, such as the ticker `CMIG4` or a plural; it is recognized and left exactly as said, D-020). The original caption and its timestamps are never modified: every change is a separate record that points at the text (D-004). It is not a spell checker, it does not summarize, and it does not ask an AI to rewrite anything.

## 2. Install

**I just want to use it.** Download the program for your system from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases). `lite` (about 40 MB) gets the platform's captions; `full` (several hundred MB) can also transcribe audio on your computer, and downloads its speech model the first time it does. Windows: double-click the `.exe`; the file is not signed, so if Windows says it protected your PC, choose *More info*, then *Run anyway*. macOS (Apple silicon): unzip, then right-click and *Open* the first time. Linux: extract it and run it from a terminal. It opens the menu (section 3). Your files go to `Documents/transcript-normalizer/` (`runs/` and `packs/`), and the menu's first line says where (D-052).

**I use Python.**

```
pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.0"
```

Without an extra you get the normalizer alone (a few MB): call it from your own program, or normalize caption files you already have. `[captions]` adds `fetch` with platform captions (yt-dlp); `[ingest]` adds local speech recognition (faster-whisper) too. Files go under the current directory. The package is not on PyPI yet; the wheel is also attached to each Release.

**I want to contribute.**

```
git clone https://github.com/Tatiwel/transcript-normalizer
cd transcript-normalizer
uv sync --extra ingest
uv run pytest -q
```

Then read [CONTRIBUTING.md](../CONTRIBUTING.md).

Whichever way: no ffmpeg is needed (faster-whisper decodes audio itself). To read YouTube, recent yt-dlp versions need a JavaScript runtime such as Deno; if YouTube downloads fail with a message about JavaScript, install one.

## 3. First run, two ways

**The menu.** Double-click the program, or type `transcript-normalizer` with nothing after it in a terminal:

```
your files: /home/ana/Documents/transcript-normalizer
╭────────────────────────── transcript-normalizer ───────────────────────────╮
│ 1. Fetch a video or file   download a caption, or transcribe audio locally │
│ 2. Normalize a run         fix domain terms in a fetched caption           │
│ 3. Review pending          answer what the tool was unsure about           │
│ 4. Show a run's outputs    where the files are, first lines of the result  │
│ 5. List runs               everything under runs/                          │
│ 6. Help                    what each action does and its command           │
│ q. Quit                                                                    │
╰────────────────────────────────────────────────────────────────────────────╯
(a number; ? for help, ?N for one item; q to quit)
```

Fetch a video (1), normalize it (2), and answer the questions it is unsure about (3). Every menu item runs one of the commands below, so anything you learn in the menu works in a script (D-051). `?2` shows what item 2 does and the command it runs:

```
  2. Normalize a run  pick a run by number; shows the report, then offers the
                      review if anything is pending
                      `transcript-normalizer runs/<id>/legenda.txt`
```

`transcript-normalizer help` (or `--help`, or menu item 6) prints the whole reference in sections: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE. One of them:

```
THE REVIEW LOOP
  y  the recognizer garbled the term: correct it from now on
  n  not this term: never propose it again
  l  this term, said that way: recognize it, never change it
  s  not sure: asked again next time; two seconds of doubt is a skip
  a  yes to this form and the remaining forms of the same term
  r  no to this form and the remaining forms of the same term
```

**The three commands.**

```
transcript-normalizer fetch https://youtu.be/4wCtn8BWR4o
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt --confirm
```

`fetch` takes the platform's caption (the original-language track, never an automatic translation, D-045) and falls back to transcribing the audio locally if there is none (D-036). A local audio or video file works too: `transcript-normalizer fetch aula.mp4`. The second command normalizes; the third does the same and then asks you about what it was unsure of. `transcript-normalizer list` shows what you have. Part of what the second one prints for the video above:

```
runs/4wCtn8BWR4o/legenda.txt: 239 caption lines, pack 0.3.3
terms:
  Semig, semiga, SEMIG, Semiga (21 occurrences) -> CEMIG
  evitida (1 occurrence) -> EBITDA
  dívida alíquida (1 occurrence) -> dívida líquida

recognized (not changed):
  CEMIG (14 occurrences) -> CEMIG
  bilhões, Bilhões (8 occurrences) -> bilhão

to confirm:
  Adaptavalda, a DAPTA Valdre, AdaptaValor, adaptavala (4 occurrences) -> Adapta Valuer
  dividido (2 occurrences) -> dividendo
```

## 4. Reading the outputs

Everything goes under `runs/<video-id>/` in the current directory; nothing is written beside your input (D-015, D-022).

| file | what it is |
|---|---|
| `legenda.txt` | the transcript as received, with a header saying where it came from |
| `meta.yaml` | title, channel, date, and which step of `fetch` produced the text |
| `normalized.txt` | the transcript with corrections applied, same lines, same timestamps |
| `annotations.json` | every change and recognition, as data |
| `report.txt` | what the command printed |
| `needs-review/pending.txt` | what still needs your answer |
| `needs-review/corrections.csv` | with `--corrections`: the changes as a table to check by hand |

`needs-review/` holds the files that need a person. If it is empty or missing, nothing is waiting for you.

`normalized.txt` reads like the original. Line 9:36 of the video above, before and after:

```
9:36 lógico indicador de alavancagem, dívida alíquida sobre evitida, cresceu uma vez,
9:36  lógico indicador de alavancagem, dívida líquida sobre EBITDA, cresceu uma vez,
```

`annotations.json` has one record per change, pointing at character offsets in the original:

```json
{"start": 9141, "end": 9156, "original": "dívida alíquida", "replacement": "dívida líquida",
 "term": "dívida líquida", "rule": "term:variant", "kind": "correction", "band": "high",
 "score": 100, "applied": true, "pack_version": "0.3.3"}
```

`kind` is `correction` or `alias`. `band` is how sure the tool is: **high** (a listed form: applied), **medium** (a close guess: applied, and listed in `pending.txt` for you to confirm), **low** (a faint resemblance: only recorded, never applied) (D-011).

## 5. The confirmation loop

`--confirm` (or menu item 3) asks about each medium-band guess, one form at a time, with the lines it appears on:

```
Oswaldo Cruz  (1 occurrence)
  Osvaldo Cruz  (1 occurrence)
    0:20  a metformina ainda é a primeira escolha, segundo o Osvaldo Cruz
    Osvaldo Cruz -> Oswaldo Cruz? [y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no:
```

| answer | when |
|---|---|
| `y` | the recognizer garbled the term; correct it from now on |
| `n` | it is not this term; never propose it again |
| `l` | it is this term, but the speaker really said it that way; recognize it, never change it |
| `s` | you are not sure |
| `a` | yes to this form and every remaining form of the same term |
| `r` | no to this form and every remaining form of the same term |

**If you have to think more than two seconds, skip.** A skipped question comes back next time; a wrong answer is remembered. Answers are saved after each one, so Ctrl+C loses nothing (D-037). They go to `packs/<pack-name>.learned.yaml`, your personal layer, never into the pack (D-013).

## 6. Your own domain

A pack is a YAML file. Here is a first biomedicine pack with six terms, one of each kind you are likely to need:

```yaml
# Biomedicina, pt-BR. 0.1.0: first terms, from one lecture.
language: pt-BR
version: 0.1.0
terms:
  - term: metformina          # a drug
    class: conceito
    aliases: [Glifage]
    variants: [metiformina, met forming]
  - term: PCR                 # an acronym
    class: sigla
    aliases: [RT-PCR, reação em cadeia da polimerase]
    variants: [pê cê erre]
  - term: miligrama           # a unit
    class: unidade
    aliases: [mg, miligramas]
  - term: Oswaldo Cruz        # a person
    class: pessoa
    variants: [Oswald Cruise]
  - term: Western blot        # a method
    class: conceito
    variants: [western blood, uéstern blot]
  - term: Anvisa              # an organization
    class: organizacao
    variants: [Anuvisa, Am visa]
```

- `term` is how it should be written. `aliases` are other correct names (a brand, a plural, the full form of an acronym). `variants` are what the recognizer produced instead.
- `class` must be one of eight: `companhia`, `indicador`, `conceito`, `unidade`, `pessoa`, `organizacao`, `ferramenta`, `sigla` (D-021). They were written for finance: a drug or a method is a `conceito`. Names (`companhia`, `pessoa`) also get phonetic matching, which catches garbles never seen before (D-050).
- Keep out variants of one or two letters and variants that are ordinary words, even if the caption used them (D-005, D-032).

Put the file in `packs/` in the directory you work in, and point at it:

```
transcript-normalizer aula.txt --pack packs/biomed-ptbr.yaml
```

```
  Anuvisa (1 occurrence) -> Anvisa
  Oswald Cruise (1 occurrence) -> Oswaldo Cruz
  pê cê erre (1 occurrence) -> PCR
  western blood (1 occurrence) -> Western blot
  metiformina (1 occurrence) -> metformina
```

Your answers in the confirmation loop grow `packs/biomed-ptbr.learned.yaml`. When a learned entry has proven itself, move it into the pack by hand and bump the version; [CONTRIBUTING.md](../CONTRIBUTING.md) section 2 has the curation rules and how to measure a pack.

## 7. Another language

A pack declares its language (`language: pt-BR`), and a language module supplies what the core must not guess: how text is folded, what a plural looks like, the unit patterns, where a sentence ends, and the phonetic skeleton. Brazilian Portuguese is the only one so far. Adding one is a single Python file; [CONTRIBUTING.md](../CONTRIBUTING.md) section 1 walks through it.

## 8. How good is it

Four videos have a hand-checked answer key (a **gold** file) and are re-measured on every change (`uv run python scripts/measure.py`). With the pack that ships (0.3.3):

| video | rows to get right | right | missed | wrong changes |
|---|---|---|---|---|
| R2Qgz8tFWVI | 167 | 145 | 22 | 16 |
| wxgFO_fyfXg | 222 | 211 | 11 | 10 |
| 4wCtn8BWR4o | 45 | 44 | 1 | 2 |
| 4tTmY8Buask | 119 | 108 | 11 | 4 |

- **R2Qgz8tFWVI**: a finance channel on one utility (CEMIG), platform captions; the first fixture, where most variants come from.
- **wxgFO_fyfXg**: the same channel comparing two utilities; many aliases (tickers, plurals) that must not be changed.
- **4wCtn8BWR4o**: another speaker on the same company, transcribed locally with faster-whisper instead of platform captions.
- **4tTmY8Buask**: that second speaker on a new sector (an investment bank), with a company name the pack did not know.

The limits, honestly:

- **Ordinary words are left alone**, even when the recognizer used one for a term (`tira` for TIR, `divide` for dividendo). Telling them apart needs the surrounding words, which the tool does not read yet.
- **The same garble can mean two terms.** `dividendio` is dividend yield for one speaker and dividendo for the other; the pack can hold it for only one (D-046).
- **Short strings match only exactly.** `RO` for ROE, `sel` for Selic: a form under six letters is never guessed by spelling, and the phonetic check for names needs five consonants.
- **A new field starts from zero.** The fourth video found 4 of 81 corrections before its company name was in the pack.

## 9. Glossary

- **pack**: the YAML list of terms the tool may touch, for one field and one language.
- **variant**: a form the recognizer produced instead of the term; it is corrected.
- **alias**: another correct name of the term (ticker, brand, plural); recognized, never changed.
- **band**: how sure a match is: high (applied), medium (applied and asked about), low (recorded only).
- **run**: the directory `runs/<video-id>/` holding one video's transcript and everything made from it.
- **fixture**: a video kept in the repository with its transcript, a frozen pack and a gold file, for measuring.
- **gold**: the hand-checked answer key of a fixture: every place that should change, and every place that must not.
- **learned layer**: your answers from the confirmation loop, in `packs/<pack>.learned.yaml`; personal, never shipped.
- **stand-off**: keeping changes as separate records that point at the original text, instead of editing it.
