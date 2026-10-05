# Third-party software in the executables

The Python package (`pip install`) contains only this project's code, under the MIT license (`LICENSE`); its dependencies are installed separately by pip, each under its own license. The standalone executables (D-052) are different: PyInstaller copies a Python interpreter and every dependency into one file, so they *distribute* the software below. This file is the notice for that.

## ffmpeg (the `full` executables for Windows and Linux)

- **What:** the `ffmpeg` program, bundled at the top of the executable and put first on `PATH` by `packaging/entry.py`.
- **Build:** the static **LGPL** builds of [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds): `ffmpeg-master-latest-win64-lgpl.zip` and `ffmpeg-master-latest-linux64-lgpl.tar.xz`. The GPL builds of the same project are not used: they would put the executable under the GPL.
- **License:** GNU Lesser General Public License, version 2.1 or later ([text](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html)).
- **Source:** FFmpeg's own source is at <https://git.ffmpeg.org/ffmpeg.git>, and the scripts that produce the build are at <https://github.com/BtbN/FFmpeg-Builds>. Each build records the exact FFmpeg revision it was made from (`ffmpeg -version`, first line). The release workflow prints that line in its log. Pin `FFMPEG_BUILD` in `.github/workflows/release.yml` to a dated autobuild tag to make a release reproducible.
- **macOS:** BtbN publishes no macOS LGPL build, so the macOS `full` executable carries no ffmpeg.

Nothing in this project calls `ffmpeg` directly. `fetch` downloads audio without converting it, and faster-whisper decodes audio through PyAV, which carries its own FFmpeg libraries (also LGPL). The binary is there for yt-dlp and for anything that looks for `ffmpeg` on `PATH`.

## Python packages in the executables

| package | in | license |
|---|---|---|
| Python (CPython) | both | PSF License |
| rapidfuzz | both | MIT |
| PyYAML | both | MIT |
| platformdirs | both | MIT |
| yt-dlp | both | Unlicense |
| curl_cffi (with curl-impersonate) | both | MIT |
| rich | both | MIT |
| faster-whisper | full | MIT |
| CTranslate2 | full | MIT |
| ONNX Runtime | full | MIT |
| PyAV (with FFmpeg libraries) | full | BSD-3-Clause; the FFmpeg libraries are LGPL-2.1+ |
| tokenizers, huggingface_hub | full | Apache-2.0 |
| NumPy | full | BSD-3-Clause |

Their transitive dependencies (certifi, requests and the like) carry permissive licenses of their own; PyInstaller copies their license files into the executable where the packages ship them.

## Not bundled

The Whisper model weights are not in any executable. faster-whisper downloads the model you choose (`--model`, default `medium`) on first use, from Hugging Face, into its cache. The weights are released by OpenAI under the MIT license. The `full` executable therefore needs an internet connection the first time it transcribes.
