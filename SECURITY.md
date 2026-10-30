# Security

## Supported versions

Only the latest release on [Releases](https://github.com/Tatiwel/transcript-normalizer/releases). A fix ships as a patch version of it.

## Reporting a vulnerability

Use **Report a vulnerability** on the repository's [Security advisories](https://github.com/Tatiwel/transcript-normalizer/security/advisories) page. If that does not work for you, email danieldandez@gmail.com. Never in a public issue.

Say what you found, the version (`transcript-normalizer --version`), your system, and how to reproduce it.

## What is in scope

- **The sign-in** (your browser's login, D-071, D-078): how the browser or `cookies.txt` is named to yt-dlp, and anything that would make a cookie leave the computer for a site other than the one being fetched, or land in a file the program writes.
- **Packs from the repository** (D-055): `pack install` and `pack update` writing a file that does not match the index's sha256, a pack name that writes outside `packs/`, and a pack file that runs code when loaded.
- **The executables** and how the release workflow builds them.
- **Dependencies**: a vulnerable version in `uv.lock`, which is what the executables are built with.

## What is not

- **A wrong correction in a transcript.** That is an ordinary [issue](https://github.com/Tatiwel/transcript-normalizer/issues).
- **A problem in a pack's content** (a term, a variant, a context). Packs are maintained in [transcript-normalizer-packs](https://github.com/Tatiwel/transcript-normalizer-packs); see its [SECURITY.md](https://github.com/Tatiwel/transcript-normalizer-packs/blob/main/SECURITY.md).

## What to expect

The project has one maintainer. You get an acknowledgement within 7 days. The fix, when there is one, is published as a patch release with the advisory.

## For users

- **Download only from [Releases](https://github.com/Tatiwel/transcript-normalizer/releases).** The release workflow builds every file from the tagged commit, and the Release page ends with the SHA-256 of each one: compare it with `sha256sum <file>`, or `certutil -hashfile <file> SHA256` on Windows. The checksums come from the same page as the files, so they show a download is intact, not who made it.
- **The executables are not signed.** Windows says it protected your PC (choose *More info*, then *Run anyway*), and macOS asks the first time (right-click, then *Open*). That warning is expected; a file from anywhere else is not one of ours.
- **Your browser's login.** The program never reads, copies or stores a cookie itself. It tells yt-dlp which browser, or which `cookies.txt`, to use; yt-dlp reads it in the same process and sends a site only that site's cookies. `config.toml` keeps the browser's name or the file's path, never a cookie, and no run's files mention either. With a `cookies.txt`, yt-dlp writes the refreshed cookies back into that same file when it finishes.
- **What goes online.** By itself the program reaches the site of the link you fetch (through yt-dlp, with the servers that site sends it to), the packs index and pack files on raw.githubusercontent.com (`pack list`, `install`, `update`, and the menu), and Hugging Face, once, for the speech model of the full build. `pack propose` sends nothing: it opens a prefilled issue in your browser, which you check and submit there.
- **Packs.** Pack files are read with `yaml.safe_load`, so a pack cannot run code. A pack from the repository is checked against the sha256 in its index before it is written. That index comes from the same repository, so it catches a broken download, not a compromised repository.
