# Plan: Backend Content Parts + Native Assistant-UI

Branch: `feat/content-parts-backend`
Status: in-progress

## Goal

Migrate the entire chat rendering to native assistant-ui primitives. The backend becomes the source of truth for message content shape, emitting `content_parts` arrays via SSE instead of custom event types. The frontend becomes a thin pass-through with no custom override.

## Key Decisions

| Decision | Choice |
|---|---|
| Custom override | Remove `EvidentAssistantMessage` — use default `AssistantMessage` from `thread.tsx` |
| Backend | Emits `content_parts` events with native part types (reasoning, text, source) |
| SSE events | Only 2 event types: `content_parts` + `done` (with error flag) |
| Reasoning steps | Route selected → Retrieving → Fusing candidates → Reranking candidates → Generating answer (collapsible BrainIcon UI via `group-reasoning`) |
| Generating | Token-level streaming: reasoning("Generating Answer...") + text("<accumulated>") side by side |
| Done | reasoning part removed, only text + source parts remain |
| Sources | Wired via `case "source"` in thread.tsx's GroupedParts switch |
| Evidence panel | Archived (`.archive` suffix), rewire later |
| Convert message | Pass-through (just wraps contentParts in ThreadMessageLike) |
| Replayed threads | `content_parts` added to `GET /queries/{id}/answer` response (backward-compatible) |

## Reasoning Steps in Collapsible UI

```
T1: 🧠 Reasoning ─► "Routing Query via Simple Route..."
T2: 🧠 Reasoning ─► "Retrieving Evidence from Qdrant..."
T3: 🧠 Reasoning ─► "Fusing dense + sparse candidates via RRF..."
T4: 🧠 Reasoning ─► "Reranking top-20 candidates via Cohere..."
T5: 🧠 Reasoning ─► "Generating Answer..."   ← stays open while streaming
    HNSW stands for...                        ← text streams below
T6: [source badge] [source badge]             ← reasoning collapsed, sources shown
```

## Backend Changes

### 1. New file: `server/app/application/query_pipeline/content_parts.py`

Helper module with pure functions:

- `reasoning_part(text: str) -> dict`
- `text_part(text: str) -> dict`
- `source_part(evidence_row) -> dict` — embeds full evidence data in `providerMetadata.evidentrag`
- `answer_content_parts(full_text: str, evidence_list) -> list[dict]` — builds final text + source parts

### 2. Modify `JsonStreamParser` — add `get_accumulated_text()`

Returns all complete sentences joined by space, plus any partial sentence still streaming. Used to emit text parts on every LLM chunk instead of waiting for complete sentences.

### 3. Modify `query_pipeline.py`

**SSE emission changes:**

| Old event | New event | Data |
|---|---|---|
| `route_selected` | `content_parts` | `{"parts": [reasoning_part("Routing Query via Simple Route...")]}` |
| — (new) | `content_parts` | `{"parts": [reasoning_part("Retrieving Evidence from Qdrant...")]}` |
| — (new) | `content_parts` | `{"parts": [reasoning_part("Fusing dense + sparse candidates via RRF...")]}` |
| — (new) | `content_parts` | `{"parts": [reasoning_part("Reranking top-20 candidates via Cohere...")]}` (only if reranker configured) |
| `generating` (xN) | `content_parts` | `{"parts": [reasoning_part("Generating Answer..."), text_part("<accumulated>")]}` |
| `done` | `done` | `{"query_id": "...", "content_parts": [...text + sources], "error": false}` |
| `error` | folded into `done` | `{"query_id": "...", "content_parts": [...], "error": true, "error_message": "..."}` |

**`_generate_and_persist_answer` changes:**

```python
async for chunk in llm_client.generate_stream(messages):
    parser.feed(chunk)
    accumulated = parser.get_accumulated_text()
    await self._publish(query.id, "content_parts", {
        "parts": [
            reasoning_part("Generating Answer..."),
            text_part(accumulated),
        ]
    })
```

### 4. Add `content_parts` to `GET /queries/{id}/answer` response

Backward-compatible addition to `AnswerResponse` schema. Reconstructed from `full_text` + `evidence` via `answer_content_parts()`.

### 5. Remove old event types

Delete `route_selected`, `retrieving`, `generating` event emissions. Remove `ErrorEvent` — folded into `done`.

## Frontend Changes

### 1. Wire `Sources` in `thread.tsx`

```tsx
case "source":
  return <Sources {...part} />;
```

### 2. Update types (`types.ts`)

Remove:
- `RouteSelectedEvent`, `RetrievingEvent`, `GeneratingEvent`, `ErrorEvent`
- `QueryRoute` (no longer needed on message)
- `phase` and `route` from `EvidentChatMessage`
- `AnswerDetail`, `SentenceTrace`, `Evidence` (keep for REST API but remove from message shape)

Add:
```ts
interface ContentPartsEvent {
  parts: ThreadAssistantMessagePart[];
}

interface DoneEvent {
  query_id: string;
  content_parts: ThreadAssistantMessagePart[];
  error: boolean;
  error_message?: string;
}
```

Simplify `EvidentChatMessage`:
```ts
interface EvidentChatMessage {
  contentParts: ThreadAssistantMessagePart[];
  createdAt: Date;
  id: string;
  queryId?: string | null;
  role: "assistant" | "user";
  status: "running" | "complete" | "error";
}
```

### 3. Simplify `convertEvidentMessage` in `message-utils.ts`

Pass-through:
```ts
function convertEvidentMessage(message: EvidentChatMessage): ThreadMessageLike {
  return {
    content: message.contentParts,
    createdAt: message.createdAt,
    id: message.id,
    role: message.role,
    status: toMessageStatus(message.status),
  };
}
```

### 4. Simplify `useEvidentRuntime` in `use-evident-runtime.ts`

- Single `content_parts` event listener replaces `route_selected`/`retrieving`/`generating`
- `done` event listener handles both success and error (via `error` flag)
- `onSwitchToThread` reads `content_parts` from API response

### 5. Simplify `chat-thread.tsx`

```tsx
const Thread: FC = () => <AssistantThread />;
```

### 6. Simplify `chat.tsx`

- Remove evidence panel, `EvidenceSelectionProvider`, `currentAnswer` memo, `EvidentMessagesProvider`
- Remove `ChatLayout` props related to evidence
- Layout just has `<Thread />`

### 7. Archive unused files

Add `.archive` suffix:

| File | New name |
|---|---|
| `evident-assistant-message.tsx` | `evident-assistant-message.archive.tsx` |
| `evident-messages.tsx` | `evident-messages.archive.tsx` |
| `evidence-utils.ts` | `evidence-utils.archive.ts` |
| `evidence-panel.tsx` | `evidence-panel.archive.tsx` |
| `evidence-selection.tsx` | `evidence-selection.archive.tsx` |
| `evident-assistant-message.test.tsx` | `evident-assistant-message.archive.test.tsx` |
| `evidence-utils.test.ts` | `evidence-utils.archive.test.ts` |
| `evidence-panel.test.tsx` | `evidence-panel.archive.test.tsx` |

## Implementation Order (TDD)

### Slice 1: Backend content_parts.py (pure functions)
- **Red**: Write tests for `reasoning_part()`, `text_part()`, `source_part()`, `answer_content_parts()`
- **Green**: Implement the module
- **Seam**: `server/tests/unit/test_content_parts.py`

### Slice 2: Backend JsonStreamParser.get_accumulated_text()
- **Red**: Write tests for partial-token extraction
- **Green**: Add method to `JsonStreamParser`
- **Seam**: `server/tests/unit/test_json_stream_parser.py`

### Slice 3: Frontend types + convertMessage
- **Red**: Write tests for new `convertEvidentMessage()` (pass-through)
- **Green**: Simplify types and converter

### Slice 4: Frontend runtime + Sources wire
- **Red**: Ensure thread renders sources (component test)
- **Green**: Wire `Sources` in thread.tsx, simplify `useEvidentRuntime`

### Slice 5: Backend pipeline emission
- Modify `query_pipeline.py` to emit `content_parts` events
- Verify E2E with manual test

### Slice 6: Frontend cleanup
- Archive unused files
- Clean up `chat.tsx`
- Remove evidence panel

### Slice 7: Backend REST API
- Add `content_parts` to `GET /queries/{id}/answer`
- Verify replayed threads work

## Verification

- [ ] `server`: `uv run pytest` passes
- [ ] `server`: `uv run ruff check . --fix` clean
- [ ] `server`: `npx basedpyright` clean
- [ ] `client`: `npm test` passes
- [ ] `client`: `npm run check` clean
- [ ] `client`: `tsc --noEmit` clean
- [ ] Manual: Submit query → all 5 reasoning steps appear → text streams token-by-token → source badges render → error shows error text

---

Complete assistant-ui Data Contract for ExternalStoreRuntime
All type definitions below are from the actual source at packages/core/src/types/message.ts, packages/core/src/runtime/utils/thread-message-like.ts, and packages/core/src/react/runtimes/external-message-converter.ts on GitHub.
1. ThreadAssistantMessagePart -- the full union type
export type ThreadAssistantMessagePart =
  | TextMessagePart
  | ReasoningMessagePart
  | ToolCallMessagePart
  | SourceMessagePart
  | FileMessagePart
  | ImageMessagePart
  | DataMessagePart
  | GenerativeUIMessagePart;
2. ThreadUserMessagePart -- the full union type
export type ThreadUserMessagePart =
  | TextMessagePart
  | ImageMessagePart
  | FileMessagePart
  | DataMessagePart
  | Unstable_AudioMessagePart;
3. Individual part types
TextMessagePart
export type TextMessagePart = {
  readonly type: "text";
  readonly text: string;
  readonly parentId?: string;
};
Explore
ReasoningMessagePart
export type ReasoningMessagePart = {
  readonly type: "reasoning";
  readonly text: string;
  readonly parentId?: string;
};
SourceMessagePart (discriminated union on sourceType)
export type SourceMessagePart =
  | {
      readonly type: "source";
      readonly sourceType: "url";
      readonly id: string;
      readonly url: string;
      readonly title?: string;
      readonly providerMetadata?: SourceProviderMetadata;
      readonly parentId?: string;
    }
  | {
      readonly type: "source";
      readonly sourceType: "document";
      readonly id: string;
      readonly url?: undefined;
      readonly title: string;
      readonly mediaType: string;
      readonly filename?: string;
      readonly providerMetadata?: SourceProviderMetadata;
      readonly parentId?: string;
    };

export type SourceProviderMetadata = {
  readonly [providerName: string]: ReadonlyJSONObject;
};
ImageMessagePart
export type ImageMessagePart = {
  readonly type: "image";
  readonly image: string;  // "data:image/..." URI, "https://..." URL, or "blob:" URL
  readonly filename?: string;
};
FileMessagePart
export type FileMessagePart = {
  readonly type: "file";
  readonly filename?: string;
  readonly data: string;    // base64 data URL or similar
  readonly mimeType: string;
  readonly parentId?: string;
};
DataMessagePart
export type DataMessagePart<T = any> = {
  readonly type: "data";
  readonly name: string;
  readonly data: T;
};
ToolCallMessagePart
export type ToolCallMessagePart<TArgs = ReadonlyJSONObject, TResult = unknown> = {
  readonly type: "tool-call";
  readonly toolCallId: string;
  readonly toolName: string;
  readonly args: TArgs;
  readonly argsText: string;
  readonly result?: TResult | undefined;
  readonly isError?: boolean | undefined;
  readonly artifact?: unknown;
  readonly timing?: ToolCallTiming;
  readonly mcp?: ToolCallMessagePartMcpMetadata;
  readonly modelContent?: readonly ToolModelContentPart[] | undefined;
  readonly interrupt?: { type: "human"; payload: unknown };
  readonly approval?: {
    readonly id: string;
    readonly approved?: boolean;
    readonly reason?: string;
    readonly isAutomatic?: boolean;
    readonly options?: readonly ToolApprovalOption[];
    readonly optionId?: string;
    readonly resolution?: "cancelled" | "expired";
  };
  readonly parentId?: string;
  readonly messages?: readonly ThreadMessage[];
};
GenerativeUIMessagePart
export type GenerativeUIMessagePart = {
  readonly type: "generative-ui";
  readonly spec: GenerativeUISpec;
  readonly id?: string;
  readonly parentId?: string;
};
Unstable_AudioMessagePart
export type Unstable_AudioMessagePart = {
  readonly type: "audio";
  readonly audio: {
    readonly data: string;
    readonly format: "mp3" | "wav";
  };
};
4. Status types
MessagePartStatus
export type MessagePartStatus =
  | {
      readonly type: "running";
    }
  | {
      readonly type: "complete";
    }
  | {
      readonly type: "incomplete";
      readonly reason: "cancelled" | "length" | "content-filter" | "other" | "error";
      readonly error?: unknown;
    };
ToolCallMessagePartStatus
export type ToolCallMessagePartStatus =
  | {
      readonly type: "requires-action";
      readonly reason: "interrupt";
    }
  | MessagePartStatus;
MessageStatus
export type MessageStatus =
  | {
      readonly type: "running";
    }
  | {
      readonly type: "requires-action";
      readonly reason: "tool-calls" | "interrupt";
    }
  | {
      readonly type: "complete";
      readonly reason: "stop" | "unknown";
    }
  | {
      readonly type: "incomplete";
      readonly reason:
        | "cancelled"
        | "tool-calls"
        | "length"
        | "content-filter"
        | "other"
        | "error";
      readonly error?: ReadonlyJSONValue;
    };
5. ThreadMessage -- the full message type
type MessageCommonProps = {
  readonly id: string;
  readonly createdAt: Date;
};

export type ThreadSystemMessage = MessageCommonProps & {
  readonly role: "system";
  readonly content: readonly [TextMessagePart];
  readonly metadata: {
    readonly unstable_state?: undefined;
    readonly unstable_annotations?: undefined;
    readonly unstable_data?: undefined;
    readonly steps?: undefined;
    readonly submittedFeedback?: undefined;
    readonly timing?: undefined;
    readonly custom: Record<string, unknown>;
  };
};

export type ThreadUserMessage = MessageCommonProps & {
  readonly role: "user";
  readonly content: readonly ThreadUserMessagePart[];
  readonly attachments: readonly CompleteAttachment[];
  readonly metadata: {
    readonly unstable_state?: undefined;
    readonly unstable_annotations?: undefined;
    readonly unstable_data?: undefined;
    readonly steps?: undefined;
    readonly submittedFeedback?: undefined;
    readonly timing?: undefined;
    readonly custom: Record<string, unknown>;
  };
};

export type ThreadAssistantMessage = MessageCommonProps & {
  readonly role: "assistant";
  readonly content: readonly ThreadAssistantMessagePart[];
  readonly status: MessageStatus;
  readonly metadata: {
    readonly unstable_state: ReadonlyJSONValue;
    readonly unstable_annotations: readonly ReadonlyJSONValue[];
    readonly unstable_data: readonly ReadonlyJSONValue[];
    readonly steps: readonly ThreadStep[];
    readonly submittedFeedback?: { readonly type: "positive" | "negative" };
    readonly timing?: MessageTiming;
    readonly isOptimistic?: boolean;
    readonly custom: Record<string, unknown>;
  };
};

type BaseThreadMessage = {
  readonly status?: ThreadAssistantMessage["status"];
  readonly metadata: {
    readonly unstable_state?: ReadonlyJSONValue;
    readonly unstable_annotations?: readonly ReadonlyJSONValue[];
    readonly unstable_data?: readonly ReadonlyJSONValue[];
    readonly steps?: readonly ThreadStep[];
    readonly submittedFeedback?: { readonly type: "positive" | "negative" };
    readonly timing?: MessageTiming;
    readonly isOptimistic?: boolean;
    readonly custom: Record<string, unknown>;
  };
  readonly attachments?: ThreadUserMessage["attachments"];
};

export type ThreadMessage = BaseThreadMessage &
  (ThreadSystemMessage | ThreadUserMessage | ThreadAssistantMessage);
MessageTiming
export type MessageTiming = {
  readonly streamStartTime: number;
  readonly firstTokenTime?: number;
  readonly totalStreamTime?: number;
  readonly tokenCount?: number;
  readonly tokensPerSecond?: number;
  readonly totalChunks: number;
  readonly toolCallCount: number;
};
ThreadStep
export type ThreadStep = {
  readonly messageId?: string;
  readonly usage?:
    | {
        readonly inputTokens: number;
        readonly outputTokens: number;
      }
    | undefined;
};
6. ThreadMessageLike -- what ExternalStoreRuntime accepts
This is the "loose" input type that convertMessage and useExternalMessageConverter accept. It is more permissive than ThreadMessage.
type DataPrefixedPart = {
  readonly type: `data-${string}`;
  readonly data: any;
};

export type ThreadMessageLike = {
  readonly role: "assistant" | "user" | "system";
  readonly content:
    | string
    | readonly (
        | TextMessagePart
        | ReasoningMessagePart
        | SourceMessagePart
        | ImageMessagePart
        | FileMessagePart
        | DataMessagePart
        | GenerativeUIMessagePart
        | Unstable_AudioMessagePart
        | DataPrefixedPart
        | {
            readonly type: "tool-call";
            readonly toolCallId?: string;
            readonly toolName: string;
            readonly args?: ReadonlyJSONObject;
            readonly argsText?: string;
            readonly artifact?: any;
            readonly result?: any | undefined;
            readonly isError?: boolean | undefined;
            readonly parentId?: string | undefined;
            readonly messages?: readonly ThreadMessage[] | undefined;
            readonly interrupt?: { type: "human"; payload: unknown };
            readonly timing?: ToolCallTiming;
            readonly approval?: {
              readonly id: string;
              readonly approved?: boolean;
              readonly reason?: string;
              readonly isAutomatic?: boolean;
              readonly options?: readonly ToolApprovalOption[];
              readonly optionId?: string;
              readonly resolution?: "cancelled" | "expired";
            };
          }
      )[];
  readonly id?: string | undefined;
  readonly createdAt?: Date | undefined;
  readonly status?: MessageStatus | undefined;
  readonly attachments?:
    | readonly (Omit<CompleteAttachment, "content"> & {
        readonly content: readonly (ThreadUserMessagePart | DataPrefixedPart)[];
      })[]
    | undefined;
  readonly metadata?:
    | {
        readonly unstable_state?: ReadonlyJSONValue;
        readonly unstable_annotations?: readonly ReadonlyJSONValue[] | undefined;
        readonly unstable_data?: readonly ReadonlyJSONValue[] | undefined;
        readonly steps?: readonly ThreadStep[] | undefined;
        readonly timing?: MessageTiming | undefined;
        readonly submittedFeedback?: { readonly type: "positive" | "negative" };
        readonly isOptimistic?: boolean | undefined;
        readonly custom?: Record<string, unknown> | undefined;
      }
    | undefined;
};
Key notes about ThreadMessageLike:
- content can be a plain string (converted to [{ type: "text", text: ... }])
- id, createdAt, status, attachments, metadata are all optional
- Tool call parts have loose fields (toolCallId?, args?, argsText?)
- data-* prefixed types (e.g. { type: "data-workflow", data: {...} }) are auto-converted to DataMessagePart
7. CompleteAttachment -- attachment shape
type BaseAttachment = {
  id: string;
  type: "image" | "document" | "file" | (string & {});
  name: string;
  contentType?: string | undefined;
  file?: File;
  content?: ThreadUserMessagePart[];
};

export type CompleteAttachment = BaseAttachment & {
  status: CompleteAttachmentStatus;
  content: ThreadUserMessagePart[];
};

export type CompleteAttachmentStatus = {
  type: "complete";
};
8. useExternalMessageConverter callback signature
export namespace useExternalMessageConverter {
  export type Message =
    | (ThreadMessageLike & {
        readonly convertConfig?: {
          readonly joinStrategy?: JoinStrategy; // "concat-content" | "none"
        };
      })
    | {
        role: "tool";
        toolCallId: string;
        toolName?: string | undefined;
        result: any;
        artifact?: any;
        isError?: boolean;
        messages?: readonly ThreadMessage[];
      };

  export type Metadata = {
    readonly toolStatuses?: Record<string, ToolExecutionStatus>;
    readonly error?: ReadonlyJSONValue;
    readonly messageTiming?: Record<string, MessageTiming>;
  };

  // The callback signature:
  export type Callback<T> = (
    message: T,
    metadata: Metadata,
  ) => Message | Message[];
}
Usage:
const convertedMessages = useExternalMessageConverter({
  callback: (message: MyMessage): ThreadMessageLike => ({
    role: message.role,
    content: [{ type: "text", text: message.text }],
    id: message.id,
  }),
  messages,       // T[]
  isRunning,      // boolean
  joinStrategy,   // "concat-content" | "none" | undefined
  metadata,       // { toolStatuses?, error?, messageTiming? }
});
9. How the ExternalStoreAdapter (runtime input) looks
export type ExternalStoreAdapter<T = ThreadMessage> = {
  messages?: readonly T[];
  isRunning?: boolean;
  isLoading?: boolean;
  isDisabled?: boolean;
  isSendDisabled?: boolean;
  suggestions?: readonly ThreadSuggestion[];
  extras?: unknown;
  messageRepository?: ExportedMessageRepository;
  state?: ReadonlyJSONValue;

  // Handlers
  onNew: (message: AppendMessage) => Promise<void>;
  setMessages?: (messages: readonly T[]) => void;
  onEdit?: (message: AppendMessage) => Promise<void>;
  onReload?: (parentId: string | null, config: StartRunConfig) => Promise<void>;
  onCancel?: () => Promise<void>;
  onAddToolResult?: (options: AddToolResultOptions) => Promise<void> | void;
  onResume?: (config: ResumeRunConfig) => Promise<void>;
  onImport?: (messages: readonly ThreadMessage[]) => void;
  onExportExternalState?: () => any;
  onLoadExternalState?: (state: any) => void;
  convertMessage?: (message: T, index: number) => ThreadMessageLike;

  // Adapters
  adapters?: object;
  unstable_capabilities?: object;
};
Summary for your Python backend
For a RAG chat app with SSE streaming, the minimum your Python backend needs to emit as JSON (matching ThreadMessageLike) is:
User message:
{
  "role": "user",
  "content": [{ "type": "text", "text": "What is RAG?" }],
  "id": "msg-1",
  "createdAt": "2026-07-05T12:00:00Z"
}
Assistant message (text only):
{
  "role": "assistant",
  "content": [{ "type": "text", "text": "RAG stands for..." }],
  "id": "msg-2",
  "createdAt": "2026-07-05T12:00:01Z",
  "status": { "type": "complete", "reason": "stop" }
}
Assistant message with sources:
{
  "role": "assistant",
  "content": [
    { "type": "text", "text": "According to the documentation..." },
    { "type": "source", "sourceType": "url", "id": "src-1", "url": "https://example.com/doc", "title": "RAG Guide" },
    { "type": "source", "sourceType": "document", "id": "src-2", "title": "internal-doc.pdf", "mediaType": "application/pdf" }
  ],
  "id": "msg-3",
  "status": { "type": "complete", "reason": "stop" }
}
Assistant message with image:
{
  "role": "assistant",
  "content": [
    { "type": "text", "text": "Here is the diagram:" },
    { "type": "image", "image": "data:image/png;base64,iVBOR...", "filename": "architecture.png" }
  ],
  "id": "msg-4",
  "status": { "type": "complete", "reason": "stop" }
}
Streaming (incomplete):
{
  "role": "assistant",
  "content": [{ "type": "text", "text": "Partial response so far..." }],
  "id": "msg-5",
  "status": { "type": "running" }
}
