"""D-092: passages a local transcription wrote twice.

Measured on a 2h40 lesson transcribed whole with faster-whisper medium: around
44:29 a passage of 24 words said at 44:06 and 44:24 came out a second time, and
what was said there was lost. The same model on a clip of that stretch got it
right, so the cause is how the long file was cut into windows, not the model,
the VAD or the volume. The text cannot show what is missing; it can show what
came out twice, and that marks where to listen.

A speaker repeats too: in that lesson the next longest repetition within a
minute was 13 words, and they were said. So a passage counts only from
MIN_WORDS words up, and only when its first copy is less than WINDOW_SECONDS
earlier. This is a warning to listen, never a correction: the text is not
touched.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Words compared at a time.
NGRAM = 6
#: How far back the first copy may be, in seconds.
WINDOW_SECONDS = 60
#: The shortest passage reported, in words.
MIN_WORDS = 15

#: The file needs-review/ gets when there is something to listen to.
REPEATS_FILE = "repeats.txt"

_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Repeat:
    """A passage written twice: where the second copy is, where the first was."""

    start: str  # m:ss of the line where the second copy begins
    end: str  # m:ss of the line where it ends
    source_start: str  # m:ss of the line where the earliest of the first copies begins
    source_end: str  # m:ss of the line where the latest of them ends
    words: int
    text: str  # the lines the second copy is in, `m:ss text`, as written
    #: The stretches it repeats, each (m:ss start, m:ss end). Usually one; the
    #: lesson that motivated this wrote two earlier stretches back to back.
    sources: tuple[tuple[str, str], ...] = ()


def _fold(word: str) -> str:
    folded = unicodedata.normalize("NFKD", word.lower())
    return "".join(c for c in folded if not unicodedata.combining(c))


def _seconds(stamp: str) -> int:
    minutes, seconds = stamp.split(":")
    return int(minutes) * 60 + int(seconds)


def _lines(body: str) -> list[tuple[str, str]]:
    lines = []
    for raw in body.splitlines():
        stamp, _, text = raw.strip().partition(" ")
        if re.fullmatch(r"\d+:\d\d", stamp) and text:
            lines.append((stamp, text))
    return lines


def find_repeats(body: str) -> list[Repeat]:
    """The passages of `m:ss text` lines that repeat an earlier one, in order."""
    lines = _lines(body)
    tokens: list[tuple[str, int]] = []  # (folded word, line)
    for index, (_, text) in enumerate(lines):
        tokens.extend((_fold(m.group()), index) for m in _WORD.finditer(text))

    def when(token: int) -> int:
        return _seconds(lines[tokens[token][1]][0])

    seen: dict[tuple[str, ...], list[int]] = {}
    hits: list[tuple[int, int]] = []  # (where the n-gram repeats, where it was first)
    for j in range(len(tokens) - NGRAM + 1):
        gram = tuple(t[0] for t in tokens[j : j + NGRAM])
        for i in seen.get(gram, ()):
            # Not overlapping itself, and close enough in time.
            if i + NGRAM <= j and when(j) - when(i) <= WINDOW_SECONDS:
                hits.append((j, i))
                break
        seen.setdefault(gram, []).append(j)

    # A passage: [first token, last token, [[source first, source last], ...]].
    # Its sources are kept apart when they are apart in the text, so a report
    # never spans words between them that were not repeated.
    passages: list[list] = []
    for j, i in hits:
        if passages and j <= passages[-1][1] + 1:
            passage = passages[-1]
            passage[1] = j + NGRAM - 1
            runs = passage[2]
            if i <= runs[-1][1] + 1 and i >= runs[-1][0]:
                runs[-1][1] = max(runs[-1][1], i + NGRAM - 1)
            else:
                runs.append([i, i + NGRAM - 1])
        else:
            passages.append([j, j + NGRAM - 1, [[i, i + NGRAM - 1]]])

    def stamp(token: int) -> str:
        return lines[tokens[token][1]][0]

    found = []
    for first, last, runs in passages:
        words = last - first + 1
        # The second copy counts only in the words it does not share with its
        # own first copies: a refrain sung over and over overlaps itself, and
        # is not one passage written twice.
        inside = {token for start, end in runs for token in range(start, end + 1)}
        if sum(1 for token in range(first, last + 1) if token not in inside) < MIN_WORDS:
            continue
        found.append(Repeat(
            start=stamp(first), end=stamp(last),
            source_start=stamp(min(start for start, _ in runs)), source_end=stamp(max(end for _, end in runs)),
            words=words,
            text="\n".join(f"{when} {text}" for when, text in lines[tokens[first][1] : tokens[last][1] + 1]),
            sources=tuple((stamp(start), stamp(end)) for start, end in runs),
        ))
    return found


def _span(start: str, end: str, to: str = "a") -> str:
    return start if start == end else f"{start} {to} {end}"


def _sources(repeat: Repeat, to: str, join: str) -> str:
    spans = repeat.sources or ((repeat.source_start, repeat.source_end),)
    return join.join(_span(start, end, to) for start, end in spans)


def header_lines(repeats: list[Repeat]) -> list[str]:
    """The lines the header of a transcription gets (in Portuguese, like the header)."""
    if not repeats:
        return ["# Trecho repetido: nenhum encontrado. Isto nao garante que nada faltou."]
    lines = [f"# Trecho repetido: {len(repeats)}. Ouca o audio antes de usar estes trechos:"]
    for repeat in repeats:
        lines.append(
            f"#   {_span(repeat.start, repeat.end)} repete {_sources(repeat, 'a', ' e ')}"
            f" ({repeat.words} palavras); a fala real ali pode ter se perdido."
        )
    return lines


def report(repeats: list[Repeat]) -> str:
    """needs-review/repeats.txt: each passage, where its first copy was, and its words."""
    out = [
        "Passages the local transcription wrote twice.",
        "The second copy usually stands where something else was said, which is lost.",
        "Listen to the audio at each time before using it. The text was not changed.",
        "",
    ]
    for repeat in repeats:
        out.append(
            f"{_span(repeat.start, repeat.end, 'to')}  repeats {_sources(repeat, 'to', ' and ')}"
            f"  ({repeat.words} words)"
        )
        out.extend(f"  {line}" for line in repeat.text.splitlines())
        out.append("")
    return "\n".join(out)


def summary(repeats: list[Repeat]) -> str:
    """The one line fetch prints."""
    where = ", ".join(r.start for r in repeats)
    return (f"{len(repeats)} passage(s) came out twice, at {where}: listen there before using it "
            f"(needs-review/{REPEATS_FILE})")
