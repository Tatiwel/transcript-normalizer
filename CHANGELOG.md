# Changelog

## Unreleased

- Test builds: the release workflow can be started by hand (Actions → release → Run workflow) on any commit. It builds and tests the same executables, named after the commit, and keeps them as workflow artifacts `<sha>-<os>-<flavor>`; no tag check, no Release. Tag pushes release as before.
- `--gold-draft`, the old name of `--corrections`, is removed (D-023, amended); it was kept far longer than its one release.
- Docs: the `pip install` lines point at v0.6.3 instead of v0.4.2, whose `ingest` extra lacked D-058's faster-whisper/av bounds. GUIDE §8 and the README's Status give the current measured numbers and name `scripts/measure.py` as their source. The `ask` band (D-060) is documented. Smaller fixes to sample output, the merge backup name, the phonetic classes in CONTRIBUTING and the release page's Windows full row.
- Residue removed after the 2026-10 inspection (docs/INSPECTION-2026-10.md): the unused `contains_words` and its test, `META_FIELDS`, evaluate's two one-line wrappers; `fits()` is now what normalize and measure.py call. Tests share one bundled-pack fixture and cache the fixture's medium band, which they used to recompute per call.
- Tests pin three matcher rules no test covered: D-047's ranking (a canonical term at 80 beats a variant at 84 for the same span) and the D-040 and D-049 guards, before and after overlap resolution, including the case that shows why they are needed (a rejection that removes the longer name). Matching is unchanged.
- Normalizing is about three times faster, with byte-identical results: each caption window is compared only with the pack forms that can match it (its exact equals, and fuzzy forms within two letters of its length, D-005), and the phonetic pass no longer checks every window against every applied change, which made it quadratic in caption length. wxgFO_fyfXg (40 min): 2.29 s → 0.69 s; the same caption four times over: 13.2 s → 3.2 s.
- The menu never waits for the packs repository at startup (D-069, amended). It looks for pack updates in the background, keeps the index for a day in `packs/.index-cache.json` (inside the folder in portable mode), and when a copy of yours can be merged it says so in one line and offers "Merge an update" in Packs, instead of asking "Merge?" on the first screen. Offline with a copy, the first screen went from 3.2 s to 0.2 s.

## 0.6.3

A Windows installer and a portable build (D-070). Nothing changes in how captions are normalized.

- Windows full is now two downloads. `-windows-full-setup.exe`, an installer: choose where it goes, for you only (no administrator) or for all users; Start menu shortcut, optional desktop shortcut; a clean uninstall from "Add or remove programs" that keeps your files and says so. `-windows-full-portable.zip`: unzip anywhere, e.g. a USB drive, and delete the folder to remove it. The plain windows-full zip is gone; lite, macOS and Linux are unchanged.
- Portable mode: with `portable.txt` beside the program (any build, lite too), everything stays in its `data` folder: runs, packs, settings, the speech model (`HF_HOME`), yt-dlp's cache and whatever its JavaScript runtime writes. Settings says "portable mode: everything stays in <folder>" and has no folder dialog. `TRANSCRIPT_NORMALIZER_HOME` still wins.
- The release runner installs, runs and uninstalls the installer silently, and checks that the portable build writes only inside its folder.

## 0.6.2

Three-way pack merge (D-069).

- A copy of a pack (`pack copy`, or the menu's copy before editing) records `based_on: <name>@<version>` and `local_edits`, and keeps its base in `packs/.bases/`. Every saved edit counts.
- When upstream (the bundled pack or the packs repository) is newer than a copy's base, the menu's first screen asks "Merge?", Installed packs shows `↑ merge available`, and `pack update` says so. Nothing is merged unasked.
- `pack merge <name> [--dry-run] [--yes-theirs | --yes-mine]`: by canonical term, three-way with the base (two-way for a copy from before 0.6.2, which then gains a base). Conflicts are asked one at a time with both versions and lines from your runs: keep mine (`m`), take theirs (`t`), keep both (`k`, when compatible), decide later (`l`, recorded in `<name>.merge-pending.yaml`).
- Before writing: a `<name>.yaml.bak-<timestamp>` backup, and the result checked as normalize loads it. A summary of what was added, updated, kept, combined and removed, the conflicts, and where the learned layer (never changed) now repeats or contradicts the pack.
- `pack propose --whole` on a copy proposes only its changes since the base: "<name>: N additions from <user>".

## 0.6.1

Editing packs (D-066), contributing a whole pack (D-067), English and phonetic classes (D-068).

- Packs → Edit a pack: add a term (class from the pack's classes, aliases, variants one per line), edit a term, remove a term, show terms (paged, searchable). A bundled or repository pack is read-only; the menu offers your own copy first. Every change is checked and saved with the next patch version. A variant under 3 letters is refused (D-005); a variant made of ordinary words is saved with a warning (D-032). Commands: `pack copy`, `pack add-term`, `pack edit-term`, `pack remove-term`, `pack show`.
- "Add a term you noticed", offered after Normalize and in Show a run's outputs: the wrong form (with up to five of the run's lines containing it), what it should be, then a variant or alias of an existing term, or a new term; then an offer to normalize the run again.
- Packs → Export a pack file and `pack export <name> [--to <path>]`: `<name>-<version>.yaml`.
- Packs → Contribute a pack and `pack propose --whole <name>`: the pack's summary, a question, `contributions/<name>-<version>.yaml`, and a prefilled issue "New pack: <name>" or "Update: <name>" with the file in the body, collapsed.
- An English language module: folding, plurals (-s, -es, -ies), `bn`/`B` and `mn`/`M` after a number as billion and million, sentence punctuation. The menu passes `--allow-generic`, with a notice, only for a language that still has no module.
- `phonetic_classes:` per pack: which classes the phonetic source compares (default `pessoa`, `organizacao`, and `companhia` where declared). The medicina, tecnologia and esportes templates set their own. Pack 0.3.7: financas-ptbr declares D-050's `companhia` and `pessoa`; nothing it matches changes. Created packs record their `field:`.
- The Packs menu is now: Installed, Get, Create, Edit, Import, Export, Remove, Contribute, The pack offered first.

## 0.6.0

Packs for other fields: classes per pack (D-064), field templates and a Packs menu (D-065).

- A pack declares its classes (`classes: [farmaco, doenca]`). `pessoa`, `organizacao`, `sigla` and `unidade` are allowed in every pack. A term with any other class is an error at load, naming the file and the term. A pack with no `classes:` line keeps the eight finance classes, so every existing pack still loads. Pack 0.3.6: financas-ptbr declares its eight; no term changes.
- Ten field templates: financas, medicina, direito, tecnologia, engenharia, educacao-ciencias, esportes, politica-governo, agro, geral. Each gives a new pack its classes and no terms.
- Menu item 6, Packs: Installed packs, Get a pack, Create a pack, Import a pack file, Remove a pack, and The pack offered first (moved from Settings). Settings is now 7 and only the folder; Help is 8.
- New commands: `pack list --installed` (version, language, terms, size, source, and `↑ update` when the packs repository has a newer version; offline, no wait over 3 seconds), `pack create --template <field> --name <n> --lang <l>`, `pack import <file>`, `pack remove <name>` (never a bundled pack; the learned layer is kept).
- When a pack does not fit, the menu says "Pick another pack, or get or create one in Packs."
- D-063 records the 0.5.3 measurements: `help` on windows-full in 5.78, 5.59, 5.13 s as one file, 0.30, 0.29, 0.28 s as a folder; the Linux runner has glibc 2.35.

## 0.5.3

Packaging (D-063), and four fixes from the last Windows run.

- The full executables for Windows and macOS are a folder, shipped as a zip (`transcript-normalizer-0.5.3-windows-full.zip`): unzip, then open `transcript-normalizer.exe` inside the folder (`transcript-normalizer` on macOS). As one file, the full build unpacked about 100 MB to a temporary folder on every start, which made it slow to open on Windows. lite stays one file, and so does Linux full. The release runner measures `help`'s start time against 0.5.2's one-file build.
- The Linux executables are built on Ubuntu 22.04 (glibc 2.35), so they run on 22.04-based systems such as Zorin 17; 0.5.2's needed the glibc of the newest runner.
- The file dialog opens on "All supported (audio, video, captions)"; the separate filters are still there.
- Automatic translations in the track list carry "(translations are rate-limited more often)".
- A chosen option is echoed by its label, without its description.
- Checked: when a pack does not fit, normalized.txt is written with the input's text, line for line (D-054); a test now says so.

## 0.5.2

The fetch flow (D-062). Only the menu and fetch's options changed; normalizing works as before.

- "Fetch a video or file" asks "Where is it?": a link, or a file on this computer. A file opens the system's file dialog (audio and video, captions, or all files), or asks for a typed path where there is none. A caption file (.srt, .vtt, .txt) goes straight to normalizing; an audio or video file to local transcription.
- For a link, the menu shows the video's details and asks "Use the platform's caption, or transcribe the audio on this computer?". In the lite build the second option is shown, disabled, "(full build only)". With no caption, the full build asks whether to transcribe, and the lite build says why it cannot.
- The caption track is picked by name: "Portuguese, original audio (automatic)" first, and Enter takes it, as before (D-045); then the channel's own ("Portuguese (written by the channel)"); then "Other languages (automatic translations)…", which opens the list. A video with one track names it without asking.
- `fetch --track <code>` takes exactly that track (`pt-orig`, `pt`, `en`). `--lang` is unchanged.
- Settings prints its hint once, not again after each change.

## 0.5.1

- Fix for the Linux executables of 0.5.0, which were not published: their build used the runner's Python, which has no tkinter, so the folder dialog was missing and the release check stopped them. Linux executables are now built from a uv-managed Python that ships tkinter (D-061).

## 0.5.0

A clearer menu (D-061). Only the menu changed; normalizing works as before.

- Settings (menu item 7). "Where to save your files" shows the folder in use and opens a folder dialog; where there is none (no display), you type the path. "The pack offered first" puts a pack at the top of "What is this video about?". Both are kept in `config.toml` in your user settings folder. The chosen folder is used by the executables and by pip installs alike; `TRANSCRIPT_NORMALIZER_HOME` still wins, for scripts. The first screen says which folder is in use.
- Back everywhere: every list ends with "← Back", which returns to the previous screen (the menu, or the previous question: Back from "What is this video about?" returns to the run list). Esc does the same. Text fields say "(empty or Esc: back)".
- A visible structure: a rule and a stage label before each block (◆ Fetch, ◆ Normalize, ◆ Review, ◆ Settings), ● and ○ in multi-selects, » for the cursor, a "── paste below ──" or "── type a path ──" line above each text field, and the video's details as label and value (paths blue, numbers bold). Without a terminal or questionary, the same structure in ASCII (`* Fetch`, `b. <- Back`, `[*]`).
- The first screen says what the installation can do: "full build: captions and local transcription" or "lite build: platform captions only (no local transcription)" in the executables, "captions + local transcription" or "captions only" in a pip install.
- From the Windows run: the menu never prints exit codes ("not normalized yet (2)" is "not normalized yet"); "Review pending" on a run with nothing pending, or whose pack did not fit, says "nothing to review for this run" and returns, without "Open the folder?"; when the pack does not fit, the menu says "Pick another pack in Settings, or install one with pack install." instead of the `--force` advice, which stays on the command line.
- The executables carry tkinter for the folder dialog; the release smoke test checks that it loads.

## 0.4.6

- Phonetic matches only ask (D-060). A name found by sound and not by spelling (the phonetic source of D-050) goes to "to confirm" and is never substituted until you confirm it. In a forced run on a video about prions, `proteínas` had been turned into BR Partners 40 times; now it is a question, and the text stays.
- Pack 0.3.5: `trio` counts as the unit `tri` only in `primeiro/segundo/terceiro/quarto trio`; alone it is an ordinary word.
- D-035 records a second out-of-domain silence run (yJxxTf0IQC8): nothing applied, with or without `--force`.

## 0.4.5

- A failed attempt no longer breaks the next one (D-059). An incomplete audio file left in the run folder (the cause of "HTTP Error 416: Requested range not satisfiable" after 0.4.3's crash) is deleted before downloading, and downloads always start from zero. A 416 is retried once. When fetch fails, it removes the files it wrote in that attempt.
- A crash while transcribing is reported as a failure, not as a traceback.
- The executables write UTF-8, so yt-dlp's messages keep their quotes in logs and redirected output on Windows.
- Unused imports removed from two test files.

## 0.4.4

- Fix for the full executables: transcribing failed with "open() got an unexpected keyword argument 'metadata_errors'". The build had paired faster-whisper with a newer av it does not support. Executables are now built from the lock, the two have upper bounds, and every full executable is checked to decode audio before release (D-058).
- `?` in the menu explains each option with its help entry and command, instead of repeating the menu.
- When the caption cannot be had, the menu says why in plain words (HTTP 429, or no caption) before asking about transcription, and does not show the video's details twice.
- The retry countdown stays on screen ("retrying in 4 s"), so the waits between attempts are visible.
- No Hugging Face warnings. The first model download says so in one line ("downloading the speech model (about 1.5 GB, first time only)…"), with a progress bar.

## 0.4.3

- Fix for the executables: `fetch` failed in every frozen build with "invalid choice: 'yt_dlp'", because it ran yt-dlp as a subprocess of the executable itself. yt-dlp now runs in-process through its Python API (D-057).
- Errors from the platform caption step are shown as yt-dlp gives them, first. The lite build's "cannot transcribe audio" notice appears only when transcription is really needed.
- `fetch --check` lists the fetch tools installed (yt-dlp, curl_cffi, faster-whisper) and their versions.
- The release workflow tests every executable with `fetch --check` and a real `fetch --list` before publishing.

## 0.4.2

- Pack fit (D-054): a pack that names fewer than three of its terms with confidence does not fit the transcript, and nothing is applied: `normalized.txt` stays as the input, with a message saying so. `--force` applies anyway. The menu asks "What is this video about?" before normalizing: your packs, or "none / another area".
- A packs repository (D-055): packs live in [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs), each with its maintainers. `pack list`, `pack install <name>` (checked against the index's sha256) and `pack update`. The bundled financas-ptbr stays the offline default.
- Contributing back (D-056): `pack propose` shows what your reviews taught the tool (term, form, decision; never the transcript), writes `contributions/<pack>-<date>.yaml` and opens a prefilled issue on the packs repository. The menu offers it after a review.
- `normalize` on a missing file says "no caption at <path>; run fetch first" instead of a traceback; so does any missing file.
- `normalize` takes a `.srt` or `.vtt`, converted into `runs/<stem>/legenda.txt`. The menu's "Normalize a run" takes a typed path too.
- The menu offers "Open the folder?" after normalize or review, and prints the counters once when it goes straight from one to the other.
- `fetch` deletes the downloaded `.vtt` or `.srt` once converted; `--keep-raw` keeps it.
- For contributors: `uv sync` keeps every extra (the `dev` group includes `[ingest]`).

## 0.4.1

- A lower-friction menu (D-053): arrow keys and multi-select with the new `[menu]` extra (rich, questionary), numbered text without it. A first screen with the version, where your files are and the typical flow. Runs are picked from a list, and each step offers the next one. Esc or empty input goes back, and `?` explains any question.
- `normalize --review`: the review one term per screen. Select the forms that are the term; the rest are rejected; then say which of those the speaker really said that way. The menu reviews this way. `--confirm` keeps the per-form loop.
- `normalize --summary`: three counters (corrected, recognized, to confirm) and where the result is, instead of the full report. The menu uses it.
- Colour on a terminal, one colour per meaning. Plain text everywhere else.
- The `lite` executable says it cannot transcribe audio and points to the full build.
- The release page starts with "Which file do I download?", in English and Portuguese.

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
