<img width="5000" height="1079" alt="logo-transparent" src="https://github.com/user-attachments/assets/33c3608b-a579-483b-900a-c33a693aef17" />

# EvidentRAG

EvidentRAG is a Docker Compose demo of adaptive retrieval, sentence-level
Evidence traces, and Evidence Retrieval Memory.

## Run with Docker

```powershell
Copy-Item .env.docker.example .env.docker
docker compose up --build
```

The application is served at `http://localhost:8000`. PostgreSQL, Qdrant, and
Redis start without provider credentials, so document management and health
checks remain available. Add `GEMINI_API_KEY`, `LLM_API_KEY`, and
`RERANKER_API_KEY` to `.env.docker` before running ingestion or Queries. Set
`SEED_DEMO_DATA=true` to embed and publish the bundled demo corpus at startup.

The optional Vite development container is available with
`docker compose --profile dev up frontend`.

## Local development

Run PostgreSQL, Qdrant, and Redis yourself (or via
`docker compose up postgres qdrant redis`), then start the three services in
separate terminals from the repo root:

```powershell
# API server (FastAPI + uvicorn)
cd server
uv sync
uv run uvicorn app.main:app --reload --port 8000

# Worker (ARQ task queue for ingestion + queries)
cd server
uv run arq app.worker:WorkerSettings

# Client (Vite dev server)
cd client
npm install
npm run dev
```

The client expects the API at `http://localhost:8000`. Copy `.env.docker.example`
to `.env` and adjust the `POSTGRES_*`, `QDRANT_*`, and `REDIS_*` connection
strings for your local services, plus `GEMINI_API_KEY`/`LLM_API_KEY`/
`RERANKER_API_KEY` for ingestion and queries. Set `SEED_DEMO_DATA=true` to
embed and publish the bundled demo corpus on startup.
