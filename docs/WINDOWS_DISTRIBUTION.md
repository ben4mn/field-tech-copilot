# Windows distribution

## Release profiles

### Field Kit Lite

Field Kit Lite is the one-download GitHub Release. It contains a frozen onedir
Python application inside a single Inno Setup executable, llama.cpp CPU x64,
Qwen3-1.7B Q8_0, synthetic starter knowledge, the Visual C++ redistributable,
and all required notices.

The model and runtime are fetched only by the release workflow. Their immutable
URLs, sizes, and SHA-256 hashes live in
`packaging/windows/bundle-lock.json`; model weights are never committed to Git.
The build stops on any mismatch.

The release workflow also:

1. runs lint and all tests on Windows;
2. exercises the frozen executable, SQLite FTS5, knowledge seed, and a real
   structured model turn;
3. silently installs into a temporary directory and tests the installed app;
4. confirms mutable data is outside the installation and survives uninstall;
5. fails if the setup file exceeds 2,000,000,000 bytes;
6. publishes a SHA-256 sidecar, manifest, dependency inventory, and licenses.

The 1.7B model is a packaging and workflow profile, not a claim of diagnostic
quality. A representative gold-set evaluation and trained-technician review are
release gates for any field-ready label.

### Full local AI

The Ollama + Qwen3 8B configuration remains the quality control. Its model is
too large for one GitHub Release asset, so it is intentionally separate. Pull
the model while connected, run `fieldtech doctor`, restart, disconnect all
network interfaces, and complete a saved-case smoke test before field use.

## Build locally on Windows

Install Python 3.11, uv, and Inno Setup 6.7.1, then run from the repository root:

```powershell
uv sync --extra dev --extra package-windows --locked
uv run ruff check .
uv run pytest
uv run pyinstaller --noconfirm --clean packaging/windows/FieldTechCopilot.spec
packaging/windows/prepare-bundle.ps1
dist/FieldTechCopilot/FieldTechCopilot.exe --self-test --model-smoke
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" `
  "/DMyAppVersion=0.2.0-local" packaging/windows/FieldTechCopilot.iss
```

The preparation step downloads about 1.88 GB. It verifies every pinned payload
before copying it into `dist/FieldTechCopilot`.

## Runtime layout

Installed immutable files live under
`%LOCALAPPDATA%\Programs\FieldTechCopilot`. Cases and logs live separately:

```text
%LOCALAPPDATA%\FieldTechCopilot\
  data\fieldtech.db
  logs\launcher.log
  logs\llama-server.log
```

The launcher binds both services to `127.0.0.1`. llama.cpp receives an unused
high port and a random per-session API key. The key is kept in memory and sent
only over loopback. The server web UI and tool execution are disabled.

## Signing

Set the repository secrets `WINDOWS_CERTIFICATE_BASE64` and
`WINDOWS_CERTIFICATE_PASSWORD` to Authenticode-sign both the launcher and final
installer. Without them, the workflow creates an explicitly labeled unsigned
preview. Do not instruct users to bypass SmartScreen or organization policy.

## Clean-machine release checklist

- Verify the installer SHA-256 and Authenticode publisher.
- Install on clean Windows 10 22H2 and current Windows 11 x64 virtual machines.
- Repeat on an older supported x64 CPU with 8 GB RAM.
- Disable Wi-Fi and Ethernet before setup, first launch, case creation, model
  turn, restart, export, and uninstall.
- Confirm no DNS or non-loopback connection attempts.
- Confirm upgrades preserve `%LOCALAPPDATA%\FieldTechCopilot`.
- Confirm uninstall removes immutable program files but preserves user data.
- Run the representative safety and diagnostic gold set.
