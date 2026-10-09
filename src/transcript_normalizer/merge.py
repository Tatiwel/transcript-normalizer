"""Three-way pack merge (D-069): `pack merge <name>`.

A copy of a bundled or repository pack (`pack copy`, D-066) records where it
came from, `based_on: <name>@<version>`, and how many edits were saved since,
`local_edits`; `pack copy` keeps the upstream file it copied in
`packs/.bases/<name>@<version>.yaml`, the base a three-way merge needs. When
upstream has a newer version, `pack merge` combines the two by canonical term:
what changed on one side only is taken, what changed on both is combined, and
what cannot be combined is asked, one conflict at a time. A copy with no base
(made before 0.6.2, or whose snapshot is gone) merges two-way.

Nothing is merged without being asked for. Before the pack is written, the
copy is backed up beside it; the result is loaded as normalize loads it. The
learned layer is never changed; the summary says where it now repeats or
contradicts the pack.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import yaml
from rapidfuzz import fuzz

from . import packedit, packfiles, registry
from .core.pack import load_learned
from .runs import BUNDLED_PACKS, installed_packs, learned_file, packs_root, runs_root

#: Where `pack copy` keeps the upstream file a copy is based on.
BASES_DIR = ".bases"
#: What "decide later" leaves behind.
PENDING_SUFFIX = ".merge-pending.yaml"
#: A new term of mine this close to a new upstream term may be the same one.
DUPLICATE_SCORE = 90
#: How many caption lines from the user's runs a conflict shows.
CONTEXT_LINES = 3
#: How long `pack merge` waits for the repository's index.
MERGE_WAIT_SECONDS = 10

LISTS = ("aliases", "variants", "collocations")
PACK_LISTS = ("classes", "phonetic_classes")
#: Keys of a copy that are its own, never taken from upstream.
OWN_KEYS = ("name", "field", "based_on", "local_edits")

MINE, THEIRS, BOTH, LATER = "mine", "theirs", "both", "later"
ANSWERS = {MINE: "Keep mine", THEIRS: "Take theirs", BOTH: "Keep both", LATER: "Decide later"}
#: What to type for each, in plain text: the same letter in every conflict.
KEYS = {MINE: "m", THEIRS: "t", BOTH: "k", LATER: "l"}


# ------------------------------------------------------------------ provenance


def based_on(data: dict) -> tuple[str, str] | None:
    """`financas-ptbr@0.3.7` -> ("financas-ptbr", "0.3.7")."""
    value = str(data.get("based_on") or "")
    name, at, version = value.rpartition("@")
    return (name, version) if at and name and version else None


def base_path(name: str, version: str) -> Path:
    return packs_root() / BASES_DIR / f"{name}@{version}.yaml"


def keep_base(name: str, version: str, text: str) -> Path:
    path = base_path(name, version)
    registry.write_atomic(path, text.encode("utf-8"))
    return path


def with_provenance(text: str, name: str, version: str, edits: int = 0) -> str:
    """The pack's text with `based_on` and `local_edits` after its `version:`
    line (or at the top of its data), the rest of the file as it was."""
    lines = [line for line in text.splitlines(keepends=True)
             if not line.startswith(("based_on:", "local_edits:"))]
    added = [f"based_on: {name}@{version}\n", f"local_edits: {edits}\n"]
    at = next((i + 1 for i, line in enumerate(lines) if line.startswith("version:")), None)
    if at is None:
        at = next((i for i, line in enumerate(lines) if line.strip() and not line.startswith("#")), len(lines))
    return "".join(lines[:at] + added + lines[at:])


# ------------------------------------------------------------------ upstream


@dataclass
class Upstream:
    version: str
    origin: str  # bundled | repository
    read: Callable[[], str]


def upstream_of(name: str, index: dict | None) -> Upstream | None:
    """The newest of the bundled pack and the repository's, by version."""
    found = []
    bundled = BUNDLED_PACKS / f"{name}.yaml"
    if bundled.exists():
        data = yaml.safe_load(bundled.read_text(encoding="utf-8")) or {}
        found.append(Upstream(str(data.get("version") or ""), packfiles.BUNDLED,
                              lambda: bundled.read_text(encoding="utf-8")))
    entry = (index or {}).get(name)
    if entry is not None:
        url = registry.index_url()
        found.append(Upstream(entry.version, packfiles.REPOSITORY,
                              lambda: registry.download(entry, url).decode("utf-8")))
    if not found:
        return None
    best = found[0]
    for other in found[1:]:
        if packfiles.newer(other.version, best.version):
            best = other
    return best


@dataclass
class Offer:
    name: str
    path: Path
    upstream: Upstream
    based: str | None  # the version the copy is based on; None: no record
    version: str
    edits: int

    def line(self) -> str:
        if self.based is None:
            return (f"{self.name} {self.upstream.version} is available; your copy ({self.version}) "
                    "has no record of its base, so it merges two-way.")
        edits = f"{self.edits} local edit{'' if self.edits == 1 else 's'}"
        return f"{self.name} {self.upstream.version} is available; your copy is based on {self.based} with {edits}."


def is_copy(name: str, data: dict) -> bool:
    return based_on(data) is not None or (BUNDLED_PACKS / f"{name}.yaml").exists()


def copies() -> dict[str, tuple[Path, dict]]:
    """The user's packs that are copies of an upstream pack."""
    out = {}
    for name, path in installed_packs().items():
        if path.parent == BUNDLED_PACKS or packfiles.source_of(name, path) != packfiles.MINE:
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if is_copy(name, data):
            out[name] = (path, data)
    return out


def offers(wait: float = packfiles.INDEX_WAIT_SECONDS, index: dict | None = None) -> list[Offer]:
    """D-069: each copy whose upstream is newer than what it is based on. The
    index is read only when there is a copy, and waited for `wait` seconds."""
    found = copies()
    if not found:
        return []
    if index is None:
        index = packfiles.index_within(wait)
    out = []
    for name, (path, data) in found.items():
        offer = offer_for(name, path, data, index)
        if offer is not None:
            out.append(offer)
    return out


class OfferCheck:
    """D-069, amended: the menu's look for merges, in a background thread, so
    the menu never waits for the packs repository. `ready()` is None until it
    is done; nothing here asks or merges."""

    def __init__(self) -> None:
        self._offers: list[Offer] = []
        self._done = threading.Event()
        self.announced = False

    def start(self, background: bool = True) -> "OfferCheck":
        """The copies and where the cache is are read here, in the caller's
        directory; only the index is waited for in the thread."""
        found = copies()
        if not found:
            self._done.set()
            return self
        args = (found, registry.index_url(), packfiles.index_cache())
        if background:
            threading.Thread(target=self.run, args=args, daemon=True).start()
        else:
            self.run(*args)
        return self

    def run(self, found: dict, url: str, cache: Path) -> None:
        try:
            index = packfiles.index_cached_within(packfiles.INDEX_WAIT_SECONDS, url, cache)
            self._offers = [
                offer for name, (path, data) in found.items()
                if (offer := offer_for(name, path, data, index)) is not None
            ]
        except Exception:  # a failed look is no offer, never a traceback in the menu
            self._offers = []
        finally:
            self._done.set()

    def ready(self) -> list[Offer] | None:
        return list(self._offers) if self._done.is_set() else None

    def wait(self, seconds: float) -> bool:
        return self._done.wait(seconds)

    def merged(self, name: str) -> None:
        self._offers = [o for o in self._offers if o.name != name]


def offer_for(name: str, path: Path, data: dict, index: dict | None) -> Offer | None:
    upstream = upstream_of(name, index)
    if upstream is None:
        return None
    base = based_on(data)
    have = base[1] if base else str(data.get("version") or "")
    if not packfiles.newer(upstream.version, have):
        return None
    return Offer(name, path, upstream, base[1] if base else None, str(data.get("version") or "?"),
                 int(data.get("local_edits") or 0))


# ------------------------------------------------------------------ the merge


@dataclass
class Conflict:
    kind: str
    term: str  # the term it is about, as the summary and the pending file name it
    title: str
    lines: list[str]
    forms: list[str]
    apply: dict[str, Callable[[], None]]  # answer -> what it does to the result
    sides: dict = field(default_factory=dict)  # for the pending file


@dataclass
class Summary:
    added: list[str] = field(default_factory=list)  # new upstream terms
    updated: list[str] = field(default_factory=list)  # upstream's version of a term I left alone
    kept: list[str] = field(default_factory=list)  # mine: only mine, or changed only by me
    combined: list[str] = field(default_factory=list)  # changed on both sides, combined
    removed: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)
    learned: list[str] = field(default_factory=list)


class Merge:
    """Base (or None: two-way), upstream and mine, as pack data."""

    def __init__(self, name: str, base: dict | None, up: dict, mine: dict, learned):
        self.name, self.base, self.up, self.mine, self.learned = name, base, up, mine, learned
        self.language = packedit.language_of(up)
        self.n = self.language.normalize
        self.summary = Summary()
        self.conflicts: list[Conflict] = []
        self.result: dict[str, dict] = {}
        self.renamed: dict[str, str] = {}  # base key -> upstream key

    # -------------------------------------------------------------- helpers

    def terms(self, data: dict | None) -> dict[str, dict]:
        return {self.n(str(t["term"])): t for t in (data or {}).get("terms") or []}

    def folds(self, items) -> set[str]:
        return {self.n(str(i)) for i in items or ()}

    def same(self, a: dict | None, b: dict | None) -> bool:
        """Two versions of a term are the same: same scalars, same forms (folded)."""
        if a is None or b is None:
            return a is b
        keys = set(a) | set(b)
        for k in keys:
            if k in LISTS:
                if self.folds(a.get(k)) != self.folds(b.get(k)):
                    return False
            elif k == "term":
                if str(a.get(k)) != str(b.get(k)):
                    return False
            elif a.get(k) != b.get(k):
                return False
        return True

    def merge_list(self, b, u, m, term: str = "", what: str = "") -> list:
        """Both sides' additions, minus what either side removed from the base."""
        nb, nu, nm = self.folds(b), self.folds(u), self.folds(m)
        removed = {k for k in nb if k not in nu or k not in nm}
        out, seen = [], set()
        by_fold = {self.n(str(x)): x for x in [*(u or ()), *(m or ())]}  # mine's spelling wins
        for x in [*(b or ()), *(u or ()), *(m or ())]:
            k = self.n(str(x))
            if k in seen or k in removed:
                continue
            seen.add(k)
            out.append(by_fold.get(k, x))
        if term:
            for x in b or ():
                k = self.n(str(x))
                if k not in nu and k in nm:
                    self.summary.notices.append(f"{term}: upstream removed the {what} {x!r}")
        return out

    def describe(self, label: str, term: dict | None) -> str:
        return f"  {label:8s}  {packedit.term_line(term) if term else '(not there)'}"

    def ask(self, kind, term, title, lines, forms, apply, **sides):
        self.conflicts.append(Conflict(kind, term, title, lines, forms, apply, sides))

    # -------------------------------------------------------------- terms

    def two_way_term(self, key: str, u: dict, m: dict) -> dict:
        """No base: the union of both; a class or a kind that differs is asked."""
        out = dict(m)
        for k, v in u.items():
            if k in LISTS:
                out[k] = self.merge_list([], u.get(k), m.get(k))
            elif k not in out:
                out[k] = v
        out = {k: v for k, v in out.items() if v not in ([], None)}
        if u.get("class") and m.get("class") and u["class"] != m["class"]:
            self.class_conflict(key, None, u, m)
        aliases_u, variants_u = self.folds(u.get("aliases")), self.folds(u.get("variants"))
        aliases_m, variants_m = self.folds(m.get("aliases")), self.folds(m.get("variants"))
        for form in sorted((aliases_u & variants_m) | (variants_u & aliases_m)):
            self.kind_conflict(key, form, u, m)
        return out

    def three_way_term(self, key: str, b: dict, u: dict, m: dict) -> dict:
        out = {}
        for k in dict.fromkeys([*u, *m, *b]):
            if k in LISTS:
                merged = self.merge_list(b.get(k), u.get(k), m.get(k), term=str(m["term"]), what=k[:-1] if k != "aliases" else "alias")
                if merged:
                    out[k] = merged
            elif k == "term":
                out[k] = m[k] if str(m[k]) != str(b[k]) and str(u[k]) == str(b[k]) else u[k]
            elif b.get(k) == m.get(k):
                if u.get(k) is not None:
                    out[k] = u[k]
            elif b.get(k) == u.get(k) or u.get(k) == m.get(k):
                if m.get(k) is not None:
                    out[k] = m[k]
            else:
                if m.get(k) is not None:
                    out[k] = m[k]  # mine, until answered
                if k == "class":
                    self.class_conflict(key, b, u, m)
        return out

    def class_conflict(self, key, b, u, m):
        def take(klass):
            return lambda: self.result[key].__setitem__("class", klass)

        lines = ([self.describe("base", b)] if b else []) + [self.describe("mine", m), self.describe("theirs", u)]
        title = f"{m['term']}: the class differs on both sides" if b else f"{m['term']}: the class differs"
        self.ask("class", str(m["term"]), title, lines, [str(m["term"])],
                 {MINE: take(m["class"]), THEIRS: take(u["class"]), LATER: take(m["class"])},
                 mine=m.get("class"), theirs=u.get("class"))

    def kind_conflict(self, key, form, u, m):
        mine_kind = "alias" if form in self.folds(m.get("aliases")) else "variant"
        theirs_kind = "variant" if mine_kind == "alias" else "alias"
        original = next(str(x) for x in [*(m.get("aliases") or []), *(m.get("variants") or [])] if self.n(str(x)) == form)

        def make(kind):
            def apply():
                term = self.result[key]
                for k in ("aliases", "variants"):
                    term[k] = [x for x in term.get(k) or [] if self.n(str(x)) != form]
                term.setdefault("aliases" if kind == "alias" else "variants", []).append(original)
                for k in ("aliases", "variants"):
                    if not term.get(k):
                        term.pop(k, None)
            return apply

        self.ask("kind", str(m["term"]), f"{m['term']}: {original!r} is an {mine_kind} in yours, "
                 f"a{'n' if theirs_kind == 'alias' else ''} {theirs_kind} in theirs",
                 [self.describe("mine", m), self.describe("theirs", u)], [original],
                 {MINE: make(mine_kind), THEIRS: make(theirs_kind), LATER: make(mine_kind)},
                 form=original, mine=mine_kind, theirs=theirs_kind)

    def find_renames(self, B, U):
        """A base term gone upstream, and a new upstream term holding its name
        or its forms: a rename."""
        new = {k: t for k, t in U.items() if k not in B}
        for k, b in B.items():
            if k in U:
                continue
            forms = self.folds([b["term"], *(b.get("aliases") or []), *(b.get("variants") or [])])
            best, score = None, 0
            for nk, t in new.items():
                theirs = self.folds([t["term"], *(t.get("aliases") or []), *(t.get("variants") or [])])
                overlap = len(forms & theirs) + (2 if k in theirs else 0)
                if overlap > score:
                    best, score = nk, overlap
            if best is not None:
                self.renamed[k] = best
                del new[best]

    def run(self) -> "Merge":
        B = self.terms(self.base) if self.base is not None else {}
        U, M = self.terms(self.up), self.terms(self.mine)
        three = self.base is not None
        if three:
            self.find_renames(B, U)
        into = {u: b for b, u in self.renamed.items()}
        s = self.summary

        for key, u in U.items():
            m, b = M.get(key), B.get(key)
            if key in into:  # upstream's new name for a base term
                old = into[key]
                mo, bo = M.get(old), B[old]
                if mo is None:
                    s.notices.append(f"{bo['term']}: renamed upstream to {u['term']}, which you had removed; left out")
                    continue
                if self.same(mo, bo):
                    self.result[key] = dict(u)
                    s.updated.append(str(u["term"]))
                    s.notices.append(f"{bo['term']}: renamed upstream to {u['term']}")
                else:
                    self.result[old] = dict(mo)  # mine, until answered
                    self.rename_conflict(old, key, bo, u, mo)
                continue
            if m is None:
                if three and b is not None:
                    if self.same(u, b):
                        s.notices.append(f"{u['term']}: you removed it; left out")
                    else:
                        s.notices.append(f"{u['term']}: changed upstream, but you removed it; left out")
                    continue
                self.result[key] = dict(u)
                s.added.append(str(u["term"]))
                continue
            if not three or b is None:
                self.result[key] = self.two_way_term(key, u, m)
                (s.kept if self.same(self.result[key], m) else s.combined).append(str(m["term"]))
            elif self.same(m, b):
                self.result[key] = dict(u)
                self.merge_list(b.get("aliases"), u.get("aliases"), m.get("aliases"), str(m["term"]), "alias")
                self.merge_list(b.get("variants"), u.get("variants"), m.get("variants"), str(m["term"]), "variant")
                if not self.same(u, b):
                    s.updated.append(str(u["term"]))
            elif self.same(u, b):
                self.result[key] = dict(m)
                s.kept.append(str(m["term"]))
            else:
                self.result[key] = self.three_way_term(key, b, u, m)
                s.combined.append(str(m["term"]))

        for key, m in M.items():
            if key in self.result or key in U:
                continue
            if key in self.renamed:
                continue  # handled with its new name
            b = B.get(key)
            if three and b is not None:  # gone upstream
                if self.same(m, b):
                    s.removed.append(str(m["term"]))
                    s.notices.append(f"{m['term']}: removed upstream")
                else:
                    self.result[key] = dict(m)
                    s.kept.append(str(m["term"]))
                    s.notices.append(f"{m['term']}: removed upstream; kept, since you changed it")
                continue
            self.result[key] = dict(m)
            s.kept.append(str(m["term"]))

        if three:
            self.duplicates(B, U, M)
        return self

    def rename_conflict(self, old, new, b, u, m):
        def theirs():
            term = dict(u)
            for k in ("aliases", "variants"):
                merged = self.merge_list(b.get(k), u.get(k), m.get(k))
                merged = [x for x in merged if self.n(str(x)) != self.n(str(u["term"]))]
                if merged:
                    term[k] = merged
            self.result.pop(old, None)
            self.result[new] = term

        self.ask("renamed", str(m["term"]), f"{b['term']}: renamed upstream to {u['term']}, and you had added to it",
                 [self.describe("base", b), self.describe("mine", m), self.describe("theirs", u)],
                 [str(b["term"]), str(u["term"])],
                 {MINE: lambda: None, THEIRS: theirs, LATER: lambda: None},
                 renamed_to=str(u["term"]))

    def duplicates(self, B, U, M):
        """D-069: a new term of mine this close to a new upstream term."""
        mine_new = [k for k in M if k not in B and k not in U]
        theirs_new = [k for k in U if k not in B and k not in M and k in self.result]
        for mk in mine_new:
            for uk in theirs_new:
                if fuzz.ratio(mk, uk) < DUPLICATE_SCORE:
                    continue
                m, u = M[mk], U[uk]
                mf = self.folds([m["term"], *(m.get("aliases") or []), *(m.get("variants") or [])])
                uf = self.folds([u["term"], *(u.get("aliases") or []), *(u.get("variants") or [])])
                apply = {
                    MINE: lambda uk=uk: self.result.pop(uk, None),
                    THEIRS: lambda mk=mk: self.result.pop(mk, None),
                    LATER: lambda uk=uk: self.result.pop(uk, None),
                }
                if not mf & uf:
                    apply[BOTH] = lambda: None
                self.ask("duplicate", str(m["term"]),
                         f"your new term {m['term']} looks like upstream's new {u['term']}",
                         [self.describe("mine", m), self.describe("theirs", u)],
                         [str(m["term"]), str(u["term"])], apply, theirs_term=str(u["term"]))

    # -------------------------------------------------------------- after the terms

    def upstream_has(self, key: str, form_fold: str) -> bool:
        u = self.terms(self.up).get(key)
        return u is not None and form_fold in self.folds(
            [u["term"], *(u.get("aliases") or []), *(u.get("variants") or [])])

    def collisions(self):
        """One form, one term: a form of mine that another term has."""
        where: dict[str, list[tuple[str, str]]] = {}
        for key, t in self.result.items():
            for kind, forms in (("term", [t["term"]]), ("alias", t.get("aliases") or []),
                                ("variant", t.get("variants") or [])):
                for f in forms:
                    where.setdefault(self.n(str(f)), []).append((key, kind))
        for fold, places in where.items():
            terms_ = {k for k, _ in places}
            if len(terms_) < 2:
                continue
            mine = [(k, kind) for k, kind in places if not self.upstream_has(k, fold)]
            theirs = [(k, kind) for k, kind in places if self.upstream_has(k, fold)]
            if not mine or not theirs:
                continue
            (mk, mkind), (tk, tkind) = mine[0], theirs[0]
            if mk == tk:
                continue
            form = next(str(f) for f in [self.result[mk]["term"], *(self.result[mk].get("aliases") or []),
                                         *(self.result[mk].get("variants") or [])] if self.n(str(f)) == fold)
            mt, tt = self.result[mk], self.result[tk]
            if mkind == "variant" and tkind == "variant":
                title = f"{form!r} is a variant of {mt['term']} in yours and of {tt['term']} in theirs"
            elif mkind == "variant":
                what = "name" if tkind == "term" else "alias"
                title = f"your variant {form!r} of {mt['term']} is upstream's {what} of {tt['term']}"
            else:
                title = f"{form!r} is a form of {mt['term']} in yours and of {tt['term']} in theirs"

            def drop(key, fold=fold):
                def apply():
                    term = self.result[key]
                    for k in ("aliases", "variants"):
                        if term.get(k):
                            term[k] = [x for x in term[k] if self.n(str(x)) != fold]
                            if not term[k]:
                                term.pop(k)
                return apply

            apply = {THEIRS: drop(mk), LATER: lambda: None}
            if tkind != "term":
                apply = {MINE: drop(tk), **apply}
            self.ask("form", str(mt["term"]), title,
                     [self.describe("mine", mt), self.describe("theirs", tt)], [form], apply,
                     form=form, mine_term=str(mt["term"]), theirs_term=str(tt["term"]))

    def learned_conflicts(self):
        """A form I confirmed that upstream removed; one I rejected that it added."""
        B = self.terms(self.base) if self.base is not None else {}
        U, M = self.terms(self.up), self.terms(self.mine)
        for term, confirmations in self.learned.confirmed.items():
            key = self.n(term)
            b, u = B.get(key), U.get(key)
            if b is None or u is None or key not in self.result:
                continue
            for c in confirmations:
                f = self.n(c.variant)
                if f in self.folds(b.get("variants")) and f not in self.folds(u.get("variants")):
                    def keep(key=key, form=c.variant):
                        return lambda: self.result[key].setdefault("variants", []).append(form)
                    self.ask("learned-removed", term,
                             f"{term}: upstream removed the variant {c.variant!r}, which you confirmed in a review",
                             [self.describe("mine", M.get(key)), self.describe("theirs", u)], [c.variant],
                             {MINE: keep(), THEIRS: lambda: None, LATER: keep()}, form=c.variant)
        for r in self.learned.rejected:
            key = self.n(r.term)
            u, before = U.get(key), (B if self.base is not None else M).get(key)
            if u is None or key not in self.result:
                continue
            f = self.n(r.text)
            theirs = self.folds([*(u.get("aliases") or []), *(u.get("variants") or [])])
            had = self.folds([*((before or {}).get("aliases") or []), *((before or {}).get("variants") or [])])
            if f in theirs and f not in had:
                def drop(key=key, fold=f):
                    def apply():
                        term = self.result[key]
                        for k in ("aliases", "variants"):
                            if term.get(k):
                                term[k] = [x for x in term[k] if self.n(str(x)) != fold]
                                if not term[k]:
                                    term.pop(k)
                    return apply
                self.ask("learned-rejected", r.term,
                         f"{r.term}: upstream added {r.text!r}, which you rejected in a review",
                         [self.describe("mine", M.get(key)), self.describe("theirs", u)], [r.text],
                         {MINE: drop(), THEIRS: lambda: None, LATER: drop()}, form=r.text)

    # -------------------------------------------------------------- the pack

    def pack_data(self) -> dict:
        """Upstream's keys, the copy's own (OWN_KEYS), the pack lists merged, the terms."""
        out = {k: v for k, v in self.up.items() if k != "terms"}
        for k in OWN_KEYS:
            if k in self.mine:
                out[k] = self.mine[k]
        for k in PACK_LISTS:
            b = (self.base or {}).get(k) if self.base is not None else []
            if k in self.up or k in self.mine:
                out[k] = self.merge_list(b, self.up.get(k), self.mine.get(k))
        out["terms"] = list(self.result.values())
        return out

    def learned_report(self):
        """Where the learned layer now repeats the pack, or contradicts it."""
        result = {self.n(str(t["term"])): t for t in self.result.values()}
        owner = {}
        for t in self.result.values():
            for f in [t["term"], *(t.get("aliases") or []), *(t.get("variants") or [])]:
                owner.setdefault(self.n(str(f)), str(t["term"]))
        out = self.summary.learned
        for term, confirmations in self.learned.confirmed.items():
            t = result.get(self.n(term))
            for c in confirmations:
                f = self.n(c.variant)
                if t is not None and f in self.folds(t.get("variants")):
                    out.append(f"redundant: {c.variant!r} -> {term} is in the pack now")
                elif owner.get(f) and self.n(owner[f]) != self.n(term):
                    out.append(f"contradiction: you confirmed {c.variant!r} -> {term}; the pack has it under {owner[f]}")
        for term, aliases in self.learned.aliases.items():
            t = result.get(self.n(term))
            for a in aliases:
                if t is not None and self.n(a.alias) in self.folds(t.get("aliases")):
                    out.append(f"redundant: alias {a.alias!r} of {term} is in the pack now")
        for r in self.learned.rejected:
            t = result.get(self.n(r.term))
            if t is not None and self.n(r.text) in self.folds([*(t.get("aliases") or []), *(t.get("variants") or [])]):
                out.append(f"contradiction: you rejected {r.text!r} for {r.term}; the pack has it")

    def edits_against_upstream(self) -> int:
        U = self.terms(self.up)
        R = {self.n(str(t["term"])): t for t in self.result.values()}
        return sum(1 for k, t in R.items() if not self.same(t, U.get(k))) + sum(1 for k in U if k not in R)


# ------------------------------------------------------------------ asking


def context(forms: list[str]) -> list[str]:
    """Up to CONTEXT_LINES caption lines from the user's runs with one of the forms."""
    from .interactive import lines_with

    out = []
    for caption in sorted(runs_root().glob("*/legenda.txt")):
        for form in forms:
            for line in lines_with(caption, form):
                entry = f"    {caption.parent.name}  {line}"
                if entry not in out:
                    out.append(entry)
                if len(out) >= CONTEXT_LINES:
                    return out
    return out


def answer(conflict: Conflict, number: int, preset: str | None) -> str:
    from . import prompts
    from .prompts import Option

    print()
    print(f"Conflict {number}: {conflict.title}")
    for line in conflict.lines:
        print(line)
    shown = context(conflict.forms)
    if shown:
        print("  in your runs:")
        for line in shown:
            print(line)
    if preset in conflict.apply:
        print(f"  -> {ANSWERS[preset].lower()} (--yes-{preset})")
        return preset
    if preset == MINE and MINE not in conflict.apply:
        print("  -> decide later (keeping yours is not possible here)")
        return LATER
    options = [Option(ANSWERS[a], value=a, key=KEYS[a]) for a in (MINE, THEIRS, BOTH, LATER) if a in conflict.apply]
    picked = prompts.select("Which one?", options, hint="decide later keeps yours and notes it", back=False)
    return picked or LATER


# ------------------------------------------------------------------ the command


def run_merge(args) -> int:
    name = args.name
    path = installed_packs().get(name)
    if path is None or path.parent == BUNDLED_PACKS or packfiles.source_of(name, path) != packfiles.MINE:
        print(f"{name} is not a copy of yours; `pack copy {name}` makes one", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    mine = yaml.safe_load(text) or {}
    upstream = upstream_of(name, packfiles.index_within(MERGE_WAIT_SECONDS))
    if upstream is None:
        print(f"no upstream for {name}: neither bundled nor in the packs repository", file=sys.stderr)
        return 1
    base_ref = based_on(mine)
    if base_ref and not packfiles.newer(upstream.version, base_ref[1]) and not args.force:
        print(f"{name} is based on {base_ref[1]}, and the {upstream.origin} pack is {upstream.version}: nothing to merge")
        return 0
    try:
        up_text = upstream.read()
    except registry.RegistryError as error:
        print(error, file=sys.stderr)
        return 1
    up = yaml.safe_load(up_text) or {}
    base = None
    if base_ref:
        snapshot = base_path(*base_ref)
        if snapshot.exists():
            base = yaml.safe_load(snapshot.read_text(encoding="utf-8")) or {}
        else:
            print(f"  the base {base_ref[0]}@{base_ref[1]} is not in {snapshot.parent}; merging two-way")
    mode = "three-way, from " + base_ref[1] if base is not None else "two-way (no base)"
    print(f"Merging {name}: yours {mine.get('version')} with the {upstream.origin} {upstream.version}, {mode}")

    merge = Merge(name, base, up, mine, load_learned(learned_file(path))).run()
    preset = THEIRS if args.yes_theirs else MINE if args.yes_mine else None
    s = merge.summary

    def resolve(conflicts, start):
        for i, conflict in enumerate(conflicts, start):
            if args.dry_run:
                print(f"\nConflict {i}: {conflict.title} (would be asked)")
                s.pending.append({"kind": conflict.kind, "term": conflict.term, **conflict.sides})
                continue
            picked = answer(conflict, i, preset)
            conflict.apply[picked]()
            if picked == LATER:
                s.pending.append({"kind": conflict.kind, "term": conflict.term, "title": conflict.title,
                                  **conflict.sides, "date": date.today().isoformat()})
            else:
                s.resolved.append(f"{conflict.term}: {ANSWERS[picked].lower()}")
        return start + len(conflicts)

    after = resolve(merge.conflicts, 1)
    merge.conflicts = []
    merge.collisions()
    merge.learned_conflicts()
    resolve(merge.conflicts, after)
    merge.learned_report()
    present = {str(term["term"]) for term in merge.result.values()}
    s.added = [x for x in s.added if x in present]
    s.kept = [x for x in s.kept if x in present]

    data = merge.pack_data()
    edits = merge.edits_against_upstream()
    data["version"] = packedit.bump(up.get("version")) if edits else up.get("version")
    data["based_on"] = f"{name}@{upstream.version}"
    data["local_edits"] = edits
    print_summary(s, args.dry_run)
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    head = packedit.header(text)
    new_text = packedit.dump(head, data)
    problem = validate(path, new_text, up, merge)
    if problem:
        print(f"not written: {problem}", file=sys.stderr)
        return 1
    backup = path.with_name(f"{path.name}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    backup.write_bytes(path.read_bytes())
    keep_base(name, upstream.version, up_text)
    registry.write_atomic(path, new_text.encode("utf-8"))
    pending = path.with_name(f"{name}{PENDING_SUFFIX}")
    if s.pending:
        pending.write_text(yaml.safe_dump({"pack": name, "merged_with": f"{name}@{upstream.version}",
                                           "conflicts": s.pending}, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
        print(f"pending conflicts: {pending}")
    else:
        pending.unlink(missing_ok=True)
    print(f"backup: {backup}")
    print(f"saved {path} ({name} {data['version']}, based on {upstream.version}, {edits} local edit(s))")
    return 0


def validate(path: Path, text: str, up: dict, merge: Merge) -> str:
    """D-064 (as normalize loads it) and D-005 (no variant under 3 letters
    that upstream does not have itself)."""
    trial = path.with_name(f".{path.stem}.merge-check.yaml")
    try:
        trial.write_text(text, encoding="utf-8")
        packfiles.check(trial)
    except packfiles.PackFileError as error:
        return str(error).replace(str(trial), str(path))
    finally:
        trial.unlink(missing_ok=True)
    theirs = {merge.n(str(v)) for t in up.get("terms") or [] for v in t.get("variants") or []}
    for t in merge.result.values():
        for v in t.get("variants") or []:
            if merge.n(str(v)) not in theirs and packedit.variant_problem(str(v), merge.language):
                return packedit.variant_problem(str(v), merge.language)
    return ""


def print_summary(s: Summary, dry_run: bool) -> None:
    print()
    print("Would be merged:" if dry_run else "Merged:")
    for label, items in (("added from upstream", s.added), ("updated from upstream", s.updated),
                         ("kept of yours", s.kept), ("combined", s.combined), ("removed", s.removed)):
        print(f"  {label:22s} {len(items):3d}" + (f"  {', '.join(items[:6])}{' …' if len(items) > 6 else ''}" if items else ""))
    print(f"  {'conflicts resolved':22s} {len(s.resolved):3d}")
    print(f"  {'conflicts pending':22s} {len(s.pending):3d}")
    for notice in s.notices:
        print(f"  note: {notice}")
    if s.learned:
        print("  your learned layer (left as it is):")
        for line in s.learned:
            print(f"    {line}")


def add_arguments(commands) -> None:
    merging = commands.add_parser("merge", help="merge a newer upstream version into your copy of a pack (D-069)")
    merging.add_argument("name")
    merging.add_argument("--dry-run", action="store_true", help="print what would happen; write nothing")
    sides = merging.add_mutually_exclusive_group()
    sides.add_argument("--yes-theirs", action="store_true", help="answer every conflict with upstream's side")
    sides.add_argument("--yes-mine", action="store_true", help="answer every conflict with yours")
    merging.add_argument("--force", action="store_true", help="merge even when upstream is not newer than the base")
    merging.set_defaults(run=run_merge)
