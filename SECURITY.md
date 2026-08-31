# Security and privacy

This is pre-alpha local software and should not be exposed to a network or trusted with secrets.

## Supported deployment boundary

- Bind the application and model runtime to loopback only.
- Keep operating-system full-disk encryption enabled.
- Do not put customer passwords, recovery keys, license keys, payment data, or unrelated customer files in a case.
- Do not enable telemetry or cloud model fallback.
- Treat exported case summaries as customer-sensitive records.

The browser API uses a random per-launch token, rejects untrusted Host headers, serves no CORS policy, and sets restrictive browser headers. These controls reduce localhost abuse; they do not make the alpha suitable for shared or hostile machines.

## Reporting a vulnerability

Do not open a public issue containing customer data, secrets, exploit details, or the source conversation. Contact the repository owner privately and include a minimal synthetic reproduction.

## Repository exclusions

Never commit runtime databases, case exports, logs, prompts containing customer data, licensed manuals without redistribution rights, embeddings, model weights, `.env` files, or the raw Discord transcript.

