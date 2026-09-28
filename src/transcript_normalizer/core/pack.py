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
SOURCE_INFLECTION = "inflection"  # D-031: a plural generated from a term or alias

#: D-021: the closed list of term classes. A label for consumers; matching
#: never reads it.
CLASSES = (
    "companhia",  # has a ticker and a balance sheet
    "indicador",  # a number per company or asset
    "conceito",  # an idea, method or strategy
    "unidade",
    "pessoa",
    "organizacao",  # not a listed company: regulator, fund manager, channel, series
    "ferramenta",
    "sigla",  # a sector or regulatory abbreviation
)


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
    learned_aliases: tuple[str, ...] = ()  # the subset of `aliases` that came from D-020


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
class LearnedAlias:
    """D-020: the user said this is the term, spoken the way the speaker said it."""

    alias: str
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
    aliases: dict[str, tuple[LearnedAlias, ...]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.confirmed and not self.rejected and not self.aliases

    def confirm(self, term: str, variant: str, decided: str | None = None) -> "Learned":
        """A variant: substituted from now on. Replaces an alias entry for the same text."""
        decided = decided or date.today().isoformat()
        existing = self.confirmed.get(term, ())
        if any(fold(c.variant) == fold(variant) for c in existing):
            return self
        merged = dict(self.confirmed)
        merged[term] = existing + (Confirmation(nfc(variant), decided),)
        return replace(self, confirmed=merged, aliases=_without(self.aliases, term, variant))

    def alias(self, term: str, text: str, decided: str | None = None) -> "Learned":
        """An alias (D-020): recognized from now on, never substituted.

        Replaces a confirmed variant for the same text, since a text is one or
        the other for a given term.
        """
        decided = decided or date.today().isoformat()
        existing = self.aliases.get(term, ())
        if any(fold(a.alias) == fold(text) for a in existing):
            return self
        merged = dict(self.aliases)
        merged[term] = existing + (LearnedAlias(nfc(text), decided),)
        confirmed = {
            t: tuple(c for c in cs if not (t == term and fold(c.variant) == fold(text)))
            for t, cs in self.confirmed.items()
        }
        confirmed = {t: cs for t, cs in confirmed.items() if cs}
        return replace(self, aliases=merged, confirmed=confirmed)

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
            "aliases": {
                term: [{"alias": a.alias, "date": a.decided} for a in entries]
                for term, entries in self.aliases.items()
            },
            "rejected": [
                {"text": r.text, "term": r.term, "date": r.decided} for r in self.rejected
            ],
        }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def _without(
    aliases: dict[str, tuple[LearnedAlias, ...]], term: str, text: str
) -> dict[str, tuple[LearnedAlias, ...]]:
    kept = {
        t: tuple(a for a in entries if not (t == term and fold(a.alias) == fold(text)))
        for t, entries in aliases.items()
    }
    return {t: entries for t, entries in kept.items() if entries}


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

    aliases: dict[str, tuple[LearnedAlias, ...]] = {}
    for term, entries in (data.get("aliases") or {}).items():
        items = []
        for entry in entries or ():
            if isinstance(entry, dict):
                items.append(LearnedAlias(nfc(str(entry["alias"])), str(entry.get("date", ""))))
            else:
                items.append(LearnedAlias(nfc(str(entry)), ""))
        aliases[nfc(str(term))] = tuple(items)

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
        aliases=aliases,
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

    def term_named(self, name: str) -> Term | None:
        """The pack term called `name`, by its own name or one of its aliases."""
        target = fold(name)
        for t in self.terms:
            if fold(t.term) == target or target in {fold(a) for a in t.aliases}:
                return t
        return None

    def is_rejected(self, folded_text: str, term: str) -> bool:
        """D-013, D-027: a pair the user turned down is never proposed again.

        Containment, by whole words: rejecting `divide -> dividendo` also rules
        out `divide a -> dividendo`, but not `dividida -> dividendo`, and it
        says nothing about another term.
        """
        span = f" {_words(folded_text)} "
        return any(t == term and f" {text} " in span for text, t in self.rejected)


def plural_forms(folded: str) -> tuple[str, ...]:
    """D-031: the Portuguese plurals of a folded single word, accents already gone.

    -s, -es, -ão -> -ões, -al -> -ais, -el -> -eis. A multi-word string has no
    plural here: D-031 speaks of a word.
    """
    if not folded or " " in folded:
        return ()
    forms = [folded + "s", folded + "es"]
    for ending, plural in (("ao", "oes"), ("al", "ais"), ("el", "eis")):
        if folded.endswith(ending):
            forms.append(folded[: -len(ending)] + plural)
    return tuple(dict.fromkeys(f for f in forms if f != folded))


def _words(folded: str) -> str:
    """Folded text with its words separated by exactly one space."""
    return " ".join(folded.split())


def _strings(raw: dict, key: str) -> tuple[str, ...]:
    return tuple(nfc(str(s)) for s in raw.get(key) or ())


def load_pack(
    path: str | Path,
    learned: Learned | None = None,
    learned_from: str | Path | None = None,
) -> Pack:
    """Read a domain pack from YAML, merging the learned layer of D-013.

    `fixtures/R2Qgz8tFWVI/pack.yaml` is the schema. The learned layer is read
    from `packs/<pack-name>.learned.yaml` (D-017); `learned_from` names a
    different file and `learned` supplies the layer directly. Its confirmed
    variants become corrections and its aliases become alias annotations (D-020).
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
        pack_aliases = _strings(raw, "aliases")
        known = {fold(v) for v in pack_variants} | {fold(a) for a in pack_aliases}
        learned_variants = tuple(
            c.variant
            for c in learned.confirmed.get(name, ())
            if fold(c.variant) not in known
        )
        learned_aliases = tuple(
            a.alias
            for a in learned.aliases.get(name, ())
            if fold(a.alias) not in known
        )
        klass = nfc(str(raw["class"])) if raw.get("class") else None
        if klass is not None and klass not in CLASSES:
            raise ValueError(
                f"{path}: term {name!r} has class {klass!r}, which is not one of "
                f"D-021's {', '.join(CLASSES)}"
            )
        term = Term(
            term=name,
            klass=klass,
            aliases=pack_aliases + learned_aliases,
            variants=pack_variants + learned_variants,
            collocations=_strings(raw, "collocations"),
            learned_variants=learned_variants,
            learned_aliases=learned_aliases,
        )
        terms.append(term)
        # Order matters: it is the order the matcher scans candidates in.
        for display, origin, source in (
            [(term.term, "term", SOURCE_PACK)]
            + [(a, "alias", SOURCE_PACK) for a in pack_aliases]
            + [(v, "variant", SOURCE_PACK) for v in pack_variants]
            + [(v, "variant", SOURCE_LEARNED) for v in learned_variants]
            + [(a, "alias", SOURCE_LEARNED) for a in learned_aliases]
        ):
            candidates.append(Candidate(display, fold(display), term.term, origin, source))

    # D-031: the plural of a term or alias is that term spelled out. It becomes
    # an alias candidate, so it is exact-only (D-025) and never a correction.
    # Explicit entries win: a plural that some term already lists is skipped.
    taken = {c.folded for c in candidates}
    for c in list(candidates):
        if c.origin not in ("term", "alias") or c.source == SOURCE_INFLECTION:
            continue
        for plural in plural_forms(c.folded):
            if plural not in taken:
                taken.add(plural)
                candidates.append(Candidate(plural, plural, c.term, "alias", SOURCE_INFLECTION))

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
        rejected=frozenset((_words(fold(r.text)), r.term) for r in learned.rejected),
        learned=learned,
    )
