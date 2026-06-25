# ARAG Router as 4-route LLM classifier

EvidentRAG uses an LLM-based Adaptive RAG router that classifies every Query into one of four retrieval routes — Simple, Multi-hop, Comparison, or Aggregation — and optionally decomposes the query into sub-queries. We chose an LLM classifier over heuristic rules or a trained embedding classifier because the route selection is semantically rich (distinguishing "compare X and Y" from "walk me through the steps linking A to B") and a prompted LLM achieves high accuracy without training data. The trade-off is latency and cost: every Query incurs a Flash-classifier call before retrieval begins, which adds ~200-500ms. For a demo project, classification quality matters more than throughput.

**Considered options**: Heuristic keyword matching (fast but fragile — misses implicit comparisons), fine-tuned embedding classifier (accurate but requires labelled training data we don't have).
