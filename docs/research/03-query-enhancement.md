## 3. Query Enhancement

Query enhancement transforms raw user queries into richer representations before retrieval, bridging the semantic gap between short/vague questions and long/detailed documents. As of mid-2026, the field has matured from simple expansion to multi-stage, RL-trained, and offline-precomputed strategies.

---

### 3.1 Query Transformations (Rewriting, Expansion, Decomposition)

#### 3.1.1 Query Rewriting

**How it works:** An LLM takes the user's raw query and restructures it — rephrasing syntax, substituting vocabulary toward corpus-preferred terminology, disambiguating terms, or filling in underspecified context. Unlike expansion (which adds terms), rewriting may change structure entirely. Recent work (DVCQR, 2026) generates *separate* rewrites optimized for sparse vs. dense retrievers. The rewrite is then embedded and used for vector search, replacing or augmenting the original query.

**Use cases:** Conversational search (resolving context dependence across turns), domain-specific verticals where user vocab ≠ corpus vocab (medical queries, legal search, codebase Q&A), and knowledge-gap scenarios where the LLM itself doesn't know the answer and needs better retrieval.

**Complexity & latency:** 1 LLM call per query (~100–500 ms with small models, 1–3 s with large models). Lightweight SLMs like Azure's query rewriting model generate up to 10 rewrites in ~158 ms. RL-trained rewriters (RL-QR, RaFe) add upfront training cost but no inference overhead over base rewriting.

**Benchmarks:**
- **DVCQR (ACL 2026):** Consistent SoTA across TopiOCQA, QReCC, CAsT-19/20 under both BM25 and ANCE dense retrieval.
- **Q-PRM (EMNLP Findings 2025):** Outperforms outcome-supervised RL across AmbigQA, PopQA, NQ, HotpotQA. Online A/B: 57.3% win rate vs. production baseline.
- **RaFe (ASPLOS 2024):** +2–3% QA accuracy over baseline OQR in Expand-Ranked setting on NQ and FreshQA.
- **Caution:** Prompt-only rewriting can *degrade* retrieval by 9.0% nDCG@10 on well-optimized domains (FiQA) when it replaces domain-specific terms (arXiv:2603.13301).
- **Microsoft Azure AI Search:** Query rewriting + semantic ranker delivers +22 NDCG@3 over hybrid L1 alone; rewriting alone adds +4 NDCG@3 on text-only indexes.

**Production readiness:** **High.** Deployed in Microsoft Azure AI Search (general availability), Elasticsearch query rewriting pipelines, and LangChain's `MultiQueryRetriever`. Best deployed with a gating mechanism to skip rewriting when queries are already well-formed. Prefer fine-tuned SLMs over prompt-only for stable terminology alignment.

**Key papers:**
- *"Masking or Mitigating?"* (arXiv:2604.06097, 2026) — First systematic study of query rewriting's effect on retriever biases; found simple rewriting reduces aggregate bias by 54%.
- *"DVCQR: Dual-View Conversational Query Rewriting"* (ACL 2026)
- *"RaFe: Ranking Feedback Improves Query Rewriting for RAG"* (2024)
- *"Q-PRM: Adaptive Query Rewriting via Step-level Process Supervision"* (EMNLP Findings 2025)
- *"Crafting the Path: Robust Query Rewriting for IR"* (arXiv:2407.12529)

---

#### 3.1.2 Query Expansion

**How it works:** Adds related terms, synonyms, entities, or context to the original query *without* fundamentally changing its structure. Unlike rewriting, expansion augments the existing query. Methods include: LLM-generated keyword lists, pseudo-relevance feedback (PRF — using top-K retrieved docs to expand), and entity-grounded expansion (extracting key entities, then appending definitions or related concepts). The expanded query is used as-is with a hybrid retriever or in a `should` clause (lexical) alongside the original query in a `must` clause.

**Use cases:** Lexical (BM25) retrieval where vocabulary mismatch is the primary failure mode, domain-specific corpora where controlled vocabulary matters, and any scenario where adding rather than replacing terms is safer. Particularly valuable for text-only indexes that can't migrate to vectors.

**Complexity & latency:** Lightweight when using precomputed thesauri or shallow models. LLM-based expansion adds 1 call per query. Pseudo-relevance feedback adds a retrieval round then an expansion LLM call, doubling retrieval latency. Elasticsearch found that SLMs match LLM expansion quality at a fraction of the cost.

**Benchmarks:**
- **Elasticsearch (2026):** Lexical keyword enrichment from prompt-based expansion provides significant gains on text-only indexes; pseudo-answer generation is the single best expansion strategy for multistage pipelines.
- **ADORE (arXiv:2606.13905, 2026):** Iterative retrieval-grounded expansion outperforms static expansion, with +122.9% over BM25 baseline and +9.2% over best static LLM-based expansion on BEIR benchmarks.
- **Azure:** Query rewriting (which includes expansion-like variants) improves NDCG@3 by +2 to +4 more points on text-only L1 vs. hybrid L1.

**Production readiness:** **Very high.** The oldest query enhancement technique, with decades of deployment in traditional IR (RM3, Rocchio). Modern LLM-based variants are production-ready but benefit from templated output (structured keyword lists rather than free-form text) for stability. Elasticsearch recommends keyword lists as a `should` clause booster, not as a replacement for the original query.

**Key papers:**
- *"ADORE: Iterative Query Expansion with Retrieval-Grounded Relevance Feedback"* (arXiv:2606.13905, 2026)
- *"Query rewriting strategies for LLMs & search engines"* (Elasticsearch Labs, 2026)
- *"Improving Neural Retrieval with Attribution-Guided Query Rewriting"* (arXiv:2602.11841)

---

#### 3.1.3 Query Decomposition

**How it works:** Complex/multi-hop queries are broken into simpler sub-questions by an LLM. Each sub-question is retrieved independently, results are merged (deduplicated), and a reranker filters or a final LLM synthesizes across the evidence. Key variants: (a) flat decomposition (parallel sub-questions), (b) sequential/chain decomposition (each sub-answer feeds the next), and (c) topology-graph decomposition (ToQD, 2025) where sub-questions form a DAG allowing parallel and sequential branches. Some frameworks (UniRAG, EMNLP 2025) combine decomposition with entity-grounding and verifier modules for reliability.

**Use cases:** Multi-hop QA (HotpotQA, 2WikiMultihopQA, MuSiQue), comparative queries ("which company made more profit?"), temporal reasoning across multiple documents, and any query requiring facts from non-co-occurring documents. Pairs naturally with multi-query retrieval.

**Complexity & latency:** Higher than single-query rewriting: N sub-questions × (1 retrieval + potentially 1 LLM answer per sub-question) + 1 synthesis LLM call. For 3 sub-questions, expect 3–4× the retrieval latency plus 2–4 LLM calls. ToQD reduces this by using self-verify inference to skip unnecessary retrievals. The NVIDIA RAG Blueprint supports query decomposition natively with iterative refinement and follow-up generation.

**Benchmarks:**
- **Question Decomposition for RAG (ACL-SRW 2025):** +36.7% MRR@10 and +11.6% F1 on MultiHop-RAG and HotpotQA over standard RAG.
- **UniRAG (EMNLP Findings 2025):** Consistent improvements across LLaMA-3.1-8B, GPT-3.5-Turbo, and Gemini-1.5-Flash on HotpotQA, 2WikiMultihopQA, MedMCQA, MedQA, FEVER, and SciFact.
- **DAGR (2025):** Decomposition-augmented graph retrieval achieves comparable/superior performance to SoTA with smaller models.
- **ACL 2025 multi-hop transformation paper:** Decomposing multihop questions + generating answerable questions from documents improves across MuSiQue, 2WikiMultiHopQa, HotpotQA.
- **LiveRAG Challenge (SIGIR 2025):** Single-subquestion rewriting alone *harms* retrieval; only original query + multiple diverse rewrites improves recall (original alone: R@500 = 0.320; original + 3 rewrites: 0.397).

**Production readiness:** **Moderate-High.** NVIDIA RAG Blueprint and Haystack provide production implementations. The main concern is latency amplification — decomposition multiplies retrieval calls. Best deployed with: (a) a complexity classifier that only decomposes when needed, (b) parallel sub-query retrieval, and (c) aggressive deduplication.

**Key papers:**
- *"UniRAG: A Unified RAG Framework"* (EMNLP Findings 2025)
- *"Question Decomposition for RAG"* (ACL-SRW 2025)
- *"ToQD: Topology-of-Question Decomposition"* (COLING 2025)
- *"DAGR: Decomposition Augmented Graph Retrieval"* (arXiv:2506.13380)
- *"Generating Complex Question Decompositions in the Face of Distribution Shifts"* (NAACL 2025)

---

### 3.2 HyDE (Hypothetical Document Embeddings)

**How it works:** Given a user query, an instruction-following LLM is prompted to "write a document that answers the question" — producing a hypothetical/synthetic passage. This passage is then embedded using a contrastive encoder (e.g., Contriever). The hypothesis is that the generated passage sits closer to real relevant documents in embedding space than the original query does, because it shares the vocabulary, structure, and density of the target corpus. The embedding is then used for vector similarity search against the real document corpus. The retrieval problem is thus *decomposed* into two tasks: NLG (generate a relevant-like document) and document-to-document similarity matching. No retrieval-specific training is required.

**Use cases:** Domains with a large semantic gap between short user queries and long documents (legal, medical, technical), zero-shot settings where no labeled relevance data exists, multilingual retrieval (original paper showed gains on Swahili, Korean, Japanese), and developer support (Stack Overflow Q&A pairs). Particularly effective when the corpus is highly structured or uses specialized terminology not present in natural-language queries.

**Complexity & latency:** 1 LLM generation call + 1 embedding call + 1 vector search. The LLM call is the bottleneck (0.5–3 s for a mid-sized model). In practice, many implementations generate 3–5 hypothetical documents and average their embeddings, multiplying the LLM cost. For latency-sensitive apps, use a smaller/faster LLM for hypothesis generation (GoogLe's Gemma 4B was tested with acceptable quality). Total: 1–5 s.

**Benchmarks:**
- **Original HyDE (Gao et al., 2022):** Significantly outperforms Contriever zero-shot on 11 query sets across Web Search, QA, Fact Verification, and languages (Swahili, Korean, Japanese) on BEIR. Exceeds fine-tuned DPR and ANCE on several tasks without any relevance-label training.
- **TREC RAG 2025 — #1 System (UTokyo-HitU):** HyDE Vector Mix (weighted combination of original query + hypothetical answer embeddings at ratio α=0.7) outperforms both vanilla HyDE and text concatenation. Achieved **nDCG@30 = 0.693, nDCG@100 = 0.613, recall@100 = 0.257**, placing **1st out of 12 teams (46 runs)** in the Retrieval task. HyDE Vector Mix improved nDCG@10 from 0.493 (no HyDE) to 0.564, a +14.4% relative gain for BGE-small.
- **Adaptive HyDE (Lei et al., Jul 2025):** On developer support (Stack Overflow Java+Python, 5,510 held-out questions), HyDE with answer-context retrieval achieved Helpfulness 4.2, Correctness 4.1, Detail 4.0 (~+20% over standard RAG). Adaptive thresholding delivered 100% coverage on novel questions.
- **SL-HyDE (Li et al., 2024):** Self-learning HyDE for medical retrieval achieves +4.9% NDCG@10 over vanilla HyDE.
- **HyDE + Rocchio (Jedidi et al., Nov 2025):** +4.2% Recall@20 vs. MuGI Concat on web and low-resource retrieval.
- **Elasticsearch Labs (2026):** Pseudo-answer generation (HyDE-style) identified as the single most effective strategy for maximizing recall in multistage pipelines.

**Production readiness:** **High.** Integrated into Haystack (first-class `HypotheticalDocumentEmbedder` component), LangChain, and Azure AI Search (via pseudo-answer prompt templates). Caveats: (a) adds LLM latency per query — use small/fast models; (b) hallucinations in the hypothetical document can misdirect retrieval — keep generated text short (~1 paragraph); (c) prompt design matters — generate a *document fragment*, not a chatty answer. Production systems like LM-Kit.NET offer both HyDE and Multi-Query as configurable strategies with recommended heuristics.

**Key papers:**
- *"Precise Zero-Shot Dense Retrieval without Relevance Labels"* (Gao et al., 2022) — Original HyDE paper
- *"Never Come Up Empty: Adaptive HyDE Retrieval"* (arXiv:2507.16754, Jul 2025)
- *"UTokyo-HitU at TREC 2025 RAG Track"* (TREC 2025) — HyDE Vector Mix, #1 system
- *"SL-HyDE"* (Li et al., 2024) — Self-learning HyDE for medical retrieval

---

### 3.3 HyPE (Hypothetical Prompt Embeddings)

**How it works:** HyPE inverts HyDE: instead of generating hypothetical answers at query time, it generates hypothetical *questions* for each document chunk **at indexing time**. For each chunk, an LLM is prompted: "What questions would this chunk answer?" — producing 3–8 question-like prompts. Each prompt is embedded and stored in the vector database, pointing back to the original chunk. At query time, the user's question is embedded and matched against this sea of precomputed question embeddings. This transforms retrieval from **question → document** matching into **question → question** matching, a fundamentally easier semantic matching problem. The key architectural insight: the vector store's search key (question embedding) is decoupled from its stored content (document chunk). No per-query LLM calls needed.

**Use cases:** Latency-sensitive production deployments where per-query LLM calls are too expensive, Q&A systems over static/semi-static knowledge bases (documentation, policy, internal wikis), and domains where the user naturally asks questions (customer support, FAQs, search). Also composable with HyDE — HyPE provides the baseline offline index enrichment, HyDE handles edge cases at query time.

**Complexity & latency:** **Indexing time (offline):** High. For a corpus of N chunks, generates K × N questions (e.g., 5 questions × 10,000 chunks = 50,000 LLM calls + 50,000 embeddings). Index size balloons by factor K. **Query time:** Minimal — 1 embedding + 1 vector search, identical to standard RAG. The over-fetching + deduplication strategy is needed (fetch K × top_k results, deduplicate by chunk content, return top_k unique chunks) because the same chunk may have multiple near-match question embeddings.

**Benchmarks:**
- **HyPE preprint (SSRN, 2025):** Up to **+42 percentage points improvement in retrieval context precision** and **+45 percentage points in claim recall** compared to standard RAG, evaluated across 6 datasets. Outperforms both Naive RAG and HyDE on multiple metrics.
- The technique is new enough that comprehensive third-party benchmark comparisons are still emerging as of mid-2026.

**Production readiness:** **Moderate.** The concept is production-viable (zero query-time overhead, elegant semantic matching), but the indexing cost is substantial. Best suited for:
- Corpora that change infrequently (rebuild index once, serve many queries)
- Systems where query-time latency is paramount (real-time chatbots, edge devices)
- Hybrid setups where HyPE covers 80%+ of cases and HyDE is the fallback

Caveats: (a) If the LLM misses an important angle when generating questions, the corresponding chunk becomes unfindable for that query angle (mitigation: generate 5–8 questions per chunk). (b) Deduplication logic is mandatory. (c) Index size grows linearly with K — for very large corpora, storage cost may be prohibitive. Reference implementation available via NirDiamant's `RAG_Techniques` repo and Semantic Kernel-based implementations.

**Key papers:**
- *"Bridging the Question-Answer Gap in RAG: Hypothetical Prompt Embeddings"* (IEEE, 2025) — Original HyPE paper
- *"HyPE: The Index That Already Speaks Questions"* (Panchal, Medium, May 2026) — Practical tutorial and architecture discussion
- Reference implementation: NirDiamant/RAG_Techniques: `HyPE_Hypothetical_Prompt_Embeddings.py`

---

### 3.4 Multi-Query Retrieval

**How it works:** Instead of retrieving with a single query, an LLM generates N semantically diverse variants of the original query (or breaks it into sub-aspects). Each variant is used for an independent retrieval, producing N separate ranked result lists. These lists are fused using Reciprocal Rank Fusion (RRF): `RRF(d) = Σ 1/(k + rank_i(d))`, ensuring documents that appear highly ranked in *any* single variant's result set are boosted. The fused deduplicated list is passed downstream. Unlike query rewriting (which picks one best rewrite), multi-query explicitly leverages diversity, assuming different phrasings probe different regions of embedding space. Also known as RAG-Fusion in practitioner circles.

**Use cases:** Open-domain QA with high vocabulary variance, search applications where recall trumps precision, conversational search, multi-faceted queries ("What are the causes, symptoms, and treatments of X?"), and composable with HyDE (HyDE generates the hypothesis, Multi-Query generates variants of the hypothesis). Also pairs with step-back prompting for hybrid breadth+depth strategies.

**Complexity & latency:** 1 LLM call to generate variants + N parallel retrieval calls + RRF fusion. N is typically 3–5 for a good cost/benefit ratio. Parallel execution (e.g., Haystack's `MultiQueryEmbeddingRetriever` with thread pool) keeps additional latency close to that of the slowest single retrieval. For 5 variants with parallel retrieval, expect 1.5–2× the latency of single-query retrieval.

**Benchmarks:**
- **DMQR-RAG (ACL 2025):** Four-strategy multi-query rewriting framework. +14.45% P@5 on FreshQA over best single-query baseline. +7% on HotpotQA over HyDE, +2.55% over RAG-Fusion. On AmbigQA: +1.47% EM, +3.75% F1 over HyDE. Online test with 15M real queries: H@5 improved +2.0%, P@5 +10.0%.
- **Multi-Query on vocabulary-variant corpora (practitioner reports):** +5–15% Recall@K on open-domain QA; +1–5% on tightly-scoped technical corpora where terminology is shared. Gains saturate after 3–5 variants.
- **AMSER (arXiv:2511.02770):** Autoregressive multi-embedding retriever achieves **4× better** retrieval than single-embedding on synthetic multimodal targets, +4–21% relative gains on real-world multi-answer datasets.
- **LiveRAG:** Original query + 3 diverse rewrites = R@500 of 0.397 (vs. 0.320 for original alone). Original + 10 rewrites gives only 0.398 — gains saturate rapidly.
- **MQRF-RAG (2025):** +14.45% P@5 on FreshQA, +9% P@5 on AmbigNQ over single-query.
- **Query Variant Selection (arXiv:2604.22661):** QPP (Query Performance Prediction) can identify promising variants before retrieval, but simple feature-gating is weak (AUC = 0.593); full generation-then-select is more reliable if latency allows.

**Production readiness:** **Very high.** First-class support in LangChain (`MultiQueryRetriever`), Haystack (`MultiQueryEmbeddingRetriever` + `QueryExpander`), LM-Kit.NET (MultiQuery mode), and Elasticsearch (multi-hypothesis expansion). Best practices: (a) limit to 3–5 variants (diminishing returns beyond that), (b) use parallel retrieval, (c) validate variant quality (filter out redundant/off-topic variants), (d) always include the original query in the variant set, (e) use RRF over score averaging for fusion.

**Key papers:**
- *"DMQR-RAG: Diverse Multi-Query Rewriting for RAG"* (arXiv:2411.13154, 2024/2025)
- *"MQRF-RAG: Optimization of RAG Multi Query Rewrite"* (ACM, 2025)
- *"Beyond Single Embeddings: Capturing Diverse Targets with Multi-Query Retrieval"* (arXiv:2511.02770)
- *"Can QPP Choose the Right Query Variant?"* (arXiv:2604.22661)
- *RAG-Fusion* (Rackauckas, 2024) — Practitioner introduction of RRF-based multi-query fusion

---

### 3.5 Step-Back Prompting

**How it works:** Before retrieval, an LLM is prompted to "take a step back" and generate a more abstract version of the user's specific question — focused on the underlying concept, principle, or domain, rather than the literal phrasing. For example, "What did the CEO say about Q3 margins in the 2024 earnings call?" → "What were the key financial results and management commentary from the 2024 earnings calls?" Both the original and abstracted queries are used for retrieval (dual-retrieval), and results are merged/re-ranked. The abstraction surfaces foundational/conceptual documents that the literal query would miss, while the original query preserves specificity. First introduced by Google DeepMind in 2023.

**Use cases:** Knowledge-intensive QA (TimeQA, SituatedQA), over-constrained queries with dates/IDs/version numbers where the corpus may discuss the topic but not with the exact constraints, multi-hop reasoning (MuSiQue), and domains where principles/concepts are documented separately from specific instances (policy manuals, science textbooks, API documentation, codebase architecture docs).

**Complexity & latency:** 1 LLM abstraction call + 2 retrieval calls (original + abstracted) + optional reranker. ~300–800 ms additional latency vs. single-query retrieval with a fast LLM. Using a cheap/fast model for abstraction reduces cost. Guardrails needed to prevent over-abstraction (ResNet50 batch norm → "deep learning" is too general; should be "batch normalization in deep neural networks").

**Benchmarks:**
- **Original (Zheng et al., ICLR 2024):** Step-back prompting + RAG improves PaLM-2L on TimeQA by **+34%**, MMLU Physics by **+7%**, MMLU Chemistry by **+11%**, and MuSiQue by **+7%** over baseline. On Knowledge QA: GPT-4 + RAG baseline = 45.6%; with step-back = **high-60s%** (from the paper's Figure 5).
- **Practitioner reports (2025–2026):** Step-back paired with RAG surfaces canonical references (textbook chapters, standards documents, internal policy manuals) that literal-query retrieval misses entirely. When combined with dual-retrieval + reranker, it adds safety against over-abstraction.
- **SurePrompts (2026):** Recommends step-back as the best retrieval anchor for knowledge-intensive tasks when a structured knowledge base exists.

**Production readiness:** **Moderate.** The technique is conceptually simple and easy to implement (one prompt + dual retrieval), but prone to over-abstraction. Guidelines: (a) generalize one level up, not to the entire domain; (b) keep entity names intact; (c) use hybrid retrieval (BM25 catches literal tokens, dense catches semantics); (d) use dual-retrieval mode (original + abstract) not abstract-only; (e) validate abstraction quality on 5–10 real queries before deployment. If over-abstraction is common, fall back to multi-query retrieval instead.

**Key papers:**
- *"Take a Step Back: Evoking Reasoning via Abstraction in Large Language Models"* (Zheng et al., ICLR 2024, Google DeepMind)
- *"Step-Back Prompting: Smarter Query Rewriting for Higher Accuracy RAG"* (Scaibu, devops.dev, Sep 2025) — Practical deployment guide

---

### 3.6 Query Planning and Routing

**How it works:** Instead of a fixed retrieval pipeline, a router dynamically decides *how* to handle each query — which retriever to use (sparse vs. dense, or a specific index), which knowledge base/source to query, whether to decompose, whether retrieval is even needed, and which downstream LLM to answer. Architectures range from hard routing (select one source → retrieve) to soft routing (retrieve from all → verify → select). Recent advances include: (a) RAG-aware routing (RAGRouter, NeurIPS 2025) that models how retrieved documents shift LLM capabilities, (b) step-wise routing (R1-Router, DeepSieve) that makes per-subquery source decisions during multi-step reasoning, (c) training-free routing using retrieval score skewness (SkewRoute), and (d) learning-to-rank retrievers as a routing problem (LTRR).

**Use cases:** Multi-source heterogeneous knowledge bases (SQL + vector stores + APIs), cost-sensitive deployments (route simple queries to cheap/small LLMs, complex queries to large/powerful ones), federated search across organizations (RAGRoute), and any RAG system with a pool of retrievers where no single retriever dominates.

**Complexity & latency:** Varies dramatically by architecture:
- **Training-free (SkewRoute):** Negligible — compute retrieval score skewness after the first retrieval, route. <0.001× the runtime of training-based methods.
- **Hard routing (LLM-as-Router):** 1 routing LLM call pre-retrieval (~100–500 ms) + targeted retrieval. Failure mode: wrong routing decision blocks evidence permanently.
- **Soft routing (RealRoute):** Parallel retrieval across all candidate sources + verification-based selection. Higher retrieval cost but avoids catastrophic routing failures.
- **Contrastive-learning routers (RAGRouter):** Small inference overhead after training; uses document embeddings + RAG capability embeddings.
- **Step-wise routers (R1-Router, DeepSieve):** Per-step routing decisions × number of reasoning steps. Highest latency; best for complex multi-source tasks.

**Benchmarks:**
- **RAGRouter (NeurIPS 2025 poster):** Outperforms best individual LLM *and* all existing routing methods (Hybrid-LLM, RouterDC, AutoMix) across diverse knowledge-intensive tasks and retrieval settings for both open- and closed-source LLMs.
- **LTRR (arXiv:2506.13743):** Routing-based RAG consistently beats the strongest single-retriever baseline, with XGBoost + pairwise ranking yielding the best results. Generalizes to OOD queries.
- **SkewRoute (2025):** 3× higher routing effectiveness than existing methods with <0.001× runtime. Training-free, plug-and-play for KG-RAG.
- **RAGRouter-Bench (2026):** First dedicated dataset and benchmark for adaptive RAG routing. Shows that joint query-corpus features are necessary for effective routing; no single paradigm dominates across all query types.
- **RAGRoute (2025):** Up to 80.65% communication volume reduction and 52.50% latency reduction in federated search, matching accuracy of querying all sources.
- **R1-Router (2025):** +7% over competitive baselines on multimodal open-domain QA, adaptively routing to appropriate modalities.
- **DeepSieve (2025):** Outperforms both RAG baselines and agentic baselines on 3 multi-hop QA benchmarks across different LLMs.

**Production readiness:** **Moderate-High.** Simple routing (retriever selection, complexity classification) is production-ready. Complex multi-step routing (R1-Router, DeepSieve) is still research-phase but promising. Production recommendations: (a) start with a simple complexity classifier → retriever router; (b) use RealRoute-style parallel+verify over hard routing when source boundaries are fuzzy; (c) train-free methods (SkewRoute) are the safest first step for cost-routing.

**Key papers:**
- *"RAGRouter: Learning to Route Queries to Multiple Retrieval-Augmented LLMs"* (NeurIPS 2025)
- *"LTRR: Learning To Rank Retrievers for LLMs"* (arXiv:2506.13743, 2025)
- *"RealRoute: Dynamic Query Routing via Retrieve-then-Verify"* (arXiv:2604.20860, 2025)
- *"SkewRoute: Training-Free LLM Routing for KG-RAG"* (2025)
- *"R1-Router: Learning to Route Queries across Knowledge Bases for Step-wise RAG"* (arXiv:2505.22095, 2025)
- *"DeepSieve: Information Sieving via LLM-as-a-Knowledge-Router"* (arXiv:2507.22050, 2025)
- *"RAGRoute: Efficient Federated Search for RAG using Lightweight Routing"* (2025)

---

### Comparison Table

| Technique | Query-time LLM calls | Retrieval calls | Latency impact | Best for | Maturity |
|---|---|---|---|---|---|
| Query Rewriting | 1 | 1 | Low–Medium | Domain mismatch, conversational | **Production** |
| Query Expansion | 0–1 | 1 | Low | Lexical retrieval, text-only indexes | **Production** |
| Query Decomposition | 2–N+1 | 2–N | High | Multi-hop/comparative QA | **Moderate-High** |
| **HyDE** | 1 | 1 | Medium | Short/vague queries, large query-doc gap | **High** |
| **HyPE** | 0 (offline: high) | 1 | Zero (query time) | Latency-critical Q&A, static corpora | **Moderate** |
| Multi-Query | 1 | 3–5 (parallel) | Medium | Vocabulary diversity, recall-critical | **Very High** |
| Step-Back | 1 | 2 | Medium | Knowledge-intensive, over-constrained queries | **Moderate** |
| Query Routing | 1+ (per step) | 1+ (per source) | Variable | Multi-source, cost-optimization | **Moderate-High** |

### Decision Heuristic

1. **Short, vague queries with large semantic gap?** → HyDE (query-time) or HyPE (if indexable offline)
2. **Multi-faceted or vocabulary-diverse queries?** → Multi-Query Retrieval
3. **Expensive per-query cost unacceptable?** → HyPE (offline preprocessing)
4. **User queries over-constrained with dates/IDs?** → Step-Back Prompting + dual retrieval
5. **Complex multi-hop queries requiring multiple facts?** → Query Decomposition + reranker
6. **Multiple knowledge sources / LLM pool?** → Query Routing (start simple, add complexity as needed)
7. **Well-formed queries on well-matched corpora?** → **Skip query enhancement entirely** — it can degrade performance
