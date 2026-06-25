## 5. Embedding Models — Comprehensive Comparison (2025–2026)

> **Sources:** MTEB Leaderboard (Hugging Face, Codesota, April 2026), MMTEB paper (arXiv:2502.13595), vendor docs & published benchmarks, BEIR/MIRACL results, community latency benchmarks (nixiesearch, Milvus, DeployBase), and vendor blog posts.

---

### 5.1 BGE (BAAI) — BGE-M3 & BGE-en-ICL

#### 5.1.1 BGE-M3

| Property | Value |
|---|---|
| **MTEB Score (English, v1, 56 tasks)** | 63.0 |
| **MMTEB (Multilingual, v2)** | ~59.56 |
| **MTEB Retrieval (BEIR subset)** | ~54.5 (nDCG@10) |
| **C-MTEB (Chinese, 35 tasks)** | ~58.1 |
| **BEIR (zero-shot)** | ~48.8 (nDCG@10 avg) |
| **MIRACL (multilingual retrieval)** | ~69.2 |
| **Multilingual** | 170+ languages (uneven training distribution) |
| **Parameters** | 568M |
| **Dimensions** | 1024 (dense), plus sparse (lexical) and multi-vector (ColBERT) |
| **Max tokens** | 8,192 |
| **Cost** | Free (MIT license, self-hosted); ~$0.016/M tokens via SiliconFlow API |
| **Latency** | ~52ms p50, ~95ms p95, ~180ms p99 (self-hosted on A100, including sparse computation) |
| **License** | MIT |

**Strengths:**
- Multi-granularity: outputs dense, sparse (lexical), and multi-vector embeddings from one model
- Strong multilingual coverage (170+ languages), best MIRACL score among open models of its class
- MIT license — fully commercial-friendly, no strings attached
- Lightweight at 568M params — runs on single consumer GPU
- Long input support (8K tokens)
- Battle-tested: the most widely deployed open embedding model in production RAG

**Weaknesses:**
- Trails newer models (Qwen3, NV-Embed-v2, APIs) on MTEB retrieval by 5–15 points
- Dense-only retrieval lags Voyage/Cohere/Gemini on English BEIR
- Offers no Matryoshka truncation — stuck at 1024 dims
- Multi-vector (ColBERT) mode adds latency and storage overhead
- Training data distribution highly skewed toward high-resource languages
- Not updated since early 2024

**Best use cases:** budget self-hosted RAG, hybrid search (dense + sparse), multilingual retrieval with MIT licensing, privacy-critical on-prem deployments, Chinese-language retrieval.

#### 5.1.2 BGE-en-ICL

| Property | Value |
|---|---|
| **MTEB Score (English v1 — zero-shot)** | 71.24 |
| **MTEB Score (English v1 — few-shot)** | 71.67 |
| **BEIR (zero-shot)** | ~64.67 |
| **BEIR (few-shot)** | ~66.08 |
| **AIR-Bench QA (few-shot)** | 54.36 (nDCG@10, 8 domains) |
| **Multilingual** | English-only |
| **Parameters** | 7.11B (LLM-based) |
| **Dimensions** | 4096 |
| **Max tokens** | 32,768 |
| **Cost** | Free (open weights, research use) |
| **License** | Research-friendly (check model card) |

**Strengths:**
- In-context learning: few-shot examples in the query dramatically improve task adaptation
- SOTA on MTEB English at release (Aug 2024), competitive even in 2026
- Long context support (32K tokens)
- Public model weights, dataset, and training code

**Weaknesses:**
- English-only — no multilingual support
- 7.11B params requires significant GPU (A100-class)
- 4096-dim vectors increase vector DB storage 4× over BGE-M3
- Few-shot prompts increase query token count and latency
- In-context examples must be curated per task
- Research license may restrict commercial use; verify

**Best use cases:** English-only high-accuracy RAG, task-adaptable embeddings via few-shot prompting, long-document retrieval, academic benchmarks.

---

### 5.2 Qwen (Alibaba) — GTE-Qwen2-7B-Instruct

| Property | Value |
|---|---|
| **MTEB Score (English, 56 tasks)** | 70.24 |
| **C-MTEB (Chinese, 35 tasks)** | 72.05 |
| **MTEB-FR (French, 26 tasks)** | 68.25 |
| **MTEB-PL (Polish, 26 tasks)** | 67.86 |
| **BEIR (retrieval)** | ~65.4 |
| **Multilingual** | 70+ languages (strong on CN, EN, FR, PL) |
| **Parameters** | 7.06B |
| **Dimensions** | 3584 |
| **Max tokens** | 32,768 |
| **Cost** | Free (Apache 2.0, self-hosted); requires ~26.5 GB GPU memory (fp32) |
| **Latency** | ~50–200ms p95 depending on batch and GPU (corpus: ~3.7K tok/s, query ~228 tok/s on L4) |
| **License** | Apache 2.0 |

**Strengths:**
- #1 on MTEB and C-MTEB at release (June 2024), still among top open models
- Apache 2.0 — fully commercial-friendly
- 32K token context for embedding full documents
- Instruction-tuned with bidirectional attention — strong query understanding
- Excellent Chinese + English performance; solid on European languages
- Backed by Qwen2 architecture (established, well-documented)

**Weaknesses:**
- 7B params = heavy; needs GPU (A100/L4 or better)
- 3584-dim vectors = ~3.5× storage vs 1024-dim models
- No Matryoshka truncation support
- Higher inference latency than smaller models (BGE-M3, Nomic)
- Training data not fully disclosed

**Best use cases:** enterprise RAG where quality matters above all, long-document (32K) multilingual search, Chinese + English bilingual retrieval, self-hosted GPU deployments with Apache 2.0 licensing.

---

### 5.3 OpenAI — text-embedding-3-large & text-embedding-3-small

#### 5.3.1 text-embedding-3-large

| Property | Value |
|---|---|
| **MTEB Score (English, v1)** | 64.6 |
| **MTEB Retrieval** | ~59.0 |
| **MTEB Classification** | ~75.4 |
| **Multilingual** | Moderate (~100 languages; lags on CJK, Arabic) |
| **Parameters** | Undisclosed |
| **Dimensions** | 3072 (default); Matryoshka down to 256 |
| **Max tokens** | 8,191 |
| **Cost** | $0.13 per 1M tokens |
| **Latency** | ~80–120ms p50; ~150ms p95 (API, includes network) |
| **API** | Proprietary (API only, no self-host) |

**Strengths:**
- Tight OpenAI ecosystem integration (GPT, Assistants API, Azure)
- Matryoshka Representation Learning: truncate to 256/512/1024/1536/3072 dims
- Stable, well-documented, global infrastructure with low error rate (~0.05%)
- Good classification and STS scores
- Battle-tested at massive scale

**Weaknesses:**
- No model update since January 2024
- Trails Qwen3-Embedding-8B by 6+ MTEB points, Voyage-3.5 by 8+%, Gemini by 4+ points
- Weak on legal retrieval: ranks 11th of 15 on CUAD benchmark
- 8K context — half or less of Voyage/Cohere/GTE-Qwen2
- No fine-tuning support
- Multilingual performance weak on Asian languages (Chinese: ~58.7, Japanese: ~57.2)
- Closed source, data leaves your infrastructure

**Best use cases:** existing OpenAI stack (zero-migration), general-purpose English RAG with ecosystem simplicity, prototyping, classification-heavy workloads.

#### 5.3.2 text-embedding-3-small

| Property | Value |
|---|---|
| **MTEB Score (English, v1)** | 62.3 |
| **MTEB Retrieval** | ~55.9 |
| **Dimensions** | 1536 (default); Matryoshka down to 256 |
| **Max tokens** | 8,191 |
| **Cost** | $0.02 per 1M tokens |
| **Latency** | ~45–60ms p50; ~85ms p95 |
| **Multilingual** | Moderate |

**Strengths:**
- Lowest API cost among commercial embedders at $0.02/M
- Matryoshka truncation saves storage
- Fastest API latency among OpenAI models
- Same ecosystem benefits as large variant

**Weaknesses:**
- Quality gap: ~2.3 MTEB points below large; substantial gap vs Voyage/Gemini
- No updates since Jan 2024
- Weaker multilingual retrieval

**Best use cases:** cost-sensitive RAG, high-volume embedding, quick prototyping on OpenAI stack, where embedding is not the retrieval bottleneck.

---

### 5.4 Gemini (Google) — text-embedding-004 & Gemini Embedding 001/2

#### 5.4.1 Gemini Embedding 001 (stable, current-gen)

| Property | Value |
|---|---|
| **MTEB Score (Multilingual)** | 68.32 |
| **MTEB Retrieval** | 67.71 |
| **MTEB Classification** | Top-tier |
| **MTEB Code** | 84.0 |
| **Multilingual** | 100+ languages, #1 on MTEB Multilingual among APIs |
| **Parameters** | Undisclosed |
| **Dimensions** | 3072 (default); MRL down to 128 (recommended: 768/1536) |
| **Max tokens** | 2,048 (API) |
| **Cost** | $0.15 per 1M tokens (paid); free tier available; batch at $0.075/M |
| **Latency** | ~15ms p50 (Google's infra); ~50–100ms p95 including network |
| **API** | Vertex AI / Gemini API |

**Strengths:**
- #1 MTEB retrieval (67.71) among all API models
- 5.81-point lead over next competing model at launch
- MRL support: 3072→768 with near-zero quality loss (68.32→67.99)
- Unified model: replaces 3 older specialized models (text-embedding-005, multilingual-002, code)
- Ultra-low latency on Google infra (~15ms)
- Multi-task type support (RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, etc.)
- Free tier + batch pricing halves cost

**Weaknesses:**
- 2048-token context limit (short vs Voyage's 32K, Cohere's 128K)
- Text-only (Gemini Embedding 2 adds multimodal)
- Single-text-per-request on Vertex AI limits throughput
- Google lock-in concerns
- Higher per-token cost at $0.15 vs Cohere's $0.12, Jina's $0.02

#### 5.4.2 text-embedding-004 (Gecko, legacy)

| Property | Value |
|---|---|
| **MTEB Score** | ~63–64 (approximate) |
| **Dimensions** | 768 |
| **Max tokens** | 2,048 |
| **Cost** | $0.025 per 1M tokens |
| **Latency** | ~15–16ms p50 |
| **Deprecation** | January 14, 2026 |

**Best use cases:** Gemini Embedding 001: best retrieval quality among API models, multilingual RAG on GCP, classification and clustering, code search (MTEB Code: 84.0); Gemini Embedding 2: multimodal (text + image + video + audio), best all-rounder per Milvus CCKM benchmark.

---

### 5.5 Voyage AI — voyage-3 & voyage-multilingual-2

#### 5.5.1 voyage-3-large

| Property | Value |
|---|---|
| **MTEB Score (v1)** | ~70.32 (avg); vendor reports 80.8 NDCG@10 on RTEB (internal, 100 datasets) |
| **MTEB Retrieval (Voyage RTEB)** | 80.8 NDCG@10 |
| **MTEB Averaged (3rd party)** | ~67.1–68.2 |
| **Multilingual** | Strong, slightly below voyage-multilingual-2 |
| **Parameters** | Undisclosed |
| **Dimensions** | 1024 (default); Matryoshka: 256, 512, 2048 |
| **Max tokens** | 32,000 |
| **Cost** | $0.18 per 1M tokens |
| **Latency** | ~90ms p50; ~272ms averaged (API, varies by region) |
| **Free tier** | 200M tokens (first use) |

**Strengths:**
- Highest raw retrieval quality among API embedders in real-world RAG benchmarks
- 9.74% better than OpenAI v3-large, 20.71% better than Cohere v3-English across 100 datasets
- Domain-specialized variants: voyage-code-3, voyage-law-2, voyage-finance-2
- Matryoshka + quantization (int8, uint8, binary): 200× storage reduction with binary
- 32K context (4× OpenAI, 16× Gemini 001)
- Outperforms OpenAI at 1/200th the storage with binary quantization

**Weaknesses:**
- Most expensive commercial API at $0.18/M (3× Jina, 9× Cohere embed-v4 budget)
- Smaller company (acquired by MongoDB); less infrastructure maturity
- No multimodal support (text only)
- Latency ~3× higher than Gemini and Cohere
- Benchmark scores partially vendor-reported on RTEB (not fully MTEB-audited)

#### 5.5.2 voyage-3 / voyage-3-lite

| Property | voyage-3 | voyage-3-lite |
|---|---|---|
| **Dimensions** | 1024 | 512 |
| **Max tokens** | 32K | 32K |
| **Cost** | $0.06/M | $0.02/M |
| **Quality vs OpenAI v3-large** | +5.6% | +2.06% |
| **Best for** | Balanced quality/cost | Budget API alternative |

#### 5.5.3 voyage-multilingual-2

| Property | Value |
|---|---|
| **Dimensions** | 1024 |
| **Max tokens** | 32,000 |
| **Cost** | $0.12 per 1M tokens |
| **Multilingual** | Optimized for 30+ languages |
| **Note** | Legacy — voyage-3-large now matches/surpasses it on multilingual |

**Best use cases:** highest-quality API retrieval (English + multilingual), domain-specific RAG (code/legal/finance via specialized models), large-scale production where storage cost matters (binary quantization), long-document retrieval (32K tokens).

---

### 5.6 Jina AI — jina-embeddings-v3

| Property | Value |
|---|---|
| **MTEB Score (English v1, 56 tasks)** | 65.18–65.52 |
| **MTEB Multilingual** | ~64.44 |
| **MTEB Retrieval** | ~55.44 |
| **MTEB Classification** | 82.58 |
| **MTEB STS (Semantic Textual Similarity)** | 85.80 |
| **Multilingual** | 89 languages total; 30 languages with best performance: Arabic, Bengali, Chinese, Danish, Dutch, English, Finnish, French, Georgian, German, Hindi, Indonesian, Italian, Japanese, Korean, etc. |
| **Parameters** | 570M |
| **Dimensions** | 1024 (default); Matryoshka down to 32 |
| **Max tokens** | 8,192 |
| **Cost** | $0.02 per 1M tokens (API); free (Apache 2.0 self-hosted) |
| **Latency** | ~55–75ms p50 (API); consistently slowest among major APIs (~300ms batching window per nixiesearch) |
| **Error rate** | 1.45% (highest among major API providers) |
| **License** | Apache 2.0 (open weights) |

**Strengths:**
- Outstanding quality-to-parameter ratio: 570M params, beats OpenAI v3-large on English MTEB
- Task-LoRA adapters: retrieval, classification, clustering, text-matching — one model, multiple task modes
- Matryoshka down to 32 dims: 92% of full retrieval performance at 64 dims
- 8192 token input — strong for long documents (late chunking support)
- Fully open-source (Apache 2.0) + cheap API ($0.02/M)
- Strong classification (82.58) and STS (85.80) scores

**Weaknesses:**
- Slowest API latency among providers (~300–500ms p90, 99th percentile spikes to 5s per nixiesearch)
- Highest error rate (1.45%) — reliability concern for production
- Retrieval MTEB (55.44) lags significantly behind Voyage/Gemini/Qwen3
- LoRA adapter architecture incompatible with `optimum`; breaks async batching libraries like `infinity`
- API throughput intentionally throttled per vendor
- Documentation and community smaller vs OpenAI/Cohere
- May underperform on low-resource languages

**Best use cases:** self-hosted classification and clustering tasks, long-document embedding (8K tokens with late chunking), cost-sensitive multilingual RAG with Matryoshka dimension reduction, on-premises/air-gapped deployments, off-the-shelf task-switching via LoRA adapters.

---

### 5.7 Cohere — embed-v4 & embed-multilingual-v3

#### 5.7.1 embed-v4

| Property | Value |
|---|---|
| **MTEB Score (English)** | ~65.2–65.8 |
| **MTEB Retrieval** | ~56.1 |
| **MTEB Multilingual** | Top-tier across 100+ languages |
| **Multilingual** | 100+ languages with minimal cross-language quality gap (~5% vs English) |
| **Parameters** | Undisclosed |
| **Dimensions** | 1536 (default); Matryoshka: 256, 512, 1024 |
| **Max tokens** | 128,000 (longest among all embedders) |
| **Cost** | $0.12 per 1M tokens (API); $0.47/M image tokens; $4–5/hr Model Vault instances |
| **Latency** | ~40–55ms p50 (fastest among commercial APIs per DeployBase) |
| **Modality** | Text + Images + interleaved (PDFs) |
| **API** | Proprietary |

**Strengths:**
- 128K context — embeds entire books/chapters without chunking (250× BGE, 16× OpenAI)
- First production multimodal embedder: text + images in unified vector space
- Best-in-class multilingual: 100+ languages with only ~5% gap to English
- Fastest commercial API latency (~40ms p50)
- Input type optimization: `search_document` vs `search_query` for asymmetric retrieval
- Matryoshka + quantization (int8, uint8, binary, ubinary)
- Available on AWS Bedrock and Oracle Cloud

**Weaknesses:**
- Retrieval MTEB (56.1) trails Voyage-3-large (~67) and Gemini (~67.7) on raw retrieval
- Image token pricing relatively high ($0.47/M)
- API-only (no self-host option)
- Requires specifying input_type for optimal results — easy to misconfigure
- 1536 dims default = 1.5× storage vs 1024-dim models

#### 5.7.2 embed-multilingual-v3 (legacy)

| Property | Value |
|---|---|
| **MTEB Score** | ~66.3 (Cohere reported) |
| **Dimensions** | 1024 |
| **Max tokens** | 512 |
| **Cost** | $0.10 per 1M tokens |
| **Multilingual** | 100+ languages |
| **Note** | Embed-v4 recommended for new projects |

**Best use cases:** multilingual RAG at scale, multimodal retrieval (text + images in PDFs/slides/charts), extreme long-context embedding (128K tokens), enterprise deployments on AWS Bedrock, fastest API latency among commercial options.

---

### 5.8 Nomic AI — nomic-embed-text-v2

| Property | Value |
|---|---|
| **MTEB Score (Multilingual)** | ~60 (approximate) |
| **BEIR (English retrieval)** | 52.86 (nDCG@10) |
| **MIRACL (Multilingual retrieval)** | 65.80 |
| **Multilingual** | 100+ languages (trained on 1.6B pairs from mC4 + CC News) |
| **Parameters** | 475M total, 305M active (MoE with 8 experts, top-2 routing) |
| **Dimensions** | 768 (default); Matryoshka down to 256 |
| **Max tokens** | 512 |
| **Cost** | Free (Apache 2.0, fully open: weights + data + training code) |
| **Latency** | ~15–25ms p50 (GPU, self-hosted) |
| **License** | Apache 2.0 |

**Strengths:**
- First Mixture-of-Experts (MoE) embedding model — 305M active / 475M total params
- Fully open: weights, training data (1.6B pairs), and training code publicly available
- Apache 2.0 license — full commercial use
- Matryoshka: 768→256 dims with minimal degradation (~97% performance retained)
- Outscores similarly-sized models (mE5, mGTE) on MIRACL by significant margins
- 30–40% lower inference cost than dense equivalent via MoE sparse activation

**Weaknesses:**
- 512-token context: shortest among all compared models
- BEIR/MTEB scores trail API leaders by 5–12 points
- MoE architecture requires `trust_remote_code=True` — integration friction
- 305M active params still heavier than Nomic v1.5 (137M)
- Smaller ecosystem/framework support than OpenAI, Cohere
- Performance gap widens at batch sizes; MoE efficiency gains diminish at scale

**Best use cases:** fully reproducible/open research, regulated industries with audit requirements, on-prem multilingual enterprise search, low-cost vector stores with Matryoshka dimension compression, academic use, teams that value transparency (open data + code) above absolute MTEB scores.

---

### 5.9 Comparison Table

| # | Model | MTEB Avg (v1) | MTEB Retrieval | MMTEB/ Multilingual | Dims | Max Tokens | Cost/1M tokens | Params | License | Modality |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **GTE-Qwen2-7B-Instruct** | 70.24 | ~65.4 | 72.05 (CN) | 3584 | 32K | Free (self-host) | 7B | Apache 2.0 | Text |
| 2 | **BGE-en-ICL** (few-shot) | 71.67 | ~64.7 | EN only | 4096 | 32K | Free (self-host) | 7B | Research | Text |
| 3 | **Gemini Embedding 001** | 68.32 | 67.71 | 68.32 | 3072 | 2K | $0.15 | — | API | Text |
| 4 | **voyage-3-large** | ~68.2 | 80.8 RTEB | Strong | 1024 | 32K | $0.18 | — | API | Text |
| 5 | **Cohere embed-v4** | ~65.8 | ~56.1 | Top (100+ lg) | 1536 | 128K | $0.12 | — | API | Text+Img |
| 6 | **jina-embeddings-v3** | 65.5 | 55.4 | 64.4 | 1024 | 8K | $0.02 | 570M | Apache 2.0 | Text |
| 7 | **OpenAI text-3-large** | 64.6 | ~59.0 | Moderate | 3072 | 8K | $0.13 | — | API | Text |
| 8 | **BGE-M3** | 63.0 | ~54.5 | 59.56 (v2) | 1024 | 8K | Free (MIT) | 568M | MIT | Text |
| 9 | **Cohere embed-multi-v3** | ~66.3* | ~55 | ~60 (v2) | 1024 | 512 | $0.10 | — | API | Text |
| 10 | **OpenAI text-3-small** | 62.3 | ~55.9 | Moderate | 1536 | 8K | $0.02 | — | API | Text |
| 11 | **text-embedding-004** | ~63 | — | ~59.1 | 768 | 2K | $0.025 | — | API | Text |
| 12 | **nomic-embed-text-v2** | ~60 | ~52.9 | ~65.8 (MIRACL) | 768 | 512 | Free (Apache) | 305M active | Apache 2.0 | Text |
| 13 | **voyage-3** | ~65.1 | 76.72 RTEB | Strong | 1024 | 32K | $0.06 | — | API | Text |
| 14 | **voyage-multilingual-2** | ~64.8* | — | 30+ lg optimized | 1024 | 32K | $0.12 | — | API | Text |

> *Vendor-reported scores. MTEB v1 and MMTEB v2 scores are not directly comparable. RTEB scores are Voyage's internal benchmark.

---

### 5.10 Latency Comparison (API)

| Provider | Model | p50 (ms) | p95 (ms) | p99 (ms) | Batch Window | Error Rate |
|---|---|---|---|---|---|---|
| Cohere | embed-v4 | 40–55 | 60–80 | ~110 | ~100ms | 0.06% |
| Google | Gemini Embedding 001 | 15–50 | 100–130 | ~200 | ~50ms | 0.002% |
| OpenAI | text-embedding-3-large | 80–120 | 150 | ~300 | ~300ms | 0.05% |
| OpenAI | text-embedding-3-small | 45–60 | 85 | ~200 | ~300ms | 0.05% |
| Voyage | voyage-3-large | 90–270 | 310 | ~500 | — | — |
| Jina | jina-embeddings-v3 | 55–300 | 500 | 5000 | ~300ms | 1.45% |
| Self-hosted (GPU) | BGE-M3 / Nomic v2 | 15–52 | 95 | 180 | — | 0% (local) |

**Key finding from nixiesearch (April 2025):** API latency spikes to 500ms at p90 and up to 5 seconds at p99 during provider volatility. Self-hosted models achieve 3–10× lower and more predictable latency (5–20ms on CPU with ONNX quantization). Cross-region access adds 3–4× latency universally.

---

### 5.11 Multilingual Quality (Per-Language MTEB Scores)

| Language | Qwen3-8B | Gemini 001 | Cohere v4 | OpenAI v3-large |
|---|---|---|---|---|
| English | 72.1 | 70.5 | 67.2 | 68.9 |
| French | 69.8 | 66.2 | 65.8 | 62.4 |
| German | 68.5 | 65.8 | 64.9 | 61.8 |
| Spanish | 69.2 | 66.4 | 65.5 | 62.1 |
| Chinese | 71.5 | 68.1 | 62.3 | 58.7 |
| Japanese | 68.9 | 65.2 | 61.8 | 57.2 |
| Arabic | 64.2 | 61.5 | 59.7 | 54.3 |

OpenAI shows a 10–15 point drop on CJK/Arabic vs English. Cohere maintains <5% gap across all languages. Qwen3 leads across the board, especially on Asian languages.

---

### 5.12 Recommendation Matrix

| Use Case | Best Pick | Runner-Up | Budget Alternative |
|---|---|---|---|
| **General RAG (max quality, API)** | Gemini Embedding 001 | voyage-3-large | voyage-3 ($0.06/M) |
| **General RAG (max quality, self-hosted)** | Qwen3-Embedding-8B | GTE-Qwen2-7B-Instruct | BGE-M3 |
| **Best value (API)** | Cohere embed-v4 | text-embedding-3-small | voyage-3-lite ($0.02/M) |
| **Best value (self-hosted)** | BGE-M3 | Nomic Embed Text v2 | all-MiniLM-L6-v2 |
| **Multilingual RAG (API)** | Cohere embed-v4 | Gemini Embedding 001 | voyage-3 |
| **Multilingual RAG (self-hosted)** | Qwen3-Embedding-8B | BGE-M3 | Nomic Embed Text v2 |
| **Chinese + English** | Qwen3-Embedding-8B (self-host) | GTE-Qwen2-7B (self-host) | BGE-M3 |
| **Multimodal (text + images)** | Cohere embed-v4 | Gemini Embedding 2 | — |
| **Long documents (32K+ tokens)** | Cohere embed-v4 (128K) | GTE-Qwen2-7B (32K) | voyage-3-large (32K) |
| **Code search** | voyage-code-3 | Gemini Embedding 001 | Qwen3-Embedding-8B |
| **Legal retrieval** | voyage-law-2 | voyage-3-large | Cohere embed-v4 |
| **Privacy-critical / air-gapped** | BGE-M3 (MIT) | Jina v3 (Apache 2.0) | Nomic v2 (Apache 2.0) |
| **Classification / clustering** | Jina v3 (LoRA adapters) | Gemini Embedding 001 | OpenAI text-3-large |
| **Lowest latency (API)** | Cohere embed-v4 (~40ms) | Gemini Embedding 001 (~15-50ms) | OpenAI text-3-small (~45ms) |
| **Open-source transparency** | Nomic Embed Text v2 | BGE-M3 | BGE-en-ICL |
| **Existing OpenAI ecosystem** | text-embedding-3-large | text-embedding-3-small | — |
| **Existing GCP ecosystem** | Gemini Embedding 001 | Gemini Embedding 2 (multimodal) | — |

---

### 5.13 Key Takeaways (2025–2026)

1. **Open-source has overtaken closed APIs on quality.** Qwen3-Embedding-8B (70.6 MMTEB) and GTE-Qwen2-7B (70.24 MTEB) both outscore every closed API model. If you have GPU infrastructure, self-hosting is now the quality leader.

2. **MTEB scores don't tell the whole story.** The MTEB average rewards generalists. For RAG, retrieval NDCG matters more — and Gemini Embedding 001 leads at 67.71. Voyage-3-large leads on domain-specific retrieval (RTEB: 80.8 NDCG). Always benchmark on your own data.

3. **The cost landscape has inverted.** Google ($0.15/M) and Cohere ($0.12/M) are now competitive with OpenAI ($0.13/M) while offering better quality. OpenAI's primary advantage is ecosystem integration, not quality or price.

4. **Multimodal is the new frontier.** Cohere embed-v4 (text+images, 128K context) and Gemini Embedding 2 (text+image+video+audio+PDF) are the first production-grade multimodal embedders. For RAG over visual documents, these are essential.

5. **Context length matters for RAG.** Cohere (128K), Voyage/GTE-Qwen2 (32K) vastly outstrip OpenAI/Gemini 001 (8K/2K). Longer context means less chunking and better context preservation.

6. **Matryoshka + quantization are production must-haves.** Voyage's binary 512-dim embeddings outperform OpenAI 3072-dim float while using 1/200 the storage. This is a warehouse-cost-level difference at scale.

7. **BGE-M3 remains the pragmatic self-host default.** Despite trailing newer models on MTEB, its MIT license, multi-granularity (dense+sparse+ColBERT), 568M size, and 8K context make it the most battle-tested open embedder for production.
