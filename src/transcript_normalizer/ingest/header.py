"""The provenance header of a `legenda.txt`.

The header is what the core reads: `core.text.parse_caption` skips these `#`
lines and every line after them is `m:ss text`. The wording stays in Portuguese
because `fixtures/R2Qgz8tFWVI/legenda.txt` is the reference for this format and
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


def _today() -> str:
    return date.today().isoformat()


def caption_header(
    meta: Metadata, url: str, source: str, lang: str, downloaded: str | None = None
) -> str:
    """The header of a caption taken from the platform. `source` is manual/automatica."""
    return "\n".join(
        [
            "# Legenda de video, material bruto para ingestao",
            "#",
            "# NAO E CONHECIMENTO AUTORADO. Nao carregue isto em conhecimento/.",
            "# Legenda obtida da plataforma, sem transcricao por IA.",
            f"# Origem da legenda: {source} ({lang})",
            f"# Titulo: {meta.title}",
            f"# Canal: {meta.channel}",
            f"# Publicado: {meta.published}",
            f"# URL: {url}",
            f"# Baixado em: {downloaded or _today()}",
            "#",
            "# Cada linha comeca com o timestamp mm:ss. O timestamp e a",
            "# procedencia de qualquer afirmacao extraida daqui, do mesmo modo",
            "# que documento e pagina sao a procedencia de um PDF.",
            "#",
            "# Legenda automatica erra termo de dominio por semelhanca fonetica.",
            "# Confira nome proprio e sigla contra outra fonte antes de citar.",
            "",
        ]
    )


def speech_header(
    meta: Metadata, url: str, lang: str, model: str, transcribed: str | None = None
) -> str:
    """The header of a transcript produced by local speech recognition."""
    return "\n".join(
        [
            "# Transcricao por reconhecimento de fala local, material bruto",
            "#",
            "# NAO E CONHECIMENTO AUTORADO. Nao carregue isto em conhecimento/.",
            "# NAO FOI TRANSCRITO POR PROVEDOR DE IA. Reconhecimento de fala",
            "# mapeia audio para texto e nao completa lacuna com plausibilidade.",
            f"# Modelo: faster-whisper {model}, idioma {lang}, vad_filter ativo",
            f"# Titulo: {meta.title}",
            f"# Canal: {meta.channel}",
            f"# Publicado: {meta.published}",
            f"# URL: {url}",
            f"# Transcrito em: {transcribed or _today()}",
            "#",
            "# Cada linha comeca com o timestamp mm:ss. O timestamp e a",
            "# procedencia de qualquer afirmacao extraida daqui.",
            "#",
            "# DUAS LIMITACOES MEDIDAS:",
            "# 1. Erro fonetico em termo de dominio. Sigla, nome de agencia,",
            "#    nome de norma e nome de companhia sao os mais afetados.",
            "#    Confira contra outra fonte antes de citar.",
            "# 2. Trecho sem fala pode gerar texto inventado. O vad_filter",
            "#    reduz isso e nao elimina. Frase curta e generica isolada,",
            "#    perto de vinheta ou musica, e suspeita.",
            "",
        ]
    )
