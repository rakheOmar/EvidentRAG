Status: done

## What to build

Stand up the full Docker Compose environment with all services healthy and talking to each other. This includes the FastAPI backend shell (a single health-check endpoint), the React/Vite frontend shell (a single welcome page), PostgreSQL, Qdrant, and Redis — all containerized and configurable via a `.env.example` file. No business logic yet, just infrastructure that proves the stack works end-to-end.

## Acceptance criteria

- [x] `docker compose up` starts FastAPI, React/Vite (dev server or nginx), PostgreSQL, Qdrant, and Redis
- [x] FastAPI `/health` returns `{"status": "ok"}` and verifies PostgreSQL, Qdrant, and Redis connectivity
- [x] React frontend loads at `localhost:3000` and displays "EvidentRAG" placeholder
- [x] `.env.example` exists with placeholder values for `GOOGLE_API_KEY`, `COHERE_API_KEY`, DB URLs
- [x] `pyproject.toml` renamed from "rag" to "evidentrag" with FastAPI, uvicorn, httpx, qdrant-client, psycopg2, redis as dependencies
- [x] No business logic — just the skeleton

## Blocked by

None — can start immediately
