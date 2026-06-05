# Docs Index

## Release / Baseline

- `95-release-baseline-freeze-v1.md` — v0.1.0 stable freeze baseline.

## Architecture

- README current architecture section — source layout and module boundaries.

## Reviews

Review records are stored under:

```text
reports/reviews/
```

Key review categories:

- route split reviews
- release smoke reviews
- packaging reviews
- hotfix reviews
- baseline freeze reviews

## Development Rules

- Keep business API route logic under `src/backend/routes/`.
- Keep reusable business logic under `src/backend/services/`.
- Keep infrastructure helpers under `src/backend/infra/`.
- Keep runtime/user data out of Git and release zip.

## Deferred Items

- Prompt caching
- `/api/tree recursive=1` optimization
- packaged GUI/tray manual verification
- logging/caching hardening beyond current quick wins
- real summarize-first / RAG
- Vision/OCR
