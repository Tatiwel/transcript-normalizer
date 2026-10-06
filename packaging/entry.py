"""The PyInstaller entry point for the standalone executable (D-052).

The executable is `transcript-normalizer` itself: no arguments on a terminal
opens the menu (D-051), and runs/ and packs/ live in the documents directory
(D-052), because the package sees `sys.frozen` and moves them there.

Output is UTF-8 whatever the system's code page (D-059). yt-dlp's messages
carry curly quotes; written through a pipe in cp1252 on Windows (a log, a
redirect) and read back as UTF-8, they showed as a replacement character.
"""

import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from transcript_normalizer.cli import main  # noqa: E402

sys.exit(main())
