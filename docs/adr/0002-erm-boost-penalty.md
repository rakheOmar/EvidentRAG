# ERM as post-retrieval boost/penalty layer

Evidence Retrieval Memory applies a numeric boost or penalty to Evidence scores after the cross-encoder reranker, based on past retrieval outcomes for similar Queries. We chose a simple cosine-similarity lookup over training a latent adapter model because (a) the boost/penalty mechanism is explainable — users can see *why* a chunk was boosted — and (b) it avoids the training infrastructure and cold-start problems of a learned adapter. The trade-off is that similarity-based memory may miss non-obvious query-evidence relationships that a learned model could capture.

**Considered options**: Latent adapter model (more sophisticated but requires training data, GPU, and continuous retraining), success-only caching (simpler but loses the failure-suppression signal that makes ERM novel).
