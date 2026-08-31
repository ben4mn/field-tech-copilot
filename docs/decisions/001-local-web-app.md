# ADR 001: Local web application with external model runtime

- Status: accepted for MVP
- Date: 2026-08-31

## Context

The application must run offline on a Windows-class laptop, be quick to iterate, and avoid coupling the product to one model. A local browser UI keeps iteration fast while still allowing a native Windows installer to own the application lifecycle.

## Decision

Build a Python/FastAPI service bound to loopback with a bundled zero-build browser UI. Store cases and the initial knowledge index in SQLite. Call a local inference runtime through a provider interface; the Full profile may use a separately installed runtime, while Field Kit Lite launches its pinned bundled runtime.

## Consequences

- The same core works on Windows, Linux, and macOS during development.
- Ollama provides the Full-profile integration; llama.cpp powers the one-file Lite bundle without changing domain logic.
- The MVP can be tested with a deterministic mock provider.
- PyInstaller and Inno Setup can wrap the same local service into a one-click Windows field kit.
- Binding beyond loopback is prohibited until authentication and network hardening exist.
