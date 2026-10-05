"""The PyInstaller entry point for the standalone executable (D-052).

The executable is `transcript-normalizer` itself: no arguments on a terminal
opens the menu (D-051), and runs/ and packs/ live in the documents directory
(D-052), because the package sees `sys.frozen` and moves them there.
"""

import sys

from transcript_normalizer.cli import main

sys.exit(main())
