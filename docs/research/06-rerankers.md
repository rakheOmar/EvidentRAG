## 6. Rerankers

### 6.1 Cross-Encoders (BERT-Based Reranking)

**How it works:**
A cross-encoder concatenates query and document into a single sequence `[CLS] query [SEP] document [SEP]` and runs full bidirectional self-attention across all tokens through a transformer (typically BERT/RoBERTa-based). The model outputs a single relevance logit from the `[CLS]` token head. Every query–document pair requires a full forward pass — documents **cannot** be pre-computed.

**Representative models:** `BGE-reranker-v2-m3`, `mxbai-rerank-large-v2`, `ms-marco-MiniLM-L6-v2`, `gte-reranker-modernbert-base`.

| Metric | Value |
|---|---|
| **BEIR NDCG@10** | 51.8–56.5 (bge-v2-m3), 61.44 (mxbai-large-v2), 63.10 (bge-v2.5-gemma2) |
| **Hit@1 (AIMultiple)** | 83.00% (gte-modernbert, 149M params — matches nemotron 1.2B) |
| **Latency (100 docs, GPU)** | 38–500 ms (self-hosted); 100–500 ms for large models |
| **Cost (self-hosted)** | $0 + GPU compute (~$0.04/1K queries on a single A100) |
| **Max context** | 512 tokens (classic BERT), 8,192 tokens (bge-v2-m3) |
| **Max docs per call** | 1 pair per forward pass; typically batch up to 100 |

**Strengths:**
- Highest accuracy among non-LLM architectures for small candidate sets.
- Trained specifically for relevance classification; strong domain adaptation via fine-tuning.
- Mature ecosystem (`sentence-transformers`, `FlagEmbedding`, HuggingFace).

**Weaknesses:**
- Cannot pre-compute document representations — every query requires N forward passes.
- Quadratic attention cost limits scalability to >100–200 candidates at query time.
- Many older models capped at 512 tokens.

**Production recommendation:**
Use as the **default second-stage reranker** for RAG pipelines. Self-host BGE-v2-m3 or gte-modernbert for cost-sensitive deployments. Pair a fast bi-encoder (top-100) → cross-encoder (top-10) → LLM.

---

### 6.2 ColBERT (Late-Interaction Retrieval + Reranking)

**How it works:**
ColBERT encodes query and document **independently** into per-token contextual embeddings. At scoring time, it computes **MaxSim**: for each query token vector, find the maximum cosine similarity with any document token vector, then sum across all query tokens. Document token embeddings are pre-computed and stored in a PLAID (or similar) index. This is "late interaction" — query-document interaction happens after encoding, via cheap dot products instead of expensive cross-attention.

| Metric | Value |
|---|---|
| **BEIR NDCG@10** | ~50 (ColBERTv2); ~73% (ColBERTv2 on some MS MARCO subsets) |
| **Hit Rate / Recall** | Recovers more relevant passages in 50 results than BM25 does in 1000 (original paper claim) |
| **Latency (100 docs)** | 50–200 ms (pre-computed docs); 27–35 ms with MUVERA+Rerank |
| **FLOPs vs cross-encoder** | ~180× fewer at k=10; ~13,900× fewer at k=1,000 |
| **Cost (self-hosted)** | $0 + storage (~$0.05/1K queries at scale) |
| **Storage** | ~25× more than bi-encoder (~90 KB/doc vs ~4 KB); compressed to ~16 GB for MS MARCO (8.8M passages) |
| **Max context** | 512 tokens (ColBERTv2) |

**Architecture variants:**
- **ColBERTv2** — residual compression + denoised supervision. MS MARCO index: 16 GB (1-bit) / 25 GB (2-bit).
- **PLAID** — centroid pruning + exact MaxSim scoring for production-scale retrieval.
- **MUVERA** — fixed-dimensional encodings + approximate NN search + rerank. 3.3× faster than PLAID.
- **ColPali** — ColBERT extended to vision (PDF/documents), binary quantization cuts storage by 32×.
- **ModernColBERT** — Rotary positional embeddings, updated activations.
- **Jina ColBERT v2** — 89 languages, user-controlled embedding sizes.

**Strengths:**
- Pre-computed document embeddings → fast at query time.
- Captures token-level interactions that single-vector models miss.
- Approaches cross-encoder quality (within 2–5% NDCG gap) at much lower latency.
- Works as both retriever and reranker.

**Weaknesses:**
- Indexing step required (non-trivial infrastructure: PLAID, Vespa, Qdrant multi-vector).
- Storage explosion (25×+ vs bi-encoder).
- Slightly lower accuracy than top cross-encoders.
- Requires stable corpus (re-indexing is expensive).

**Production recommendation:**
Use ColBERT as a reranker over bi-encoder retrieval for **latency-sensitive, high-volume systems**. Best for domains where token-level matching matters (technical docs, code, legal). The two-stage pattern (bi-encoder top-100 → ColBERT rerank → top-10) combines scalability with accuracy. Not recommended as a drop-in component swap — it is a retrieval architecture decision.

---

### 6.3 BGE Reranker v2 (BAAI)

**How it works:**
Cross-encoder architecture. The v2-m3 variant uses the BGE-M3 backbone (XLM-RoBERTa-based, 568M params). The v2-gemma variant uses Google Gemma-2B as the backbone and is invoked as an LLM-based reranker (FlagLLMReranker). The v2.5-gemma2-lightweight variant (Gemma-2-9B base) supports layer-wise inference and token compression for 60% FLOPs savings with slight accuracy gains.

| Model | BEIR NDCG@10 | MIRACL NDCG@10 | Params | Context | Cost |
|---|---|---|---|---|---|
| **bge-reranker-v2-m3** | 56.51 | 69.32 | 568M | 8,192 | Free (Apache 2.0) |
| **bge-reranker-v2-gemma** | 60.71 | — | 2B | 8,192 | Free (Gemma license) |
| **bge-reranker-v2.5-gemma2-lightweight** | 63.10 | — | 9B (compressed) | 8,192 | Free (Gemma license) |

| Metric | Value |
|---|---|
| **Latency** | 38–72 ms p50, 72 ms p95 on GPU (100 docs); 80–150 ms on T4 GPU for 20 documents |
| **Throughput** | ~50–100 query-passage pairs/sec on single A100 |
| **Languages** | 100+ languages (multilingual M3 backbone) |
| **License** | Apache 2.0 (v2-m3), Gemma license (v2-gemma/v2.5) |
| **HuggingFace downloads** | 6.6M+ (v2-m3) |

**Strengths:**
- Fully open-source, MIT/Apache 2.0 — no API costs, no vendor lock-in.
- Strong multilingual performance (MIRACL NDCG@10: 69.32 — highest among open-source).
- Seamless pairing with BGE-M3 embeddings for an all-BAAI stack.
- Layer-wise lightweight variant offers configurable speed/accuracy trade-off.
- Runs on consumer GPUs (12–16 GB VRAM for v2-m3).

**Weaknesses:**
- v2-m3 trails newer closed-source models (Jina v3 BEIR: 61.94 vs BGE v2-m3: 56.51).
- Gemma-based variants require HuggingFace license acceptance.
- No managed API — self-hosting ops required.
- Documentation primarily in Chinese/English.

**Production recommendation:**
**Best open-source self-hosted reranker** for teams that already operate ML infrastructure. Pair with BGE-M3 embeddings for a fully open-source retrieval stack. Use v2-m3 as the practical sweet spot for cost/quality; upgrade to v2.5-gemma2-lightweight for higher accuracy with 60% FLOPs savings. Ideal for regulated environments and multilingual enterprise search.

---

### 6.4 Cohere Rerank (rerank-v3.5 / rerank-v4.0)

**How it works:**
Proprietary cross-encoder API. Cohere has not disclosed exact architecture details, but it is a transformer-based cross-encoder trained on large-scale multilingual data with native support for structured data (JSON, tables, code). The v3.5 model improved reasoning and multilingual capabilities over v3. The v4.0 generation (Pro/Fast) is the current flagship (2026).

| Model | ELO (Agentset) | Latency (avg) | Max Context | Pricing |
|---|---|---|---|---|
| **rerank-v3.5** | ~1692 (finance) | ~600 ms | 4,096 tokens | $2.00/1K searches |
| **rerank-v4.0-pro** | 1629 | 614 ms | 4,096 tokens | $2.00/1K searches |
| **rerank-v4.0-fast** | — | ~200 ms | 4,096 tokens | $2.00/1K searches |

| Metric | Value |
|---|---|
| **Latency (OCI benchmark, 96 docs × 128 tokens)** | 0.20s request-level latency, 4.81 RPS |
| **Latency (OCI benchmark, 48 docs × 256 tokens)** | 0.16s request-level latency, 6.34 RPS |
| **Languages** | 100+ languages |
| **Structured data** | Native JSON, table, code handling (v3.5+) |
| **nDCG improvement** | +10–20 NDCG@10 points over BM25/dense retrieval alone; ~0.65–0.70 on BEIR |
| **Head-to-head** | Outperformed by ZeRank-1 and Voyage 2.5 in GPT-5 ELO evaluations (Agentset Nov 2025) |

**Strengths:**
- Zero infrastructure — API call only.
- Broadest language support among managed APIs (100+ languages).
- Native structured data handling (JSON, tables, code).
- Consistent latency under load (better p90 stability than ZeRank).
- Deep framework integration (LangChain, LlamaIndex, Elasticsearch).

**Weaknesses:**
- **Expensive at scale**: $2/1K searches = ~$600/month for 10K daily queries.
- Vendor lock-in (no self-hosting). Dedicated deployments cost $3,250/month.
- 4,096 token context limit (8× less than Voyage 2.5's 32K).
- ELO and accuracy trails Voyage 2.5 and ZeRank in recent benchmarks.
- Lower ELO on specialized domains (spiky radar chart — inconsistent across datasets).

**Production recommendation:**
Best **managed API for teams that want zero infrastructure** and broad multilingual coverage. Use v4.0-fast for latency-sensitive apps; use v4.0-pro for maximum quality. Good for enterprise RAG with structured/semi-structured data. Budget-conscious teams should compare against Voyage 2.5 (better price/performance).

---

### 6.5 Voyage Rerank (rerank-2.5 / rerank-2.5-lite)

**How it works:**
Proprietary cross-encoder with instruction-following capabilities. Users can append natural language instructions to queries to steer relevance scoring. Supports a 32K token context window — 8× Cohere v3.5's limit. Released August 2025.

| Model | NDCG@10 (Voyage internal, 93 datasets) | Latency (avg) | Max Context | Pricing |
|---|---|---|---|---|
| **rerank-2.5** | 84.32% | ~613 ms | 32,000 tokens | $0.05/M tokens |
| **rerank-2.5-lite** | 83.12% | ~400 ms | 32,000 tokens | $0.02/M tokens |

| Metric | Value |
|---|---|
| **ELO (Agentset)** | 1544 |
| **Max documents** | 1,000 per request |
| **Max query tokens** | 8,000 |
| **Max total tokens** | 600K per request |
| **First 200M tokens** | Free |
| **vs Cohere v3.5** | +7.94% accuracy improvement (avg across 4 first-stage methods) |
| **vs GPT-5** | 12.61% better NDCG@10, 48× faster, 25–60× cheaper |
| **Batch API** | 33% discount, 12-hour completion window |

**Strengths:**
- Best cost-to-performance ratio among managed APIs.
- Largest context window (32K tokens) — rerank entire long documents without truncation.
- Instruction-following enables domain-specific steering without model changes.
- Token-based pricing is predictable and cheap at high volume.
- Outperforms all LLM-based rerankers (GPT-5, Claude, Gemini) at a fraction of the cost.
- Consistent across domains (smooth radar chart in Agentset benchmarks).

**Weaknesses:**
- API-only (no self-host option).
- English-focused (multilingual support less documented than Cohere).
- Slightly lower ELO than Cohere v4 Pro (1544 vs 1629) on Agentset rankings.
- Newer provider — smaller ecosystem integrations than Cohere.

**Production recommendation:**
**Best balanced managed reranker** for production RAG. Use rerank-2.5 for quality-critical workloads; use rerank-2.5-lite for cost/latency-sensitive workloads. The 32K context window makes it the top choice for long-document retrieval. Token-based pricing is ideal for high-volume, predictable-cost deployments.

---

### 6.6 Jina Reranker (jina-reranker-v2 / v3 / m0 / colbert-v2)

**How it works:**
The Jina family spans multiple architectures:
- **v2** (0.3B): Traditional cross-encoder, pointwise scoring, 100+ languages, 8,192-token window.
- **v3** (0.6B): Novel **"Last but Not Late Interaction"** — causal self-attention between query and all documents in a single context window (listwise). Extracts contextual embeddings from the last token of each document. Up to 64 documents processed together in one forward pass with 131K token context.
- **m0** (2.4B): Multimodal reranker that scores PDF documents from visual representations.
- **colbert-v2**: ColBERT architecture (late interaction), 89 languages, user-controlled embedding sizes.

| Model | BEIR NDCG@10 | MIRACL NDCG@10 | MKQA Recall@10 | CoIR NDCG@10 | Params |
|---|---|---|---|---|---|
| **jina-reranker-v3** | **61.94** | 66.50 | 67.84 | 63.28 | 0.6B |
| **jina-reranker-v2** | 57.06 | 63.65 | 67.90 | 56.14 | 0.3B |
| **jina-reranker-m0** | 58.95 | 66.75 | 68.19 | 63.55 | 2.4B |
| **bge-reranker-v2-m3** (ref) | 56.51 | 69.32 | 67.88 | 35.97 | 0.6B |
| **mxbai-rerank-large-v2** (ref) | 61.44 | 57.94 | 67.06 | 70.87 | 1.5B |

| Metric | Value |
|---|---|
| **Hit@1 (AIMultiple)** | 81.33% (v3), at **188 ms** latency (best speed-accuracy in benchmark) |
| **Latency (100 docs)** | v3: ~188–300 ms; v2: ~280 ms p50 |
| **Latency breakdown (v3)** | 64-token query, 256-token docs × 100: ~156 ms; 512-token query, 4096-token docs: ~7 sec |
| **Pricing** | $0.05/M input tokens (API); free self-host (CC-BY-NC 4.0); 10M free tokens per key |
| **Max context** | 131,072 tokens (v3); 8,192 tokens (v2) |
| **Max docs per call** | 64 (v3, listwise); 100+ (v2, pointwise) |

**Strengths:**
- **v3 achieves SOTA BEIR NDCG@10 (61.94)** — highest among all rerankers, 10× smaller than generative alternatives.
- Listwise architecture (v3) enables cross-document reasoning without separate forward passes.
- Best speed-accuracy tradeoff for latency-sensitive production (188 ms, 81.33% Hit@1).
- Multilingual: 100+ languages; specialized code retrieval (CoIR: 70.64).
- Freemium model with self-hosting option.

**Weaknesses:**
- CC-BY-NC 4.0 license limits commercial self-hosting without a Jina AI agreement.
- v3 latency scales with context length (3.5–7 sec for 4096-token docs).
- v3 limited to 64 documents per call (listwise window).
- m0 (multimodal) is 2.4B parameters — requires substantial GPU.

**Production recommendation:**
**Best for latency-sensitive, high-volume production** where sub-200 ms latency is required and self-hosting is acceptable. v3's listwise architecture is ideal for RAG pipelines where cross-document deduplication matters. For long documents, prefer Voyage 2.5. For commercial self-hosting without CC-BY-NC constraints, use BGE or mxbai.

---

### 6.7 NVIDIA NeMo Retriever Reranker

**How it works:**
Fine-tuned cross-encoder rerankers based on Llama/Mistral architectures, deployed via NVIDIA NIM (NVIDIA Inference Microservice) Docker containers with Triton Inference Server and TensorRT optimization. The primary models are based on decoder-only LLMs (Llama 3.2, Mistral) adapted for relevance scoring via a prompt-template format.

| Model | Avg Recall@5 (NQ, HotpotQA, FiQA, TechQA) | MLQA Recall@5 (Cross-lingual) | Params | GPU |
|---|---|---|---|---|
| **nv-rerankqa-mistral-4b-v3** | 75.45% | — | 3.5B | H100 |
| **llama-nemotron-rerank-1b-v2** | 73.64% | 86.83% | 1B | H100/A100 |
| **llama-3.2-nemoretriever-rerankqa-500m** | 72.03% | 82.27% | 500M | L40S/A10G |

| Metric | Value |
|---|---|
| **Hit@1 (AIMultiple)** | 83.00% (nemotron-1b, tied with gte-modernbert at 149M) |
| **MRR@10** | 0.8514 (nemotron-1b) |
| **Latency (100 docs)** | ~243 ms (nemotron-1b); ~1,750 ms for 500 passages on H100 |
| **Cost** | Self-hosted on NVIDIA GPU infrastructure; enterprise support included |
| **Recall improvement** | +5.9% NDCG@5, +5.6% MRR@5 over retrieval alone (HotpotQA) |
| **Languages** | Multilingual (26+ languages), cross-lingual support |
| **Throughput** | FP8 precision, batch processing optimized via TensorRT |

**Strengths:**
- Enterprise-grade: security, support, SLAs, production-ready containers.
- Top-tier accuracy (83% Hit@1, matching or exceeding all open-source cross-encoders).
- Multilingual and cross-lingual retrieval (MLQA: 86.83% Recall@5 for 1B model).
- NVIDIA ecosystem integration (NeMo, Triton, TensorRT).
- Scales from single GPU to multi-node deployments.

**Weaknesses:**
- NVIDIA GPU dependency (H100/A100 recommended).
- Container-based deployment complexity (NIM microservice setup).
- The 500M model can run on smaller GPUs (A10G/L40S), but 1B+ models need data-center hardware.
- Cost tied to NVIDIA infrastructure (GPU compute, NIM licensing for production).
- Larger model (1.2B) only matches a 149M model (gte-modernbert) on top-line Hit@1.

**Production recommendation:**
Best for **NVIDIA-ecosystem enterprises** already running NIM microservices. The 1B model provides strong accuracy with multilingual support. Consider gte-reranker-modernbert-base (149M, open-source, identical Hit@1 at 8× smaller size) for non-NVIDIA infrastructure. The 500M model is a good entry point for smaller GPU budgets.

---

### 6.8 LLM-as-a-Reranker (RankGPT / RankVicuna / GPT-4 / Claude)

**How it works:**
General-purpose LLMs are prompted to rank documents using one of three paradigms:
- **Pointwise** (RelGen): LLM outputs a relevance score or yes/no for each query-document pair.
- **Pairwise** (PRP-Heap): LLM compares document pairs; results aggregated via sorting.
- **Listwise** (RankGPT, TourRank): LLM is prompted with all candidate documents and outputs a permutation (ordered list of indices). Uses sliding window strategy (window=20, step=10) to handle >context-length candidate sets.

Key variants: **RankGPT** (GPT-4/GPT-3.5), **RankVicuna** (fine-tuned Vicuna-7B), **RankZephyr** (fine-tuned Zephyr-7B, 105K synthetic examples), **RankQwen**, **Rearank** (RL-trained), **RankFlow** (multi-role: rewrite → answer → summarize → rank), **DEAR** (distillation + CoT reasoning).

| Method | NDCG@10 DL19 | NDCG@10 DL20 | BEIR Avg NDCG@10 | FutureQueryEval NDCG@10 | Runtime |
|---|---|---|---|---|---|
| **RankGPT-4** | 0.7559 | 0.7056 | ~53.68 | — | ~3,420s (TourRank) |
| **RankGPT-3.5** | 0.6580 | 0.6291 | ~50.62 | — | — |
| **RankZephyr-7B** | 0.7420 | 0.7086 | — | **62.65** (best listwise) | 1,240s |
| **RankVicuna-7B** | — | 0.6981–0.7061 | — | 58.63 | — |
| **DEAR-L (LLaMA-8B)** | — | — | 53.72 | 90.97 (NovelEval avg) | — |
| **GPT-4o** | 0.7506 | 0.7106 | — | — | — |
| **Claude 3.7 Sonnet** | 0.7319 | 0.7009 | — | — | — |
| **DeepSeek-V3** | 0.7590 | 0.7064 | — | — | — |
| **MonoT5-3B** (pointwise) | 0.7183 | 0.6889 | ~51.36 | 60.75 | 486s |

| Metric | Value |
|---|---|
| **Cost vs specialized rerankers** | 25–60× more expensive ($1.25–$3/M tokens for LLMs vs $0.05/M for Voyage 2.5) |
| **Latency vs specialized rerankers** | GPT-5: 48× slower than Voyage rerank-2.5; Claude: 9× slower |
| **Accuracy vs Voyage 2.5** | Voyage 2.5 outperforms GPT-5 by 12.61%, Gemini 2.5 Pro by 13.43%, Qwen 3 32B by 14.78% in NDCG@10 |
| **Context window** | 4K–1M tokens (model-dependent); sliding window needed for >context docs |
| **Sensitivity** | Highly sensitive to prompt design, document ordering, and LLM temperature |

**Strengths:**
- Zero-shot — no training needed. Works with any domain.
- Captures complex reasoning (multi-hop, nuanced criteria).
- Can incorporate freshness, authority, and custom logic via prompts.
- Top-tier accuracy on novel/unseen queries (listwise methods generalize best to FutureQueryEval).

**Weaknesses:**
- **Prohibitively expensive and slow for production** — 25–60× cost, 9–48× latency vs specialized rerankers.
- Underperform purpose-built rerankers when paired with strong first-stage retrievers.
- Prompt sensitivity — small prompt changes can cause large accuracy swings.
- Sliding window approach breaks inter-document relationships across windows.
- Temporal degradation: 5–15% performance drop on queries about events after LLM training cutoff.

**Production recommendation:**
**Not recommended for production RAG at scale.** Only use LLMs as rerankers for:
- High-stakes queries where maximum accuracy justifies 10–50× higher cost (e.g., legal, medical).
- Domains requiring dynamic, non-standard relevance criteria.
- Evaluation/benchmarking of dedicated rerankers.
- Offline, batch reranking pipelines where latency is not a constraint.

For most production systems, specialized cross-encoders (Voyage 2.5, Cohere v4, Jina v3) outperform LLM rerankers in accuracy, latency, and cost simultaneously.

---

### 6.9 Comparison Table

| Reranker | Type | BEIR NDCG@10 | ELO (Agentset) | Latency (100 docs) | Cost / 1K queries | Max Context | Self-host | Multilingual |
|---|---|---|---|---|---|---|---|---|
| **Jina Reranker v3** | Listwise CE (0.6B) | **61.94** | — | ~188 ms | ~$0.18 (API) / Free (CC-BY-NC) | 131K tokens | Yes* | 100+ langs |
| **Voyage Rerank 2.5** | Cross-encoder (API) | 84.32% (internal) | 1544 | ~613 ms | ~$0.50 | 32K tokens | No | Yes |
| **Voyage Rerank 2.5-lite** | Cross-encoder (API) | 83.12% (internal) | — | ~400 ms | ~$0.20 | 32K tokens | No | Yes |
| **Cohere Rerank v4 Pro** | Cross-encoder (API) | — | **1629** | ~614 ms | ~$2.00 | 4,096 tokens | No | 100+ langs |
| **Cohere Rerank v3.5** | Cross-encoder (API) | ~65–70 (BEIR uplift) | ~1692 (finance) | ~600 ms | ~$2.00 | 4,096 tokens | No | 100+ langs |
| **BGE Reranker v2-m3** | Cross-encoder (0.6B) | 56.51 | — | 38–72 ms (GPU) | ~$0.04 | 8,192 tokens | Yes (Apache 2.0) | 100+ langs |
| **BGE Reranker v2.5-gemma2** | Cross-encoder (9B→compressed) | 63.10 | — | Variable | ~$0.08 (GPU) | 8,192 tokens | Yes (Gemma) | Yes |
| **gte-modernbert-base** | Cross-encoder (149M) | — | — | ~60–100 ms | ~$0.01 | 512 tokens | Yes (OS) | English |
| **nemotron-rerank-1b** | Cross-encoder (1.2B) | — | — | ~243 ms | Enterprise GPU | — | Yes (NVIDIA NIM) | 26+ langs |
| **mxbai-rerank-large-v2** | Cross-encoder (1.5B) | 61.44 | — | ~140 ms | ~$0.06 | 8,192 tokens | Yes (Apache 2.0) | Yes |
| **ColBERT v2** | Late interaction | ~50 | — | 55–95 ms | ~$0.05 | 512 tokens | Yes (OS) | Limited |
| **RankGPT-4** | LLM listwise | ~53.68 | — | 2,000–3,420 ms | ~$10–20 | 128K tokens | No (API) | Via LLM |
| **FlashRank** | Distilled CE | ~44 | — | ~40 ms | ~$0.01 | 512 tokens | Yes (OS) | Limited |

*Jina v3 self-host: CC-BY-NC 4.0 license — commercial use requires agreement.

---

### 6.10 Production Recommendations by Budget & Use Case

| Profile | Recommendation | Rationale |
|---|---|---|
| **Maximum accuracy, managed** | Voyage Rerank 2.5 or Cohere Rerank v4 Pro | Voyage: better cost; Cohere: better ELO + structured data |
| **Balanced cost/quality, managed** | Voyage Rerank 2.5-lite | $0.02/M tokens, 83% NDCG@10, 32K context |
| **Latency-critical (<200 ms)** | Jina Reranker v3 (188 ms) or FlashRank (40 ms) | Jina v3: best speed-accuracy (81.33% Hit@1 at 188 ms) |
| **Lowest cost, self-hosted** | BGE Reranker v2-m3 or gte-modernbert-base | Apache 2.0, free, 83% Hit@1 from 149M params |
| **Multilingual, self-hosted** | BGE Reranker v2-m3 or mxbai-rerank-large-v2 | Apache 2.0, 100+ languages, strong MIRACL scores |
| **Enterprise, NVIDIA ecosystem** | NeMo Retriever nemotron-rerank-1b-v2 | Enterprise support, TensorRT optimized, multilingual |
| **Large corpus, token-level matching** | ColBERT v2 (as reranker over bi-encoder) | Pre-computed per-token embeddings, 2.2× faster than cross-encoder |
| **Long documents (>4K tokens)** | Voyage Rerank 2.5 (32K) or Jina v3 (131K) | Avoid truncation; Jina v3 has largest context at 131K |
| **Non-standard relevance criteria** | Voyage Rerank 2.5 (instruction-following) or RankGPT-4 (ad-hoc, offline) | Use LLM rerankers only for complex, low-volume, or offline tasks |

**Three-tier pipeline architecture (recommended for most RAG systems):**

```
BM25 + Dense Bi-encoder (top‑100)
  → ColBERT or FlashRank rerank (top‑50)
    → Cross-encoder (Voyage 2.5 / BGE v2‑m3 / Jina v3) final rerank (top‑10)
      → LLM generation (top‑5 chunks)
```

**Key takeaways:**
1. **Specialized rerankers beat LLMs** on accuracy, cost, and latency (12–15% better NDCG@10, 25–60× cheaper, 9–48× faster).
2. **Model size does not determine quality** — a 149M cross-encoder matches a 1.2B model on Hit@1; a 4B model ranks 4th.
3. **The reranker cannot fix bad retrieval** — all top rerankers converge at the retriever's recall ceiling (~87–88% Hit@10).
4. **Test on your data** — academic benchmarks (BEIR, MIRACL) do not always transfer to production corpora. Always benchmark with your own queries and documents.
5. **A reranker is not automatically beneficial** — the smallest models (70M params) can underperform the baseline. Validate before deploying.
