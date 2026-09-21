"""Domain packs (D-001, D-002, D-003) and the learned layer beside them (D-013)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import yaml

from ..runs import learned_file

_KEEP = re.compile(r"[^a-z0-9$ ]+")

#: Schema version written into a new learned file.
LEARNED_VERSION = 1

SOURCE_PACK = "pack"
SOURCE_LEARNED = "learned"


def nfc(s: str) -> str:
    """Display form: NFC, nothing else. The original is never lost."""
    return unicodedata.normalize("NFC", s)


def fold(s: str) -> str:
    """Matching form: lowercase, accents stripped, punctuation flattened to spaces."""
    s = unicodedata.normalize("NFD", nfc(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return _KEEP.sub(" ", s).strip()


@dataclass(frozen=True)
class Candidate:
    """One string the matcher may compare a span of text against."""

    display: str
    folded: str
    term: str
    origin: str  # "term" | "alias" | "variant"
    source: str = SOURCE_PACK  # "pack" | "learned"


@dataclass(frozen=True)
class Term:
    term: str
    klass: str | None = None
    aliases: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    collocations: tuple[str, ...] = ()
    learned_variants: tuple[str, ...] = ()  # the subset of `variants` that came from D-013


@dataclass(frozen=True)
class UnitRule:
    pattern: str
    correction: str


# --------------------------------------------------------------------------- learned layer


@dataclass(frozen=True)
class Confirmation:
    variant: str
    decided: str  # ISO date


@dataclass(frozen=True)
class Rejection:
    text: str
    term: str
    decided: str  # ISO date


@dataclass(frozen=True)
class Learned:
    """D-013: the personal, unreviewed layer. Never merged back into the pack file."""

    confirmed: dict[str, tuple[Confirmation, ...]] = field(default_factory=dict)
    rejected: tuple[Rejection, ...] = ()
    version: int = LEARNED_VERSION

    def is_empty(self) -> bool:
        return not self.confirmed and not self.rejected

    def confirm(self, term: str, variant: str, decided: str | None = None) -> "Learned":
        decided = decided or date.today().isoformat()
        existing = self.confirmed.get(term, ())
        if any(fold(c.variant) == fold(variant) for c in existing):
            return self
        merged = dict(self.confirmed)
        merged[term] = existing + (Confirmation(nfc(variant), decided),)
        return replace(self, confirmed=merged)

    def reject(self, text: str, term: str, decided: str | None = None) -> "Learned":
        decided = decided or date.today().isoformat()
        if any(fold(r.text) == fold(text) and r.term == term for r in self.rejected):
            return self
        return replace(self, rejected=self.rejected + (Rejection(nfc(text), term, decided),))

    def to_yaml(self) -> str:
        data = {
            "version": self.version,
            "confirmed": {
                term: [{"variant": c.variant, "date": c.decided} for c in confirmations]
                for term, confirmations in self.confirmed.items()
            },
            "rejected": [
                {"text": r.text, "term": r.term, "date": r.decided} for r in self.rejected
            ],
        }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def load_learned(path: str | Path) -> Learned:
    path = Path(path)
    if not path.exists():
        return Learned()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    confirmed: dict[str, tuple[Confirmation, ...]] = {}
    for term, entries in (data.get("confirmed") or {}).items():
        items = []
        for entry in entries or ():
            if isinstance(entry, dict):
                items.append(
                    Confirmation(nfc(str(entry["variant"])), str(entry.get("date", "")))
                )
            else:  # a bare string is accepted; it just has no date
                items.append(Confirmation(nfc(str(entry)), ""))
        confirmed[nfc(str(term))] = tuple(items)

    rejected = tuple(
        Rejection(
            nfc(str(entry["text"])), nfc(str(entry["term"])), str(entry.get("date", ""))
        )
        for entry in (data.get("rejected") or ())
    )
    return Learned(
        confirmed=confirmed,
        rejected=rejected,
        version=int(data.get("version", LEARNED_VERSION)),
    )


def save_learned(learned: Learned, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(learned.to_yaml(), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- pack


@dataclass(frozen=True)
class Pack:
    terms: tuple[Term, ...]
    unit_rules: tuple[UnitRule, ...]
    version: str
    candidates: tuple[Candidate, ...] = ()
    rejected: frozenset[tuple[str, str]] = frozenset()  # (folded text, term)
    learned: Learned = field(default_factory=Learned)

    def is_rejected(self, folded_text: str, term: str) -> bool:
        """D-013: a pair the user turned down is never proposed again."""
        return (folded_text, term) in self.rejected


def _strings(raw: dict, key: str) -> tuple[str, ...]:
    return tuple(nfc(str(s)) for s in raw.get(key) or ())


def load_pack(
    path: str | Path,
    learned: Learned | None = None,
    learned_from: str | Path | None = None,
) -> Pack:
    """Read a domain pack from YAML, merging the learned layer of D-013.

    `fixtures/R2Qgz8tFWVI/pack.yaml` is the schema. The learned layer is read
    from `runs/learned/<pack-name>.learned.yaml` (D-015); `learned_from` names a
    different file and `learned` supplies the layer directly.
    """
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if learned is None:
        learned = load_learned(learned_file(path, learned_from))

    terms: list[Term] = []
    candidates: list[Candidate] = []
    for raw in data.get("terms") or ():
        name = nfc(str(raw["term"]))
        pack_variants = _strings(raw, "variants")
        known = {fold(v) for v in pack_variants}
        learned_variants = tuple(
            c.variant
            for c in learned.confirmed.get(name, ())
            if fold(c.variant) not in known
        )
        term = Term(
            term=name,
            klass=nfc(str(raw["class"])) if raw.get("class") else None,
            aliases=_strings(raw, "aliases"),
            variants=pack_variants + learned_variants,
            collocations=_strings(raw, "collocations"),
            learned_variants=learned_variants,
        )
        terms.append(term)
        # Order matters: it is the order the matcher scans candidates in.
        for display, origin, source in (
            [(term.term, "term", SOURCE_PACK)]
            + [(a, "alias", SOURCE_PACK) for a in term.aliases]
            + [(v, "variant", SOURCE_PACK) for v in pack_variants]
            + [(v, "variant", SOURCE_LEARNED) for v in learned_variants]
        ):
            candidates.append(Candidate(display, fold(display), term.term, origin, source))

    unit_rules = tuple(
        UnitRule(pattern=str(r.get("pattern", "")), correction=str(r.get("replacement", "")))
        for r in data.get("unit_rules") or ()
    )

    version = data.get("version")
    if version is None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        version = f"sha256:{digest}"

    return Pack(
        terms=tuple(terms),
        unit_rules=unit_rules,
        version=str(version),
        candidates=tuple(candidates),
        rejected=frozenset((fold(r.text), r.term) for r in learned.rejected),
        learned=learned,
    )
