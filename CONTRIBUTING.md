# Contributing

Feedback, bug reports, and ideas are welcome through GitHub issues.

The workflow is:

1. Branch from `main` (one short-lived branch per change).
2. Keep changes small and focused.
3. Run the project checks locally before pushing (format, lint, tests, build).
   See the Setup section below for the exact commands once they are defined.
4. Open a pull request into `main`. CI must pass before merge.

## Setup

The web app lives in `web/` and needs Node 20.19 or newer.

```bash
cd web
npm ci
npm run dev          # local dev server
npm run typecheck && npm test && npm run build   # what CI runs
```

See `web/README.md` for the data layout and the synthetic demo fixture, and
`CLAUDE.md` for anything stack-specific.

## Conventions

- Conventional Commits (for example `feat: ...`, `fix: ...`, `chore: ...`,
  `docs: ...`).
- No em dashes in code, comments, docs, commit messages, or user-facing text.
- See `CLAUDE.md` for the full working rules and `docs/` for design notes and
  decision records.
