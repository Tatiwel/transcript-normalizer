"""Language modules, and how a pack's `language:` finds one (D-033).

`pt-BR` is the module `pt_br` in this package; any code maps to a module the
same way (lowercase, `-` becomes `_`). A module that lives elsewhere, a plugin
or a test, is made known with `register(code, module)`.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from . import generic
from .base import Language, UnitRule

__all__ = [
    "Language",
    "LanguageNotFound",
    "UnitRule",
    "for_code",
    "module_name",
    "register",
]

_REGISTRY: dict[str, ModuleType] = {}
_NOT_LANGUAGES = {"base", "generic"}


class LanguageNotFound(LookupError):
    """A pack names a language no module implements."""


def module_name(code: str) -> str:
    """`pt-BR` -> `pt_br`."""
    return code.strip().lower().replace("-", "_")


def register(code: str, module: ModuleType) -> None:
    """Make `module` the implementation of `code`, checking it keeps the protocol."""
    if not isinstance(module, Language):
        missing = [
            name
            for name in ("normalize", "inflections", "unit_rules", "sentence_boundaries")
            if not hasattr(module, name)
        ]
        raise TypeError(f"{module.__name__} does not implement the language protocol: {missing}")
    _REGISTRY[module_name(code)] = module


def for_code(code: str | None, allow_generic: bool = False) -> ModuleType:
    """The module for a pack's `language:`. Unknown codes are an error unless
    `allow_generic`, which falls back to the generic module."""
    if not code:
        raise LanguageNotFound(
            "the pack declares no language; add a `language:` line, e.g. "
            "`language: pt-BR` (D-002, D-033)"
        )
    name = module_name(code)
    if name in _REGISTRY:
        return _REGISTRY[name]
    if name not in _NOT_LANGUAGES:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as error:
            if error.name != f"{__name__}.{name}":
                raise
        else:
            register(code, module)
            return module
    if allow_generic:
        return generic
    raise LanguageNotFound(
        f"no language module for {code!r}: expected "
        f"src/transcript_normalizer/languages/{name}.py. Add one (see CONTRIBUTING.md), "
        f"or pass --allow-generic to match with no inflections and no unit rules"
    )
