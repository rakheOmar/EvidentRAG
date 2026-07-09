# Handoff — EvidentRAG Issue #06: Multi-hop, Comparison, Aggregation Routes

**Created**: 2026-07-06  
**Workspace**: `c:\Users\rakhe\Desktop\Code\Projects\RAG`

---

## Context

EvidentRAG is an Adaptive RAG engine with evidence retrieval memory and sentence-level citation traces. The project has a FastAPI + PostgreSQL + Qdrant + Redis backend and a React/Vite/Tailwind/shadcn frontend.

**Domain glossary**: [CONTEXT.md](file:///C:/Users/rakhe/Desktop/Code/Projects/RAG/CONTEXT.md)  
**PRD**: [.scratch/evidentrag/PRD.md](file:///C:/Users/rakhe/Desktop/Code/Projects/RAG/.scratch/evidentrag/PRD.md)  
**Issue**: [.scratch/evidentrag/issues/06-multi-hop-comparison-aggregation-routes.md](file:///C:/Users/rakhe/Desktop/Code/Projects/RAG/.scratch/evidentrag/issues/06-multi-hop-comparison-aggregation-routes.md)  
**Implementation plan**: [.scratch/evidentrag/plans/06-multi-hop-comparison-aggregation-routes.md](file:///C:/Users/rakhe/Desktop/Code/Projects/RAG/.scratch/evidentrag/plans/06-multi-hop-comparison-aggregation-routes.md)

---

## What happened this session

1. **Codebase exploration** — 4 subagents explored client architecture, client components, server architecture, and server endpoints.

2. **Baseline tests pass** — `uv run pytest`: **81 passed, 15 skipped** (e2e/integration skipped due to no live services).

3. **Implementation plan created** — Detailed plan written after reading the issue, PRD, and relevant source files.

4. **Grilling session** — 10 design questions resolved interactively. All decisions captured in the implementation plan.

5. **Status** — Plan is ready for execution. Not yet started.

---

## Key design decisions (from grilling)

| Decision | Choice |
|---|---|
| Router location | Separate `AragRouter` class in `arag_router.py`, injected into `QueryPipeline` |
| LLM invocation | New non-streaming `generate` method on `LLMClient` |
| Model | Utility LLM (Gemini 2.5 Flash) |
| Router output | Unified `{"route": "...", "sub_queries": [...]}` for all routes |
| Multi-hop | Sequential: retrieve → generate intermediate answer → feed to next hop |
| Multi-hop SSE | New `hop_progress` event with structured data |
| Comparison | Parallel retrieval via `asyncio.gather`, deduplicate, single generation |
| Aggregation | Multi-pass reformulation: router generates diverse reformulations, each gets retrieval, merge + deduplicate, summarize |
| Route SSE | New `route_selected` event per PRD contract |
| Classification failure | Graceful fallback to Simple route |
| Persistence | New `sub_queries` JSONB column on `Query` model |
| Client display | `route`/`subQueries` on `EvidentChatMessage`, shadcn Badge in `thread.tsx` |

---

## Key files to modify

### Server
| File | What |
|---|---|
| `server/app/infrastructure/llm/llm.py` | Add `generate` (non-streaming) method |
| `server/app/application/query_pipeline/arag_router.py` | **NEW** — `AragRouter` class |
| `server/app/application/query_pipeline/query_pipeline.py` | Classification dispatch + 3 new route methods |
| `server/app/infrastructure/db/models.py` | Add `sub_queries` JSONB column to `Query` |
| `server/app/api/schemas/queries.py` | Add `sub_queries` to `QueryResponse` |

### Client
| File | What |
|---|---|
| `client/src/lib/types.ts` | Extend `QueryRoute`, add `HopProgressEvent` |
| `client/src/hooks/use-evident-runtime.ts` | Handle `route_selected` + `hop_progress` SSE events |
| `client/src/hooks/use-query-stream.ts` | Update `route_selected` listener, add `subQueries` to state |
| `client/src/components/assistant-ui/thread.tsx` | Route badge + multi-hop accordion |

---

## Pre-commit checks

### Server (`server/`)
```
npx basedpyright
uv run pytest
uv run ruff check . --fix
uv run ruff format .
```

### Client (`client/`)
```
npm run typecheck
npm test
npm run check && npm run fix
```

---

## Suggested skills

- **tdd** — The issue has clear acceptance criteria; build features test-first
- **codebase-design** — When implementing `AragRouter` and the route handlers, use deep-module design principles
- **shadcn** — For adding the route Badge component to the thread UI
- **logging-best-practices** — The pipeline already uses wide events; maintain that pattern in new route handlers

---

## Gotchas & things to watch

- The `Query.selected_route` column currently defaults to `"simple"` — there is **no** CHECK constraint on it (the CHECK constraint `ck_queries_status` only constrains the `status` column), so new route values will work without a migration
- The existing `_run_simple_route` hardcodes `"Routing Query via Simple Route..."` as the first reasoning part — the new dispatch logic should replace this with route-specific messaging
- The `use-evident-runtime.ts` hook does NOT currently listen for `route_selected` events — this is a new event type
- The `use-query-stream.ts` hook DOES listen for `route_selected` but only reads `route`, not `sub_queries`
- All existing tests pass cleanly — don't break the baseline
