# Frontend Implementation Plan — Issue 4 Chat UI

## What we're building

The React frontend for the EvidentRAG query pipeline. Three-zone layout: collapsible sidebar (query history), center chat panel (input + streaming answers + citation badges), right evidence panel (collapsed, expands on citation click). Connects to the fully-implemented backend via `POST /api/v1/queries` + `GET /api/v1/queries/{id}/events` (SSE).

## Decisions from Grilling Session

| Decision | Choice |
|---|---|
| Layout | 3-zone: collapsible `Sidebar` (left) + chat panel (center) + evidence `Sheet` (right, hidden by default) |
| Evidence panel | Collapsed until a `[1]` citation badge is clicked |
| Streaming UX | Optimistic — user message appears immediately, status progresses Routing → Retrieving → Generating (sentences append live), `done` replaces with structured citations |
| State management | Local `useState` for streaming; React Query for history list + past answer fetches |
| Citation markers | Inline `Badge` superscripts `[1]` `[2]` after each sentence, only after `done`. Plain text during streaming |
| Citation numbering | Per-answer first-appearance order (UUID → display index) |
| SSE client | Native `EventSource` with per-event-type `addEventListener` |
| History loading | Click sidebar item → React Query fetches `GET /answer` → renders as completed message |

---

## Existing Inventory

### shadcn UI components already installed

Chat-relevant: `Message`, `MessageGroup`, `MessageContent`, `MessageHeader`, `MessageFooter`, `Bubble`, `BubbleGroup`, `BubbleContent`, `MessageScroller`, `MessageScrollerProvider`, `Marker`, `MarkerContent`, `Sidebar` (full suite), `Sheet`, `Badge`, `Card`, `ScrollArea`, `Skeleton`, `Spinner`, `Button`, `Textarea`, `Separator`.

### Routing & providers

`react-router` with `BrowserRouter` is in [main.tsx](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/main.tsx). Single route renders [home.tsx](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/pages/home.tsx) (placeholder). `ThemeProvider` and `TooltipProvider` already wrap the app.

### Vite proxy

[vite.config.ts](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/vite.config.ts) proxies `/api` and `/events` to `http://localhost:8000`. No CORS issues in dev.

---

## SSE Event Contracts (from backend)

The pipeline publishes these events to `query:{query_id}:events` via Redis Pub/Sub. The SSE endpoint delivers them as named events:

| Event | Data shape | When |
|---|---|---|
| `route_selected` | `{ route: "simple" }` | After ARAG Router classifies |
| `retrieving` | `{ status: "retrieving" }` | During hybrid retrieval |
| `generating` | `{ sentence: "..." }` | Per completed sentence from the JSON stream parser |
| `done` | `{ id, query_id, full_text, sentences: [{sentence_index, sentence_text, evidence_ids}], evidence: [{id, content}] }` | Pipeline complete |
| `error` | `{ message: "..." }` | Terminal failure |

> [!NOTE]
> The `done` payload includes `evidence` but only with `id` and `content` (from [query_pipeline.py L176-181](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/application/query_pipeline/query_pipeline.py#L176-L181)). For full evidence detail (`context_header`, `document_title`, `document_slug`, `page`), we fetch via `GET /api/v1/queries/{id}/answer` which joins through the DB relationships.

---

## Proposed Changes

### 1. Types & API Client

#### [NEW] `src/lib/types.ts`

TypeScript types mirroring the backend Pydantic schemas:

```typescript
// Matches QueryResponse from server
interface QuerySummary {
  id: string
  query_text: string
  selected_route: string
  status: "pending" | "running" | "completed" | "failed"
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

// Matches SentenceTraceResponse
interface SentenceTrace {
  sentence_index: number
  sentence_text: string
  evidence_ids: string[]
}

// Matches EvidenceResponse (full, from GET /answer)
interface Evidence {
  id: string
  content: string
  context_header: string
  document_title: string
  document_slug: string
  page: number
}

// Matches AnswerResponse
interface AnswerDetail {
  id: string
  query_id: string
  full_text: string
  sentences: SentenceTrace[]
  evidence: Evidence[]
}

// SSE event data shapes
interface RouteSelectedEvent { route: string }
interface RetrievingEvent { status: string }
interface GeneratingEvent { sentence: string }
interface DoneEvent {
  id: string
  query_id: string
  full_text: string
  sentences: SentenceTrace[]
  evidence: { id: string; content: string }[]
}
interface ErrorEvent { message: string }
```

#### [NEW] `src/lib/api.ts`

Plain `fetch` functions + React Query hooks:

- `postQuery(queryText: string): Promise<QuerySummary>` — `POST /api/v1/queries`.
- `fetchQueryHistory(): Promise<QuerySummary[]>` — `GET /api/v1/queries`.
- `fetchAnswer(queryId: string): Promise<AnswerDetail>` — `GET /api/v1/queries/{id}/answer`. Returns the full `AnswerResponse` with joined evidence.
- `useQueryHistory()` — React Query `useQuery` wrapping `fetchQueryHistory`. Refetches on window focus.
- `useAnswer(queryId: string | null)` — React Query `useQuery` wrapping `fetchAnswer`. Enabled only when `queryId` is non-null and the query status is `completed`.

---

### 2. SSE Streaming Hook

#### [NEW] `src/hooks/use-query-stream.ts`

Custom hook managing the full query lifecycle:

**State:**
```typescript
type StreamPhase = "idle" | "routing" | "retrieving" | "generating" | "done" | "error"

interface StreamState {
  phase: StreamPhase
  queryId: string | null
  route: string | null
  streamedSentences: string[]       // accumulated during generating
  donePayload: DoneEvent | null     // set when done arrives
  errorMessage: string | null
}
```

**Behavior:**
1. `submit(queryText: string)` — calls `postQuery`, sets `phase: "routing"`, opens `EventSource` to `/api/v1/queries/{id}/events`.
2. `route_selected` → sets `phase: "routing"`, stores route name.
3. `retrieving` → sets `phase: "retrieving"`.
4. `generating` → sets `phase: "generating"`, appends sentence to `streamedSentences`.
5. `done` → sets `phase: "done"`, stores `donePayload`, closes `EventSource`.
6. `error` → sets `phase: "error"`, stores `errorMessage`, closes `EventSource`.
7. Cleanup: closes `EventSource` on unmount.

**Returns:** `{ state, submit, reset }`.

---

### 3. Chat Message Model

#### Part of `src/components/chat.tsx` (internal state)

```typescript
interface ChatMessage {
  id: string                        // query UUID or generated client ID
  role: "user" | "assistant"
  content: string                   // user query text, or assembled answer text
  status: StreamPhase               // idle for user messages, streaming phase for assistant
  route: string | null              // "simple" badge
  streamedSentences: string[]       // live sentences during generating
  answer: AnswerDetail | null       // full structured answer (from done + GET /answer fetch)
}
```

Messages array managed via `useState<ChatMessage[]>`. On submit:
1. Push user message `{ role: "user", content: queryText }`.
2. Push assistant placeholder `{ role: "assistant", status: "routing" }`.
3. SSE events update the assistant message in-place.
4. On `done`, fire `fetchAnswer(queryId)` to get full evidence detail, then set `answer` on the assistant message.

---

### 4. Page Layout

#### [MODIFY] `src/main.tsx`

- Add `QueryClientProvider` wrapping the app (from `@tanstack/react-query`).

#### [MODIFY] `src/pages/home.tsx`

Three-zone layout using existing components:

```
┌──────────┬────────────────────────┬──────────────┐
│          │                        │              │
│ Sidebar  │     Chat Panel         │  Evidence    │
│ (query   │  (MessageScroller +    │  Panel       │
│  history)│   input)               │  (Sheet,     │
│          │                        │   hidden)    │
│          │                        │              │
└──────────┴────────────────────────┴──────────────┘
```

- `SidebarProvider` + `Sidebar` (left) — contains the `QueryHistorySidebar` component.
- Center — contains the `Chat` component.
- `Sheet` (right, `side="right"`) — contains the `EvidencePanel` component. Controlled open state driven by `selectedEvidenceId`.

---

### 5. Components

#### [NEW] `src/components/query-history-sidebar.tsx`

- Uses `useQueryHistory()` to fetch past queries.
- Renders each query as a sidebar menu item showing truncated `query_text` and a status badge.
- Clicking a query calls `onSelectQuery(queryId)` prop.
- "New Query" button at the top resets the chat.
- Shows `Skeleton` loaders while fetching.

#### [NEW] `src/components/chat.tsx`

Main chat component. Uses `useQueryStream` hook.

- **Message feed**: wraps in `MessageScrollerProvider` + `MessageScroller` for auto-scroll.
  - User messages: `Message` + `Bubble` (aligned end, `variant="default"`).
  - Assistant messages: `Message` + `Bubble` (aligned start, `variant="secondary"`).
    - Shows route `Badge` (e.g., "Simple") in `MessageHeader`.
    - During `routing` / `retrieving`: shows `Spinner` + status text.
    - During `generating`: renders accumulated `streamedSentences` as plain text paragraphs.
    - After `done` + answer fetch: renders each sentence from `answer.sentences` with inline citation `Badge` markers `[1]` `[2]`.
    - On `error`: renders error message with destructive styling.

- **Input area**: `Textarea` + `Button` at the bottom. Disabled while a query is in flight (`phase !== "idle" && phase !== "done" && phase !== "error"`).

- **Citation badge click handler**: builds a per-answer UUID→index map (first-appearance order across all sentences), sets `selectedEvidenceId` state, which opens the evidence `Sheet`.

#### [NEW] `src/components/evidence-panel.tsx`

Right-side `Sheet` component:

- Controlled by `open` / `onOpenChange` props driven by `selectedEvidenceId !== null`.
- When open, shows the selected evidence card:
  - Document title + page number in `SheetHeader`.
  - Context header as muted subheading.
  - Full evidence content text in `SheetDescription` / body.
- Below the selected card, lists all other evidence for the current answer as smaller cards (numbered `[1]`, `[2]`, etc.), allowing the user to browse without closing.
- Uses `ScrollArea` for long evidence text.

---

### 6. Evidence Index Mapping

Utility function in `src/lib/evidence-utils.ts`:

```typescript
function buildEvidenceIndexMap(sentences: SentenceTrace[]): Map<string, number> {
  const map = new Map<string, number>()
  let index = 1
  for (const sentence of sentences) {
    for (const evidenceId of sentence.evidence_ids) {
      if (!map.has(evidenceId)) {
        map.set(evidenceId, index++)
      }
    }
  }
  return map
}
```

Returns a stable `UUID → [1]` mapping based on first-appearance order. Used by both `chat.tsx` (rendering badges) and `evidence-panel.tsx` (numbering cards).

---

## File Summary

| File | Action | Purpose |
|---|---|---|
| `src/lib/types.ts` | NEW | TypeScript types for API responses and SSE events |
| `src/lib/api.ts` | NEW | Fetch functions + React Query hooks |
| `src/lib/evidence-utils.ts` | NEW | UUID → display index mapping |
| `src/hooks/use-query-stream.ts` | NEW | SSE streaming lifecycle hook |
| `src/components/query-history-sidebar.tsx` | NEW | Sidebar with query history list |
| `src/components/chat.tsx` | NEW | Chat message feed + input + citation badges |
| `src/components/evidence-panel.tsx` | NEW | Right Sheet with evidence detail cards |
| `src/pages/home.tsx` | MODIFY | 3-zone layout wiring |
| `src/main.tsx` | MODIFY | Add `QueryClientProvider` |

## Verification Plan

### Automated Tests

```bash
cd client && npm run typecheck
cd client && npm test
```

- `src/lib/__tests__/evidence-utils.test.ts` — unit tests for `buildEvidenceIndexMap` (empty input, single sentence, multiple sentences with shared evidence IDs, ordering).
- `src/hooks/__tests__/use-query-stream.test.ts` — mock `EventSource`, verify state transitions through all phases.
- `src/lib/__tests__/api.test.ts` — mock `fetch`, verify request shapes and response parsing.

### Manual Verification

1. Start backend + worker: `scripts/dev-backend.ps1` (or `docker compose up postgres qdrant redis` + `uv run uvicorn`).
2. Start frontend: `scripts/dev-frontend.ps1` (or `cd client && npm run dev`).
3. Open `http://localhost:3000`:
   - Type a query → route badge appears → "Retrieving..." → sentences stream in → citation badges render.
   - Click a `[1]` badge → evidence panel slides in from right → shows document title, page, context header, content.
   - Click a different past query in the sidebar → its completed answer loads with citations.
   - Submit a query that fails → error message renders inline.

### Pre-commit Checks

| Check | Command |
|---|---|
| Type check | `npm run typecheck` |
| Tests | `npm test` |
| Lint & Format | `npm run check` then `npm run fix` |
