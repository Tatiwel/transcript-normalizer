"""The header of a `legenda.txt`.

The header is what the core reads: `core.text.parse_caption` skips these `#`
lines and every line after them is `m:ss text`, or `h:mm:ss text` from 1 hour on (D-103). The wording stays in Portuguese
because `fixtures/fixture0001/legenda.txt` is the reference for this format and
the fixture is the regression test's input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Metadata:
    """What the platform says about a video."""

    id: str = ""
    title: str = ""
    channel: str = ""
    published: str = ""
    duration: int = 0
    manual_captions: tuple[str, ...] = field(default=())
    automatic_captions: tuple[str, ...] = field(default=())
    language: str = ""  # D-074: the spoken language, as yt-dlp's `language` reports it
    site: str = ""  # D-078: "YouTube", "Instagram", from yt-dlp's extractor
    audio: str = ""  # D-078: "audio only (m4a)", "with the video", or "" for none offered
    duration_from_audio: bool = False  # D-079: the site gave none; step 2 measured it


#: D-103: how the timestamp is written, as a video player shows the time.
CLOCK = "# Antes de 1 hora, m:ss (44:29); depois, h:mm:ss (1:14:14)."

#: D-093: which moment of a line the timestamp is. A caption cue (the
#: platform's, or a .srt or .vtt) is stamped with its end, as the converter does
#: (ingest/subtitles.py); a speech segment with its start (fetch.transcribe).
END_OF_CUE = (
    "# Cada linha comeca com o timestamp do FIM do trecho: o",
    "# instante em que a legenda sai da tela. A fala comeca antes dele.",
    CLOCK,
)
START_OF_SEGMENT = (
    "# Cada linha comeca com o timestamp do INICIO do trecho: o",
    "# instante em que a fala comeca.",
    CLOCK,
)


def _today() -> str:
    return date.today().isoformat()


def _step_line(step: str | None) -> list[str]:
    """D-036: which step of the fetch chain produced this text, when known."""
    return [f"# Etapa: {step}"] if step else []


def caption_header(
    meta: Metadata,
    url: str,
    source: str,
    lang: str,
    downloaded: str | None = None,
    step: str | None = None,
) -> str:
    """The header of a caption taken from the platform.

    `source` is manual, automatica or (D-045) automatica original; with `lang`
    it names the track, e.g. `automatica original (pt-orig)`.
    """
    return "\n".join(
        [
            "# Legenda de video, material bruto para ingestao",
            "#",
            "# Legenda obtida da plataforma, sem transcricao por IA.",
            f"# Origem da legenda: {source} ({lang})",
            *_step_line(step),
            f"# Titulo: {meta.title}",
            f"# Canal: {meta.channel}",
            f"# Publicado: {meta.published}",
            f"# URL: {url}",
            f"# Baixado em: {downloaded or _today()}",
            "#",
            *END_OF_CUE,
            "#",
            "# Legenda automatica erra termo de dominio por semelhanca fonetica.",
            "# Confira nome proprio e sigla contra outra fonte antes de usar.",
            "",
        ]
    )


def speech_header(
    meta: Metadata,
    url: str,
    lang: str,
    model: str,
    transcribed: str | None = None,
    step: str | None = None,
    file_name: str | None = None,
    repeats: list[str] | None = None,
    fingerprint: str | None = None,
) -> str:
    """The header of a transcript produced by local speech recognition.

    `repeats` are the lines D-092's search wrote (ingest/repeats.py);
    `fingerprint`, D-099's `sha256 <hex>, <n> bytes` of a local file."""
    return "\n".join(
        [
            "# Transcricao por reconhecimento de fala local, material bruto",
            "#",
            "# NAO FOI TRANSCRITO POR PROVEDOR DE IA. Reconhecimento de fala",
            "# mapeia audio para texto e nao completa lacuna com plausibilidade.",
            f"# Modelo: faster-whisper {model}, idioma {lang}, vad_filter ativo",
            *_step_line(step),
            f"# Titulo: {meta.title}",
            f"# Canal: {meta.channel}",
            f"# Publicado: {meta.published}",
            f"# Arquivo: {file_name}" if file_name else f"# URL: {url}",
            *([f"# Impressao digital: {fingerprint}"] if file_name and fingerprint else []),
            f"# Transcrito em: {transcribed or _today()}",
            "#",
            *START_OF_SEGMENT,
            "#",
            "# TRES LIMITACOES MEDIDAS:",
            "# 1. Erro fonetico em termo de dominio. Sigla, nome de agencia,",
            "#    nome de norma e nome de companhia sao os mais afetados.",
            "#    Confira contra outra fonte antes de usar.",
            "# 2. Trecho sem fala pode gerar texto inventado. O vad_filter",
            "#    reduz isso e nao elimina. Frase curta e generica isolada,",
            "#    perto de vinheta ou musica, e suspeita.",
            "# 3. Em arquivo longo, um trecho pode sair duas vezes, e o que foi",
            "#    dito ali se perde. O trecho repetido e procurado e listado abaixo.",
            *(repeats if repeats is not None else []),
            "",
        ]
    )


def file_header(file_name: str, title: str, converted: str | None = None) -> str:
    """The header of a caption converted from a .srt or .vtt the user already had."""
    return "\n".join(
        [
            "# Legenda convertida de arquivo, material bruto para ingestao",
            "#",
            f"# Titulo: {title}",
            f"# Arquivo: {file_name}",
            f"# Convertido em: {converted or _today()}",
            "#",
            *END_OF_CUE,
            "",
        ]
    )
