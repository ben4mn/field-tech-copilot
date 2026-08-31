# Third-party notices

Field Kit Lite redistributes the following pinned third-party components. Their
license files are included in the installed `licenses` directory and in each
GitHub release. These components are not affiliated with or endorsed by Field
Tech Copilot.

## Qwen3-1.7B-GGUF

- Project: Qwen3-1.7B-GGUF by the Qwen team
- Artifact: `Qwen3-1.7B-Q8_0.gguf` (unmodified)
- Source commit: `90862c4b9d2787eaed51d12237eafdfe7c5f6077`
- SHA-256: `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`
- License: Apache License 2.0
- Source: <https://huggingface.co/Qwen/Qwen3-1.7B-GGUF>

## llama.cpp

- Project: llama.cpp
- Windows CPU x64 build: `b10724`
- Archive SHA-256: `287b320f2b217809e24e0a7459a25e627b8785223080667d9ecf575253ef0762`
- License: MIT
- Source: <https://github.com/ggml-org/llama.cpp/tree/b10724>

The llama.cpp archive also contains LLVM OpenMP runtime components under the
license included as `licenses/LLVM-OpenMP.txt`.

## Microsoft Visual C++ Redistributable

- Component: Visual C++ Redistributable for Visual Studio 2015–2026, x64
- Installer SHA-256: `cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b`
- Microsoft terms: <https://visualstudio.microsoft.com/license-terms/>
- Download information: <https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist>

## Python application dependencies

The release workflow produces `python-dependencies.txt` from the locked Python
environment. Each package remains subject to its own license and notices.
