"""D-087: which engine this is, and whether a pack's `min_engine` admits it.

A pack can use what an older engine does not know and would silently ignore
(D-086's `context:`). The packs index and the pack file may then say
`min_engine: "0.7.0"`; an engine older than that skips the index entry and
refuses the file, instead of half-understanding it.
"""

from __future__ import annotations

import re

#: A `min_engine` is plain numbers: "0.7", "0.7.0".
REQUIRED = re.compile(r"^\d+(\.\d+){0,3}$")
#: The engine's own version may carry a suffix ("0.7.0.dev1", "0.7.0rc1"): its numbers count.
LEADING = re.compile(r"^v?(\d+(?:\.\d+)*)")


def version() -> str | None:
    """The running engine's version, from the package metadata; None in a
    checkout that was never installed."""
    from importlib.metadata import PackageNotFoundError, version as installed

    try:
        return installed("transcript-normalizer")
    except PackageNotFoundError:
        return None


def _numbers(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def numbers(text: str) -> tuple[int, ...]:
    """A pack version as numbers, to sort by: "0.3.10" after "0.3.8"; () when it has none."""
    found = LEADING.match(str(text))
    return _numbers(found.group(1)) if found else ()


def _padded(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def too_old_for(min_engine: object, running: str | None = None) -> bool:
    """Whether this engine is older than `min_engine` asks.

    No `min_engine`: never. One that is not plain numbers cannot be checked,
    so it counts as too old (refused, not guessed). An engine whose own
    version is unknown (a source checkout) is let through: it is the newest
    code there is.
    """
    if min_engine is None or str(min_engine).strip() == "":
        return False
    required = str(min_engine).strip()
    if not REQUIRED.match(required):
        return True
    have = running if running is not None else version()
    found = LEADING.match(have or "")
    if found is None:
        return False
    mine, needed = _padded(_numbers(found.group(1)), _numbers(required))
    return mine < needed


def needs(name: str, pack_version: str, min_engine: object) -> str:
    """'financas-ptbr 0.3.8 needs transcript-normalizer 0.7.0 or later (this is 0.6.5)'."""
    have = version()
    this = f" (this is {have})" if have else ""
    return f"{name} {pack_version} needs transcript-normalizer {str(min_engine).strip()} or later{this}"
