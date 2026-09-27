"""Scoring annotations against a hand-checked gold file.

A fixture is a directory holding `legenda.txt`, `pack.yaml` and `gold.csv`. Each
gold row names a stretch of a caption line (`wrong`), the term it belongs to,
and a status that says what the tool was supposed to do with it:

- `certo`: the tool proposed this correction and it was right. A hit when an
  applied correction for this term covers this text on this line.
- `alias`: the text is a legitimate other name of the term (ticker, plural,
  spoken form). A hit when an alias annotation for this term covers it and no
  correction substitutes it. A substitution here is a false positive.
- `conferido`: the tool missed it and a person wrote the row. Always a miss:
  it measures pack coverage. If the tool now finds it, that annotation is not a
  false positive, and the row is reported as found.
- `manter`: the tool must produce no applied annotation on this text.
- `so_caixa`: ignored (D-008).

Rows with an empty term are out of scope, except `manter`, which guards its text
whatever the term.

That is gold convention `v2`. `R2Qgz8tFWVI` was written before these meanings
existed and uses `v1`, where `conferido` only meant "checked by hand" and is
scored exactly like `certo`; 11 of its 156 hits are such rows.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .core.pack import Learned, Pack, fold, load_pack
from .core.standoff import Annotation
from .core.text import Transcript, read_caption

CERTO = "certo"
ALIAS = "alias"
CONFERIDO = "conferido"
MANTER = "manter"
SO_CAIXA = "so_caixa"
STATUSES = (CERTO, ALIAS, CONFERIDO, MANTER, SO_CAIXA)

V1 = "v1"
V2 = "v2"

#: Fixtures whose gold predates the v2 meanings. Every other fixture is v2.
GOLD_CONVENTION = {"R2Qgz8tFWVI": V1}


def key(text: str) -> str:
    """Gold text is compared loosely: folded, with runs of space collapsed."""
    return " ".join(fold(text).split())


def covers(wrong: str, annotation: Annotation) -> bool:
    """Whether an annotation sits on the gold row's text, in either direction."""
    return key(wrong) in key(annotation.original) or key(annotation.original) in key(wrong)


def is_correction(annotation: Annotation) -> bool:
    """An annotation that substitutes its span in normalized.txt (D-020)."""
    return annotation.is_correction


def is_alias(annotation: Annotation) -> bool:
    """An annotation that names the term without substituting its span (D-020)."""
    return annotation.is_alias


@dataclass(frozen=True)
class Fixture:
    directory: Path

    @property
    def name(self) -> str:
        return self.directory.name

    @property
    def caption(self) -> Path:
        return self.directory / "legenda.txt"

    @property
    def pack(self) -> Path:
        return self.directory / "pack.yaml"

    @property
    def gold(self) -> Path:
        return self.directory / "gold.csv"

    @property
    def convention(self) -> str:
        return GOLD_CONVENTION.get(self.name, V2)

    def load_pack(self) -> Pack:
        """The frozen fixture pack, with no learned layer: the numbers must not
        depend on anyone's personal confirmations (D-013, D-017)."""
        return load_pack(self.pack, learned=Learned())

    def load_transcript(self) -> Transcript:
        return read_caption(self.caption)

    def load_gold(self) -> list[dict]:
        return load_gold(self.gold)


def fixtures(root: Path) -> list[Fixture]:
    """Every fixture directory directly under `root`."""
    return [
        Fixture(d)
        for d in sorted(p for p in root.iterdir() if p.is_dir())
        if (d / "gold.csv").exists()
    ]


def load_gold(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    unknown = {r["status"] for r in rows} - set(STATUSES)
    if unknown:
        raise ValueError(f"{path}: unknown gold status {sorted(unknown)}")
    return rows


@dataclass
class Result:
    in_scope: list[dict] = field(default_factory=list)
    hits: list[tuple[dict, Annotation]] = field(default_factory=list)
    misses: list[dict] = field(default_factory=list)
    false_positives: list[tuple[str, Annotation]] = field(default_factory=list)
    aliases_recognized: list[tuple[dict, Annotation]] = field(default_factory=list)
    aliases_substituted: list[tuple[dict, Annotation]] = field(default_factory=list)
    conferido_found: list[tuple[dict, Annotation]] = field(default_factory=list)
    unlisted_aliases: list[Annotation] = field(default_factory=list)
    per_term: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))
    touched_keep: dict[str, list[tuple[str, str]]] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "in scope": len(self.in_scope),
            "hits": len(self.hits),
            "misses": len(self.misses),
            "false positives": len(self.false_positives),
            "aliases recognized": len(self.aliases_recognized),
            "aliases wrongly substituted": len(self.aliases_substituted),
        }


def evaluate(
    transcript: Transcript,
    annotations: list[Annotation],
    gold: list[dict],
    convention: str = V2,
) -> Result:
    """Score the applied annotations against the gold rows."""
    applied = [a for a in annotations if a.applied]
    corrections = [a for a in applied if is_correction(a)]
    aliases = [a for a in applied if is_alias(a)]

    on_line: dict[str, list[Annotation]] = defaultdict(list)
    home: dict[int, str] = {}
    for a in applied:
        for line in transcript.spans(a.start, a.end):
            on_line[line.timestamp].append(a)
        home[id(a)] = transcript.locate(a.start)[1]

    # First match on the line, as exp2 did, so one annotation can answer for two
    # identical rows. Known effect: R2Qgz8tFWVI's gold lists `10:59 Ox -> OPEX`
    # twice for one `Ox` in the caption, and both count. Matching one-to-one
    # would score that fixture 155, not 156; it does not move wxgFO_fyfXg.
    def find(row: dict, pool: list[Annotation], any_term: bool = False) -> Annotation | None:
        allowed = {id(a) for a in pool}
        for a in on_line.get(row["timestamp"], ()):
            if (
                id(a) in allowed
                and (any_term or a.term == row["term"])
                and covers(row["wrong"], a)
            ):
                return a
        return None

    result = Result()
    used: list[Annotation] = []
    substituting: set[int] = set()

    for row in gold:
        status = row["status"]
        if status == SO_CAIXA:
            continue
        if status == MANTER:
            touched = [
                (a.original, a.term)
                for a in on_line.get(row["timestamp"], ())
                if covers(row["wrong"], a)
            ]
            result.touched_keep[f"{row['timestamp']} {row['wrong']}"] = touched
            continue
        if not row["term"]:
            continue

        result.in_scope.append(row)
        result.per_term[row["term"]][1] += 1

        if status == ALIAS:
            # Any correction here rewrites what the speaker said, whatever term
            # it corrects to: `CEMIG 4` fuzzily corrected to `Cemig D` is still
            # a substitution of an alias.
            substitution = find(row, corrections, any_term=True)
            if substitution is not None:
                result.aliases_substituted.append((row, substitution))
                substituting.add(id(substitution))
                result.misses.append(row)
                continue
            recognized = find(row, aliases)
            if recognized is not None:
                result.aliases_recognized.append((row, recognized))
                result.hits.append((row, recognized))
                result.per_term[row["term"]][0] += 1
                used.append(recognized)
            else:
                result.misses.append(row)
            continue

        found = find(row, corrections)
        if status == CONFERIDO and convention == V2:
            if found is not None:
                result.conferido_found.append((row, found))
                used.append(found)
            result.misses.append(row)
        elif found is not None:
            result.hits.append((row, found))
            result.per_term[row["term"]][0] += 1
            used.append(found)
        else:
            result.misses.append(row)

    # False positives: corrections that credit no in-scope row, minus the ones
    # that merely nest inside (or around) one that did on a shared line, plus
    # every correction that substituted an alias. Alias annotations never change
    # the text, so an unlisted one is reported but is not a false positive.
    used_ids = {id(a) for a in used}
    used_on_line: dict[str, list[Annotation]] = defaultdict(list)
    for a in used:
        for line in transcript.spans(a.start, a.end):
            used_on_line[line.timestamp].append(a)

    for a in corrections:
        if id(a) in substituting:
            result.false_positives.append((home[id(a)], a))
            continue
        if id(a) in used_ids:
            continue
        neighbours = {
            id(u): u
            for line in transcript.spans(a.start, a.end)
            for u in used_on_line.get(line.timestamp, ())
        }
        if any(
            key(a.original) in key(u.original) or key(u.original) in key(a.original)
            for u in neighbours.values()
        ):
            continue
        result.false_positives.append((home[id(a)], a))

    result.unlisted_aliases = [a for a in aliases if id(a) not in used_ids]
    return result


def evaluate_fixture(fixture: Fixture, pack: Pack | None = None) -> Result:
    """Run the matcher over a fixture and score it. `pack` overrides the frozen one.

    Scoring sees every proposal, not the overlap-resolved set the CLI writes,
    as exp2 did: the regression numbers have always been measured that way.
    """
    from .core.matcher import find_annotations

    transcript = fixture.load_transcript()
    pack = pack if pack is not None else fixture.load_pack()
    annotations = find_annotations(transcript, pack)
    return evaluate(transcript, annotations, fixture.load_gold(), fixture.convention)


def render(result: Result) -> str:
    """The long form: counts, the per-term table, misses and false positives."""
    counts = result.counts()
    out = ["   ".join(f"{k}: {v}" for k, v in counts.items()), "", "per term (hits/total):"]
    for term, (hit, total) in sorted(result.per_term.items(), key=lambda kv: (-kv[1][1], kv[0])):
        out.append(f"  {term:24s} {hit:3d}/{total}")
    out += ["", "misses:"]
    out += [f"  {g['timestamp']:6s} {g['status']:9s} {g['wrong']!r} -> {g['term']}" for g in result.misses]
    out += ["", "false positives:"]
    counted = Counter((a.original, a.term) for _, a in result.false_positives)
    out += [f"  {n:3d}x {original!r} -> {term}" for (original, term), n in counted.most_common()]
    out += ["", "aliases wrongly substituted:"]
    out += [f"  {g['timestamp']:6s} {g['wrong']!r} -> {a.replacement}" for g, a in result.aliases_substituted]
    out += ["", "conferido rows the tool now finds:"]
    out += [f"  {g['timestamp']:6s} {g['wrong']!r} -> {g['term']}" for g, _ in result.conferido_found]
    out += ["", "text that must stay untouched (applied annotations only):"]
    out += [f"  {where} {touched}" for where, touched in result.touched_keep.items()]
    return "\n".join(out)
