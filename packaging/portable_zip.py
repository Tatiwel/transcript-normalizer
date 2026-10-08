"""The portable zip of the Windows full build (D-070).

    python packaging/portable_zip.py <onedir folder> <zip>

The zip holds one folder, named like the onedir folder: the program, with
portable.txt beside it and an empty data/ folder, which is where a portable
program keeps everything. Written with zipfile so the empty folder is kept,
which PowerShell's Compress-Archive would drop.
"""

import sys
import zipfile
from pathlib import Path


def main(folder: str, target: str) -> None:
    folder = Path(folder)
    note = Path(__file__).with_name("portable.txt")
    top = folder.name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(folder.rglob("*")):
            name = f"{top}/{path.relative_to(folder).as_posix()}"
            archive.write(path, name + ("/" if path.is_dir() else ""))
        archive.write(note, f"{top}/portable.txt")
        archive.writestr(zipfile.ZipInfo(f"{top}/data/"), "")


if __name__ == "__main__":
    main(*sys.argv[1:])
