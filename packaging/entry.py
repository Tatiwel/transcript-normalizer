"""The PyInstaller entry point for the standalone executable (D-052).

The executable is `transcript-normalizer` itself: no arguments on a terminal
opens the menu (D-051), and runs/ and packs/ live in the documents directory
(D-052), because the package sees `sys.frozen` and moves them there.

The `full` build also carries an ffmpeg binary inside the bundle. Programs find
ffmpeg on PATH, so the bundle's folder is put first on it before anything runs.
"""

import os
import sys

if getattr(sys, "frozen", False):
    bundle = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    os.environ["PATH"] = bundle + os.pathsep + os.environ.get("PATH", "")

from transcript_normalizer.cli import main  # noqa: E402

sys.exit(main())
