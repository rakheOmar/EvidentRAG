Status: ready-for-agent

## What to build

Extend the ARAG Router to classify Queries into all four Routes — Simple, Multi-hop, Comparison, and Aggregation — and implement the retrieval logic for the three new routes. Multi-hop decomposes the Query into sub-queries, retrieves for each iteratively (each sub-answer informs the next retrieval), then chains results into a final Answer. Comparison retrieves Evidence for two or more entities in parallel, then synthesizes differences. Aggregation retrieves broadly across many Evidence chunks and summarizes. The UI shows the selected route badge and optionally displays intermediate steps (sub-queries for Multi-hop, entity pairs for Comparison).

## Acceptance criteria

- [ ] ARAG Router (Gemini 2.5 Flash) classifies Queries into one of: `simple`, `multi_hop`, `comparison`, `aggregation`
- [ ] Router optionally decomposes the Query into sub-queries (for Multi-hop and Comparison)
- [ ] **Multi-hop**: sub-queries execute sequentially, each sub-query's results inform the next sub-query's retrieval parameters, final Answer chains all sub-answers
- [ ] **Comparison**: parallel retrieval for 2+ entities, fused results organized by entity, final Answer synthesizes differences in a structured format
- [ ] **Aggregation**: broad retrieval with a higher top-K, summarization prompt that covers diverse Evidence
- [ ] SSE `route_selected` event reflects the chosen route and any sub-queries
- [ ] Multi-hop SSE events show intermediate progress (e.g., `retrieving` for each hop)
- [ ] Route badge in UI updates dynamically: "Simple", "Multi-hop", "Comparison", "Aggregation"
- [ ] Multi-hop route shows sub-queries and intermediate answers in the UI (expandable)

## Blocked by

- #04-simple-route-query-pipeline
