"""D-091: a run's legenda.txt is never replaced without being asked to.

What is made from a run's legenda.txt depends on it: normalized.txt, the review
lists in needs-review/, and any note a person took by its timestamps (D-102). `fetch` and `normalize
<file.vtt>` used to write it over whatever was there, so running either again,
with another model, track or file, changed the text under all of that, without
a word.

Now each command that writes a legenda.txt looks first. When one is there and
the new text would come from the same origin, the one there is used and nothing
is written. When it would come from another origin, the command stops with
EXIT_CAPTION_EXISTS and says how to keep both (`--out`) or replace it
(`--replace-caption`). Replacing moves the old text, and everything made from
it, into `replaced-<date and time>/` inside the run: it is kept, never deleted.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .review import LOCAL_FILE
from .runs import (
    ANNOTATIONS_FILE,
    CAPTION_FILE,
    META_FILE,
    NEEDS_REVIEW_DIR,
    NORMALIZED_FILE,
    NORMALIZED_SPEAKERS_FILE,
    REPORT_FILE,
    video_id_from_url,
)

#: The exit status of a command that stopped because a legenda.txt from
#: another origin is already where it would write.
EXIT_CAPTION_EXISTS = 4

#: What replacing a caption moves aside: the caption, what the video's
#: metadata says about it, and everything normalize and the review made from
#: it. The kept audio and a kept subtitle are sources, not derived, and stay.
DERIVED = (
    CAPTION_FILE,
    META_FILE,
    ANNOTATIONS_FILE,
    NORMALIZED_FILE,
    NORMALIZED_SPEAKERS_FILE,
    REPORT_FILE,
    LOCAL_FILE,
    NEEDS_REVIEW_DIR,
)

#: The folder replaced files go to, inside the run.
REPLACED_PREFIX = "replaced-"

#: The first header line of each kind of legenda.txt (ingest/header.py).
SPEECH_FIRST = "# Transcricao por reconhecimento de fala"
CAPTION_FIRST = "# Legenda de video"
FILE_FIRST = "# Legenda convertida de arquivo"

SPEECH, CAPTION, FILE, UNKNOWN = "speech", "caption", "file", "unknown"


@dataclass(frozen=True)
class Existing:
    """What the legenda.txt already in a run says about where it came from."""

    path: Path
    kind: str  # SPEECH, CAPTION, FILE or UNKNOWN
    url: str = ""
    file_name: str = ""
    model: str = ""
    track: str = ""
    lang: str = ""  # the base language: `pt` of `pt-orig`, or a transcription's `idioma pt`
    fingerprint: str = ""  # D-099: `sha256 <hex>, <n> bytes` of the local file transcribed
    header: tuple[str, ...] = ()
    body: tuple[str, ...] = ()

    def describe(self) -> str:
        """`a local transcription (model medium) of aula1.mp4`, for the messages."""
        if self.kind == SPEECH:
            what = f"a local transcription (model {self.model or 'unknown'})"
        elif self.kind == CAPTION:
            what = f"the platform's caption{f' ({self.track})' if self.track else ''}"
        elif self.kind == FILE:
            what = "a converted subtitle file"
        else:
            what = "a text"
        source = self.url or self.file_name
        return f"{what} of {source}" if source else what


def _field(header: tuple[str, ...], name: str) -> str:
    prefix = f"# {name}:"
    for line in header:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def split(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The `#` header lines and the body lines (stripped, blank ones left out)."""
    header, body = [], []
    for raw in text.splitlines():
        if raw.startswith("#"):
            header.append(raw.rstrip())
        elif raw.strip():
            body.append(raw.strip())
    return tuple(header), tuple(body)


def read_existing(run: Path) -> Existing | None:
    """The run's legenda.txt, described; None when there is none."""
    path = Path(run) / CAPTION_FILE
    if not path.is_file():
        return None
    header, body = split(path.read_text(encoding="utf-8"))
    first = header[0] if header else ""
    if first.startswith(SPEECH_FIRST):
        kind = SPEECH
    elif first.startswith(CAPTION_FIRST):
        kind = CAPTION
    elif first.startswith(FILE_FIRST):
        kind = FILE
    else:
        kind = UNKNOWN
    model = lang = ""
    found = re.match(r"faster-whisper (\S+?),\s*idioma (\S+?),", _field(header, "Modelo"))
    if found:
        model, lang = found.group(1), found.group(2)
    track = ""
    found = re.search(r"\(([^()]+)\)\s*$", _field(header, "Origem da legenda"))
    if found:
        track = found.group(1)
        lang = base_lang(track)
    return Existing(
        path=path, kind=kind, url=_field(header, "URL"), file_name=_field(header, "Arquivo"),
        model=model, track=track, lang=base_lang(lang), fingerprint=_field(header, "Impressao digital"),
        header=header, body=body,
    )


def base_lang(code: str) -> str:
    """`pt` of `pt-orig`, `pt-BR` or `pt`."""
    return code.split("-")[0].lower() if code else ""


def same_video(existing_url: str, url: str, video_id: str = "") -> bool:
    """The same link, or two links to the same video id."""
    if existing_url and existing_url == url:
        return True
    known = video_id_from_url(existing_url)
    return bool(known) and known in (video_id_from_url(url), video_id)


def fetch_mismatch(
    existing: Existing, url: str, video_id: str, *, whisper: bool, caption_only: bool, track: str | None,
    model: str, lang: str | None = None,
) -> str:
    """Why a fetch of `url` would not give the text that is already there; "" when it would.

    The origin is the video, and whatever the command asked for that pins the
    text down: local transcription and its model, or a caption track.
    """
    if existing.kind not in (SPEECH, CAPTION) or not same_video(existing.url, url, video_id):
        return f"it holds {existing.describe()}, not of this link"
    if not track and lang and existing.lang and base_lang(lang) != existing.lang:
        return f"it holds {existing.describe()} in '{existing.lang}', and you asked for '{lang}'"
    if existing.kind == SPEECH:
        if caption_only or track:
            return f"it holds {existing.describe()}, and you asked for the platform's caption"
        if existing.model != model:
            return f"it holds {existing.describe()}, and you asked for the model {model}"
        return ""
    if whisper:
        return f"it holds {existing.describe()}, and you asked for a local transcription"
    if track and existing.track != track:
        return f"it holds {existing.describe()}, and you asked for the track {track}"
    return ""


def fingerprint(path: Path) -> str:
    """D-099: `sha256 <hex>, <n> bytes` of a local file, read in blocks."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return f"sha256 {digest.hexdigest()}, {size} bytes"


def file_mismatch(
    existing: Existing, file_name: str, model: str, lang: str | None = None, fingerprint: str = ""
) -> str:
    """Why transcribing the local file `file_name` would not give the text there; "" when it would.

    D-099: when both the text there and this file have a fingerprint, the
    content decides, not the name. A text written before 0.8.3 has none, and
    the name decides, as it did.
    """
    if existing.kind != SPEECH:
        return f"it holds {existing.describe()}, not of {file_name}"
    if existing.fingerprint and fingerprint:
        if existing.fingerprint != fingerprint:
            return (f"it holds {existing.describe()}, and {file_name} has other content "
                    f"({fingerprint.split(',')[0][:19]}…, not {existing.fingerprint.split(',')[0][:19]}…)")
    elif existing.file_name != file_name:
        return f"it holds {existing.describe()}, not of {file_name}"
    if lang and existing.lang and base_lang(lang) != existing.lang:
        return f"it holds {existing.describe()} in '{existing.lang}', and you asked for '{lang}'"
    if existing.model != model:
        return f"it holds {existing.describe()}, and you asked for the model {model}"
    return ""


def refusal(existing: Existing, why: str) -> str:
    """What a command that stops says: what is there, why it stopped, the two ways on."""
    run = existing.path.parent
    return (
        f"{existing.path} is already there, and was not replaced: {why}.\n"
        f"Nothing was downloaded or written.\n"
        f"  To keep both, write the new one elsewhere: --out <folder>.\n"
        f"  To replace it: --replace-caption. The current text and what was made from it "
        f"move to {run / (REPLACED_PREFIX + '<date and time>')}{Path('/')}, and nothing is deleted."
    )


def archive(run: Path, now: datetime | None = None) -> Path | None:
    """Move the run's caption and what was made from it into `replaced-<date and time>/`.

    Returns that folder, or None when there was nothing to move. Two
    replacements within the same second get `-2`, `-3`, never the same folder.
    """
    run = Path(run)
    present = [name for name in DERIVED if (run / name).exists()]
    if not present:
        return None
    stamp = (now or datetime.now()).strftime("%Y-%m-%dT%H-%M-%S")
    target = run / f"{REPLACED_PREFIX}{stamp}"
    counter = 2
    while target.exists():
        target = run / f"{REPLACED_PREFIX}{stamp}-{counter}"
        counter += 1
    target.mkdir()
    for name in present:
        (run / name).rename(target / name)
    return target


def restore(run: Path, archived: Path | None) -> None:
    """Undo `archive`: put back what it moved, when the replacement did not happen."""
    if archived is None or not archived.is_dir():
        return
    run = Path(run)
    for item in list(archived.iterdir()):
        if not (run / item.name).exists():
            item.rename(run / item.name)
    if not any(archived.iterdir()):
        archived.rmdir()
