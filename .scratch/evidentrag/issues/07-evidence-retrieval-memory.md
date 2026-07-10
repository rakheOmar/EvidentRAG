Status: ready-for-agent

## What to build

Evidence Retrieval Memory — the system that learns from past retrieval outcomes. After an Answer is displayed, users can rate each sentence (thumbs up / thumbs down). ERM stores these ratings and, on future similar Queries, applies a cosine-similarity-based boost or penalty to Evidence Scores after the cross-encoder reranker. Evidence that was rated helpful for similar Queries gets boosted; Evidence rated unhelpful gets penalized. The boost/penalty is visible as an "ERM boost" indicator in the evidence panel.

## Acceptance criteria

- [x] `PUT /api/v1/sentence-traces/{trace_id}/feedback` idempotently sets the rating payload `{rating: "up"|"down"}` for one sentence trace and returns `200 OK`; missing traces return `404` and invalid ratings return `422`
- [x] PostgreSQL `erm_scores` table stores `(query_embedding_hash, evidence_id, boost_score, penalty_score)`
- [x] ERM computes cosine similarity between the current Query embedding and past Query embeddings to determine which ERM scores apply
- [x] After Cohere reranking, ERM applies boost (multiplier >1.0) or penalty (multiplier <1.0) to each Evidence's score based on matching ERM records
- [x] First-time queries (no matching ERM records) pass through with no modification
- [x] Thumbs up/down buttons appear next to each sentence in the Answer
- [x] After rating, buttons show selected state; user can change rating and the API overwrites the prior feedback state for that trace
- [x] Evidence panel shows "ERM boost" or "ERM penalty" badge when the score was modified
- [x] Subsequent similar Queries show improved Evidence rankings (verifiable in tests via mocked similarity + score assertions)

## Blocked by

- #04-simple-route-query-pipeline
