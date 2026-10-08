# transcript-normalizer: the guide

For three readers at once: you want cleaner transcripts and nothing else; you study another field and want to teach the tool your vocabulary (biomedicine is the running example); you are a developer. Each section is short. Decision numbers like (D-020) point into [DECISIONS.md](DECISIONS.md), where the reasons and the measurements live. A Brazilian Portuguese version is in [GUIDE.pt-BR.md](GUIDE.pt-BR.md).

**Start here** (section 2 has the details):
- *I just want to use it:* download the program for your system from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases) and double-click it.
- *I use Python:* `pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.2"`.
- *I want to contribute:* `git clone https://github.com/Tatiwel/transcript-normalizer`, then [CONTRIBUTING.md](../CONTRIBUTING.md).

## 1. What it does, and what it does not

Automatic captions and speech recognition mishear the vocabulary of a field. A finance video gets `SEMIG` for CEMIG and `evitida` for EBITDA; a pharmacology lecture gets `metiformina` for metformina. The tool knows the terms you give it, a **pack**, and finds the places where the transcript got one of them wrong. Text that resembles nothing in the pack is never touched, so a finance pack cannot damage a biology lecture (D-001).

It never changes what the speaker said; it fixes what the recognizer heard. That is the difference between a **correction** (the caption garbled the term: `SEMIG` becomes `CEMIG`) and an **alias** (the speaker really said it another way, such as the ticker `CMIG4` or a plural; it is recognized and left exactly as said, D-020). The original caption and its timestamps are never modified: every change is a separate record that points at the text (D-004). It is not a spell checker, it does not summarize, and it does not ask an AI to rewrite anything.

## 2. Install

**I just want to use it.** Download the program for your system from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases). `lite` (about 40 MB) gets the platform's captions; `full` (several hundred MB) can also transcribe audio on your computer; the first time it does, it downloads a 1.5 GB speech model. The Release page has a table of which file is which. `lite` is one file; `full` is a zip with a folder inside (on Windows and macOS): unzip it, then open `transcript-normalizer.exe` inside the folder (`transcript-normalizer` on macOS), and keep the folder together, since the program loads its parts from it (D-063). Windows: double-click the `.exe`; the file is not signed, so if Windows says it protected your PC, choose *More info*, then *Run anyway*. macOS (Apple silicon): unzip, then right-click and *Open* the first time. Linux: extract it and run it from a terminal. It opens the menu (section 3). Your files go to `Documents/transcript-normalizer/` (`runs/` and `packs/`), and the menu's first screen says where (D-052). To keep them somewhere else, choose Settings in the menu, then "Where to save your files": a folder dialog opens (or, where there is none, you type the path), and the choice is kept in `config.toml` in your user settings folder (D-061).

**I use Python.**

```
pip install "transcript-normalizer[ingest] @ git+https://github.com/Tatiwel/transcript-normalizer@v0.4.2"
```

Without an extra you get the normalizer alone (a few MB): call it from your own program, or normalize caption files you already have. `[captions]` adds `fetch` with platform captions (yt-dlp); `[ingest]` adds local speech recognition (faster-whisper) too. Files go under the current directory, unless the menu's Settings chose a folder. The package is not on PyPI yet; the wheel is also attached to each Release.

**I want to contribute.**

```
git clone https://github.com/Tatiwel/transcript-normalizer
cd transcript-normalizer
uv sync
uv run pytest -q
```

`uv sync` installs every extra, through the `dev` group. Then read [CONTRIBUTING.md](../CONTRIBUTING.md).

Whichever way: no ffmpeg is needed (faster-whisper decodes audio itself). To read YouTube, recent yt-dlp versions need a JavaScript runtime such as Deno; if YouTube downloads fail with a message about JavaScript, install one.

## 3. First run, two ways

**The menu.** Double-click the program, or type `transcript-normalizer` with nothing after it in a terminal. With the `[menu]` extra (every executable has it) you move with the arrow keys:

```
transcript-normalizer 0.5.0
full build: captions and local transcription
Your files: /home/ana/Documents/transcript-normalizer
Typical flow: 1 fetch → 2 normalize → 3 review
Keyboard: ↑↓ move · enter confirm · esc back · ? explain
  pick an action; empty input or Esc here quits
◇ What would you like to do? ↑↓ move · enter confirm · esc back · ? explain
 » Fetch a video or file   download a caption, or transcribe audio locally
   Normalize a run         fix domain terms in a fetched caption
   Review pending          answer what the tool was unsure about
   Show a run's outputs    where the files are, first lines of the result
   List runs               everything under runs/
   Packs                   installed, get, create, edit, share
   Settings                where to save your files
   Help                    what each action does and its command
   Quit
```

"Fetch a video or file" first asks "Where is it?": a link, or a file on this computer. A file opens your system's file dialog (or, where there is none, you type the path); a caption file (`.srt`, `.vtt`, `legenda.txt`) goes straight to normalizing, and an audio or video file is transcribed on your computer. For a link, the menu reads the video, shows its title, channel and duration, and asks "Use the platform's caption, or transcribe the audio on this computer?" (in the lite build the second option is shown as "full build only"). The caption is then picked by name: "Portuguese, original audio (automatic)" first, which Enter takes, then the channel's own ("Portuguese (written by the channel)"), then "Other languages (automatic translations)…", marked "(translations are rate-limited more often)", since YouTube refuses them with HTTP 429 more often. With no caption at all, the full build offers to transcribe and the lite build says why it cannot (D-062). Each step offers the next one: after a fetch, "Next: normalize this run now?"; then "What is this video about?", a list of your packs and "none / another area" (section 6); after normalizing, three counters and "Next: review the 6 uncertain one(s) now?". The result is usable without the review; reviewing makes the next video better. After a review the menu offers to contribute what you taught the tool (section 6), and at the end "Open the folder?" opens the run's folder in your file manager. "Normalize a run" also takes a file you already have: choose "A file…" and type its path, a `legenda.txt` or a `.srt` or `.vtt` subtitle. Every list ends with "← Back", which returns to the previous screen (Esc does the same, and so does empty input in a text field), and `?` explains its options. Under the version, the first screen says what this installation can do: "full build: captions and local transcription" or "lite build: platform captions only (no local transcription)" for the program, "captions + local transcription" or "captions only" for a pip install. Each block starts with a rule and its stage (◆ Fetch, ◆ Normalize, ◆ Review, ◆ Settings), and a line such as "── paste below ──" marks where you type. Without the extra, or without a terminal, the same questions come as numbered lines, with ASCII marks (`* Fetch`, `b. <- Back`). Every menu item runs one of the commands below, so anything you do in the menu works in a script (D-051, D-053). What normalizing shows in the menu, for the video below:

```
corrected 24  (semiga → CEMIG, Semig → CEMIG)
recognized 65  (terms already spelled right, left as they are)
to confirm 6  (the tool was unsure; your answer is remembered)
result: runs/4wCtn8BWR4o/normalized.txt
```

`transcript-normalizer help` (or `--help`, or menu item 8) prints the whole reference in sections: USAGE, COMMANDS, MENU, WHAT HAPPENS, THE REVIEW LOOP, EXAMPLES, LEARN MORE.

**The three commands.**

```
transcript-normalizer fetch https://youtu.be/4wCtn8BWR4o
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt
transcript-normalizer runs/4wCtn8BWR4o/legenda.txt --review
```

`fetch` takes the platform's caption (the original-language track, never an automatic translation, D-045) and falls back to transcribing the audio locally if there is none (D-036). A local audio or video file works too: `transcript-normalizer fetch aula.mp4`. The downloaded `.vtt` or `.srt` is deleted once converted into `legenda.txt`; `--keep-raw` keeps it. The second command normalizes, and takes a `.srt` or `.vtt` as well, which it converts into `runs/<file-name>/legenda.txt` first; the third does the same and then asks you about what it was unsure of. `fetch --list <url>` shows a video's caption tracks, and `fetch --track <code>` takes one exactly (`pt-orig`, `pt`, `en`) instead of the choice `--lang` makes (D-062). `transcript-normalizer list` shows what you have. Part of what the second one prints for the video above:

```
runs/4wCtn8BWR4o/legenda.txt: 239 caption lines, pack 0.3.4
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
 "score": 100, "applied": true, "pack_version": "0.3.4"}
```

`kind` is `correction` or `alias`. `band` is how sure the tool is: **high** (a listed form: applied), **medium** (a close guess: applied, and listed in `pending.txt` for you to confirm), **low** (a faint resemblance: only recorded, never applied) (D-011).

## 5. Reviewing what the tool was unsure about

Menu item 3, or `--review`, shows one screen per term: the forms the tool guessed are that term, each with how often it occurs and one line where it does. Select the ones that really are the recognizer mishearing the term (space bar, then Enter); the ones you leave are rejected and never proposed again. Here the form `a DAPTA Valdre` is the channel's tool, `Adapta Valuer`:

```
Which of these are the recognizer mishearing "Adapta Valuer"?
  pick the ones that should read Adapta Valuer; the others are rejected
  a. [ ] AdaptaValor      1 occurrence · 18:16  …uma nova aba também aqui da «AdaptaValor», análise
  b. [ ] Adaptavalda      1 occurrence · 1:04  …aba mais recente aqui da «Adaptavalda», entramos aqui
  c. [ ] a DAPTA Valdre   1 occurrence · 5:03  …É o que eu sempre te falo, «a DAPTA Valdre»
  d. [ ] adaptavala       1 occurrence · 18:42  de R, tudo isso na «adaptavala».
```

If you selected any, a second screen asks which of those the speaker really said that way (a ticker, a plural, a nickname): those are kept as said and only recognized (D-020). **If you have to think more than two seconds about a term, press Esc:** it stays pending and comes back next time; a wrong answer is remembered. The answers are saved after each term (D-037), to `packs/<pack-name>.learned.yaml`, your personal layer, never into the pack (D-013).

`--confirm` asks the same thing one form at a time, answered with `y` (it is the term), `n` (it is not), `l` (it is, said that way), `s` (skip), `a` or `r` (yes or no to the rest of this term's forms):

```
  Osvaldo Cruz  (1 occurrence)
    0:20  a metformina ainda é a primeira escolha, segundo o Osvaldo Cruz
    Osvaldo Cruz -> Oswaldo Cruz? [y]es / [n]o / [s]kip / a[l]ias / [a]ll-yes / [r]est-no:
```

## 6. Packs

**Which pack, and whether it fits.** A pack is for one field. Applied to a video from another field, it can only do harm: it finds the odd short word that looks like one of its terms, and every change it makes there is wrong (D-035). So before applying anything, the tool counts how many of the pack's terms it found with confidence. Fewer than three, and it changes nothing (D-054):

```
pack financas-ptbr does not seem to fit this transcript (1 terms found); nothing applied. Use --force to apply anyway.
```

`normalized.txt` is then the transcript as it was. `--force` applies the pack anyway, for a short clip that really is from the field. In the menu, "What is this video about?" asks first: pick the pack, or "none / another area", which normalizes nothing. When the pack does not fit, the menu ends the sentence with "Pick another pack, or get or create one in Packs." instead of the `--force` advice; Packs → "The pack offered first" puts a pack at the top of that question.

**The Packs menu.** Menu item 6, Packs, is where packs are managed (D-065). Each entry runs a command, so a script can do the same:

| in the menu | the command | what it does |
|---|---|---|
| Installed packs | `pack list --installed` | a table: name, version, language, terms, size (KB), source (`bundled`, `repository` or `mine`); when the packs repository answers within 3 seconds, an `↑ update` mark where it has a newer version |
| Get a pack | `pack install <name>` | lists the packs repository (name, version, description) and installs the one you pick into your `packs/` |
| Create a pack | `pack create --template <field> --name <n> --lang <l>` | a new pack from a field template, with the field's classes and no terms; the menu then offers to put it first |
| Edit a pack | `pack add-term`, `edit-term`, `remove-term`, `show` | add, edit, remove and show terms; a bundled or repository pack is read-only, and the menu offers your own copy first (`pack copy`) |
| Import a pack file | `pack import <file>` | a file dialog on `.yaml` files (or a typed path); the file is checked as `normalize` would load it, then copied into `packs/` |
| Export a pack file | `pack export <name> [--to <path>]` | writes `<name>-<version>.yaml` into the folder you choose |
| Remove a pack | `pack remove <name>` | asks twice and shows the file; a bundled pack cannot be removed |
| Contribute a pack | `pack propose --whole <name>` | proposes the whole pack to the packs repository (below) |
| The pack offered first | (the menu's own setting) | the pack at the top of "What is this video about?" |

```
name           version  language  terms  size (KB)  source   update
financas-ptbr  0.3.6    pt-BR        70        7.9  bundled
medicina-ptbr  0.1.0    pt-BR         0        0.5  mine
```

Packs live in their own repository, [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), one directory per pack, each with the people who maintain it (D-055). The finance pack also ships inside the tool, so it works offline. `pack list` lists the repository, `pack install <name>` puts a pack in your `packs/` after checking it against the checksum the repository publishes (from then on it is the one the tool uses, and the menu lists it), and `pack update` installs newer versions and leaves alone a pack you edited. `pack remove` deletes the pack's file but keeps its learned layer (`packs/<name>.learned.yaml`), which holds your review answers.

**Your own domain.** A pack is a YAML file. Start from a field template, which gives the pack its classes:

```
transcript-normalizer pack create --template medicina --name biomed-ptbr --lang pt-BR
```

The ten templates are `financas`, `medicina`, `direito`, `tecnologia`, `engenharia`, `educacao-ciencias`, `esportes`, `politica-governo`, `agro` and `geral` (for a field with none of its own). Then add terms. Here is a first biomedicine pack with six terms, one of each kind you are likely to need:

```yaml
# Biomedicina, pt-BR. 0.1.0: first terms, from one lecture.
name: biomed-ptbr
language: pt-BR
version: 0.1.0
classes: [doenca, farmaco, procedimento, anatomia, exame]
terms:
  - term: metformina          # a drug
    class: farmaco
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
    class: procedimento
    variants: [western blood, uéstern blot]
  - term: Anvisa              # an organization
    class: organizacao
    variants: [Anuvisa, Am visa]
```

- `term` is how it should be written. `aliases` are other correct names (a brand, a plural, the full form of an acronym). `variants` are what the recognizer produced instead.
- `class` must be one of the pack's `classes:`, or one of the four every pack has: `pessoa`, `organizacao`, `sigla`, `unidade` (D-064). A class is a label for whoever reads the output; it does not change what is matched, except that a `unidade` is never matched by similarity (D-028). A pack with no `classes:` line, written before 0.6.0, keeps the eight finance classes of D-021. Names also get phonetic matching, which finds garbles never seen before and asks you about them; it never changes the text by itself (D-050, D-060). Which classes are names is the pack's `phonetic_classes:` (by default `pessoa` and `organizacao`, and `companhia` where the pack has it; the medicina template adds `farmaco` and `doenca`, D-068). It needs a language with a phonetic skeleton: pt-BR has one, English not yet.
- Keep out variants of one or two letters and variants that are ordinary words, even if the caption used them (D-005, D-032).

`pack create` puts the file in your `packs/`; a pack you wrote elsewhere goes there with `pack import <file>`. Point at it:

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

Your answers in the review grow `packs/biomed-ptbr.learned.yaml`. When a learned entry has proven itself, move it into the pack by hand and bump the version; [CONTRIBUTING.md](../CONTRIBUTING.md) section 2 has the curation rules and how to measure a pack. To share a pack, propose it to the packs repository; its README says how.

**Editing a pack.** Packs → Edit a pack picks a pack and offers: Add a term (the term, its class from the pack's classes, then other correct names and the recognizer's versions, one per line, an empty line to finish), Edit a term (type part of it, pick it, then add or remove forms, change its class or rename it), Remove a term (asks once) and Show terms (page by page, or search). A bundled pack or one from the repository is read-only: the menu offers to make your own copy first, with the same name, which is then used instead. Every change is checked as normalize would load the pack and saved at once with the next patch version (0.1.0 → 0.1.1). A variant under 3 letters is refused (it would match too many words, D-005), and a variant made of ordinary words is saved with a warning (D-032). On the command line:

```
transcript-normalizer pack copy financas-ptbr
transcript-normalizer pack add-term biomed-ptbr metformina --class farmaco --alias Glifage --variant metiformina
transcript-normalizer pack edit-term biomed-ptbr metformina --add-variant "met forming"
transcript-normalizer pack show biomed-ptbr --search metf
```

**A term you noticed.** After normalizing, and in "Show a run's outputs", the menu asks "Add a term you noticed?". It asks for the wrong form you saw, shows up to five of the run's lines with it so you can check it is the one, then what it should be. If that term is in the pack, it asks whether the recognizer misheard it (a variant, corrected from now on) or the speaker said it that way (an alias, kept as said); if not, it asks for a class and adds the term with the form as a variant. Then it offers to normalize the run again with it (D-066):

```
The wrong form you saw
> mississões
  in 1 line(s) of R2Qgz8tFWVI:
    3:22 gestão, tanto as mississões e tal. Então
Is 'mississões' the form you saw? [Y/n]
What it should be
> emissão
+ term     emissão (conceito)
  + variant  mississões -> emissão
Normalize R2Qgz8tFWVI again with it? [Y/n]
```

**Giving back.** What you teach the tool in a review stays in your learned layer. To offer it to everyone who uses the pack:

```
transcript-normalizer pack propose --pack financas-ptbr
```

```
What would be contributed to financas-ptbr 0.3.4 (3), from packs/financas-ptbr.learned.yaml:
  + variant   esse mig -> CEMIG
  + alias     Klabinha -> Klabin
  - rejected  saber se  (not Sabesp)
Only these lines are sent: the term, the form and your decision, never the transcript.
Contribute these? [y/N]
```

On a yes it writes `contributions/financas-ptbr-<date>.yaml` and opens a prefilled issue on the packs repository in your browser (or prints the link); you submit it there, and the pack's maintainers decide what goes in (D-056). The menu offers this after a review.

A whole pack, yours for a new field or a bundled one you have improved, is proposed with `pack propose --whole <name>` (menu: Packs → Contribute a pack). It shows the pack's field, classes, number of terms and five of them, and asks; on a yes it writes `contributions/<name>-<version>.yaml` and opens an issue titled "New pack: <name>", or "Update: <name>" when the repository has that pack, with the file in its body, collapsed (or, for a long pack, a note to attach the file). Nothing leaves your computer until you submit the issue yourself (D-067). `pack export <name>` writes the same file anywhere, to share it another way.

## 7. Another language

A pack declares its language (`language: pt-BR`), and a language module supplies what the core must not guess: how text is folded, what a plural looks like, the unit patterns, where a sentence ends, and the phonetic skeleton. There are two: Brazilian Portuguese, and English (plurals in -s, -es and -ies, `bn`/`B` and `mn`/`M` after a number as billion and million, no phonetic skeleton yet; D-068). A pack in another language is matched with a generic module, with no inflections and no unit rules; the menu does that by itself and says so, and a command needs `--allow-generic`. Adding one is a single Python file; [CONTRIBUTING.md](../CONTRIBUTING.md) section 1 walks through it.

## 8. How good is it

Four videos have a hand-checked answer key (a **gold** file) and are re-measured on every change (`uv run python scripts/measure.py`). With the pack that ships (0.3.4):

| video | rows to get right | right | missed | wrong changes |
|---|---|---|---|---|
| R2Qgz8tFWVI | 167 | 142 | 25 | 16 |
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
- **pack fit**: whether a pack belongs to a transcript: at least three of its terms found with confidence, or nothing is applied.
- **variant**: a form the recognizer produced instead of the term; it is corrected.
- **alias**: another correct name of the term (ticker, brand, plural); recognized, never changed.
- **band**: how sure a match is: high (applied), medium (applied and asked about), low (recorded only).
- **run**: the directory `runs/<video-id>/` holding one video's transcript and everything made from it.
- **fixture**: a video kept in the repository with its transcript, a frozen pack and a gold file, for measuring.
- **gold**: the hand-checked answer key of a fixture: every place that should change, and every place that must not.
- **learned layer**: your answers from the review (`--review` or `--confirm`), in `packs/<pack>.learned.yaml`; personal, never shipped.
- **stand-off**: keeping changes as separate records that point at the original text, instead of editing it.
