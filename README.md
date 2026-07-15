<div align="center">
  <img src="https://github.com/user-attachments/assets/257ef2be-c81a-416b-94ff-e9af7913a3ad" alt="EvidentRAG" width="600" />
</div>

# EvidentRAG

Adaptive Retrieval-Augmented Generation engine that answers with **sentence-level
citation traces** back to the evidence it used. EvidentRAG picks a retrieval
strategy per query, blends dense and lexical search, reranks with a
cross-encoder, and remembers which evidence actually helped (and which didn't)
across conversations.


## Features

- **Adaptive retrieval (ARAG).** A router classifies each query into one of five
  strategies and runs the matching pipeline, instead of hitting one fixed RAG
  flow.
- **Evidence Retrieval Memory (ERM).** A persistent store of evidence with
  weights that boost useful evidence and penalize misleading evidence, so answers
  get sharper the more the system is used.
- **Citation traces.** Every sentence in an answer is linked to the specific
  evidence chunk it came from — not just a list of sources at the end.
- **Hybrid retrieval + reranking.** Dense embeddings fused with BM25 via
  Reciprocal Rank Fusion, then reranked with a cross-encoder for the final top-k.
- **Multimodal ingestion.** PDF text plus image anchors embedded with Gemini
  Embedding 2, so figures and tables enter the same knowledge base as prose.
- **Streaming answers.** Progress and the final answer stream over Server-Sent
  Events, so the UI updates as retrieval and generation happen.


## Architecture

```mermaid
flowchart LR
    classDef client fill:#6366f1,stroke:#4338ca,color:#fff,stroke-width:2px
    classDef api fill:#7c3aed,stroke:#5b21b6,color:#fff,stroke-width:2px
    classDef pipeline fill:#8b5cf6,stroke:#6d28d9,color:#fff,stroke-width:2px
    classDef ingest fill:#6b7280,stroke:#4b5563,color:#fff,stroke-width:2px
    classDef pg fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px
    classDef qd fill:#0891b2,stroke:#0e7490,color:#fff,stroke-width:2px
    classDef rd fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px

    C["Client (Vite + assistant-ui)"]:::client

    subgraph API["API Server"]
        EP["REST / SSE Streaming"]:::api
        OT["OpenTelemetry"]:::api
    end

    subgraph Worker["Worker (ARQ)"]
        direction LR
        AR["ARAG Router"]:::pipeline --> QW["Query Rewriter"]:::pipeline --> HR["Hybrid Retrieval"]:::pipeline --> RK["RRF + Rerank"]:::pipeline --> ER["ERM"]:::pipeline
        IN["Ingestion Pipeline (PDF + image → chunks)"]:::ingest
    end

    subgraph Stores["Data Stores"]
        PG[("Postgres (pgvector)")]:::pg
        QD[("Qdrant (vector + BM25)")]:::qd
        RD[("Redis (queue, cache, pub/sub)")]:::rd
    end

    C -->|"HTTP / SSE"| API
    API -.->|"enqueue"| RD
    RD -.->|"dequeue"| Worker
    RD -.->|"SSE events"| API
    Worker --- PG
    Worker --- QD
    Worker --- RD
```

A request hits the FastAPI API, which enqueues the work on Redis. The ARQ worker
runs ingestion and query pipelines against Postgres (documents, knowledge bases,
evidence, pgvector) and Qdrant (dense + BM25 indexes), then streams results back
over SSE.


## Tech stack

| Layer     | Choices |
|-----------|---------|
| Backend   | FastAPI, SQLAlchemy (async), ARQ, Qdrant client, Redis, httpx — Python 3.13, managed with `uv` |
| Frontend  | React 19 + Vite (via `vp`), assistant-ui, Tailwind, ultracite — Node 22, npm |
| Storage   | PostgreSQL (pgvector), Qdrant, Redis |
| Infra     | Multi-stage `Dockerfile` (client build → server image) + `server/Dockerfile` for the worker; `docker-compose.yml` wires Postgres/Qdrant/Redis/backend/worker |


## Quickstart (Docker)

```bash
# 1. Create the compose env file from the template
cp .env.docker.example .env.docker

# 2. Edit .env.docker and fill in at least your LLM / embedding credentials
#    (see "Configuration" below)

# 3. Build and start the stack
docker compose up --build
```

- API:       http://localhost:8000
- Worker:    runs as the `worker` compose service
- Client:    http://localhost:5173 (Vite dev server) or the built client served from the backend image

### Seed demo data (optional)

The worker keeps a healthcheck running. To populate a knowledge base with the
bundled samples, run the seeding script from the backend container:

```bash
docker compose exec backend python -m app.seed.seed_demo_data
```


## Local development

Requirements: Python 3.13 + `uv`, Node 22 + npm, and a running Postgres
(pgvector), Qdrant, and Redis (the `docker-compose.yml` provides these).

### 1. Backend

```bash
cd server
cp .env.example .env.local        # gitignored — holds your real credentials
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run arq app.worker.WorkerSettings
```

### 2. Frontend

```bash
cd client
npm install
npm run dev
```

### 3. Dev logs

A background dev setup tee's each service to its own log under `logs/`:

| Service | Log |
|---------|-----|
| Client (Vite)  | `logs/frontend.log` |
| Server (uvicorn) | `logs/backend.log` |
| Worker (ARQ)   | `logs/worker.log` |


## Configuration

All configuration is environment-driven. The authoritative, fully-commented set
of variables lives in `.env.example` (local) and `.env.docker.example` (compose).
The main groups are:

| Group        | Purpose | Notable variables |
|--------------|---------|-------------------|
| LLM          | Generation + routing models and gateways | `LLM_PROVIDER`, `GENERATION_MODEL`, `UTILITY_MODEL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `GROQ_API_KEY` |
| Embeddings   | Dense + multimodal embedding models | `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `GEMINI_EMBEDDING_MODEL`, `GEMINI_VISION_MODEL`, `GEMINI_API_KEY` |
| Retrieval    | Reranking + hybrid search tuning | `RERANKER_MODEL`, `RERANKER_PROVIDER` |
| Ingestion    | Chunking + multimodal parsing | `INGESTION_USE_GEMINI`, `INGESTION_CHUNK_SIZE`, `INGESTION_CHUNK_OVERLAP` |
| AI scheduler | Adaptive delay between LLM calls | `AI_SCHEDULER_ENABLED`, `AI_SCHEDULER_MIN_DELAY`, `AI_SCHEDULER_MIN_CONFIDENCE`, `AI_SCHEDULER_MAX_DELAY` |
| Postgres     | Relational + pgvector store | `POSTGRES_*`, `DATABASE_URL` |
| Qdrant       | Vector + BM25 index | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `QDRANT_URL` |
| Redis        | Queue + ERM cache | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_URL` |
| App / observability | CORS, logging, OTEL | `CORS_ORIGINS`, `LOG_LEVEL`, `OTEL_ENABLED`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME` |

> `.env.local` is gitignored and holds your real secrets. Never commit it.


## Query routes

The ARAG router picks a strategy per query and the UI labels it accordingly:

| Route        | UI label      | When it's used |
|--------------|---------------|----------------|
| `simple`     | Direct        | Straightforward lookups answerable from one retrieval pass |
| `multi_hop`  | Multi-step    | Questions needing several dependent retrievals to assemble the answer |
| `comparison` | Compare       | "Compare X vs Y" style questions |
| `aggregation`| Synthesis     | Questions asking for a summary or synthesis across many sources |
| `conversation` | From chat  | Follow-ups that rely on the existing conversation context |


## Testing

```bash
# Server (integration/e2e tests skip automatically without a live stack)
cd server
uv run pytest

# Client
cd client
npm test
```

### Pre-commit checks

Run these before pushing (mirrored by CI):

```bash
# Server
cd server
uv run basedpyright
uv run pytest
uv run ruff check . --fix
uv run ruff format .

# Client
cd client
npm run typecheck
npm test
npm run fix
npm run check
```


## Project structure

```
.
├── server/              FastAPI API + ARQ worker (uv-managed)
├── client/              React + Vite frontend (assistant-ui)
├── logs/                dev server logs (frontend / backend / worker)
├── Dockerfile           multi-stage: client build → server image
├── docker-compose.yml   postgres + qdrant + redis + backend + worker
├── .env.example         local dev env reference
├── .env.docker.example  compose env reference
├── CONTEXT.md           domain model & ubiquitous language
├── AGENTS.md            contributor workflow & pre-commit checks
└── docs/                ADRs and agent docs
```


## Contributing

Read `AGENTS.md` first — it defines the workflow (understand → plan → implement →
verify → review) and the exact pre-commit commands for both `server/` and
`client/`. The domain terms in `CONTEXT.md` are the canonical vocabulary; use
them in code and docs.


## License

Released under the [MIT License](./LICENSE).
