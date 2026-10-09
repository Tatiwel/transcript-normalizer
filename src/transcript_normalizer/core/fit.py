"""D-054: does the pack fit this transcript at all?

A pack that fits a transcript names several of its terms with confidence. One
that does not still finds the odd short form in someone else's speech (D-035),
and every correction there is a false positive. So before anything is applied,
the distinct terms with at least one high-band annotation are counted; unit
rules do not count, since numbers and units turn up in any field.
"""

from __future__ import annotations

from .standoff import BAND_HIGH, RULE_UNIT, Annotation

#: Fewer distinct high-band terms than this, and nothing is applied.
MIN_FIT_TERMS = 3


def fitting_terms(annotations: list[Annotation]) -> set[str]:
    """The terms with at least one high-band annotation, unit rules aside."""
    return {a.term for a in annotations if a.band == BAND_HIGH and a.rule != RULE_UNIT}


def fits(annotations: list[Annotation]) -> bool:
    """Whether the pack names at least `MIN_FIT_TERMS` of its terms with confidence."""
    return len(fitting_terms(annotations)) >= MIN_FIT_TERMS
