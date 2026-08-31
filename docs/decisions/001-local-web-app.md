# ADR 001: Local web application with external model runtime

- Status: accepted for MVP
- Date: 2026-08-31

## Context

The application must run offline on a Windows-class laptop, be quick to iterate, and avoid coupling the product to one model. Native desktop packaging is valuable later but would slow initial diagnostic workflow testing.

## Decision

Build a Python/FastAPI service bound to loopback with a bundled zero-build browser UI. Store cases and the initial knowledge index in SQLite. Call a separately installed local inference runtime through a provider interface.

## Consequences

- The same core works on Windows, Linux, and macOS during development.
- Ollama provides the first integration; llama.cpp can be added without changing domain logic.
- The MVP can be tested with a deterministic mock provider.
- Installation is not yet one-click; Windows packaging becomes a field-alpha deliverable.
- Binding beyond loopback is prohibited until authentication and network hardening exist.

