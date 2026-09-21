"""Fetching captions from a platform, as an optional extra.

Nothing here is imported by `transcript_normalizer.core`, and nothing here
imports `yt_dlp` or `faster_whisper` at module level, so the engine stays
installable without the ingest extra.
"""

from .header import Metadata, caption_header, speech_header
from .srt import srt_to_lines

__all__ = ["Metadata", "caption_header", "speech_header", "srt_to_lines"]
