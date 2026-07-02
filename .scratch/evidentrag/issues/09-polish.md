Status: ready-for-agent

## What to build

Polish and finishing touches across the entire application. This includes: error handling for all API failure modes (missing API keys, Qdrant down, Cohere rate limits), loading states and empty states for every UI view, responsive layout pass, query history view, document status polling improvement, and any rough edges discovered during integration testing of prior slices.

## Acceptance criteria

- [ ] Error toasts/banners for: API key missing, Qdrant unavailable, Cohere rate limit, Gemini API error, PDF parse failure
- [ ] Loading skeletons for: document list, query response, eval dashboard
- [ ] Empty states for: no documents uploaded, no queries yet, no golden dataset entries
- [ ] Responsive layout: works at 1920px, 1366px, and 768px widths
- [ ] Query history page: list of past Queries from `GET /api/v1/queries` with route badge and timestamp, click through to the full Answer + traces via the Query/Answer resource endpoints
- [ ] Document status polling: when ingestion is in progress, UI polls for updates without manual refresh
- [ ] Keyboard shortcuts: Enter to submit Query, Escape to close evidence panel
- [ ] All issues from prior slices are resolved and the full flow works end-to-end with `docker compose up`

## Blocked by

- #01-project-scaffold
- #02-pre-seeded-dataset
- #03-document-ingestion-pipeline
- #04-simple-route-query-pipeline
- #05-evidence-traces-ui
- #06-multi-hop-comparison-aggregation-routes
- #07-evidence-retrieval-memory
- #08-evaluation-system
