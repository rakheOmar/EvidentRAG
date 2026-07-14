# Agent rules for this repo

## Leading words

- **Relentless** — dig until you have the answer. Search the codebase, read the files,
  run the commands. Never offload legwork to the user.
- **Tight** — every change is minimal, idiomatic, and follows existing patterns.
  No dead code, no commented-out code, no renamed-but-unused variables, no extra files.
- **Predictable** — the same process every run. No skipping steps.

## Workflow

### 1. Understand
Read every file relevant to the request until the problem or intent is clear enough
to plan. A clear understanding is one where you can list every file that needs to
change before you start.

### 2. Plan
For any change touching 3+ files or introducing a new concept, present the plan
to the user before coding. For trivial changes (1-2 files, routine pattern), proceed.

### 3. Implement
Write the code. Stay tight — touch only what the plan calls for. Follow the repo's
conventions: existing libraries, same typing style, same import style.

### 4. Verify
Run every pre-commit check (see below). Every one must pass. If a check fails,
fix the issue — do not move on, do not ask the user.

### 5. Review
Review your diff against the completion criteria before reporting done:
- All requested changes addressed
- No unintended changes (stale imports, extra whitespace, etc.)
- All pre-commit checks pass
- No secrets or debug artifacts committed

## When to ask vs. act

| Situation | Response |
|---|---|
| Request is clear and within scope | Act immediately |
| Request is ambiguous or incomplete | Ask one clarifying question, then propose an approach |
| Request is clearly out of scope | Say so and suggest alternatives |
| You get stuck (2+ failed attempts at the same thing) | Report the blocker with what you tried and ask for guidance |

## Dev server

A background terminal runs all three services continuously, with each one tee'd
to its own log file:

| Service | Log file |
|---|---|
| Client (Vite dev server) | `logs/frontend.log` |
| Server (FastAPI + uvicorn) | `logs/backend.log` |
| Worker (ARQ task queue) | `logs/worker.log` |

All logs live under `C:\Users\rakhe\Desktop\Code\Projects\RAG\logs`.

## Pre-commit checks

Run these before considering work complete (step 4 above).

### Server (`server/`)

| Check | Command |
|---|---|
| Type check | `npx basedpyright` |
| Tests | `uv run pytest` |
| Lint | `uv run ruff check . --fix` |
| Format | `uv run ruff format .` |

### Client (`client/`)

| Check | Command |
|---|---|
| Type check | `npm run typecheck` |
| Tests | `npm test` |
| Lint & Format | `npm run fix` then `npm run check` |

## Reference

### Issue tracker
Issues are markdown files under `.scratch/<feature-slug>/`.
Full docs: `docs/agents/issue-tracker.md`.

### Triage labels
Canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`. Full docs: `docs/agents/triage-labels.md`.

### Domain docs
Single-context layout: `CONTEXT.md` + `docs/adr/` at repo root.
Full docs: `docs/agents/domain.md`.
