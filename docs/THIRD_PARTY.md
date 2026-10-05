# Third-party software in the executables

The Python package (`pip install`) contains only this project's code, under the MIT license (`LICENSE`); its dependencies are installed separately by pip, each under its own license. The standalone executables (D-052) are different: PyInstaller copies a Python interpreter and every dependency into one file, so they *distribute* the software below. This file is the notice for that.

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
| PyAV (with FFmpeg libraries) | full | BSD-3-Clause; the FFmpeg libraries it carries are LGPL-2.1+ |
| tokenizers, huggingface_hub | full | Apache-2.0 |
| NumPy | full | BSD-3-Clause |

Their transitive dependencies (certifi, requests and the like) carry permissive licenses of their own; PyInstaller copies their license files into the executable where the packages ship them.

## Not bundled

The Whisper model weights are not in any executable. faster-whisper downloads the model you choose (`--model`, default `medium`) on first use, from Hugging Face, into its cache. The weights are released by OpenAI under the MIT license. The `full` executable therefore needs an internet connection the first time it transcribes.
