# EvidentRAG

A demo project showcasing an Adaptive RAG engine with Evidence Retrieval Memory and sentence-level citation traces. Docker-Compose-runnable, not packaged as a library or deployed as a service.

## Versioned document lifecycle

**Source**:
A stable identity for knowledge supplied to EvidentRAG. Updating or deleting knowledge targets a Source.
_Avoid_: File, asset, resource

**Document Version**:
An immutable uploaded representation of a Source. Only the current ready Version is eligible for normal retrieval; older Versions remain for provenance and audit.
_Avoid_: Replacement file, mutable document

## Language

**EvidentRAG**:
The system itself — an Adaptive Retrieval-Augmented Generation engine that decides *how* to retrieve, remembers *what evidence worked*, and traces *why* each sentence says what it says.
_Avoid_: "the RAG", "the engine"

**Document**:
A source file ingested into EvidentRAG — typically a PDF, slide deck, or article page. May contain both text and images.
_Avoid_: File, asset, resource

**Evidence**:
A retrievable fragment of a Document (text passage, image, or figure) that can ground an answer.
_Avoid_: Chunk, snippet, passage

**Knowledge Base**:
The set of Documents uploaded by the user that EvidentRAG indexes and retrieves from.
_Avoid_: Corpus, collection, index

**Query**:
A natural-language question submitted by the user.
_Avoid_: Prompt, search term, request

**Answer**:
The final natural-language response returned to the user, with each sentence grounded to specific Evidence.
_Avoid_: Response, output, generation

### Retrieval

**Retrieval Pipeline**:
The sequence of stages that produces Evidence chunks for a Query: dense + BM25 retrieval in parallel → RRF fusion → cross-encoder rerank → ERM boost/penalty → final top-N Evidence.
_Avoid_: Search pipeline, fetch flow

**Hybrid Retrieval**:
Dense vector search (semantic similarity) and BM25 sparse search (keyword matching) run concurrently against Qdrant, then fused via Reciprocal Rank Fusion.
_Avoid_: Dual search, mixed retrieval

**Reciprocal Rank Fusion (RRF)**:
An algorithm that merges two ranked result lists (dense and BM25) into a single ranking by averaging reciprocal ranks. Run inside Qdrant.
_Avoid_: Score fusion, merge step

**Cross-Encoder Reranker**:
The Cohere Rerank API, which scores each (Query, Evidence) pair jointly to reorder fused results before ERM applies its boost/penalty. Requires a Cohere API key.
_Avoid_: Bi-encoder, pairwise scorer

**ARAG Router**:
The Adaptive RAG component that classifies a Query into exactly one Route and optionally decomposes it into sub-queries. Implemented as an LLM classifier.
_Avoid_: Query router, classifier, dispatcher

**Route**:
One of four retrieval strategies the ARAG Router selects: Simple, Multi-hop, Comparison, or Aggregation.
_Avoid_: Strategy, mode, plan

**Simple Route**:
A single-pass hybrid retrieval (dense + sparse) with reranking. For straightforward factual queries.
_Avoid_: Basic, direct

**Multi-hop Route**:
Iterative retrieval where each sub-query's Answer informs the next sub-query's retrieval. For chained-reasoning queries.
_Avoid_: Chain, sequential, iterative

**Comparison Route**:
Parallel retrieval for two or more entities followed by synthesis of differences. For "X vs Y" queries.
_Avoid_: Compare, diff, versus

**Aggregation Route**:
Broad retrieval across many Documents followed by summarization. For "give me an overview of X" queries.
_Avoid_: Summary, overview, synthesis

### Memory

**Evidence Retrieval Memory (ERM)**:
The system's memory of past retrieval outcomes. After an Answer is generated, ERM records which Evidence successfully grounded the response and which was irrelevant. Future retrievals for similar Queries receive boost or penalty scores from ERM.
_Avoid_: Cache, history, feedback loop

**Evidence Score**:
A numeric weight ERM assigns to an Evidence chunk during retrieval, combining the vector store's relevance score with ERM's boost or penalty based on past outcomes.
_Avoid_: Rank, weight, relevance score

### Citations

**Sentence Trace**:
A record linking one sentence of an Answer to one or more Evidence chunks that support it. Produced inline by the generation LLM as structured output (`[{sentence, evidence_ids}]`).
_Avoid_: Citation, attribution, grounding record

**Evidence ID**:
A unique identifier for an Evidence chunk, used to link Sentence Traces back to the source Document and passage.
_Avoid_: Chunk ID, reference, pointer

### Ingestion

**Embedding Model**:
Google's Gemini Embedding 2 — a multimodal embedding model (768-dim) accessed via API. Embeds both text chunks and Image Anchor captions into the same vector space.
_Avoid_: Embedder, vectorizer, encoder

**Context Header**:
A short LLM-generated prefix prepended to each Evidence chunk describing its document context (e.g., "This passage is from Section 3.2 of a paper about transformer attention mechanisms"). Makes chunks self-contained for retrieval.
_Avoid_: Chunk header, summary header, context prefix

**Image Anchor**:
An image embedded in a Document, linked to the nearest text chunk and paired with an LLM-generated caption embedding for multimodal retrieval.
_Avoid_: Figure attachment, image chunk

**Ingestion Pipeline**:
The async multi-stage process that transforms an uploaded Document into retrievable Evidence: parse PDF → chunk text → generate context headers → caption images → embed via Gemini Embedding 2 → upsert to Qdrant → store metadata in PostgreSQL. Progress is tracked and surfaced in the UI.
_Avoid_: Indexing pipeline, processing flow

### Evaluation

**Golden Dataset**:
A curated set of (Query, expected Answer) pairs used to run reproducible RAGAS benchmarks. Stored in the database and editable through the UI.
_Avoid_: Test set, benchmark set, ground truth

**User Rating**:
A binary thumbs-up/thumbs-down on an Answer sentence, fed into ERM to boost or penalize the associated Evidence for future similar Queries.
_Avoid_: Feedback, vote, score

**RAGAS Metrics**:
A set of automated scores — answer relevancy, faithfulness, context precision, context recall — computed against the Golden Dataset and displayed on the evaluation dashboard.
_Avoid_: Eval scores, quality metrics

### API

**SSE Stream**:
A Server-Sent Events stream that delivers Query processing progress to the frontend: `route_selected` → `retrieving` → `generating` (token-level) → `done` (final Answer + Sentence Traces + Evidence).
_Avoid_: WebSocket stream, event channel

**Generation LLM**:
Gemini 2.5 Pro — used for final Answer generation with inline structured citations.
_Avoid_: Answer model, main LLM

**Utility LLM**:
Gemini 2.5 Flash — used for ARAG Router classification, CCH context headers, and image captioning. Prioritizes speed and cost over peak quality.
_Avoid_: Fast model, helper LLM
