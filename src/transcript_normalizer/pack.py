"""Domain packs: the term list the matcher is allowed to touch (D-001, D-002, D-003)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_KEEP = re.compile(r"[^a-z0-9$ ]+")


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


@dataclass(frozen=True)
class Term:
    term: str
    klass: str | None = None
    aliases: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    collocations: tuple[str, ...] = ()


@dataclass(frozen=True)
class UnitRule:
    pattern: str
    correction: str


@dataclass(frozen=True)
class Pack:
    terms: tuple[Term, ...]
    unit_rules: tuple[UnitRule, ...]
    version: str
    candidates: tuple[Candidate, ...] = field(default=())

    def folded_aliases(self, term: str) -> tuple[str, ...]:
        for t in self.terms:
            if t.term == term:
                return tuple(fold(a) for a in t.aliases)
        return ()


def _strings(raw: dict, key: str) -> tuple[str, ...]:
    return tuple(nfc(str(s)) for s in raw.get(key) or ())


def load_pack(path: str | Path) -> Pack:
    """Read a domain pack from YAML. `fixtures/R2Qgz8tFWVI/termos.yaml` is the schema."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    terms: list[Term] = []
    candidates: list[Candidate] = []
    for raw in data.get("termos") or ():
        term = Term(
            term=nfc(str(raw["termo"])),
            klass=nfc(str(raw["classe"])) if raw.get("classe") else None,
            aliases=_strings(raw, "apelidos"),
            variants=_strings(raw, "variantes"),
            collocations=_strings(raw, "colocacoes"),
        )
        terms.append(term)
        # Order matters: it is the order the matcher scans candidates in.
        for display, origin in (
            [(term.term, "term")]
            + [(a, "alias") for a in term.aliases]
            + [(v, "variant") for v in term.variants]
        ):
            candidates.append(Candidate(display, fold(display), term.term, origin))

    unit_rules = tuple(
        UnitRule(pattern=str(r.get("padrao", "")), correction=str(r.get("correcao", "")))
        for r in data.get("regras_de_unidade") or ()
    )

    version = data.get("versao") or data.get("version")
    if version is None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        version = f"sha256:{digest}"

    return Pack(
        terms=tuple(terms),
        unit_rules=unit_rules,
        version=str(version),
        candidates=tuple(candidates),
    )
