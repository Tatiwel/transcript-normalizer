"""Scoring annotations against a hand-checked gold file (D-026).

A fixture is a directory holding `legenda.txt`, `pack.yaml` and `gold.csv`. Each
gold row names a stretch of a caption line (`wrong`), the text it should become
(`correct`) and the term it belongs to. One rule scores every fixture:

- a row whose normalized `correct` differs from its `wrong` expects that
  correction: a hit when an applied correction for this term covers this text
  on this line, a miss otherwise;
- an `alias` row expects an alias annotation for this term and no substitution
  of its text; a substitution there, to any term, is a false positive;
- a `manter` row expects no applied annotation on its text, whatever the term;
- a row with an empty term is out of scope, and so is `so_caixa` or any other
  row whose `correct` differs from `wrong` only by case or accent (D-008).

`certo` and `conferido` record who wrote the row: the tool proposed it and a
person checked it, or a person added it. Scoring does not tell them apart.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .core.pack import Learned, Pack, load_pack
from .core.standoff import Annotation
from .core.text import Transcript, read_caption
from .languages import generic

CERTO = "certo"
ALIAS = "alias"
CONFERIDO = "conferido"
MANTER = "manter"
SO_CAIXA = "so_caixa"
STATUSES = (CERTO, ALIAS, CONFERIDO, MANTER, SO_CAIXA)


def key(text: str, normalize=generic.normalize) -> str:
    """Gold text is compared loosely: normalized by the pack's language (D-033),
    with runs of space collapsed."""
    return " ".join(normalize(text).split())


def covers(wrong: str, annotation: Annotation, normalize=generic.normalize) -> bool:
    """Whether an annotation sits on the gold row's text, in either direction."""
    a, b = key(wrong, normalize), key(annotation.original, normalize)
    return a in b or b in a


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


def expects_correction(row: dict, normalize=generic.normalize) -> bool:
    """D-026, with D-008: `correct` differs from `wrong` by more than case or accent."""
    return key(row["correct"], normalize) != key(row["wrong"], normalize)


def evaluate(
    transcript: Transcript,
    annotations: list[Annotation],
    gold: list[dict],
    normalize=generic.normalize,
) -> Result:
    """Score the applied annotations against the gold rows, by D-026's one rule.

    `normalize` is the pack's language normalization (D-033); the generic one
    is only a default for callers that have no pack.
    """
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
    # identical rows. No fixture has such a pair since commit 7 removed the
    # duplicated `10:59 Ox` row from R2Qgz8tFWVI.
    def find(row: dict, pool: list[Annotation], any_term: bool = False) -> Annotation | None:
        allowed = {id(a) for a in pool}
        for a in on_line.get(row["timestamp"], ()):
            if (
                id(a) in allowed
                and (any_term or a.term == row["term"])
                and covers(row["wrong"], a, normalize)
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
                if covers(row["wrong"], a, normalize)
            ]
            result.touched_keep[f"{row['timestamp']} {row['wrong']}"] = touched
            continue
        if not row["term"]:
            continue
        if status != ALIAS and not expects_correction(row, normalize):
            continue  # D-008: a case- or accent-only difference is not a correction

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

        # certo or conferido: who wrote the row, not how it is scored.
        found = find(row, corrections)
        if found is not None:
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
            key(a.original, normalize) in key(u.original, normalize)
            or key(u.original, normalize) in key(a.original, normalize)
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
    return evaluate(transcript, annotations, fixture.load_gold(), pack.normalize)


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
    out += ["", "text that must stay untouched (applied annotations only):"]
    out += [f"  {where} {touched}" for where, touched in result.touched_keep.items()]
    return "\n".join(out)
