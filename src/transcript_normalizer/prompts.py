"""Asking the person at the terminal (D-053).

Four questions: `select` (one of a list), `multi_select` (any of a list),
`confirm` (yes or no) and `text` (a line). Two implementations stand behind them:
questionary, with arrow keys and a space bar, when it is installed and stdout is a
terminal; plain numbered or lettered text everywhere else, which is also what
the tests drive. The core never imports this module.

Every question shows a hint (what it expects) and a key legend. Empty input or
Esc means "go back": the function returns None, and so does the "← Back" option
that ends every select list (D-061). `?` prints one line per option and asks
again.

The structure is drawn the same way in both (D-061): a dim rule and a stage
label before each block (`stage`), a line above every text field (`field`),
label/value pairs for details (`detail`). With questionary the marks are
Unicode (─ ◆ ● ○ »); in plain text they are ASCII (- * * >), so a pipe or a
Windows console with a narrow code page reads the same structure.

Colour, via rich, one colour per meaning (`mark` and `say`): yellow for what
needs the user, green for success, red for refusals and errors, blue for paths
and term names, dim for hints, bold for titles. No colour when stdout is not a
terminal or rich is missing.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass

# ------------------------------------------------------------------ colour

STYLES = {
    "need": "yellow",
    "ok": "green",
    "bad": "red",
    "path": "blue",
    "hint": "dim",
    "title": "bold",
    "label": "dim",
    "value": "white",
    "number": "bold",
}


@dataclass(frozen=True)
class Marked:
    text: str
    meaning: str


def mark(text, meaning: str) -> Marked:
    return Marked(str(text), meaning)


_console = None


def console():
    """A rich console when colour makes sense here, else None."""
    global _console
    if not sys.stdout.isatty() or importlib.util.find_spec("rich") is None:
        return None
    if _console is None or _console.file is not sys.stdout:
        from rich.console import Console

        _console = Console(highlight=False, soft_wrap=True)
    return _console


def say(*parts) -> None:
    """One line made of plain strings and `mark`ed pieces."""
    rich = console()
    if rich is None:
        print("".join(p.text if isinstance(p, Marked) else str(p) for p in parts))
        return
    from rich.markup import escape

    rich.print("".join(
        f"[{STYLES[p.meaning]}]{escape(p.text)}[/]" if isinstance(p, Marked) else escape(str(p))
        for p in parts
    ))


# ------------------------------------------------------------------ options


@dataclass(frozen=True)
class Option:
    label: str
    description: str = ""
    examples: tuple[str, ...] = ()
    value: object = None
    key: str = ""  # what to type in plain text; a number when empty
    help: str = ""  # what `?` prints: a longer entry than the description
    command: str = ""  # the equivalent command, shown under `help`

    @property
    def result(self):
        return self.label if self.value is None else self.value


def explain(options: list[Option]) -> None:
    """`?`: each option's help entry, aligned like `help` (D-051), with its
    command; the one-line description when an option has no entry."""
    from .helptext import entries, width

    rows = [(o.label, o.help or o.description, *([o.command] if o.command else [])) for o in options]
    rows = [row for row in rows if row[1]]
    print()
    for line in entries(rows, width()):
        print(line)
    for o in options:
        for line in o.examples:
            say(mark(f"      {line}", "hint"))
    print()


def interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def use_questionary() -> bool:
    return interactive_terminal() and importlib.util.find_spec("questionary") is not None


# ------------------------------------------------------------------ structure

#: The marks, Unicode with questionary and ASCII in plain text (D-061).
UNICODE = {"rule": "─", "stage": "◆", "on": "●", "off": "○", "pointer": "»", "back": "←", "qmark": "◇"}
ASCII = {"rule": "-", "stage": "*", "on": "*", "off": " ", "pointer": ">", "back": "<-"}


def glyph(name: str) -> str:
    return (UNICODE if use_questionary() else ASCII)[name]


def rule() -> None:
    """A dim rule, as wide as the terminal up to 60 columns."""
    from .helptext import width

    say(mark(glyph("rule") * min(width(), 60), "hint"))


def stage(label: str, detail: str = "") -> None:
    """`◆ Fetch`: a one-word stage label under a rule, before each block."""
    print()
    rule()
    say(mark(f"{glyph('stage')} {label}", "title"), mark(f"  {detail}", "hint") if detail else "")


#: What `field` says above a text input.
FIELDS = {"paste": "paste below", "path": "type a path"}


def field(kind: str = "paste") -> None:
    """`── paste below ──`: where the input goes."""
    line = glyph("rule") * 2
    say(mark(f"{line} {FIELDS[kind]} {line}", "hint"))


def detail(label: str, value, kind: str = "value", indent: str = "  ") -> None:
    """`label: value`, the label dim and the value white, blue (path) or bold (number)."""
    say(indent, mark(f"{label}: ", "label"), mark(value, kind))


def legend(kind: str = "select") -> str:
    """The key legend under a question."""
    if use_questionary():
        keys = {
            "select": "↑↓ move · enter confirm · esc back · ? explain",
            "multi": "↑↓ move · space select · enter confirm · esc back · ? explain",
            "confirm": "y / n · enter takes the default · esc back",
            "text": "type, then enter · ? alone explains",
        }
    else:
        keys = {
            "select": "a number or letter shown, then enter · empty goes back · ? explains",
            "multi": "letters (e.g. a c), - for none, then enter · empty goes back · ? explains",
            "confirm": "y or n, then enter · enter alone takes the default",
            "text": "type, then enter · ? alone explains",
        }
    return keys[kind]


#: What a text field adds to its hint (D-061).
BACK_HINT = "(empty or Esc: back)"


def _header(title: str, hint: str, kind: str) -> None:
    say(mark(title, "title"))
    if hint:
        say(mark(f"  {hint}", "hint"))
    say(mark(f"  keys: {legend(kind)}", "hint"))


# ------------------------------------------------------------------ the four questions


_GO_BACK = object()


def back_option() -> Option:
    """The last option of every select list (D-061): the previous screen."""
    return Option(f"{glyph('back')} Back", value=_GO_BACK, key="b", help="return to the previous screen")


def select(title: str, options: list[Option], hint: str = "", back: bool = True):
    """One option's `result`, or None for back (the Back option, Esc or empty).

    `back` adds the Back option; the menu itself has Quit instead.
    """
    options = list(options) + ([back_option()] if back else [])
    answer = (_Questionary if use_questionary() else _Plain).select(title, options, hint)
    return None if answer is _GO_BACK else answer


def multi_select(title: str, options: list[Option], preselected=(), hint: str = ""):
    """The `result` of every option chosen (possibly none), or None for back."""
    return (_Questionary if use_questionary() else _Plain).multi_select(
        title, list(options), set(preselected), hint
    )


def confirm(title: str, default: bool = True, hint: str = ""):
    """True or False; None for back."""
    return (_Questionary if use_questionary() else _Plain).confirm(title, default, hint)


def text(title: str, hint: str = "", kind: str = "paste"):
    """A stripped line, or None for back. `kind` is the line above the field."""
    hint = f"{hint} {BACK_HINT}" if hint else BACK_HINT
    return (_Questionary if use_questionary() else _Plain).text(title, hint, kind)


# ------------------------------------------------------------------ plain text


def _read(prompt: str = "> ") -> str | None:
    try:
        return input(prompt).strip()
    except EOFError:
        return None


def _letters(n: int) -> list[str]:
    if n <= 26:
        return [chr(ord("a") + i) for i in range(n)]
    return [str(i + 1) for i in range(n)]


class _Plain:
    @staticmethod
    def select(title, options, hint):
        _header(title, hint, "select")
        keys = [o.key or str(i) for i, o in enumerate(options, 1)]
        width = max(len(o.label) for o in options)
        for key, o in zip(keys, options):
            label = o.label.ljust(width) if o.description else o.label
            say(f"  {key:>2}. ", mark(label, "need"), f"   {o.description}" if o.description else "")
        while True:
            answer = _read()
            if not answer:
                return None
            if answer == "?":
                explain(options)
                continue
            if answer.lower() in keys:
                return options[keys.index(answer.lower())].result
            say(mark(f"  {answer!r} is not one of {', '.join(keys)}", "bad"))

    @staticmethod
    def multi_select(title, options, preselected, hint):
        _header(title, hint, "multi")
        keys = _letters(len(options))
        width = max(len(o.label) for o in options)
        for key, o in zip(keys, options):
            box = f"[{glyph('on')}]" if o.result in preselected else "[ ]"
            label = o.label.ljust(width) if o.description else o.label
            say(f"  {key}. {box} ", mark(label, "need"), f"   {o.description}" if o.description else "")
        while True:
            answer = _read()
            if not answer:
                return None
            if answer == "?":
                explain(options)
                continue
            if answer == "-":
                return []
            tokens = re.split(r"[\s,]+", answer.lower())
            if len(tokens) == 1 and all(c in keys for c in tokens[0]) and len(keys) <= 26:
                tokens = list(tokens[0])
            if all(t in keys for t in tokens):
                picked = {keys.index(t) for t in tokens}
                return [o.result for i, o in enumerate(options) if i in picked]
            say(mark(f"  {answer!r}: use the letters shown, or - for none", "bad"))

    @staticmethod
    def confirm(title, default, hint):
        if hint:
            say(mark(f"  {hint}", "hint"))
        suffix = "[Y/n]" if default else "[y/N]"
        while True:
            try:
                answer = input(f"{title} {suffix} ").strip().lower()
            except EOFError:
                return None
            if not answer:
                return default
            if answer in ("y", "yes", "s", "sim"):
                return True
            if answer in ("n", "no", "não", "nao"):
                return False
            say(mark("  y or n", "bad"))

    @staticmethod
    def text(title, hint, kind):
        _header(title, hint, "text")
        field(kind)
        while True:
            answer = _read()
            if answer == "?":
                say(mark(f"  {hint}", "hint"))
                continue
            if answer == "\x1b":  # Esc, then enter
                return None
            return answer or None


# ------------------------------------------------------------------ questionary

_BACK = object()
_EXPLAIN = object()


def _bind(question, explainable: bool = True):
    """Esc goes back; `?` explains. A no-op on anything without an application."""
    app = getattr(question, "application", None)
    if app is None:
        return question
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

    keys = KeyBindings()

    @keys.add("escape", eager=True)
    def _(event):
        event.app.exit(result=_BACK)

    if explainable:
        @keys.add("?")
        def _(event):
            event.app.exit(result=_EXPLAIN)

    app.key_bindings = merge_key_bindings([app.key_bindings, keys]) if app.key_bindings else keys
    return question


def _style() -> dict:
    """questionary's marks and colours (D-061); nothing if it has no Style."""
    import questionary

    if not hasattr(questionary, "Style"):
        return {}
    return {"qmark": UNICODE["qmark"], "style": questionary.Style([
        ("qmark", "fg:ansicyan bold"),
        ("question", "bold"),
        ("pointer", "fg:ansicyan bold"),
        ("highlighted", "fg:ansicyan bold"),
        ("selected", "fg:ansigreen"),
        ("instruction", "fg:ansibrightblack"),
        ("answer", "fg:ansicyan"),
    ])}


class _Questionary:
    @staticmethod
    def _choices(options, preselected=()):
        import questionary

        width = max(len(o.label) for o in options)
        return [
            questionary.Choice(
                title=f"{o.label.ljust(width)}   {o.description}".rstrip(),
                value=i,
                checked=o.result in preselected,
            )
            for i, o in enumerate(options)
        ]

    @staticmethod
    def select(title, options, hint):
        import questionary

        while True:
            if hint:
                say(mark(f"  {hint}", "hint"))
            answer = _bind(questionary.select(
                title, choices=_Questionary._choices(options), instruction=legend("select"),
                pointer=UNICODE["pointer"], **_style(),
            )).unsafe_ask()
            if answer is _EXPLAIN:
                explain(options)
                continue
            return None if answer is _BACK or answer is None else options[answer].result

    @staticmethod
    def multi_select(title, options, preselected, hint):
        import questionary

        while True:
            if hint:
                say(mark(f"  {hint}", "hint"))
            answer = _bind(questionary.checkbox(
                title, choices=_Questionary._choices(options, preselected), instruction=legend("multi"),
                pointer=UNICODE["pointer"], **_style(),
            )).unsafe_ask()
            if answer is _EXPLAIN:
                explain(options)
                continue
            if answer is _BACK or answer is None:
                return None
            return [options[i].result for i in answer]

    @staticmethod
    def confirm(title, default, hint):
        import questionary

        if hint:
            say(mark(f"  {hint}", "hint"))
        answer = _bind(questionary.confirm(title, default=default, **_style()), explainable=False).unsafe_ask()
        return None if answer is _BACK else answer

    @staticmethod
    def text(title, hint, kind):
        import questionary

        while True:
            say(mark(f"  {hint}", "hint"))
            field(kind)
            # `?` is not bound here: it belongs in URLs. `?` alone explains.
            answer = _bind(
                questionary.text(title, instruction=legend("text"), **_style()), explainable=False
            ).unsafe_ask()
            if answer is _BACK or answer is None:
                return None
            if answer.strip() == "?":
                say(mark(f"  {hint}", "hint"))
                continue
            return answer.strip() or None
