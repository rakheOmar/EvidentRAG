# Implementation Plan — Multi-hop, Comparison, and Aggregation Routes

Extend the ARAG Router to classify Queries into all four Routes (Simple, Multi-hop, Comparison, Aggregation) and implement the retrieval logic for the three new routes.

## Design Decisions (from grilling)

| Decision | Choice |
|---|---|
| Router location | Separate `AragRouter` class in `arag_router.py`, injected into `QueryPipeline` |
| LLM invocation | New non-streaming `generate` method on `LLMClient`; router calls it with the utility model |
| Model | Utility LLM (Gemini 2.5 Flash) — per CONTEXT.md |
| Router output schema | `{"route": "...", "sub_queries": [...]}` — unified for all routes |
| Multi-hop chaining | Truly sequential: each hop retrieves → generates intermediate answer → feeds it as context to next hop |
| Multi-hop SSE | New `hop_progress` event: `{"hop": 1, "sub_query": "...", "intermediate_answer": "..."}` |
| Comparison retrieval | Parallel via `asyncio.gather`, deduplicate evidence, single generation pass |
| Aggregation strategy | Multi-pass reformulation: router generates diverse reformulations in `sub_queries`, each gets its own retrieval pass, merge + deduplicate, then summarize |
| Route SSE event | New `route_selected` event: `{"route": "...", "sub_queries": [...]}` per PRD contract |
| Classification failure | Graceful fallback to Simple route with warning log |
| Persistence | New `sub_queries` JSONB column on `Query` model |
| Client route display | `route` and `subQueries` fields on `EvidentChatMessage`, badge via shadcn `Badge` in `thread.tsx` |

---

## Proposed Changes

### Server — Infrastructure

---

#### [MODIFY] `server/app/infrastructure/llm/llm.py`

Add a non-streaming `generate` method:
- Accepts `messages: list[dict]` and optional `model: str`
- Makes a single POST to `/chat/completions` (no `stream: True`)
- Returns the full response text as a `str`
- Includes wide-event logging (model, prompt_messages, duration_ms, outcome)

---

### Server — Domain / Application

---

#### [NEW] `server/app/application/query_pipeline/arag_router.py`

New `AragRouter` class:
- Constructor accepts `llm_client: LLMClient`
- `async def classify(self, query_text: str) -> RoutingResult`
  - Builds a system prompt instructing Flash to return `{"route": "simple|multi_hop|comparison|aggregation", "sub_queries": [...]}`
  - Calls `llm_client.generate(messages, model=utility_model)`
  - Parses JSON response
  - On failure (timeout, malformed JSON, invalid route): logs warning, returns `RoutingResult(route="simple", sub_queries=[])`
- `RoutingResult` dataclass: `route: str`, `sub_queries: list[str]`

#### [MODIFY] `server/app/application/query_pipeline/query_pipeline.py`

Major refactor of the `run` method:
1. **Classification step**: Call `self._arag_router.classify(query.query_text)` at the start
2. **Persist route**: Set `query.selected_route` and `query.sub_queries` on the DB model
3. **Publish `route_selected`** SSE event: `{"route": "...", "sub_queries": [...]}`
4. **Dispatch to route handler** based on classification:
   - `"simple"` → existing `_run_simple_route` (unchanged)
   - `"multi_hop"` → new `_run_multi_hop_route`
   - `"comparison"` → new `_run_comparison_route`
   - `"aggregation"` → new `_run_aggregation_route`

New `__init__` parameter: `arag_router: AragRouter | None = None`

**`_run_multi_hop_route(session, query, sub_queries, wide_event)`**:
- For each sub-query (sequentially):
  - Publish `content_parts` reasoning: `"Multi-hop step {i}/{n}: Retrieving for '{sub_query}'..."`
  - Embed sub-query → hybrid search → rerank → stage candidates
  - Generate intermediate answer via Generation LLM, with previous intermediate answers as context
  - Publish `hop_progress` event: `{"hop": i, "sub_query": "...", "intermediate_answer": "..."}`
- Final generation pass over all collected evidence with full chain context
- Persist answer + segments via existing `_persist_segments`

**`_run_comparison_route(session, query, sub_queries, wide_event)`**:
- Run retrieval for all entity sub-queries in parallel (`asyncio.gather`)
- Deduplicate evidence across entity pools
- Stage all candidates with entity-tagged stages (e.g., `"dense:entity_0"`, `"fused:entity_1"`)
- Generate comparison answer with a comparison-specific prompt
- Persist answer + segments

**`_run_aggregation_route(session, query, sub_queries, wide_event)`**:
- Run retrieval for all reformulated sub-queries in parallel (`asyncio.gather`)
- Merge and deduplicate all evidence
- Rerank the merged pool with a higher `top_n` (10)
- Generate summary with an aggregation-specific prompt
- Persist answer + segments

---

### Server — Database

---

#### [MODIFY] `server/app/infrastructure/db/models.py`

Add to `Query` model:
```python
sub_queries: Mapped[list] = mapped_column(
    JSONB, nullable=False, default=list, server_default="[]"
)
```

Update `selected_route` to allow the new route values (the existing CHECK constraint `ck_queries_status` only constrains `status`, not `selected_route`, so no constraint change needed).

#### [MODIFY] `server/app/api/schemas/queries.py`

Add `sub_queries: list[str]` field to `QueryResponse`.

---

### Client

---

#### [MODIFY] `client/src/lib/types.ts`

- Extend `QueryRoute`: `"simple" | "multi_hop" | "comparison" | "aggregation"`
- Update `RouteSelectedEvent`: add `sub_queries: string[]`
- Add `HopProgressEvent`: `{ hop: number; sub_query: string; intermediate_answer: string }`
- Add `route?: string` and `subQueries?: string[]` to `EvidentChatMessage`

#### [MODIFY] `client/src/hooks/use-evident-runtime.ts`

- Add `route_selected` SSE event listener:
  - Calls `updateAssistantMessage` to set `route` and `subQueries` on the assistant message
- Add `hop_progress` SSE event listener:
  - Appends hop data to the assistant message's reasoning content parts

#### [MODIFY] `client/src/hooks/use-query-stream.ts`

- Update `route_selected` listener to capture `sub_queries` from the event payload
- Add `subQueries` to `StreamState`

#### [MODIFY] `client/src/components/assistant-ui/thread.tsx`

- In `AssistantMessage`, render a route badge (using shadcn `Badge` component) above the message content:
  - Color-coded: Simple (default), Multi-hop (blue), Comparison (purple), Aggregation (green)
  - Label: `"Simple"`, `"Multi-hop"`, `"Comparison"`, `"Aggregation"`
- For Multi-hop, render sub-queries and intermediate answers in an expandable Accordion below the badge

---

## Verification Plan

### Automated Tests

| Area | Command |
|---|---|
| Server type check | `npx basedpyright` |
| Server tests | `uv run pytest` |
| Server lint | `uv run ruff check . --fix` |
| Server format | `uv run ruff format .` |
| Client type check | `npm run typecheck` |
| Client tests | `npm test` |
| Client lint | `npm run check` then `npm run fix` |

### New Tests to Write

- `test_arag_router.py`: Unit tests for `AragRouter.classify` with mocked LLM responses (valid classification, malformed JSON fallback, timeout fallback)
- Update `test_query_pipeline.py`: Tests for each route handler with fake dependencies
- Client: Update `use-evident-runtime.test.ts` for `route_selected` and `hop_progress` event handling

### Manual Verification

- Start with `docker compose up`
- Submit "What is RAG?" → verify Simple badge
- Submit "What causes hallucinations in LLMs, and how does RAG address them?" → verify Multi-hop badge + intermediate steps
- Submit "Compare dense retrieval and sparse retrieval" → verify Comparison badge
- Submit "Give me an overview of the main themes in these documents" → verify Aggregation badge
