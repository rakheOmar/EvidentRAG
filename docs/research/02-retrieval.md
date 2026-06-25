## 2. Retrieval Techniques

### 2.1 Fusion Retrieval

#### How It Works

Fusion retrieval combines outputs from multiple heterogeneous retrieval methods — typically sparse (BM25, SPLADE), dense (bi-encoders like BGE, Qwen-Embed), and sometimes graph-based or structured retrievers — into a single, higher-quality ranked list. The core insight: no single retriever excels on all query types. BM25 captures exact lexical matches; dense embeddings capture semantic similarity; knowledge graphs capture structured relationships. Fusion aggregates these complementary signals so the final list inherits the strengths of each. In production RAG pipelines, fusion is typically applied as a mid-stage component: each retriever produces its own top-_k_ (often 100–1000), then a fusion algorithm merges them before reranking.

#### Mechanisms / Algorithms

| Method | Description |
|--------|-------------|
| **Reciprocal Rank Fusion (RRF)** | Merges _n_ ranked lists by scoring each document as `∑ 1/(k + rank)`, where `k` (typically 60) is a smoothing constant. Dominant in practice — parameter-free, robust to score-scale differences. Used by the winning TREC 2025 RAG Track entry (UTokyo-HitU). |
| **Weighted Score Fusion** | Linearly combines normalized similarity scores from each retriever. Requires score calibration — z-score normalization (as in HF-RAG) or min-max scaling is essential when sources produce non-comparable scores. |
| **Borda Count / CombSUM** | Voting-based rank aggregation. Each document earns points inversely proportional to its rank in each list. Less common in modern RAG vs. RRF. |
| **Adaptive / Learned Fusion** | Uses a lightweight model (or LLM-as-judge) to learn per-query fusion weights. MoR (Mixture of Retrievers) uses embedding-space geometry for zero-shot weighting; AMSRAG uses confidence-aware RRF. |
| **Hierarchical Fusion (HF-RAG)** | Two-phase: first fuse within each source type (e.g., multiple rankers on labeled data), then fuse across sources after z-score normalization. |
| **HyDE Vector Mix** | A weighted combination of the original query embedding and a HyDE (hypothetical answer) embedding, with a tunable mixing ratio α. Achieved 1st place in TREC 2025 RAG Track retrieval task. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | ↑↑ Higher. Running _N_ retrievers in parallel can keep wall-clock time reasonable, but total compute is _N_×. Production studies (RAG Fusion at Scale, arXiv 2603.02153) show fusion adds ~1.5–2× latency vs. single-retriever. |
| **Accuracy / Recall** | ↑↑ Significantly higher. TREC 2025 RAG Track winner achieved nDCG@30 of 0.693 (vs. ~0.55 for single-method baselines). UTokyo-HitU: 4-method RRF fusion yielded recall@100 of 0.257. |
| **Complexity** | Moderate. RRF is trivial to implement (~10 lines). Score calibration and adaptive weighting add complexity. HF-RAG-style hierarchical fusion is architecturally heavier. |
| **Cost** | ↑ Higher. Multiple retrieval calls + LLM reranking overhead. AMSRAG addresses this with complexity-aware routing — only invoke multi-retriever for hard queries. |

#### Production Applicability

**Ready now.** RRF-based fusion is deployed in production at multiple organizations (Coinbase, LinkedIn). FusionRAG (GitHub) and HetaRAG are open-source frameworks with production-ready orchestrators. However, the 2025 production study (arXiv 2603.02153) warns: "benefits of fusion are highly context-dependent and largely confined to recall-scarce queries." For many production settings with strong single retrievers, fusion may not justify the latency cost.

#### Key Papers / Implementations

- **UTokyo-HitU at TREC 2025 RAG Track** — 1st place; HyDE Vector Mix + 4-method RRF fusion (TREC 2025)
- **HF-RAG** — Hierarchical Fusion-based RAG with z-score inter-source merging (arXiv 2509.02837, 2025)
- **Scaling RAG with RAG Fusion: Lessons from an Industry Deployment** — Production study finding context-dependent fusion benefits (arXiv 2603.02153, 2025)
- **MoR: Mixture of Sparse, Dense, and Human Retrievers** — Zero-shot dynamic retriever weighting, EMNLP 2025
- **MMLF: Multi-query Multi-passage Late Fusion Retrieval** — Findings of NAACL 2025
- **AMSRAG** — Adaptive Multi-Source RAG with complexity-aware fusion, Applied Sciences 2026
- **FusionRAG** (GitHub: THAMIZH-ARASU/FusionRAG) — Open-source production-oriented implementation
- **HetaRAG** — Hybrid retrieval across Milvus + Elasticsearch + Neo4j + MySQL (arXiv 2509.21336, 2025)

---

### 2.2 Multi-Hop Retrieval

#### How It Works

Multi-hop retrieval addresses questions that cannot be answered from a single document — the answer depends on chaining facts across multiple passages. The system decomposes a complex query into sub-questions, retrieves evidence for each, and iteratively refines the search using previously discovered information. Modern approaches fall into three families: (1) **Iterative RAG** — retrieve → reason → generate next query → retrieve, repeating until sufficiency; (2) **Agentic decomposition** — specialized agents (Question Analyzer, Selector, Adder) coordinate precision-oriented filtering and recall-oriented expansion; (3) **Structure-aware** — pre-build a passage graph with LLM-generated pseudo-queries as edges, then traverse the graph during retrieval (HopRAG).

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **Retrieve-Reason-Prune (HopRAG)** | Index time: construct passage graph with pseudo-query edges. Retrieval: start with semantic matches, explore multi-hop neighbors via graph traversal guided by LLM reasoning, prune irrelevant branches. |
| **Iterative Retrieval with LLM Reasoning (IRCoT)** | Classic approach: at each iteration, LLM generates a reasoning step + next query, retriever fetches documents, loop continues. Basis for most modern iterative RAG. |
| **Reasoning-augmented Querying + Progressive Knowledge Aggregation (DualRAG)** | Two tightly coupled processes: RaQ navigates reasoning paths and generates queries; pKA systematically integrates new evidence. Creates a virtuous cycle. ACL 2025. |
| **Precision-Recall Iterative Selection (PRISM)** | Three agents: Question Analyzer decomposes query, Selector filters distractors, Adder recovers missed evidence. Explicitly balances precision and recall. |
| **Knowledge-Driven Iterative Retrieval (KiRAG)** | Decomposes documents into knowledge triples; performs iterative retrieval at triple-level rather than document-level. More factually reliable, less noise-prone. ACL 2025. |
| **Intermediate Representations (L-RAG)** | Novel approach: instead of generating new queries, uses intermediate-layer LLM representations (which capture "next-hop" information) to retrieve directly. Matches multi-step performance with single-step overhead. Findings of ACL 2025. |
| **Reinforcement Learning for Multi-Hop (R3-RAG)** | Uses RL (GRPO) with outcome + process rewards to train LLMs to reason, retrieve, and verify step-by-step. Findings of EMNLP 2025. |
| **Structured Planning (DPS / RAG)** | Generates a global reasoning plan with sub-questions *before* retrieval. Each sub-question provides semantic guidance, preventing retrieval drift. ACM TKDD 2026. |
| **PluriHopRAG** | For exhaustive, recall-sensitive QA across large corpora. Learns corpus-specific document structure; uses cross-encoder filtering for cheap document-level filtering. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | ↑↑↑ Very high. Each hop requires an LLM inference + retrieval round-trip. PRISM and IRCoT may need 3–5 iterations. L-RAG (intermediate representations) is the exception — single-pass latency. |
| **Accuracy** | ↑↑↑ Large gains on multi-hop benchmarks (HotpotQA, MuSiQue, 2WikiMultiHopQA). KiRAG: +9.40% R@3, +5.14% F1 over strongest baselines. DualRAG: approaches oracle-knowledge performance. |
| **Complexity** | Very high. Requires careful orchestration of decomposition, retrieval, filtering, and stopping criteria. Error propagation is a real concern — one bad retrieval step can derail the entire chain. |
| **Cost** | ↑↑↑ High. Multiple LLM calls + multiple retrievals per query. DPS and L-RAG attempt to reduce this. |

#### Production Applicability

**Experimental → emerging.** Multi-hop RAG is active in research but production deployments remain limited to well-scoped domains (legal, biomedical). The latency and cost overhead are significant. L-RAG (intermediate representations) is the most production-practical variant — competitive accuracy with single-pass latency. FAIR-RAG (Faithful Adaptive Iterative Refinement) shows promise with evidence-centric loops and explicit gap detection. PRISM and PluriHopRAG are compelling for high-stakes domains where recall is non-negotiable.

#### Key Papers / Implementations

- **HopRAG: Multi-Hop Reasoning for Logic-Aware RAG** — Findings of ACL 2025
- **DualRAG: A Dual-Process Approach to Integrate Reasoning and Retrieval** — ACL 2025
- **KiRAG: Knowledge-Driven Iterative Retriever** — ACL 2025
- **L-RAG: Optimizing Multi-Hop Document Retrieval Through Intermediate Representations** — Findings of ACL 2025
- **PRISM: Agentic Retrieval with LLMs for Multi-Hop QA** — arXiv 2510.14278, 2025
- **R3-RAG: Learning Step-by-Step Reasoning and Retrieval via RL** — Findings of EMNLP 2025
- **ReSCORE: Label-free Iterative Retriever Training** — ACL 2025
- **FAIR-RAG: Faithful Adaptive Iterative Refinement** — arXiv 2510.22344, 2025
- **PluriHopRAG** — arXiv 2510.14377, 2025
- **Retrieval-Augmented Generation for MHQA Based on Structured Planning** — ACM TKDD 2026

---

### 2.3 Hierarchical Indices

#### How It Works

Hierarchical indices organize vectors into multi-level structures where each level provides a different resolution of the search space — coarse at the top for fast navigation, fine at the bottom for precise search. This is conceptually distinct from single-level ANN indices (flat IVF, single-layer HNSW). Modern hierarchical indices operate at two distinct levels of abstraction: **(a) Geometric hierarchies** (HNSW, CHANNI, LSM-VEC) — multi-layer graph structures for approximate nearest-neighbor speedup; and **(b) Semantic hierarchies** (SPI, Quake) — multi-resolution representations where each level captures different semantic granularity (document-level → paragraph-level → sentence-level), with query-adaptive depth selection.

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **HNSW (Hierarchical Navigable Small World)** | De facto standard. Multi-layer graph: top layers sparse for long-range jumps, bottom layer dense for precision. Search: start at top, greedy descent layer-by-layer. Weaviate, Milvus, pgvector all use HNSW. |
| **CHANNI (Clustered Hierarchical Approximate Nested Navigable Index)** | Dual-level: top-level HNSW connects cluster primaries; within clusters, another HNSW. Decouples coarse cluster navigation from fine local search. Each level independently tunable. 2025. |
| **LSM-VEC** | HNSW + LSM-tree for billion-scale disk-based vector search. Upper layers in memory; bottom layer on disk managed by LSM-tree. Supports dynamic insertions/deletions. 2025. |
| **SHG (Shortcut-enabled Hierarchical Graph)** | Extends HNSW with level-skipping shortcuts using learned piecewise-linear models. Skips redundant intermediate levels. 1.5–1.8× speedup over HNSW. VLDB 2025. |
| **Quake** | Adaptive multi-level partitioning with cost model that predicts query latency based on partition sizes. Dynamically adjusts to evolving data distributions. NUMA-aware parallelism. OSDI 2025. |
| **SPI (Semantic Pyramid Indexing)** | _L_-level semantic pyramid. Level 1: broad-scope embeddings; Level _L_: fine-grained embeddings via residual refinement. Query-adaptive depth: a learned controller selects minimum resolution needed for stable top-_k_. Unlike HNSW, depth is per-query semantic, not geometric. |
| **SIEVE (Set of Indexes for Efficient Vector Exploration)** | Builds a *collection* of compact indexes each specialized to a predicate set (e.g., `stars=1–3`). Optimizes index selection to observed workload patterns. |
| **vector_kmeans_tree (YDB)** | Recursive k-means partitioning into a tree of clusters. Search descends the tree choosing nearest centroid at each level. O(1) search complexity per level. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | ↓↓ Lower vs. flat search. HNSW: logarithmic search time. SHG: 1.5–1.8× faster than HNSW. SPI: reduces cost by routing to minimum needed depth. |
| **Recall** | Slight tradeoff. HNSW typically achieves 95–99% recall@10 at reasonable parameters. More levels = faster search but slightly lower recall. SPI guarantees exact top-_K_ when retrieval margin is sufficient (Theorem 1). |
| **Memory** | ↑↑ Higher vs. flat index. HNSW stores graph edges (M × N edges). CHANNI reduces this by clustering. LSM-VEC reduces memory by 66.2% via disk-based bottom layer. |
| **Update Complexity** | Variable. Standard HNSW: insertions require edge rewiring, expensive. LSM-VEC: supports efficient incremental updates via LSM-tree. Quake: 18–126× lower update latency vs. HNSW/DiskANN. |
| **Build Time** | ↑ Higher vs. flat. HNSW build is O(N log N). Multi-level structures add overhead. |

#### Production Applicability

**Ready now (HNSW).** HNSW is deployed in virtually every production vector database (Pinecone, Weaviate, Milvus, Qdrant, pgvector). CHANNI and LSM-VEC target billion-scale+ deployments. SPI and Quake are more research-stage but address real production pain points (streaming ingestion, query-adaptive cost). The semantic hierarchy of SPI represents a paradigm shift beyond geometric hierarchies.

#### Key Papers / Implementations

- **CHANNI: A Multi-Level Vector Search Index** — Cosdata 2025
- **Quake: Adaptive Indexing for Vector Search** — OSDI 2025
- **LSM-VEC: Large-Scale Disk-Based Dynamic Vector Search** — arXiv 2505.17152, 2025
- **SHG: Shortcut-enabled Hierarchical Graph** — VLDB 2025
- **SPI: Semantic Pyramid Indexing for Streaming RAG** — arXiv 2511.16681, 2025
- **SIEVE: Effective Filtered Vector Search** — arXiv 2507.11907, 2025
- **GaussDB-Vector** — VLDB 2025
- **Version-Controlled Vector Indexes (DoltHub Proximity Map)** — 2025

---

### 2.4 Multi-Faceted Filtering

#### How It Works

Multi-faceted filtering combines metadata-based pre-filtering with semantic (vector) search to narrow the retrieval space before or during ANN search. Traditional approaches apply metadata filters *before* vector search — this is efficient but can miss relevant results. Modern approaches integrate filtering into the vector index structure itself (filtered vector search) or apply post-retrieval selection criteria. The core insight: combining structured metadata (date ranges, categories, authorship, quality scores) with semantic similarity produces more precise retrieval than either alone. Advanced variants include dynamic selection criteria (DS-RAG's graph-embedded criteria) and classifier-based relevance filtering.

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **Pre-filtering** | Apply SQL/metadata filters first, then vector search on the reduced set. Simple, fast, but restrictive — may eliminate semantically relevant documents in other categories. |
| **Post-filtering** | Vector search first, then apply metadata filters. Higher recall but wasteful — vector search over irrelevant data. |
| **Filtered Vector Search (SIEVE)** | Build specialized compact indexes per predicate combination. Queries hit the index that best matches their filter. Memory-efficient through index sharing. |
| **YDB Prefix + Vector Index** | A secondary (relational) index for filtered columns sits in front of the vector k-means tree. A separate vector sub-tree is built for each distinct filter value. |
| **Dynamic Passage Selector (DPS)** | Treats passage selection as supervised learning. Captures inter-passage dependencies; dynamically selects the optimal subset for generation, not just top-_k_. |
| **Graph-Based Selection (DS-RAG)** | Embeds selection criteria as graph nodes. Embeddes retrieved chunks as text nodes. Uses cosine similarity between criteria and chunks to select one chunk per criterion. |
| **Classifier-Based Dynamic Relevance (DR-RAG)** | Two-stage: similarity matching first, then a classifier evaluates dynamic relevance between query-document pairs. Forward selection (add relevant) and reverse selection (remove irrelevant). |
| **Cluster-Based Adaptive Retrieval (CAR)** | Detects natural breakpoints in ordered similarity distance distributions. Groups documents into relevance clusters; uses the boundary between dense relevant clusters and sparse noise as the cutoff. |
| **Tail-Aware Adaptive-_k_ (TAA-_k_)** | Uses knee detection on ranked similarity curves + Extreme Value Theory goodness-of-fit to determine query-adaptive cutoff. Reduces complexity from O(N²M) to O(√(N log N)·M). |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | Variable. Pre-filtering = fastest. Filtered vector search = moderate overhead. DPS/CAR/TAA-_k_ = adds post-processing but reduces LLM token usage (CAR: −60% tokens, −22% end-to-end latency). |
| **Accuracy** | ↑↑ Higher precision and relevance. CAR: highest TES score, reduces hallucinations by 10%. DPS: +30.06% F1 on MuSiQue. DS-RAG: eliminates redundant chunks dynamically. |
| **Complexity** | Moderate. Pre-/post-filtering is simple. SIEVE-style index collections require workload analysis. DPS requires fine-tuning. CAR is training-free and straightforward. |
| **Scalability** | SIEVE handles high-cardinality metadata well. YDB's approach scales with the number of distinct filter values. Pre-filtering degrades when filters are too selective. |

#### Production Applicability

**Ready now (basic).** Pre-filtering + post-filtering are standard in all production vector databases (Weaviate, Milvus, Qdrant). **Emerging (adaptive).** CAR (Coinbase) is deployed in production — 200% jump in user engagement. DPS and TAA-_k_ are ready for integration but require model serving infrastructure. SIEVE is experimental but addresses a clear production gap.

#### Key Papers / Implementations

- **From Ranking to Selection: Dynamic Passage Selector (DPS)** — arXiv 2508.09497, 2025
- **Cluster-based Adaptive Retrieval (CAR)** — arXiv 2511.14769, 2025 (Coinbase production)
- **Tail-Aware Adaptive-_k_ (TAA-_k_)** — arXiv 2606.11907, 2025
- **DR-RAG: Dynamic-Relevant Retrieval-Augmented Generation** — arXiv 2406.07348, 2024
- **DS-RAG: Dynamic-Selection-Based RAG** — Electronics 2025
- **SIEVE: Effective Filtered Vector Search** — arXiv 2507.11907, 2025
- **YDB vector_kmeans_tree with filtered indexes** — YDB docs 2025

---

### 2.5 Dartboard Retrieval

#### How It Works

Dartboard retrieval reformulates the retrieval problem as maximizing *relevant information gain* rather than simple similarity. The intuition: given _k_ "guesses" (retrieved passages), the system should maximize the expected relevance of the *most relevant* guess. Since the best passage isn't known in advance, the score is weighted by the probability of each passage being the best. This objective naturally encourages diversity — a redundant passage does nothing to increase the maximum relevance score, so the system is implicitly pushed toward complementary passages. The name comes from the metaphor: you want darts spread across the high-value regions of the board, not clustered on one spot.

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **Relevant Information Gain Objective** | `s(G,q) = Σ_t N(q,t,σ) · max_{g∈G} N(t,g,σ)`. Maximizes the total non-redundant, query-relevant information in the retrieved set _G_. |
| **Greedy Selection with Probability Weighting** | At each step, select the document that maximally increases the expected maximum relevance. Relevance scores are converted to probabilities via Gaussian / softmax. |
| **Weighted Relevance-Diversity Balance** | Production variants (NirDiamant implementation) add explicit `RELEVANCE_WEIGHT` and `DIVERSITY_WEIGHT` parameters for tunable control, plus a `SIGMA` smoothing parameter. |
| **Drop-in Replacement** | Dartboard operates as a post-retrieval selection module. Input: initial candidate set + similarity scores from any retriever(s). Output: re-ranked, diversity-optimized top-_k_. |
| **Cross-Encoder Compatibility** | Can use cross-encoder scores directly (1 − sim) as distances. Agnostic to the underlying retrieval method. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | ↑ Moderate. Requires pairwise document-document similarity computation among candidates (O(k²) in candidate size). Greedy selection is O(k²) per step. Mitigated by operating on a modest candidate pool (top 50–200). |
| **Accuracy** | ↑↑↑ Strong. Outperforms MMR (Maximal Marginal Relevance) on both end-to-end QA accuracy and NDCG on the RGB benchmark. State-of-the-art on RGB. |
| **Complexity** | Low. Simple optimization over existing similarity scores. No training required. Single-file implementations exist (<100 lines). |
| **Cost** | Negligible additional cost. No extra LLM calls or retriever calls. |

#### Production Applicability

**Ready now.** Dartboard is a drop-in replacement for the retrieval/diversity component of any RAG system. The open-source implementation (EmergenceAI/dartboard) and the NirDiamant RAG_Techniques notebook make it immediately integrable. It addresses a universal RAG problem — context window waste from redundant passages — with minimal overhead.

#### Key Papers / Implementations

- **Dartboard: Better RAG using Relevant Information Gain** — Pickett et al., arXiv 2407.12101, 2024
- **NirDiamant/RAG_Techniques: dartboard.ipynb** — Production-oriented implementation with weighted balancing
- **EmergenceAI/dartboard** — Official open-source implementation

---

### 2.6 Retrieval Feedback Loops

#### How It Works

Retrieval feedback loops use signals from the generation phase (LLM output quality, user feedback, or intermediate rankings) to refine subsequent retrieval. This transforms stateless, single-shot retrieval into a stateful, self-correcting process. The feedback can flow at multiple levels: **(a) Query-level feedback** — the LLM identifies knowledge gaps and reformulates queries (FAIR-RAG, RFM-RAG); **(b) Retriever-level feedback** — LLM output quality is used to train or reweight retrievers (FiGRet, DynamicRAG); **(c) Document-level feedback** — relevance assessments of retrieved documents inform expansion/contraction (ADORE, FLAIR).

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **Evidence-Centric Refinement (FAIR-RAG)** | Structured Evidence Assessment (SEA) decomposes query into a checklist, verifies what's confirmed, identifies "Remaining Gaps," then generates targeted queries for missing information. Loops until sufficiency. |
| **RFM-RAG (Retrieval Feedback Memory)** | Maintains a dynamic evidence pool. Generates refined queries using relational triples from questions + pool. R-Feedback Model evaluates completeness. Stateful across turns. |
| **ADORE (ADapt, Observe, Relevance Evaluate)** | Three-step loop: generate pseudo-passages → retrieve from corpus → assess relevance against *original* query. Produces structured feedback: what to reinforce, what's missing, what to suppress. Retrieval-grounded, not generation-only. |
| **FiGRet (Fine-grained Guidance for Retrievers)** | LLM as "teacher" provides granular feedback on three objectives: relevance, comprehensiveness, purity. Uses guided discovery learning for retriever alignment. Only 20K samples needed. |
| **DynamicRAG** | Reranker as RL agent. Uses LLM output quality as reward. Learns to dynamically adjust both order *and count* of documents. SFT for warm start + GRPO for optimization. |
| **FLAIR (Feedback Learning for Adaptive IR)** | Contextual multi-armed bandits over document embedding space. User feedback (thumbs up/down) scatters signal indicators. Two-track ranking: relevance + feedback signals. No fine-tuning needed. |
| **ExSearch** | LLM interleaves three actions: think (generate query), search (trigger retriever), record (extract evidence). Self-incentivized via Generalized EM algorithm. |
| **AutoRefine** | "Search-and-refine-during-think" paradigm. RL post-training with answer + retrieval rewards. Explicit knowledge refinement step extracts key facts from noisy documents. GRPO optimization. |
| **Orion (Test-Time Adaptive Search)** | Trains compact models (350M–1.2B params) for dynamic search policies. Turn-level rewards (cosine similarity + rank). Beam search with structural markers. Learns when to backtrack. |
| **SUNAR / SlideGAR / QUAM** | Corpus feedback: neighborhood-based expansion. If top documents are relevant, their graph neighbors likely are too. Query affinity modeling (QUAM) prioritizes neighbors by similarity. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | ↑↑↑ Very high. Each feedback iteration requires LLM inference + retrieval. FAIR-RAG and ADORE may require 2–4 rounds. Orion's beam search compounds this. |
| **Accuracy** | ↑↑↑ Significant gains on complex queries. FAIR-RAG demonstrates substantial improvements in trustworthiness. ExSearch: +7 F1 points over RankRAG-70B (HotpotQA) with a 7B model. AutoRefine: 20% refinement success rate improvement. |
| **Complexity** | Very high. Requires careful loop design, stopping criteria, reward engineering. RL-based approaches (DynamicRAG, R3-RAG) add training infrastructure complexity. |
| **Cost** | ↑↑↑ High. Multiple rounds of LLM calls. Orion mitigates this by using small models (350M). ADORE uses adaptive termination to avoid unnecessary rounds. |

#### Production Applicability

**Emerging.** FAIR-RAG and FLAIR are designed with production constraints in mind. FLAIR explicitly targets low latency and real-time feedback. ADORE's retrieval-grounded approach (preventing query drift) is production-relevant. FiGRet's small-sample requirement (20K) makes retriever alignment feasible. The bandit-based approaches (FLAIR) are particularly well-suited for production where user feedback naturally accumulates. RL-based methods (DynamicRAG, R3-RAG) remain experimental.

#### Key Papers / Implementations

- **FAIR-RAG: Faithful Adaptive Iterative Refinement** — arXiv 2510.22344, 2025
- **RFM-RAG: Retrieval Feedback Memory** — arXiv 2508.17862, 2025
- **ADORE: Iterative Query Expansion with Retrieval-Grounded Relevance Feedback** — arXiv 2606.13905, 2025
- **FiGRet: Fine-Grained Guidance for Retrievers** — arXiv 2411.03957, 2024
- **DynamicRAG: Leveraging LLM Outputs as Feedback for Dynamic Reranking** — arXiv 2505.07233, 2025
- **FLAIR: Feedback Learning for Adaptive IR** — arXiv 2508.13390, 2025
- **ExSearch: Iterative Self-Incentivization for Agentic Search** — arXiv 2505.20128, 2025
- **AutoRefine: Search and Refine During Think** — OpenReview 2025
- **Orion: Think Before You Retrieve** — arXiv 2511.07581, 2025
- **Test-time Corpus Feedback: From Retrieval to RAG** — Findings of EACL 2026

---

### 2.7 Explainable Retrieval

#### How It Works

Explainable retrieval provides transparency into *which* retrieved documents influenced the generation and *how*. This goes beyond simple citation to answer: Was this statement grounded in a retrieved source? Which specific passage? Can the user verify it? Modern approaches span several dimensions: **(a) Citation generation** — the LLM produces in-line references to source documents during generation; **(b) Post-hoc attribution** — analyzing model internals (attention patterns, saliency) to determine which documents influenced which output tokens; **(c) Visual attribution** — highlighting exact evidence regions in document screenshots with bounding boxes; **(d) Faithfulness verification** — ensuring citations reflect actual document usage, not post-hoc rationalization.

#### Mechanisms / Algorithms

| Mechanism | Description |
|-----------|-------------|
| **In-line Citation (Generation-Time)** | LLM produces `[1]`, `[2]` references inline with generated text. TRACE framework uses RL to train structured output with evidence citations. SAFE provides sentence-level in-generation attribution. |
| **Post-hoc Citation (P-Cite)** | Attributions computed after generation. Lexical (keyword + semantic) matching, fine-tuned BERTScore models, or lightweight LLM-based matching. CiteFix: +15.46% relative improvement in citation accuracy. |
| **MIRAGE (Model Internals-Based)** | Uses attention patterns and saliency methods to detect context-sensitive answer tokens and pair them with contributing documents. Plug-and-play, no fine-tuning needed. |
| **Shapley-Based Attribution** | Applies Shapley values to quantify each document's marginal contribution. Computationally expensive (2^|D| subsets). KernelSHAP and ContextCite provide approximations. Handles redundancy, complementarity, and synergy. |
| **VISA (Visual Source Attribution)** | VLMs identify evidence regions with bounding boxes in document screenshots. End-to-end: answer + document ID + bounding box. First visual attribution approach for RAG. |
| **CiteEval / CiteBench** | Principle-driven citation evaluation framework. Three principles: factual consistency, provenance precision, and citation utility. Multi-stage human annotation. |
| **TRACE (Transparent RAG)** | RL training for structured outputs: selected references + reasoning traces + final answer. Reward functions for correctness, citation faithfulness, and formatting. +10–30% accuracy improvement. |
| **VeriCite** | Three-stage: initial answer generation → NLI-based claim verification → supporting evidence selection → final answer refinement. Significantly improves citation quality while maintaining correctness. |
| **Citention** | Framework integrating generative, attention-based, and retrieval-based citation methods. Attention-based citation reveals LLMs encode more than they generate. |
| **Proof Packets** | Claim-level diagnostic records binding atomic claims to minimal evidence, provenance, conflict, counterfactual, validator, and visibility states. Diagnoses 6 distinct evidence-use failure modes. |

#### Tradeoffs

| Dimension | Assessment |
|-----------|------------|
| **Latency** | Variable. In-line citation (generation-time) adds ~20–50% generation overhead. Post-hoc citation runs separately, parallelizable. Shapley-based: prohibitively expensive for production (hundreds of LLM calls per query). MIRAGE: minimal overhead (uses existing forward-pass internals). |
| **Accuracy / Faithfulness** | Fundamental tension between correctness and faithfulness. A citation can be "correct" (the source contains the information) but not "faithful" (the model didn't actually use it). Generating correct but unfaithful citations builds misplaced trust. |
| **Groundedness** | TRACE and VeriCite significantly improve groundedness. TRACE: +10–30% accuracy. MIRAGE: high agreement with human attribution. VISA: fine-grained visual grounding at bounding-box level. |
| **User Trust** | IBM CHI 2025 study with 50 financial professionals: source transparency features (attribution + highlighting) substantially improved trust. Confidence scores alone did not. UroBot study: 74% vs. 30% source attribution ratings vs. standard LLMs. |
| **Complexity** | Moderate (in-line citation) to very high (Shapley, proof packets). Citation evaluation remains difficult — requires principled frameworks like CiteEval. |

#### Production Applicability

**Ready now (citation generation).** Perplexity, You.com, and most commercial RAG systems already provide document-level citations. In-line/sentence-level citation (SAFE, CiteFix) is production-deployable with moderate engineering effort. **Emerging (faithfulness).** TRACE, MIRAGE, and VeriCite represent the next generation. **Academic (proof packets, Shapley).** Important for understanding failure modes but not yet production-practical.

A critical finding: the IBM study and the UroBot randomized controlled trial both demonstrate that source transparency directly drives user trust. This makes explainable retrieval the highest-ROI investment for user-facing RAG products, even beyond accuracy improvements.

#### Key Papers / Implementations

- **TRACE: Towards Transparent RAG** — arXiv 2505.13258, 2025
- **MIRAGE: Model Internals-based RAG Explanations** — EMNLP 2024
- **VISA: Visual Source Attribution** — ACL 2025
- **Source Attribution in RAG (Shapley)** — arXiv 2507.04480, 2025
- **CiteEval / CiteBench** — ACL 2025
- **VeriCite: Towards Reliable Citations** — arXiv 2510.11394, 2025
- **CiteFix: Enhancing RAG Accuracy Through Post-Processing** — arXiv 2504.15629, 2025
- **SAFE: Sentence-Level In-generation Attribution** — arXiv 2505.12621, 2025
- **Citention: Citation Failure Definition, Analysis and Mitigation** — arXiv 2510.20303, 2025
- **Proof Packets for Diagnosing Evidence-Use Failures** — ACL ARR 2026
- **Exploring Trust and Transparency in RAG** — IBM Research, CHI 2025
- **UroBot: Enhancing Clinicians' Trust via Transparent Source Attribution** — European J. Cancer 2026
- **Generation-Time vs. Post-hoc Citation** — arXiv 2509.21557, 2025
- **CiteGuard: Faithful Citation Attribution via Retrieval-Augmented Validation** — arXiv 2510.17853, 2025

---

### 2.8 Comparison Table

| Technique | Latency Impact | Recall/Accuracy Gain | Complexity | Production Readiness | Key Limitation |
|-----------|---------------|---------------------|------------|---------------------|----------------|
| **Fusion Retrieval** | +50–100% | ++ (large) | Low–Moderate | ✅ Ready | Overkill for simple queries; benefits context-dependent |
| **Multi-Hop Retrieval** | +200–500% | +++ (very large) | Very High | ⚠️ Emerging | Error propagation; latency/cost prohibitive for many use cases |
| **Hierarchical Indices** | −30–60% (faster) | −1–5% (slight loss) | Moderate | ✅ Ready (HNSW) | Build/update cost for non-LSM variants |
| **Multi-Faceted Filtering** | −10–60% (varies) | ++ (large) | Moderate | ✅ Ready (basic) ⚠️ Emerging (adaptive) | Adaptive methods need model serving |
| **Dartboard Retrieval** | +10–20% | ++ (large) | Low | ✅ Ready | Only optimizes diversity; doesn't improve recall |
| **Feedback Loops** | +200–400% | +++ (very large) | Very High | ⚠️ Emerging | High per-query cost; needs careful stopping criteria |
| **Explainable Retrieval** | +20–200% (varies) | — (trust/safety) | Moderate–High | ✅ Ready (basic) ⚠️ Emerging (faithfulness) | Faithfulness remains unsolved; citation ≠ actual usage |

---

### 2.9 Production Assessment

#### What Matters Most for Production (2025–2026)

**Tier 1 — Deploy immediately:**

1. **Fusion Retrieval (RRF)** — The single highest-ROI technique. Simple RRF implementation costs <20 lines of code and consistently improves recall. Use with 2–3 complementary retrievers (BM25 + dense). Do NOT blindly fuse everything — production data shows benefits are concentrated on recall-scarce queries. Consider adaptive fusion (AMSRAG, MoR) to avoid wasteful compute on easy queries.

2. **Dartboard Retrieval** — Solves the universal context-window-waste problem with negligible overhead. Drop-in replacement for any RAG system's final selection step. Combine with fusion for maximum effect: fusion improves recall, Dartboard eliminates redundancy.

3. **Explainable Retrieval (In-line Citations)** — Not optional for user-facing products. The IBM/UroBot studies are unequivocal: source transparency drives trust. Start with document-level citations; invest in sentence-level attribution (SAFE, CiteFix) as user trust becomes critical.

**Tier 2 — Invest strategically:**

4. **Multi-Faceted Filtering (Adaptive _k_)** — CAR (Coinbase, deployed in production) demonstrates that dynamic cutoff selection cuts tokens by 60% and latency by 22%. This directly reduces per-query cost — the dominant production expense. Implement training-free methods (CAR, TAA-_k_) before fine-tuning-based approaches (DPS).

5. **Hierarchical Indices** — If you're operating at 100M+ vectors, HNSW or CHANNI-style indices are non-negotiable. For streaming workloads, investigate SPI or LSM-VEC. The semantic hierarchy paradigm (SPI) — routing queries to minimum needed representation depth — will likely become standard for cost-conscious production systems.

**Tier 3 — Watch/experiment:**

6. **Feedback Loops** — The most exciting research direction but highest production risk. The key insight from ADORE and Orion: make feedback *retrieval-grounded* (observe actual corpus behavior) not *generation-grounded* (blindly rewrite queries). FLAIR's bandit approach is the most production-practical — accumulative user feedback naturally trains the system without fine-tuning.

7. **Multi-Hop Retrieval** — Reserve for high-stakes, low-volume domains (legal, medical, financial) where recall is non-negotiable and latency is tolerable. L-RAG (intermediate representations) is the most promising path to production — multi-hop accuracy at single-hop latency. But the technique is too young for general deployment.

#### Key Trends

- **Convergence**: The winning TREC 2025 RAG system combined fusion + feedback (HyDE) + reranking. The production winners (Coinbase CAR) combine adaptive filtering + dynamic cutoff. The pattern is modular composition, not monolithic retrieval.

- **Cost-awareness**: Every 2025 paper acknowledges that more retrieval ≠ better. Adaptive retrieval (AMSRAG, CAR, TAA-_k_) that routes queries to appropriate retrieval depth is the meta-technique unifying all others.

- **Faithfulness > Correctness**: The explainability community has converged on a critical distinction — a citation can be correct (the source contains the info) without being faithful (the model didn't actually use it). MIRAGE, TRACE, and proof packets all attack this gap from different angles.

- **Small-model retrieval**: Orion (350M params) and MoR (0.8B total) demonstrate that sophisticated retrieval policies don't require large models. This is critical for production cost profiles.

#### Recommendations by Use Case

| Use Case | Priority Techniques |
|----------|-------------------|
| **Customer-facing chatbot** | Fusion (RRF) + Dartboard + Explainable (in-line citations) |
| **Enterprise knowledge base** | Fusion + Multi-Faceted Filtering (adaptive _k_) + Hierarchical Indices |
| **Legal/medical research** | Multi-Hop (L-RAG or FAIR-RAG) + Explainable (TRACE or sentence-level) + Feedback Loops |
| **Real-time search** | Hierarchical Indices (HNSW/CHANNI) + Multi-Faceted Filtering (pre-filter) |
| **Cost-sensitive high-volume** | Single retriever + CAR (adaptive cutoff) + Dartboard (diversity) |
| **High-trust applications** | Explainable (full TRACE/MIRAGE pipeline) + Fusion + Feedback Loops (for continuous improvement) |

---

*Research compiled June 2025–2026. Sources: ACL 2025, EMNLP 2025, Findings of ACL/EMNLP/NAACL 2025, OSDI 2025, VLDB 2025, TREC 2025 RAG Track proceedings, arXiv preprints.*
