# Agent skills

## Issue tracker

Issues live as markdown files under `.scratch/<feature-slug>/`. See `docs/agents/issue-tracker.md`.

## Triage labels

Default canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

## Domain docs

Single-context layout: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.

# Pre-commit checks

Run these before considering work complete:

## Server (`server/`)

| Check | Command |
|---|---|
| Type check | `npx basedpyright` |
| Tests | `uv run pytest` |
| Lint | `uv run ruff check . --fix` |
| Format | `uv run ruff format .` |

## Client (`client/`)

| Check | Command |
|---|---|
| Type check | `npm run typecheck` |
| Tests | `npm test` |
| Lint & Format | `npm run check` then `npm run fix` |

### Folder structure

Tests live in `__tests__/` directories co-located with the module they test:

```
src/
├── lib/
│   ├── __tests__/
│   │   └── utils.test.ts
│   └── utils.ts
├── components/
│   ├── __tests__/
│   │   └── Button.test.tsx
│   └── Button.tsx
└── hooks/
    ├── __tests__/
    │   └── useAuth.test.ts
    └── useAuth.ts
```

Test files use the `.test.ts` or `.test.tsx` extension. Configuration is in `vitest.config.ts`.
