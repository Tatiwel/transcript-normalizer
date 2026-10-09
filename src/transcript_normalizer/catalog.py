"""What is in `runs/`: one entry per video (D-022).

`fetch` writes `meta.yaml` beside each caption it downloads. A run from before
that, or one made by normalizing a local file, is described from the provenance
header of its caption instead, which carries the same facts in Portuguese.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from .core.text import read_caption
from .runs import ANNOTATIONS_FILE, CAPTION_FILE, META_FILE, runs_root


def iso_date(value: str) -> str:
    """`20260825` (as platforms give it) -> `2026-08-25`; anything else unchanged."""
    value = str(value or "").strip()
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def write_meta(
    directory: Path,
    title: str,
    channel: str,
    url: str,
    published: str,
    fetched_at: datetime | None = None,
    extra: dict | None = None,
) -> Path:
    """D-022's five fields, then whatever the fetch recorded about itself (D-036)."""
    fetched_at = fetched_at or datetime.now().astimezone()
    data = {
        "title": title,
        "channel": channel,
        "url": url,
        "published": iso_date(published),
        "fetched_at": fetched_at.isoformat(timespec="seconds"),
        **(extra or {}),
    }
    path = Path(directory) / META_FILE
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


@dataclass(frozen=True)
class Run:
    id: str
    date: str  # the video's publication date, ISO
    title: str
    source: str  # "meta" | "header" | "none"


def read_run(directory: Path) -> Run | None:
    """Describe one run directory, or None if it does not look like a run."""
    directory = Path(directory)
    meta = directory / META_FILE
    if meta.exists():
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        date = iso_date(data.get("published") or "") or str(data.get("fetched_at") or "")[:10]
        return Run(directory.name, date, str(data.get("title") or ""), "meta")

    caption = directory / CAPTION_FILE
    if caption.exists():
        transcript = read_caption(caption)
        date = iso_date(transcript.header_field("Publicado")) or iso_date(
            transcript.header_field("Baixado em")
        )
        return Run(directory.name, date, transcript.header_field("Titulo"), "header")

    if (directory / ANNOTATIONS_FILE).exists():
        return Run(directory.name, "", "", "none")
    return None


def list_runs(root: Path | None = None) -> list[Run]:
    """Every run under `root` (default `runs/`), oldest video first."""
    root = Path(root) if root is not None else runs_root()
    if not root.is_dir():
        return []
    found = [read_run(d) for d in sorted(p for p in root.iterdir() if p.is_dir())]
    return sorted((r for r in found if r is not None), key=lambda r: (r.date or "9999", r.id))
