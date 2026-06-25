## 10. System Design &amp; Production Stacks

> **Research date:** June 2026. Source data from arXiv (250+ papers), production case studies (Boundev, Nic Chin, Appycodes, Harvey, Chanakya, Google Research, DoorDash, LinkedIn, Ramp, Datup/Binbash), open-source reference implementations, and vendor-published pricing as of June 2026.

---

### 10.1 Startup RAG — Cost-Sensitive, Fast to Build, Managed Services

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        STARTUP RAG STACK                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌──────────┐    ┌───────────────┐    ┌──────────────────┐       │
│  │  Sources │    │   Ingestion   │    │   Vector Store    │       │
│  │  (PDF,   │───▶│   Pipeline    │───▶│   (Pinecone       │       │
│  │  Notion, │    │   (LlamaIndex │    │    Serverless)    │       │
│  │  Web)    │    │    LlamaParse)│    │                   │       │
│  └──────────┘    └───────────────┘    └────────┬──────────┘       │
│                                                 │                  │
│  ┌──────────┐                         ┌────────▼──────────┐       │
│  │  Query   │───▶ Embed ───▶ Hybrid ─▶│   Reranker        │       │
│  │  (User)  │    (text-emb │  Search  │   (Cohere Rerank  │       │
│  │          │     -3-small) │ (Pinecone│    3.5)           │       │
│  └──────────┘              │  + BM25) │                    │       │
│                             └──────────┴────────┬───────────┘       │
│                                                  │                  │
│  ┌──────────┐    ┌───────────────┐    ┌─────────▼──────────┐       │
│  │  Cache   │◀──▶│  Semantic     │◀───│   Generation       │       │
│  │  (Redis  │    │  Cache Check  │    │   (GPT-4o-mini     │       │
│  │   Cloud) │    │  (cosine sim) │    │    default,        │       │
│  └──────────┘    └───────────────┘    │    GPT-4o fallback)│       │
│                                        └────────────────────┘       │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Eval Loop (RAGAS)  │  Monitoring (LangSmith / OpenTelemetry) │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | LlamaIndex | Fastest time-to-value (30-45 min to first working pipeline); rich built-in ingestion (150+ connectors); first-class caching and persistence |
| **Embedding** | `text-embedding-3-small` (OpenAI, 1536d) | $0.02/1M tokens; good enough MTEB score; dimension quantisation available; most cost-effective managed embedding |
| **Vector DB** | Pinecone Serverless | Zero-ops; free tier covers early use; $0.033/GB-month; namespace isolation per customer; no cluster management |
| **Reranker** | Cohere Rerank 3.5 | $2/1K queries (up to 100 docs each); +8–14pp recall@4 in Appycodes benchmarks; no GPU to maintain |
| **LLM** | GPT-4o-mini (default), GPT-4o (hard) | $0.15/$0.60 per 1M input/output; routes cheap model for 70–85% of traffic; 0.92 faithfulness at 18× cheaper than GPT-4o |
| **Cache** | Redis Cloud (semantic cache) | Cuts LLM costs by 60–70% (Boundev case study); cosine-similarity lookup on prior question embeddings |
| **Eval** | RAGAS | Open-source; faithfulness, answer relevancy, context precision; golden-dataset-driven regression gates |
| **Infra** | AWS ECS Fargate / Railway / Render | Docker FastAPI containers; ALB + autoscaling on p90 TTFT >2s; no K8s overhead |

#### Why These Choices

LlamaIndex over LangChain because startups need built-in RAG primitives, not a composable agent framework they'll over-engineer. Pinecone Serverless over pgvector because zero-ops — the team is shipping product, not managing Postgres. GPT-4o-mini with semantic caching because the LLM bill dominates at scale (Appycodes: cache cuts 68.8% of LLM cost). Cohere Rerank 3.5 is the cheapest managed cross-encoder at $2/K queries and buys 8–14pp of recall improvement — the single highest-leverage upgrade after hybrid search.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Baseline** | Week 1–2 | LlamaIndex ingestion pipeline; Pinecone Serverless; single-pass retrieval; GPT-4o-mini generation; 10-document pilot |
| **Phase 2: Retrieval Quality** | Week 3–4 | Hierarchical chunking (384-token); hybrid search (dense + BM25); Cohere rerank top-50→top-5; 50-question golden eval set with RAGAS |
| **Phase 3: Cost & Scale** | Week 5–6 | Semantic cache (Redis); query complexity router (simple→mini, hard→GPT-4o); OpenTelemetry tracing; Prometheus + Grafana dashboards |
| **Phase 4: Production Hardening** | Week 7–8 | Citation validator; user feedback loop; A/B testing framework; CI/CD for eval regression gates; error handling and graceful degradation |

#### Estimated Monthly Cost at Scale

| Scale | Documents | Queries/Day | Breakdown | Monthly Cost |
|-------|-----------|-------------|-----------|--------------|
| **Prototype** | 1K | 100 | Embeddings: ~$2 one-time; Pinecone free tier; LLM: ~$9/mo | **~$15/mo** |
| **Early Production** | 10K | 500 | Embeddings: ~$8 one-time; Pinecone: ~$25; LLM (mini): ~$45; Rerank: ~$30 | **~$110/mo** |
| **Growth** | 100K | 5,000 | Embeddings: ~$190 one-time; Pinecone: ~$280; LLM: ~$900 (cached 60%); Rerank: ~$300 | **~$1,700/mo** |
| **Scale** | 1M | 20,000 | Embeddings: ~$1,900 one-time; Pinecone: ~$2,200; LLM: ~$3,600; Rerank: ~$1,200 | **~$9,000/mo** |

*Source: ZTABS cost estimator, aicost.ai, 2026 provider rate cards.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Vendor lock-in** | Medium | Abstract retrieval behind an adapter interface; LlamaIndex supports 20+ vector stores and 10+ LLM providers — switching requires config change, not code rewrite |
| **Cost overrun at scale** | High | Semantic cache from week 5; query router sends 70%+ traffic to GPT-4o-mini; set hard per-user daily token budgets |
| **Latency spikes** | Medium | Pinecone Serverless cold starts mitigated by keep-warm pings; Redis semantic cache <10ms; set p90 TTFT alert at 2s with autoscaling |
| **Poor chunking on domain docs** | Medium | Use LlamaParse for PDF structure extraction; implement domain-aware section detection before week 3 |
| **No evaluation discipline** | High | Start RAGAS golden dataset in Phase 2 (before going live); add regression gate to CI/CD; this is the #1 cause of startup RAG failures |

---

### 10.2 Enterprise RAG — On-Prem/Private Cloud, Compliance, Scale, SLAs

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE RAG STACK (On-Premises)                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    SECURITY PERIMETER                              │    │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │    │
│  │  │  IdP     │  │  RBAC    │  │  Audit   │  │  Data Residency  │   │    │
│  │  │ (Okta/   │  │  Engine  │  │  Trail   │  │  (per-tenant     │   │    │
│  │  │  AzureAD)│  │  (OPA)   │  │  (PG)    │  │   VPC / VRF)    │   │    │
│  │  └─────────┘  └──────────┘  └──────────┘  └──────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌───────────┐   ┌──────────────┐   ┌─────────────────────┐             │
│  │ Document  │   │  Ingestion   │   │   Vector Store       │             │
│  │ Sources   │──▶│  Pipeline    │──▶│   (Milvus/Qdrant    │             │
│  │ (SharePt, │   │  (Haystack   │   │    Self-Hosted)     │             │
│  │  Confl.,  │   │   pipelines) │   │   + PostgreSQL       │             │
│  │  S3, DBs) │   │              │   │   (metadata/BM25)   │             │
│  └───────────┘   └──────────────┘   └──────────┬──────────┘             │
│                                                  │                        │
│  ┌───────────┐                         ┌────────▼──────────┐             │
│  │  Query    │───▶ Classifier ──▶      │  Hybrid Retriever │             │
│  │  (User)   │    (regex+LLM)  │       │  (RRF: Dense +    │             │
│  │           │    ┌─────────┐   │       │   BM25 + Metadata │             │
│  └───────────┘    │ Route   │   │       │   Filter)         │             │
│                   │ simple  │   │       └────────┬──────────┘             │
│                   │ queries │   │                │                        │
│                   └────┬────┘   │       ┌────────▼──────────┐             │
│                        │        │       │  Multi-Stage       │             │
│  ┌─────────────────────▼──┐     │       │  Reranker          │             │
│  │  Fast Path             │     │       │  (Stage 1: BGE-M3  │             │
│  │  (Direct generation    │     │       │   Stage 2: LLM-as- │             │
│  │   Mixtral 8x7B)        │     │       │   Judge rerank)    │             │
│  └────────────────────────┘     │       └────────┬──────────┘             │
│                                  │                │                        │
│  ┌──────────────────────────────▼────────────────▼──────────────────┐    │
│  │                    Generation Layer                                │    │
│  │  ┌─────────────────────┐   ┌──────────────────────┐              │    │
│  │  │  Primary: Llama 3.1 │   │  Fallback: Mixtral    │              │    │
│  │  │  70B (vLLM, 4× A100)│   │  8x7B (2× A100)      │              │    │
│  │  └─────────────────────┘   └──────────────────────┘              │    │
│  │  ┌─────────────────────┐   ┌──────────────────────┐              │    │
│  │  │  Citation Validator │   │  Guardrails           │              │    │
│  │  │  (verify every      │   │  (PII redaction,      │              │    │
│  │  │   claim → source)   │   │   toxicity filter,    │              │    │
│  │  │                     │   │   content policy)     │              │    │
│  │  └─────────────────────┘   └──────────────────────┘              │    │
│  └───────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  OBSERVABILITY     │  Grafana + Prometheus + Jaeger + ELK         │    │
│  │  ORCHESTRATION     │  Kubernetes + ArgoCD + Helm                  │    │
│  │  GPU SCHEDULING    │  Run:ai / NVIDIA MIG + GPU Operator          │    │
│  │  LOAD BALANCING    │  HAProxy / Envoy + vLLM request queueing     │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | Haystack 2.x | Pipeline model forces explicit data flow, error handling, observability from day one; enterprise support; RBAC; air-gapped deployment; superior for regulated industries |
| **Orchestration** | LangGraph (complex multi-step only) | Used alongside Haystack for agentic workflows requiring state, checkpoints, human-in-the-loop approval edges |
| **Embedding** | `voyage-3-large` (1024d) or `BGE-M3` (self-hosted, 1024d) | Voyage for managed private cloud; BGE-M3 on-prem for air-gapped deployments; both support multilingual; 1024d balances quality and storage cost |
| **Vector DB** | Milvus (distributed) or Qdrant (self-hosted) | Both handle 10M+ vectors with sub-10ms P99; Milvus has stronger multi-tenancy; Qdrant is Rust-based with lower ops overhead; both support RBAC and encryption at rest |
| **Metadata/BM25** | PostgreSQL (pgvector + `tsvector`) | Joins relational metadata (ACL, classification) with vector search; BM25 via `ts_rank_cd`; familiar ops for enterprise DBAs |
| **Hybrid Fusion** | Reciprocal Rank Fusion (RRF, k=60) | No weight tuning required; proven in production (Nic Chin: +10pp recall@5; Chanakya banking: RRF fusion of dense + lexical lanes) |
| **Reranker (Stage 1)** | `BGE-Reranker-v2-m3` (self-hosted ONNX) | Cross-encoder; multilingual; runs on CPU or GPU; free if self-hosted; rescore top-50→top-10 |
| **Reranker (Stage 2)** | LLM-as-Judge (Mixtral 8x7B) | Runs only on top-10; validates factual alignment with retrieved chunks; catches subtle mismatches that cross-encoders miss |
| **LLM** | Llama 3.1 70B (vLLM, 4× A100-80GB) | Open-weight; no data leaves perimeter; vLLM achieves 10× throughput vs vanilla HF; PagedAttention for concurrent users |
| **Guardrails** | Guardrails-AI + custom OPA rules | PII redaction; toxicity filter; content policy enforcement; NIST 800-171 / HIPAA minimum-necessary access control |
| **Auth** | Okta/AzureAD + OPA (Open Policy Agent) | Row-level RBAC on chunks; classification-tag enforcement at retrieval time; every query logged with user identity, timestamp, retrieved documents |
| **Observability** | OpenTelemetry → Grafana + Prometheus + Jaeger | Distributed tracing across all 12 components; latency histogram per stage; accuracy trending per tenant |

#### Why These Choices

Haystack over LangChain because enterprise deployments need production discipline, not rapid prototyping patterns. Haystack's explicit pipeline model compels error handling, logging, and observability at design time — 89% of LangChain teams deviate from official patterns in production (DeployBase 2025 study).

Self-hosted BGE-M3 over managed embeddings because air-gapped environments can't call external APIs. Milvus over Pinecone for multi-tenancy (partition-key isolation per business unit) and distributed scale (billions of vectors across nodes). PostgreSQL co-located with pgvector for `tsvector` BM25 because banking and legal documents contain codes/IDs that dense embeddings miss (Chanakya case study: "pure vector search fails on enterprise documents with transaction codes and form numbers").

Llama 3.1 70B on vLLM because: (1) no data leaves perimeter (GDPR/HIPAA/ITAR compliance), (2) predictable cost (fixed GPU cluster vs per-token), (3) AIVeda reports 10× cheaper than public APIs at sustained high volume.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Infrastructure & Compliance** | Month 1 | K8s cluster on-prem/VPC; GPU node pool (4× A100); Milvus distributed deployment; PostgreSQL + pgvector; HashiCorp Vault for secrets; Okta SSO integration; audit log schema |
| **Phase 2: Core Pipeline** | Month 2 | Haystack ingestion pipelines for SharePoint, Confluence, S3; per-tenant namespace isolation; BGE-M3 embedding service (vLLM); hybrid RRF retrieval; BGE reranker; baseline eval set |
| **Phase 3: Security & Governance** | Month 3 | OPA RBAC with row-level filtering; PII/anonymization during ingestion; document classification tagging; NIST 800-171 access control mapping; full query audit trail; retention policy enforcement |
| **Phase 4: Production Hardening** | Month 4 | LLM-as-Judge second-stage rerank; citation validator; guardrails pipeline; Grafana dashboards with tenant-level SLI/SLO; chaos engineering (node failure, GPU OOM, network partition) |
| **Phase 5: Scale & Optimize** | Month 5–6 | Multi-region replication; hot/warm/cold tiered storage; GPU MIG partitioning for multi-tenant inference; Run:ai scheduling; automated nightly eval sweeps with regression alerting |

#### Estimated Monthly Cost at Scale

| Scale | Documents | Users | Infrastructure | Monthly Cost (TCO) |
|-------|-----------|-------|----------------|---------------------|
| **Department** | 50K | 50 | 1× A100-80GB, 64GB RAM, NVMe; single-node Milvus; 1× GPU (vLLM Mixtral 8x7B) | **$8,000–12,000/mo** |
| **Division** | 500K | 200 | 4× A100-80GB, 256GB RAM; 3-node Milvus cluster; 2× GPU (Llama 3.1 70B) | **$25,000–40,000/mo** |
| **Enterprise** | 5M | 2,000+ | GPU cluster (16× A100/H100); distributed Milvus (6+ nodes); K8s with GPU operator; 4× GPU inference pool | **$120,000–200,000/mo** |

*Infrastructure cost only. Excludes personnel (FTE ML engineers, MLOps, DBAs). Does not include licensing for enterprise support tiers. Private cloud pricing varies significantly by provider and committed-use discounts.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **GPU procurement delay** | High | Order 6+ months ahead; maintain relationship with 2+ hardware vendors; consider cloud burst for unexpected demand (with data-residency approval) |
| **Model staleness** | Medium | Automated nightly eval sweeps against held-out set; regression alerting triggers model rotation review; hedge by supporting 3 model families simultaneously |
| **Tenant isolation breach** | Critical | Milvus partition-key isolation; OPA enforcement at query time; automated integration test that queries as tenant A and asserts zero results from tenant B's namespace; quarterly penetration test |
| **Embedding model swap** | High | All chunks stored with source text in PostgreSQL; re-indexing pipeline can regenerate all embeddings without re-ingesting documents; plan for 48-hour re-embedding window |
| **Operational complexity** | High | Dedicated MLOps team; runbooks for GPU OOM, vLLM restart, Milvus rebalance; chaos engineering before go-live; 24/7 on-call rotation with escalation paths |
| **Compliance audit failure** | Critical | Every query logged (user, timestamp, retrieved document IDs, response); tamper-proof audit trail (immutable PostgreSQL table with cryptographic chaining); quarterly internal audit rehearsal |

---

### 10.3 Fully Open-Source RAG — No Vendor Lock-In, Self-Hosted Everything

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   FULLY OPEN-SOURCE RAG STACK                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     INGESTION LAYER                                │    │
│  │  ┌──────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐   │    │
│  │  │ Docling  │   │ Tika/     │   │ Marker    │   │ Unstructured│   │    │
│  │  │ (PDF,    │   │ Apache    │   │ (PDF→MD)  │   │ (HTML, CSV)│   │    │
│  │  │  DOCX,   │   │  Tika     │   │           │   │            │   │    │
│  │  │  PPTX)   │   │ (Office)  │   │           │   │            │   │    │
│  │  └────┬─────┘   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘   │    │
│  │       └───────────────┴───────────────┴───────────────┘          │    │
│  │                              │                                    │    │
│  │                    ┌─────────▼─────────┐                          │    │
│  │                    │  Chunking Engine   │                          │    │
│  │                    │  (6 strategies:    │                          │    │
│  │                    │   recursive,       │                          │    │
│  │                    │   semantic, markdn,│                          │    │
│  │                    │   hierarchical,    │                          │    │
│  │                    │   hybrid)          │                          │    │
│  │                    └─────────┬─────────┘                          │    │
│  └──────────────────────────────┼────────────────────────────────────┘    │
│                                 │                                         │
│  ┌──────────────────────────────▼────────────────────────────────────┐    │
│  │                     EMBEDDING & STORAGE                             │    │
│  │                                                                     │    │
│  │  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────┐    │    │
│  │  │ Embedding Model │   │  Vector Store     │   │  BM25 Index   │    │    │
│  │  │ nomic-embed-text│   │  Qdrant (dense)   │   │  MiniSearch / │    │    │
│  │  │ (768d, Ollama)  │   │  or Milvus        │   │  PostgreSQL   │    │    │
│  │  │ BGE-M3 (1024d)  │   │  or pgvector      │   │  tsvector     │    │    │
│  │  │ fastembed (BM25)│   │                    │   │               │    │    │
│  │  └────────┬────────┘   └────────┬─────────┘   └───────┬───────┘    │    │
│  │           └─────────────────────┴─────────────────────┘            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     QUERY PIPELINE                                 │    │
│  │                                                                     │    │
│  │  Query ──▶ HyDE (optional) ──▶ Dense + Sparse ──▶ RRF Fusion      │    │
│  │                                    │                               │    │
│  │                           ┌────────▼──────────┐                    │    │
│  │                           │ Cross-Encoder      │                    │    │
│  │                           │ FlashRank /        │                    │    │
│  │                           │ BGE-Reranker-v2-m3 │                    │    │
│  │                           │ (ONNX, local)      │                    │    │
│  │                           └────────┬──────────┘                    │    │
│  │                                    │                               │    │
│  │  ┌─────────────────────────────────▼─────────────────────────┐    │    │
│  │  │  Generation                                                  │    │    │
│  │  │  qwen2.5:14b / Llama 3.1 8B / DeepSeek-R1-Distill (Ollama)│    │    │
│  │  │  + Citations + Hallucination check                          │    │    │
│  │  └────────────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  INFRASTRUCTURE                                                    │    │
│  │  Docker Compose (single-node) OR K8s (multi-node)                  │    │
│  │  Traefik (API gateway) │ Redpanda (event bus) │ Redis (cache)     │    │
│  │  Prometheus + Grafana + Jaeger (observability)                     │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | LlamaIndex (retrieval) + Custom orchestration | Most mature open-source RAG framework; built-in caching, persistence, evaluation; hexagonal architecture for swapping components |
| **Doc Parsing** | Docling (IBM, Apache 2.0) | State-of-the-art PDF/DOCX/PPTX/HTML parsing; understands document layout; actively maintained in 2026 |
| **Chunking** | 6 strategies: recursive, semantic (spaCy sentence boundary), markdown-aware, hierarchical, hybrid | Production RAG needs per-document-type chunking strategy (ESG compliance case study: "differentiated chunking strategies — any system processing both rule documents and long-form text"); no single strategy works for all |
| **Embedding** | `nomic-embed-text` (768d, Ollama) → `BGE-M3` (1024d, vLLM) at scale | Nomic for low-resource start (runs on CPU); BGE-M3 for production (multilingual, MTEB leader); both Apache 2.0 / MIT |
| **Sparse Embeddings** | BM25 via `fastembed` (Qdrant) or PostgreSQL `tsvector` | No separate service; fastembed generates sparse vectors stored as named vectors in Qdrant |
| **Vector DB** | Qdrant (self-hosted, Apache 2.0) | Named vectors (dense + sparse in one collection); RRF built-in; quantization for storage efficiency; Rust performance; single-binary deployment |
| **Metadata DB** | PostgreSQL | Relational metadata, user accounts, audit logs, eval results; pgvector extension for mixed workloads |
| **Reranker** | FlashRank (ultra-light) → BGE-Reranker-v2-m3 (ONNX) | FlashRank for CPU-only deployments; BGE-Reranker ONNX for GPU; both free, local, no API calls |
| **LLM** | qwen2.5:14b (Ollama) → Llama 3.1 70B (vLLM) at scale | Qwen 2.5 strong on retrieval tasks; Llama 3.1 for highest quality; both open-weight (no usage restrictions) |
| **Cache** | Redis (exact SHA-256) + Qdrant (semantic cosine) | Two-layer: exact-match cache <5ms; semantic cache <15ms; 200× faster than full pipeline (oldforks/distributed-rag-system reference) |
| **Message Broker** | Redpanda (Kafka-compatible, no ZooKeeper) | Event-driven ingestion; documents flow asynchronously; ingestion never blocks query serving |
| **Observability** | OpenTelemetry → Jaeger + Prometheus + Grafana | Per-stage latency histograms; token accounting; retrieval recall trending; all open-source |
| **Auth** | JWT (python-jose) + API key middleware | Simple but effective; integrate with any external IdP via OIDC |

#### Why These Choices

This stack mirrors the `oldforks/distributed-rag-system` reference implementation — a production-grade, fully open-source blueprint that has been tested at scale. Every component has an Apache 2.0, MIT, or similarly permissive license. No component requires a commercial API key.

Qdrant over pgvector for pure vector workloads because: (1) named vectors allow storing dense + sparse embeddings as a single entity with RRF fusion inside the DB, (2) quantization reduces storage by 4–8×, (3) single-binary deployment with no external dependencies. PostgreSQL is still present for metadata, but vectors live in Qdrant.

Two-tier LLM strategy (Ollama → vLLM) mirrors real deployments: start with Ollama + qwen2.5:14b on a single GPU, graduate to vLLM + Llama 3.1 70B on a GPU cluster when query volume justifies it.

Redpanda for event-driven ingestion because it's a drop-in Kafka replacement without ZooKeeper — simpler operations at startup scale.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Single-Node Boot** | Week 1–2 | Docker Compose: Qdrant, PostgreSQL, Redis, Redpanda, Ollama (nomic-embed-text + qwen2.5:14b), Traefik; Docling ingestion; basic retrieval; RAGAS eval on 20-question set |
| **Phase 2: Retrieval Quality** | Week 3–4 | 3 chunking strategies (A/B tested); hybrid RRF with fastembed BM25; FlashRank reranker; HyDE query expansion; 100-question golden dataset |
| **Phase 3: Scale Out** | Week 5–6 | K8s migration; vLLM for Llama 3.1 70B; distributed Qdrant (3 nodes); semantic cache; event-driven ingestion with Redpanda; Jaeger tracing |
| **Phase 4: Production Readiness** | Week 7–8 | JWT auth; citation validation; nightly eval sweeps; Prometheus alerting rules; runbooks for all failure modes; load testing at 100 concurrent users |

#### Estimated Monthly Cost at Scale

| Scale | Documents | Queries/Day | Hardware | Monthly Cost (cloud VM) |
|-------|-----------|-------------|----------|--------------------------|
| **Single-node (dev)** | 10K | 100 | 1× RTX 4090 (24GB VRAM), 64GB RAM, 500GB NVMe | **$300–500/mo** (dedicated server) |
| **Small production** | 100K | 1,000 | 2× A10 (24GB each), 128GB RAM, 2TB NVMe | **$1,500–2,500/mo** |
| **Medium production** | 1M | 10,000 | 4× A100-80GB, 256GB RAM, 8TB NVMe, 3-node Qdrant cluster | **$8,000–12,000/mo** |
| **Large production** | 10M | 100,000 | 16× A100/H100, 512GB+ RAM per node, distributed Qdrant, K8s cluster | **$30,000–60,000/mo** |

*Cloud VM pricing (AWS, GCP, or bare-metal providers like Vultr/Lambda Labs). No per-token API costs — all inference runs on owned GPUs. Excludes personnel. Self-hosting on owned hardware cuts cloud costs by 40–60% after 18-month hardware amortization.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **GPU shortage for inference** | High | Hedge with CPU-capable models (qwen2.5:7b-q4 can run on 32GB RAM CPU at ~5 tok/s); maintain fallback to cloud GPU spot instances during capacity crunches |
| **Open-source model quality gap** | Medium | Llama 3.1 70B matches GPT-4 on many RAG benchmarks; use BGE-M3 (top MTEB performer); new open models release every 2–3 months — stay current |
| **Operational burden** | High | Invest in IaC (Terraform, Ansible); automated model updates with canary deployments; document every runbook; budget 1 FTE platform engineer minimum |
| **Vector DB scaling issues** | Medium | Qdrant supports horizontal scaling via sharding; test at 3× expected load before go-live; maintain migration path to Milvus if Qdrant proves insufficient |
| **Community dependency** | Medium | Pin exact versions in requirements.txt; vendor critical forks; contribute fixes upstream to maintain goodwill and reduce divergence |

---

### 10.4 Multilingual RAG — 10+ Languages, Cross-Lingual Retrieval

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     MULTILINGUAL RAG STACK (10+ Languages)                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    LANGUAGE DETECTION & ROUTING                    │    │
│  │                                                                     │    │
│  │  Query ──▶ LangDetect (fastText 157 languages, <1ms)              │    │
│  │              │                                                     │    │
│  │     ┌────────┼────────┬──────────────┐                            │    │
│  │     ▼        ▼        ▼              ▼                            │    │
│  │  HI-RES   MID-RES  LOW-RES      CODE-SWITCH                       │    │
│  │  (EN,ZH,  (DE,FR,  (SW,AM,      (mixed lang                       │    │
│  │   AR,JA)   ES,PT)   BN, etc.)    queries)                         │    │
│  │     │        │        │              │                            │    │
│  │     │        │        │              ▼                            │    │
│  │     │        │        │       Decompose into                       │    │
│  │     │        │        │       monolingual sub-                     │    │
│  │     │        │        │       queries per lang                     │    │
│  └─────┼────────┼────────┼──────────────┼────────────────────────────┘    │
│        │        │        │              │                                 │
│  ┌─────▼────────▼────────▼──────────────▼────────────────────────────┐    │
│  │                    CROSS-LINGUAL RETRIEVAL ENGINE                  │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐ │    │
│  │  │  Strategy Selector (per query, real-time)                     │ │    │
│  │  │                                                               │ │    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │ │    │
│  │  │  │ CrossRAG     │  │ Translate-   │  │ MultiRAG         │   │ │    │
│  │  │  │ (retrieve    │  │ then-Retrieve│  │ (multilingual     │   │ │    │
│  │  │  │  multilingual│  │ (query→EN    │  │  index, retrieve  │   │ │    │
│  │  │  │  → translate │  │  + EN index) │  │  in all langs)    │   │ │    │
│  │  │  │  docs→EN     │  │              │  │                   │   │ │    │
│  │  │  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘   │ │    │
│  │  │         └─────────────────┴────────────────────┘              │ │    │
│  │  └──────────────────────────────────────────────────────────────┘ │    │
│  │                                                                    │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Unified Multilingual Embedding: BGE-M3 (1024d, 100+ langs) │ │    │
│  │  │  Dense retrieval across languages in shared semantic space   │ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  │                                                                    │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Per-Language Sparse Index: BM25 (Elasticsearch / OpenSearch)│ │    │
│  │  │  Language-specific analyzers (tokenizer, stemming, stopwords)│ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  │                                                                    │    │
│  │  ┌─────────────────────────────────────────────────────────────┐ │    │
│  │  │  Hybrid Fusion: RRF (k=60) across dense + sparse per lang    │ │    │
│  │  │  + Language-weighted score adjustment                         │ │    │
│  │  └─────────────────────────────────────────────────────────────┘ │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                    RERANKING & GENERATION                          │    │
│  │                                                                     │    │
│  │  ┌────────────────────────────┐  ┌─────────────────────────────┐ │    │
│  │  │ Multilingual Reranker      │  │ Generation with Language      │ │    │
│  │  │ BGE-Reranker-v2-m3 (ONNX) │  │ Consistency Enforcement        │ │    │
│  │  │ Covers 100+ languages      │  │                               │ │    │
│  │  └────────────┬───────────────┘  │ ┌───────────────────────────┐ │ │    │
│  │               │                  │ │ 1. Document translation    │ │ │    │
│  │               ▼                  │ │    (NLLB-200 / MADLAD-400)│ │ │    │
│  │  ┌────────────────────────────┐  │ │    if retrieved lang ≠    │ │ │    │
│  │  │ Cross-lingual Relevance    │  │ │    user lang               │ │ │    │
│  │  │ Scoring: Penalize chunks   │  │ │                           │ │ │    │
│  │  │ when passage_lang ≠       │  │ │ 2. Generation in user      │ │ │    │
│  │  │ user_lang unless source    │  │ │    language (Llama 3.1 /  │ │ │    │
│  │  │ is uniquely informative    │  │ │    Mixtral 8x22B /        │ │ │    │
│  │  └────────────────────────────┘  │ │    GPT-4o multilingual)   │ │ │    │
│  │                                   │ │                           │ │ │    │
│  │                                   │ │ 3. Code-switching guard   │ │ │    │
│  │                                   │ │    (check response is in  │ │ │    │
│  │                                   │ │    correct language)      │ │ │    │
│  │                                   │ └───────────────────────────┘ │ │    │
│  └───────────────────────────────────┴───────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  EVALUATION (per language)                                         │    │
│  │  Language-specific golden datasets │ MMTEB benchmark tracking     │    │
│  │  Cross-lingual recall@k per lang pair │ Faithfulness per language │    │
│  │  Translation quality gate │ Response language correctness score   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | Haystack (multilingual pipeline + enterprise eval) | Best multilingual accuracy (94% across 19 languages in 2026 benchmarks); explicit pipeline model handles per-language routes cleanly |
| **Language Detection** | fastText (Meta, 157 languages, <1ms) | Production-proven; runs in-process; no API call; 99%+ accuracy on 50+ word queries |
| **Multilingual Embedding** | `BGE-M3` (BAAI, 1024d, 100+ languages) | Top of MMTEB leaderboard; supports dense + sparse + ColBERT-style in one model; open-source MIT license |
| **Alternative Embedding** | `Cohere embed-multilingual-v3.0` (1024d) | If managed is acceptable; strong low-resource language performance; $0.10/1M tokens |
| **Translation Model** | NLLB-200 (Meta, 200 languages) or MADLAD-400 (Google, 400+ languages) | NLLB for document translation in CrossRAG strategy; MADLAD for broader coverage; both open-weight |
| **Sparse Retrieval** | Elasticsearch/OpenSearch with per-language analyzers | Language-specific tokenizers (kuromoji for Japanese, IK for Chinese, etc.); BM25 tuned per language |
| **Vector DB** | Qdrant (multilingual collections) or Weaviate (native hybrid) | Both support per-collection embedding config; Qdrant named vectors for dense+sparse; Weaviate has first-class hybrid search |
| **Reranker** | `BGE-Reranker-v2-m3` (ONNX, multilingual) | Covers 100+ languages; Sigmoid-normalized relevance scores; local inference |
| **LLM** | Llama 3.1 70B (multilingual training) or GPT-4o (best cross-lingual) | Llama 3.1 for on-prem; GPT-4o for managed; both strong on 50+ languages |
| **Code-Switching Guard** | fastText + heuristics + LLM validation | Detect mixed-language queries; decompose into monolingual sub-queries; validate response language matches query language (XRAG finding: "LLMs struggle with response language correctness in cross-lingual settings") |

#### Why These Choices

BGE-M3 is the consensus multilingual embedding model in 2026 — it achieves the highest MMTEB scores, supports 100+ languages in a single 1024d space, and generates dense, sparse, and ColBERT representations from one model. This eliminates the need for separate per-language embedding models.

The **three-strategy selector** (CrossRAG, Translate-then-Retrieve, MultiRAG) is based on academic findings from 2025:
- **CrossRAG** (retrieve multilingual → translate docs → generate): Best for accuracy (XRAG/CrossRAG paper). Retrieve in all languages for maximum recall, then translate retrieved docs to a common language for generation.
- **Translate-then-Retrieve**: Best for latency-critical, high-resource language pairs where translation quality is reliable.
- **MultiRAG** (retrieve in all languages, generate in user language): Best when documents contain tables/figures that translation would corrupt.

Language-specific BM25 analyzers are critical: Japanese requires morphological segmentation (kuromoji), Chinese needs character n-gram tokenization (IK), Arabic needs root-based stemming. Generic whitespace tokenization destroys recall in these languages.

NLLB-200 for document translation because it's the only open model covering 200 languages with production-quality output. Benchmarked extensively by Meta for cross-lingual tasks.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Core 5 Languages** | Month 1–2 | BGE-M3 embedding pipeline; Qdrant per-language collections; fastText language detection; Elasticsearch with per-language analyzers for EN, ES, FR, DE, ZH; baseline eval sets per language |
| **Phase 2: Cross-Lingual Retrieval** | Month 3 | Strategy selector (CrossRAG / Translate-then-Retrieve / MultiRAG); NLLB-200 translation service; cross-lingual RRF fusion; BGE-Reranker-v2-m3; cross-lingual recall evaluation |
| **Phase 3: Expand to 10+ Languages** | Month 4 | Add JA, AR, PT, RU, KO; per-language BM25 analyzers; per-language golden datasets; code-switching handler; response language validator |
| **Phase 4: Low-Resource Languages** | Month 5–6 | Add SW, AM, BN, HI, VI; MADLAD-400 for translation; synthetic data generation for eval datasets; enhanced low-res language embedding fine-tuning (SimCSE); per-language quality SLAs |
| **Phase 5: Production Hardening** | Month 7 | Per-language latency SLOs; cascading failover (if NLLB unavailable, fallback to MultiRAG); A/B testing per language pair; user language preference persistence |

#### Estimated Monthly Cost at Scale

| Scale | Languages | Documents | Queries/Day | Monthly Cost |
|-------|-----------|-----------|-------------|--------------|
| **Startup (5 langs)** | EN, ES, FR, DE, ZH | 100K | 1,000 | **$2,500–4,000** |
| **Mid (10 langs)** | + JA, AR, PT, RU, KO | 500K | 5,000 | **$8,000–15,000** |
| **Enterprise (20+ langs)** | + HI, SW, BN, VI, TH, etc. | 5M | 50,000 | **$40,000–80,000** |
| **Global (50+ langs)** | All supported by BGE-M3 | 20M+ | 200,000 | **$150,000–300,000** |

*Includes GPU costs for NLLB-200 translation (lighter than LLM inference), Elasticsearch cluster, and Qdrant distributed deployment. Translation is the dominant cost adder vs monolingual RAG (2–3×).*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Low-resource language embedding quality** | High | BGE-M3 covers 100+ languages but performance varies wildly; evaluate per-language recall@k before launch; fine-tune embeddings with SimCSE on domain data for underperforming languages |
| **Translation quality for technical content** | High | Never translate at index time (lossy); translate only retrieved chunks at query time; use domain-specific glossaries for technical terms; A/B test NLLB-200 vs MADLAD-400 per language pair |
| **Code-switching hallucinations** | Medium | XRAG finding: LLMs often respond in wrong language in cross-lingual settings; enforce response language at system-prompt level + post-hoc validation; retry in correct language if mismatch detected |
| **Per-language latency variance** | Medium | Low-resource languages with translation step add 200–500ms; set per-language latency SLOs; pre-translate frequently retrieved chunks and cache; consider Translate-then-Retrieve for latency-sensitive pairs |
| **Evaluation complexity** | High | 10 languages × 3 retrieval strategies = 30 evaluation dimensions; automate with RAGAS per-language configs; use synthetic data generation for low-resource eval sets; budget dedicated QA linguist |

---

### 10.5 Agentic RAG — Multi-Step Reasoning, Tool Use, Autonomous Retrieval Decisions

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       AGENTIC RAG STACK                                     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     QUERY ROUTER (Hybrid)                          │    │
│  │                                                                     │    │
│  │  User Query ──▶ ┌─────────────────────────────────────────────┐  │    │
│  │                 │  Rules Engine (regex, length, keywords)      │  │    │
│  │                 │  + LLM Classifier (Haiku/GPT-4o-mini)        │  │    │
│  │                 └───────────────┬─────────────────────────────┘  │    │
│  │                                 │                                  │    │
│  │          ┌──────────────────────┼──────────────────────┐         │    │
│  │          ▼                      ▼                      ▼         │    │
│  │   ┌────────────┐    ┌─────────────────┐    ┌──────────────┐     │    │
│  │   │ Fast Path  │    │   Agentic Path  │    │  Graph Path  │     │    │
│  │   │ (Single-   │    │   (Multi-step   │    │  (GraphRAG   │     │    │
│  │   │  shot RAG) │    │    reasoning)   │    │   traversal) │     │    │
│  │   └─────┬──────┘    └───────┬─────────┘    └──────┬───────┘     │    │
│  │         │                   │                      │             │    │
│  └─────────┼───────────────────┼──────────────────────┼─────────────┘    │
│            │                   │                      │                  │
│            │     ┌─────────────▼──────────────────────▼──────────┐      │
│            │     │           AGENTIC REASONING LOOP                │      │
│            │     │                                                 │      │
│            │     │  ┌───────────────────────────────────────────┐ │      │
│            │     │  │         ORCHESTRATOR AGENT                 │ │      │
│            │     │  │  (LangGraph StateGraph)                    │ │      │
│            │     │  │  - Evaluates query complexity              │ │      │
│            │     │  │  - Plans retrieval strategy                │ │      │
│            │     │  │  - Routes to specialized agents            │ │      │
│            │     │  │  - Manages state across iterations         │ │      │
│            │     │  └──────────────────┬────────────────────────┘ │      │
│            │     │                     │                           │      │
│            │     │     ┌───────────────┼───────────────┐          │      │
│            │     │     ▼               ▼               ▼          │      │
│            │     │  ┌────────┐  ┌────────────┐  ┌──────────┐     │      │
│            │     │  │Planner │  │  Retriever │  │  Tool    │     │      │
│            │     │  │ Agent  │  │   Agent    │  │  Agent   │     │      │
│            │     │  │(decomp │  │ (dense +   │  │ (SQL,    │     │      │
│            │     │  │ queries│  │  sparse +  │  │  calc,   │     │      │
│            │     │  │ → steps│  │  GraphRAG) │  │  API)    │     │      │
│            │     │  └───┬────┘  └─────┬──────┘  └────┬─────┘     │      │
│            │     │      │             │              │            │      │
│            │     │      └─────────────┼──────────────┘            │      │
│            │     │                    ▼                           │      │
│            │     │  ┌─────────────────────────────────────────┐  │      │
│            │     │  │     REFLECTION AGENT (Evidence-Gap)      │  │      │
│            │     │  │  - Scores evidence sufficiency (0-100)   │  │      │
│            │     │  │  - Identifies specific missing info      │  │      │
│            │     │  │  - Triggers re-retrieval or reformulation│  │      │
│            │     │  │  - Sets stop condition (sufficient /     │  │      │
│            │     │  │    max_iter=4 / timeout=12s)             │  │      │
│            │     │  └──────────────────┬──────────────────────┘  │      │
│            │     │                     │                          │      │
│            │     │        ┌────────────▼───────────┐              │      │
│            │     │        │  SUFFICIENT? No → Loop  │              │      │
│            │     │        │  Yes ↓                  │              │      │
│            │     │        └────────────┬───────────┘              │      │
│            │     └─────────────────────┼──────────────────────────┘      │
│            │                           │                                 │
│  ┌─────────▼───────────────────────────▼──────────────────────────┐      │
│  │                    ANSWER SYNTHESIS                              │      │
│  │                                                                  │      │
│  │  ┌────────────────────────────────────────────────────────────┐ │      │
│  │  │  Synthesis Agent (Llama 3.1 70B / GPT-4o / Claude Sonnet)  │ │      │
│  │  │  - Compose final answer from accumulated evidence           │ │      │
│  │  │  - Per-claim citation linking                               │ │      │
│  │  │  - Confidence calibration ("high", "medium", "low")         │ │      │
│  │  │  - Flag partial coverage: "I found X, but I'm missing Y"   │ │      │
│  │  └────────────────────────────────────────────────────────────┘ │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  EVALUATION & MONITORING                                           │    │
│  │  Iteration distribution (1-pass: 65-75%, 2: 15-20%, 3: 5-10%,    │    │
│  │  4+: <5%); per-iteration latency; tool-call success rate;         │    │
│  │  cost per query by path (fast/agentic/graph)                       │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Orchestration** | **LangGraph** (StateGraph + checkpointer) | Mature agent framework with built-in state management, persistence, streaming, human-in-the-loop; used by xAI, Databricks, Google; supports supervisor-worker topology |
| **Query Router** | Hybrid: regex/heuristics first → LLM (Claude Haiku) fallback | 60–75% of queries are simple (single-hop factual); routing them through agentic loop wastes 4–12× cost for zero quality gain. Rules-based first pass is free (<1ms); LLM classifier only for ambiguous cases |
| **Planner Agent** | Claude Sonnet / GPT-4o (structured output) | Decomposes complex queries into 2–6 atomic sub-queries with dependencies; outputs JSON plan with step ordering, tool selection per step |
| **Retrieval Tools** | 3+ tools: `vector_search`, `keyword_search`, `graph_search`, `sql_query`, `api_call` | Multi-tool orchestration — agent selects right tool per sub-query; Claude tool-use API or OpenAI function calling |
| **Reflection Agent** | Claude Sonnet / GPT-4o | Scores evidence sufficiency on 100-point multidimensional rubric; identifies specific missing info (not just "needs more"); triggers rewrite-re-retrieve with targeted gap instructions |
| **Reranker** | Cohere Rerank 3.5 + LLM-as-Judge (Stage 2) | Cross-encoder for first pass (cheap); LLM-as-Judge only for top-5 validation (expensive but precise) |
| **LLM** | GPT-4o / Claude Sonnet 3.5 / Llama 3.1 70B | Strong reasoning models required for planning, reflection, and multi-step synthesis; Claude superior for tool-use accuracy; GPT-4o for broad knowledge |
| **State Store** | PostgreSQL + Redis | LangGraph checkpoint persistence in PG; Redis for hot state between loop iterations |
| **Observability** | LangSmith / structlog + OpenTelemetry | Per-iteration traces; tool-call latency; token accounting per agent; structured loop telemetry (iteration count, stop reason, gap score) |
| **Vector DB** | Same as base RAG stack (Pinecone/Qdrant/pgvector) | Agentic RAG is an orchestration layer on top of standard retrieval infrastructure |

#### Why These Choices

LangGraph is the consensus agentic RAG orchestration framework — Google Research's Gemini Enterprise Agentic RAG, xAI, Databricks, and Protocol-H all build on LangGraph patterns. It provides the StateGraph abstraction that maps directly to the supervisor-worker topology proven in production (84.5% accuracy vs 62.8% flat-agent on EntQA benchmark).

The **hybrid router** is the #1 cost-saving pattern in agentic RAG. Google Research found that 60–75% of production queries are simple and get zero quality improvement from the agentic path. Routing them to single-shot RAG saves 4–12× cost with no quality penalty (Digital Applied, 2026).

The **Reflection Agent with explicit gap identification** is the key innovation that makes agentic RAG reliable. Rather than blind re-retrieval, Google's Sufficient Context Agent explicitly logs what information is missing and triggers targeted retrieval. This is what drove the 34% accuracy improvement over vanilla RAG in Google's benchmarks.

Five **non-negotiable loop bounds**: max_iterations=4, timeout=12s, min_new_chunks_per_iteration=1, context token budget, and graceful degradation on forced termination (generate with accumulated context + caveat, never return 500).

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Baseline RAG** | Month 1 | Standard production RAG pipeline (hybrid search, reranker, citation validator); 100-question eval set; latency + cost baselines |
| **Phase 2: Router + Fast Path** | Month 2 | Hybrid router (regex + Haiku classifier); single-shot fast path for 70% of traffic; cost tracking per path; verify fast path quality == baseline on simple queries |
| **Phase 3: Agentic Loop** | Month 3 | LangGraph StateGraph orchestrator; Planner agent with structured output; multi-tool retrieval (vector + keyword + SQL); basic reflection (binary sufficient/insufficient); 4-iteration max bound |
| **Phase 4: Advanced Agents** | Month 4 | Reflection agent with evidence-gap scoring (0-100 rubric); targeted query rewriting; GraphRAG tool integration; graceful degradation on timeout/max-iter; per-iteration telemetry |
| **Phase 5: Production Hardening** | Month 5–6 | A/B test agentic vs baseline on complex queries; cost/quality Pareto analysis per query type; alerting on loop anomalies (iteration spikes, tool failures); gradual rollout to 30%→50%→100% of complex traffic |

#### Estimated Monthly Cost at Scale

| Scale | Queries/Day | % Agentic | LLM Cost (Agentic) | LLM Cost (Fast) | Total |
|-------|-------------|-----------|---------------------|-----------------|-------|
| **Startup** | 1,000 | 15% | $300 (avg 2.5 iterations) | $85 | **~$450/mo** |
| **Mid** | 10,000 | 20% | $3,200 | $900 | **~$4,500/mo** |
| **Enterprise** | 100,000 | 25% | $48,000 | $12,000 | **~$65,000/mo** |

*Agentic RAG costs 4–12× more per query than single-shot RAG (Appycodes, Digital Applied). Router is the critical cost control — every 1% of simple queries routed to agentic is wasted spend. Includes LLM + reranker + tool-call costs. Most teams should target <25% agentic path volume.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Runaway loops** | Critical | 5 hard bounds enforced in code, not prompt; circuit breaker kills loop after timeout regardless of state; Prometheus alert on p99 iterations >3 over 5-min window |
| **Cost explosion** | High | Per-user daily budget; slow rollout (5%→25%→50% of complex traffic); kill switch to route all traffic through fast path if cost anomaly detected |
| **Reflection agent miscalibration** | High | Calibrate sufficiency scores against real queries; target 65-75% termination after iteration 1, 15-20% after 2, <5% after 4+; if actual distribution deviates, freeze and investigate |
| **Tool call hallucinations** | Medium | Schema-validate all tool inputs; max 1 tool call per step to prevent combinatorial explosion; log all tool failures and alert on >5% error rate |
| **Latency regressions** | Medium | P95 latency target: <8s for agentic path (vs <2s for fast path); streaming response starts as soon as first iteration completes; user sees progress indicators per step |

---

### 10.6 Codebase QA — Code-Specific Retrieval, AST-Aware, Repo-Level Understanding

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                      CODEBASE QA RAG STACK                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     CODE INGESTION (Offline)                       │    │
│  │                                                                     │    │
│  │  Git Repo ──▶ ┌──────────────────────────────────────────────┐   │    │
│  │              │  Tree-sitter Parser (per language)              │   │    │
│  │              │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐ │   │    │
│  │              │  │ Rust │ │Python│ │ TS   │ │ Go   │ │Java │ │   │    │
│  │              │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬──┘ │   │    │
│  │              └─────┼────────┼────────┼────────┼────────┼────┘   │    │
│  │                    │        │        │        │        │         │    │
│  │         ┌──────────┼────────┼────────┼────────┼────────┼────┐   │    │
│  │         │          ▼        ▼        ▼        ▼        ▼    │   │    │
│  │         │              AST-Aware Chunking                     │   │    │
│  │         │  (cAST algorithm — split at function/class/type    │   │    │
│  │         │   boundaries, never mid-statement)                  │   │    │
│  │         │  + Docstring extraction (///, """, /** */, //)     │   │    │
│  │         │  + Declaration signature extraction                │   │    │
│  │         └─────────────────────┬──────────────────────────────┘   │    │
│  │                               │                                   │    │
│  │         ┌─────────────────────▼──────────────────────────────┐   │    │
│  │         │            Knowledge Graph Construction              │   │    │
│  │         │                                                      │   │    │
│  │         │  ┌──────────────┐  ┌─────────────────────────────┐  │   │    │
│  │         │  │ Call Graph   │  │ Dependency Graph             │  │   │    │
│  │         │  │ (caller→     │  │ (imports, exports,           │  │   │    │
│  │         │  │  callee      │  │  extends, implements,        │  │   │    │
│  │         │  │  edges)      │  │  DI injection edges)         │  │   │    │
│  │         │  └──────┬───────┘  └──────────────┬──────────────┘  │   │    │
│  │         │         │                         │                  │   │    │
│  │         │         └─────────┬───────────────┘                  │   │    │
│  │         │                   ▼                                  │   │    │
│  │         │         Neo4j / LanceDB Graph Store                  │   │    │
│  │         └──────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │         ┌──────────────────────────────────────────────────────┐   │    │
│  │         │            Vector & Keyword Indexing                   │   │    │
│  │         │                                                        │   │    │
│  │         │  Embedding: Voyage-code-3 (1024d) or CodeBERT        │   │    │
│  │         │  Vector Store: Qdrant / LanceDB                        │   │    │
│  │         │  Keyword Index: BM25 (MiniSearch / Elasticsearch)     │   │    │
│  │         │  + NL Enrichment: LLM generates summaries per chunk   │   │    │
│  │         └──────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     QUERY-TIME RETRIEVAL                           │    │
│  │                                                                     │    │
│  │  User Query ──▶ Intent Classifier                                 │    │
│  │                   │                                                │    │
│  │     ┌─────────────┼──────────────────┬──────────────┐             │    │
│  │     ▼             ▼                  ▼              ▼             │    │
│  │  Semantic   Relationship       Comparison      Symbol             │    │
│  │  Search     ("what calls X",   ("diff A vs B") Lookup             │    │
│  │  (vector)    "called by Y")    → per-compara-  ("find             │    │
│  │              → GraphRAG        tor decomp +    UserService")      │    │
│  │              augmentation      vector sub-     → keyword           │    │
│  │                                search + RRF     search            │    │
│  │     │             │                  │              │             │    │
│  │     └─────────────┼──────────────────┼──────────────┘             │    │
│  │                   ▼                  ▼                            │    │
│  │  ┌───────────────────────────────────────────────────────────┐   │    │
│  │  │   Multi-Stage Retrieval Pipeline                            │   │    │
│  │  │                                                            │   │    │
│  │  │  Stage 1: Vector Search (top-20) + BM25 (top-20)          │   │    │
│  │  │  Stage 2: RRF Fusion                                      │   │    │
│  │  │  Stage 3: Graph Expansion (add callers, callees, imports) │   │    │
│  │  │  Stage 4: Cross-Encoder Rerank (top-20 → top-5)           │   │    │
│  │  │  Stage 5: Token Budget Optimizer (cap at 8K tokens)       │   │    │
│  │  └───────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     GENERATION & RESPONSE                          │    │
│  │                                                                     │    │
│  │  Claude Sonnet / GPT-4o / DeepSeek-Coder (code-aware generation)   │    │
│  │  + Syntax-highlighted code blocks                                   │    │
│  │  + Per-file, per-function source citations                          │    │
│  │  + MCP Server (6 tools: search, context, explain, callers, refs)    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  INCREMENTAL INDEXING: Git-diff based; only changed files re-      │    │
│  │  processed; SHA-256 hash check at file level before re-indexing    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **AST Parser** | **Tree-sitter** (universal incremental parser) | Handles Rust, Python, TypeScript/JSX, Go, Java, C#, C/C++, Kotlin, SQL; incremental parsing enables fast re-indexing on Git diffs; used by every production code RAG system (nexu, CodeRAG, code-rag, codebase-expert, AST-RAG) |
| **Code Embedding** | `Voyage-code-3` (1024d) or `CodeBERT` (self-hosted, 768d) | Voyage-code-3 is purpose-built for code retrieval (top of CoIR benchmark); CodeBERT for air-gapped deployments; generic text embeddings lose 30–50% recall on code queries (LanceDB CodeQA study) |
| **Chunking** | **cAST** (Carnegie Mellon 2025): AST-aligned chunking at function/class/type boundaries | +4.3 Recall@5 on RepoEval, +2.67 Pass@1 on SWE-bench (vs fixed-size); never splits mid-function; merges sibling nodes; supports all Tree-sitter languages |
| **Vector DB** | LanceDB (embedded, zero-config) for dev → Qdrant for production | LanceDB is in-process, zero-ops, columnar — ideal for code indexing where you want fast local iteration; Qdrant for multi-user production |
| **Graph DB** | Neo4j (call graph + dependency graph) | Bidirectional traversal (callers + callees); Cypher queries for relationship exploration; DKB reference architecture: deterministic AST-derived graph outperforms LLM-generated graphs (15/15 correct vs vector-only failures on multi-hop code queries) |
| **Keyword Search** | BM25 via MiniSearch (in-process) or Elasticsearch | Code has exact identifiers that embeddings miss; BM25 catches `getUserById`, `UserRepository`, `JWT_EXPIRY_MS` with zero false negatives |
| **Hybrid Fusion** | RRF (k=60) + Graph-Augmented Slot Reservation | Standard RRF + reserve slots for graph-expanded chunks (code-rag pattern: detect direction ("what calls X"), partition graph chunks out of reranker entirely; soft-reserve for ambiguous direction) |
| **Comparison Handler** | Per-comparator decomposition (regex → sub-searches → RRF fusion) | "Compare ProjectA's auth with ProjectB's auth" → decompose into 2 sub-searches ("ProjectA auth" + "ProjectB auth") → per-comparator vector search → vote-based dominant-project filter → RRF fusion |
| **LLM** | Claude Sonnet 3.5 (best for code understanding) or DeepSeek-Coder-V2 | Claude Sonnet leads SWE-bench; DeepSeek-Coder open-source alternative; both support 100K+ context for large context windows with retrieved code |
| **MCP Server** | 6 tools: `search_codebase`, `find_symbol`, `get_callers`, `get_callees`, `analyze_impact`, `get_overview` | Model Context Protocol enables integration with Claude Desktop, Cursor, OpenCode, and other MCP clients; code RAG becomes a tool any agent can call |

#### Why These Choices

cAST chunking is the single most important code-specific decision. Fixed-size chunking that splits `def process_order(` from its body destroys retrieval signal. cAST (CMU, EMNLP 2025) preserves syntactic boundaries, resulting in +4.3 Recall@5 and +2.67 Pass@1 over line-based chunking. Every production code RAG system (nexu, CodeRAG, codebase-expert) implements AST-aligned chunking.

**Deterministic AST-derived graphs (DKB) over LLM-generated graphs**: arXiv 2601.08773 compared vector-only RAG, LLM-generated knowledge graphs (LLM-KB), and deterministic AST-derived graphs (DKB) for codebase QA. DKB achieved 15/15 correct answers with 22s build time vs LLM-KB's 215s build time. LLM-generated graphs are slower to build and no more accurate. Tree-sitter guarantees correct call edges; LLMs hallucinate relationships.

Code-specific embeddings are non-negotiable: generic text embeddings fail on code because `process_order` and `handle_request` look similar in vector space but are different functions. Voyage-code-3 is purpose-trained for code retrieval and dominates the CoIR (Code Information Retrieval) benchmark.

Intent classifier with per-pattern retrieval: code queries fall into distinct patterns — semantic ("how is auth implemented?"), relationship ("what calls `sendEmail`?"), comparison ("diff between v1 and v2 auth"), symbol lookup ("find `UserService`"). Each needs a different retrieval strategy. Graph-augmented retrieval for relationship queries; per-comparator decomposition for comparisons; keyword-forward for symbol lookups.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: AST Parsing + Basic Retrieval** | Month 1 | Tree-sitter integration for 3 languages (Python, TS, Rust); cAST chunking; Voyage-code-3 embeddings; LanceDB local vector store; BM25 MiniSearch; basic semantic search |
| **Phase 2: Graph Intelligence** | Month 2 | Call graph extraction (3-tier resolver: same-file → import-based → global); Neo4j for graph storage; bidirectional traversal; Graph-augmented retrieval (merge graph chunks, direction detection) |
| **Phase 3: Advanced Query Patterns** | Month 3 | Intent classifier; per-pattern retrieval strategies; comparison query decomposition; MCP server (6 tools); incremental indexing (Git diff → SHA-256 → selective re-index) |
| **Phase 4: Production Scale** | Month 4–5 | Qdrant migration for multi-user; cross-encoder reranker; Claude Sonnet generation; MCP integration testing with Claude Code/Cursor; eval suite with SWE-bench and RepoEval; CI/CD integration (pre-commit indexing check) |

#### Estimated Monthly Cost at Scale

| Scale | Repos | Languages | Developers | Queries/Day | Monthly Cost |
|-------|-------|-----------|------------|-------------|--------------|
| **Single Team** | 5–10 | 3–4 | 15 | 500 | **$300–600** |
| **Engineering Org** | 50–100 | 6–8 | 200 | 5,000 | **$2,500–5,000** |
| **Enterprise** | 500+ | 10+ | 2,000+ | 50,000 | **$20,000–40,000** |

*Dominated by embedding cost (Voyage-code-3 at $0.12/1M tokens) and LLM generation (code answers are often longer, 500–1,500 tokens). Graph DB (Neo4j) adds $100–500/mo. Indexing is O(repos × files) but incremental re-indexing keeps ongoing cost low. Open-source alternative with CodeBERT + DeepSeek-Coder cuts costs by 70%+.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Tree-sitter grammar gaps** | Medium | Tree-sitter covers 40+ languages but edge cases exist; fallback to recursive text chunking for unsupported languages; contribute grammar fixes upstream |
| **Large repo indexing time** | Medium | Incremental indexing with SHA-256 checks; only re-process changed files; initial full index for 500K-line monorepo: ~5 minutes (code-rag V1.3 benchmark) |
| **Stale call graphs** | Medium | Rebuild graph edges on incremental index; Git post-commit hook triggers re-index; full graph rebuild scheduled nightly; graph freshness SLA: <5 minutes from merge |
| **Code-specific embedding quality on niche languages** | Low | Voyage-code-3 covers 10+ languages; fallback to CodeBERT which can handle any Tree-sitter-supported language through code tokenization |
| **Token budget explosion** | High | Graph expansion can add 2-10× more chunks; hard cap at 8K tokens total context; LLM reranker drops low-relevance chunks to stay within budget; nexu achieves 5–10K tokens of highly relevant context (vs 200K+ of noise) |

---

### 10.7 Research-Paper QA — Scientific Literature, Citation Graphs, Structured Paper Data

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   RESEARCH-PAPER QA RAG STACK                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     PAPER INGESTION PIPELINE                       │    │
│  │                                                                     │    │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐     │    │
│  │  │ arXiv    │  │ PubMed    │  │ Semantic │  │ Google        │     │    │
│  │  │ API      │  │ API       │  │ Scholar  │  │ Scholar API   │     │    │
│  │  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └──────┬───────┘     │    │
│  │       └──────────────┴─────────────┴───────────────┘              │    │
│  │                              │                                     │    │
│  │                    ┌─────────▼─────────┐                           │    │
│  │                    │  Unified Paper    │                           │    │
│  │                    │  Model (JSON)     │                           │    │
│  │                    │  - Title          │                           │    │
│  │                    │  - Authors+affil  │                           │    │
│  │                    │  - Abstract       │                           │    │
│  │                    │  - Full text (PDF │                           │    │
│  │                    │    → Grobid/Marker│                           │    │
│  │                    │    → structured)  │                           │    │
│  │                    │  - Sections       │                           │    │
│  │                    │  - Figures/tables │                           │    │
│  │                    │  - References     │                           │    │
│  │                    │  - DOI            │                           │    │
│  │                    └─────────┬─────────┘                           │    │
│  └──────────────────────────────┼────────────────────────────────────┘    │
│                                 │                                         │
│  ┌──────────────────────────────▼────────────────────────────────────┐    │
│  │                     DUAL KNOWLEDGE REPRESENTATION                   │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────┐  ┌─────────────────────────────┐ │    │
│  │  │   CITATION GRAPH (Neo4j)    │  │   VECTOR STORE (Qdrant)     │ │    │
│  │  │                             │  │                             │ │    │
│  │  │  Nodes: Papers, Authors,    │  │  Chunked paper sections     │ │    │
│  │  │          Venues, Methods,   │  │  (Abstract, Intro, Methods, │ │    │
│  │  │          Domains            │  │   Results, Discussion)      │ │    │
│  │  │                             │  │                             │ │    │
│  │  │  Edges: CITES, AUTHORED_BY, │  │  Per-section embeddings     │ │    │
│  │  │         PUBLISHED_IN,       │  │  (voyage-3-large, 1024d)   │ │    │
│  │  │         USES_METHOD,        │  │                             │ │    │
│  │  │         BELONGS_TO_DOMAIN   │  │  + Author name embeddings   │ │    │
│  │  │                             │  │  + Method name embeddings   │ │    │
│  │  │  Citation resolution via    │  │                             │    │
│  │  │  OpenAlex / Semantic Scholar│  │                             │    │
│  │  └──────────────┬──────────────┘  └──────────────┬──────────────┘ │    │
│  │                 │                                │                 │    │
│  └─────────────────┼────────────────────────────────┼─────────────────┘    │
│                    │                                │                      │
│  ┌─────────────────▼────────────────────────────────▼─────────────────┐    │
│  │                     RETRIEVAL ENGINE                                  │    │
│  │                                                                       │    │
│  │  Query ──▶ ┌──────────────┐                                          │    │
│  │           │ Query Router  │                                          │    │
│  │           │ (Classifier:  │                                          │    │
│  │           │  survey,      │                                          │    │
│  │           │  comparison,  │                                          │    │
│  │           │  methodology, │                                          │    │
│  │           │  factoid)     │                                          │    │
│  │           └──────┬───────┘                                          │    │
│  │                  │                                                   │    │
│  │     ┌────────────┼────────────────┬───────────────┐                 │    │
│  │     ▼            ▼                ▼               ▼                 │    │
│  │  Survey     Comparison       Methodology       Factoid              │    │
│  │  (GraphRAG  (per-paper       (section-         (vector              │    │
│  │   traversal decomposition    targeted          search +             │    │
│  │   + LeSeGR)  + graph-        vector search)    reranker)            │    │
│  │              enriched RRF)                                           │    │
│  │     │            │                │               │                 │    │
│  │     └────────────┼────────────────┼───────────────┘                 │    │
│  │                  ▼                ▼                                 │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  SciRAG Retrieval Pipeline                                     │  │    │
│  │  │                                                               │  │    │
│  │  │  1. Lexical-Semantic Graph Retrieval (LeSeGR)                 │  │    │
│  │  │     - Sparse + dense signals convolved over citation graph    │  │    │
│  │  │     - Neighbor-aware: paper + cited/citing papers scored      │  │    │
│  │  │     - jointly, not independently                              │  │    │
│  │  │                                                               │  │    │
│  │  │  2. Graph Traversal (forward/backward citation paths)         │  │    │
│  │  │     - "What built on paper X?" → forward citation traversal   │  │    │
│  │  │     - "What is the foundation of method Y?" → backward path   │  │    │
│  │  │                                                               │  │    │
│  │  │  3. Citation-Aware Reranking                                  │  │    │
│  │  │     - Boost papers cited by many hits + authoritative venues │  │    │
│  │  │     - Penalize retracted papers + low-citation outliers       │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                     OUTLINE-GUIDED SYNTHESIS                       │    │
│  │                                                                     │    │
│  │  ┌────────────────────────────────────────────────────────────┐   │    │
│  │  │  SciRAG Synthesis: Plan → Search → Critique → Refine         │   │    │
│  │  │                                                              │   │    │
│  │  │  1. PLANNER: Generate answer outline (3-7 section headings) │   │    │
│  │  │  2. RESEARCHER: For each section, retrieve + synthesize     │   │    │
│  │  │  3. CRITIC: Verify every claim against cited sources;        │   │    │
│  │  │     flag unsubstantiated statements                          │   │    │
│  │  │  4. WRITER: Compose final answer with inline citations       │   │    │
│  │  │     ([Author, Year]; clickable DOI links)                    │   │    │
│  │  └────────────────────────────────────────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  EVALUATION: QASA, ScholarQA benchmarks; faithfulness per section;│    │
│  │  citation accuracy (% of claims traceable to source); coverage     │    │
│  │  (fraction of relevant literature retrieved); recency weighting    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | Custom pipeline (SciRAG-inspired) + LlamaIndex for ingestion | SciRAG is the state-of-the-art framework for scientific literature QA; outline-guided synthesis + citation-aware reasoning; LlamaIndex for the 150+ document connectors |
| **PDF Extraction** | Grobid (ML-based structured extraction) + Marker (PDF→MD) | Grobid extracts structured paper metadata (sections, references, figures, tables) with 95%+ accuracy on academic PDFs; Marker for clean Markdown conversion |
| **Paper Metadata** | OpenAlex API + Semantic Scholar API | OpenAlex (free, open) for citation graph resolution, author disambiguation, venue metadata; Semantic Scholar for citation intent classification and influential citation scoring |
| **Citation Graph** | Neo4j (property graph) | Cypher enables expressive traversal queries ("papers citing X that also cite Y"); graph algorithms (PageRank for authority, community detection for topic clusters); production-proven in Microsoft GraphRAG, LitFM, CG-RAG |
| **Embedding** | `voyage-3-large` (1024d) or `SPECTER2` (self-hosted, sci-specific) | Voyage for managed; SPECTER2 (Allen AI) for academic-domain embeddings trained on citation graph structure — captures paper-level relatedness better than generic models |
| **Vector DB** | Qdrant (per-section collections) | Section-level indexing (abstract, methods, results, discussion stored separately) enables targeted retrieval ("what methods did they use?" → methods section only) |
| **Lexical Retrieval** | BM25 via Elasticsearch (scientific term boosting) | Academic terminology exact match (gene names, chemical compounds, mathematical notation); domain-specific stopword lists |
| **Graph Retrieval** | LeSeGR (Lexical-Semantic Graph Retrieval) | CG-RAG paper's method: convolves sparse + dense signals over citation graph topology; neighbor-aware scoring (paper relevance depends on cited/citing papers); 28.1% precision improvement over baseline |
| **Reranker** | Cohere Rerank 3.5 + Citation Graph Boost | Standard cross-encoder + boost papers with high citation count in authoritative venues + penalty for retracted/low-quality sources |
| **LLM** | Claude Sonnet 3.5 (200K context, best for long-form synthesis) or GPT-4o (broad knowledge) | 200K context handles 30+ paper synthesis; Claude's extended thinking mode improves multi-paper reasoning |
| **Synthesis** | SciRAG outline-guided: Planner → Researcher → Critic → Writer | Four-agent pipeline; critic verifies factual alignment; outlines ensure coherent structure (vs flat RAG which produces fragmented answers) |

#### Why These Choices

**Citation graph is not optional** — it's the fundamental structure of scientific knowledge. CG-RAG demonstrated that flat RAG (vector similarity alone) misses papers that are citation-connected but semantically distant. LeSeGR (Lexical-Semantic Graph Retrieval) integrates sparse (lexical) and dense (semantic) signals within the graph topology, achieving 28.1% precision improvement on retrieval tasks over state-of-the-art baselines.

**Section-level indexing** because researcher queries target specific paper sections: "what methods were used?" → methods section, "what were the main findings?" → results/discussion. Indexing the entire paper as one chunk dilutes signal.

**SciRAG's outline-guided synthesis** (Planner → Researcher → Critic → Writer) produces ~29% more relevant and ~36% more readable answers than flat RAG (StructRAG paper, UTS 2025). It mirrors how humans write literature reviews: plan the structure, gather per-section evidence, verify, compose.

**SPECTER2 embeddings** trained specifically on academic citation graphs capture paper-to-paper relatedness better than generic models. If using managed services, `voyage-3-large` is the best general-purpose alternative.

**OpenAlex over proprietary APIs**: Free, open-access, covers 250M+ scholarly works, resolves citations and author identities. Avoids vendor lock-in and paywalls.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: Paper Ingestion** | Month 1–2 | Grobid + Marker PDF pipeline; OpenAlex metadata enrichment; paper JSON schema; Qdrant per-section collections; SPECTER2 embeddings; basic vector search |
| **Phase 2: Citation Graph** | Month 2–3 | Neo4j citation graph; OpenAlex citation resolution; PageRank/community detection; forward/backward traversal; graph-boosted reranking; CG-RAG LeSeGR implementation |
| **Phase 3: Advanced Retrieval** | Month 3–4 | Query router (survey/comparison/methodology/factoid); per-strategy retrieval with graph enrichment; citation-aware reranking with authority boost and retraction filter |
| **Phase 4: Synthesis Engine** | Month 4–5 | SciRAG outline-guided synthesis (Planner → Researcher → Critic → Writer); inline citation validation; DOI linking; structured output (Markdown + JSON with evidence mapping) |
| **Phase 5: Scale & Quality** | Month 5–6 | Multi-corpus support (arXiv, PubMed, SSRN, etc.); nightly re-index of new papers; QASA/ScholarQA eval benchmarks; recency weighting; user feedback integration |

#### Estimated Monthly Cost at Scale

| Scale | Papers Indexed | Queries/Day | Monthly Cost |
|-------|---------------|-------------|--------------|
| **Lab/Team** | 10K | 100 | **$500–1,000** |
| **Department** | 100K | 500 | **$2,000–4,000** |
| **University/Institute** | 1M | 2,000 | **$8,000–15,000** |
| **Research Platform** | 10M+ | 20,000 | **$40,000–80,000** |

*Includes Neo4j ($100–2,000/mo), embedding costs for paper corpus (one-time: $500–$10K depending on scale), LLM synthesis cost (dominant at scale — literature reviews are long: 2,000–5,000 output tokens per query), and GPU for SPECTER2 embeddings. OpenAlex API is free. Grobid is open-source.*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Citation graph completeness** | High | OpenAlex covers 250M+ works but has gaps; supplement with Semantic Scholar and CrossRef; mark papers with missing citation data clearly in responses |
| **Paper access restrictions** | High | Most papers are behind paywalls; only index open-access + preprint versions initially; integrate institutional SSO for paywalled access; clearly label which conclusions are based on abstract-only vs full-text |
| **Outdated/retracted papers** | Medium | Nightly retraction watch (CrossRef Retraction Database); recency weighting in retrieval (boost papers from last 3 years); display retraction warnings prominently; OpenAlex flags retractions |
| **Hallucinated citations** | Critical | SciRAG Critic agent verifies every citation against Neo4j graph; DOI validation before inclusion; post-generation citation audit (check that each [Author, Year] exists in graph) |
| **Multi-paper synthesis coherence** | Medium | Outline-guided synthesis prevents the "disconnected fact dump" problem; human evaluation of synthesis quality; iterate on Planner prompt with domain expert feedback |

---

### 10.8 ERM + ARAG Production System — Explicit Relevance Modeling with Adaptive Retrieval

#### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                ERM + ARAG PRODUCTION SYSTEM                                  │
│        (Explicit Relevance Modeling + Adaptive Retrieval-Augmented Gen)     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                ADAPTIVE RETRIEVAL DECISION ENGINE                   │    │
│  │                                                                     │    │
│  │  User Query                                                        │    │
│  │     │                                                               │    │
│  │     ▼                                                               │    │
│  │  ┌──────────────────────────────────────────────────────────────┐ │    │
│  │  │  CTRLA: Inherent Control-Based ARAG                           │ │    │
│  │  │                                                               │ │    │
│  │  │  1. Extract honesty-direction features from LLM embeddings   │ │    │
│  │  │  2. Extract confidence-direction features                     │ │    │
│  │  │  3. If model is UNCONFIDENT (low internal knowledge)         │ │    │
│  │  │     → TRIGGER RETRIEVAL                                       │ │    │
│  │  │  4. If model is CONFIDENT (sufficient internal knowledge)    │ │    │
│  │  │     → SKIP RETRIEVAL (generate directly)                      │ │    │
│  │  │  5. Apply honesty steering: suppress overconfident             │ │    │
│  │  │     completions on uncertain topics                           │ │    │
│  │  └──────────────────────────┬───────────────────────────────────┘ │    │
│  │                             │                                      │    │
│  │              ┌──────────────▼──────────────┐                      │    │
│  │              │  RETRIEVAL NEEDED?           │                      │    │
│  │              │  Yes → Execute Retrieval     │                      │    │
│  │              │  No  → Generate Directly     │                      │    │
│  │              └──────────────┬──────────────┘                      │    │
│  └─────────────────────────────┼──────────────────────────────────────┘    │
│                                 │                                           │
│  ┌──────────────────────────────▼──────────────────────────────────────┐    │
│  │                EXPLICIT RELEVANCE MODELING (ERM)                       │    │
│  │                                                                        │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │  Retrieval Phase: Semantic Alignment                              │ │    │
│  │  │                                                                  │ │    │
│  │  │  Query q ──▶ Bi-encoder (e_q) ◀── cos(e_q, e_d) ──▶ Docs D     │ │    │
│  │  │                                                                  │ │    │
│  │  │  Relevance score: R(q,d) = α·cos(e_q, e_d)                       │ │    │
│  │  │                          + β·BM25(q,d)                            │ │    │
│  │  │                          + γ·UserBehaviorBoost(q,d)               │ │    │
│  │  │                          + δ·FreshnessDecay(d,timestamp)          │ │    │
│  │  │                                                                  │ │    │
│  │  │  Only docs with R(q,d) > θ_retrieval enter candidate pool        │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  │                                                                        │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │    │
│  │  │  Reranking Phase: Listwise Relevance Scoring                      │ │    │
│  │  │                                                                  │ │    │
│  │  │  AdaRankLLM: Zero-shot listwise prompt + Passage Dropout         │ │    │
│  │  │                                                                  │ │    │
│  │  │  1. Feed top-K candidates as a ranked list to LLM                │ │    │
│  │  │  2. LLM outputs ranking + relevance justification per doc        │ │    │
│  │  │  3. Passage Dropout mechanism: LLM explicitly DROPS              │ │    │
│  │  │     irrelevant passages (outputs TERMINATE token)                 │ │    │
│  │  │  4. Output: filtered, ranked candidate set A ⊂ P                 │ │    │
│  │  │                                                                  │ │    │
│  │  │  + ProRBP: User behavior neighbors retrieved from search logs    │ │    │
│  │  │    to provide implicit relevance signals for the LLM judge       │ │    │
│  │  └─────────────────────────────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                EVIDENCE-CONSTRAINED GENERATION                     │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐    │    │
│  │  │  Unified Semantic Space Generation:                         │    │    │
│  │  │                                                            │    │    │
│  │  │  P(token_t | context, evidence) =                           │    │    │
│  │  │    softmax( W·h_t + λ·R(q, e_t) )                          │    │    │
│  │  │                                                            │    │    │
│  │  │  Where:                                                     │    │    │
│  │  │  - h_t = standard LLM hidden state                         │    │    │
│  │  │  - R(q, e_t) = relevance alignment score between            │    │    │
│  │  │    query and evidence segment being referenced              │    │    │
│  │  │  - λ = evidence constraint strength (tunable)               │    │    │
│  │  │                                                            │    │    │
│  │  │  This ensures: Every generated token is explicitly          │    │    │
│  │  │  constrained by evidence relevance — not just prompted      │    │    │
│  │  └───────────────────────────────────────────────────────────┘    │    │
│  │                                                                     │    │
│  │  ┌───────────────────────────────────────────────────────────┐    │    │
│  │  │  Citation-Verified Output:                                   │    │    │
│  │  │  - Each sentence tagged with source document + chunk ID     │    │    │
│  │  │  - Relevance score displayed per source                     │    │    │
│  │  │  - No unsupported claim survives generation                  │    │    │
│  │  └───────────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │                CONTINUOUS FEEDBACK LOOP (DMA)                      │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────┐     │    │
│  │  │  Dynamic Memory Alignment (DMA)                             │     │    │
│  │  │                                                             │     │    │
│  │  │  User Feedback → 3 Levels:                                  │     │    │
│  │  │  ┌──────────────┐  ┌───────────────┐  ┌───────────────┐   │     │    │
│  │  │  │ Document     │  │ List-Level    │  │ Response-Level│   │     │    │
│  │  │  │ Preference   │  │ Ranking       │  │ Preference    │   │     │    │
│  │  │  │ "doc A was   │  │ "ordering was │  │ "answer B     │   │     │    │
│  │  │  │  irrelevant" │  │  wrong"       │  │  better than  │   │     │    │
│  │  │  │              │  │               │  │  answer A"    │   │     │    │
│  │  │  └──────┬───────┘  └───────┬───────┘  └───────┬───────┘   │     │    │
│  │  │         └──────────────────┼──────────────────┘            │     │    │
│  │  │                            ▼                               │     │    │
│  │  │  ┌─────────────────────────────────────────────────────┐  │     │    │
│  │  │  │  Online Learning:                                     │  │     │    │
│  │  │  │  - Update similarity thresholds (θ_retrieval)         │  │     │    │
│  │  │  │  - Adjust RRF fusion weights (α, β, γ, δ)            │  │     │    │
│  │  │  │  - Tune evidence constraint strength (λ)             │  │     │    │
│  │  │  │  - Refine confidence threshold for ARAG trigger      │  │     │    │
│  │  │  │  - All updated via PPO (Proximal Policy Optimization)│  │     │    │
│  │  │  │    on user preference signals                         │  │     │    │
│  │  │  └─────────────────────────────────────────────────────┘  │     │    │
│  │  └──────────────────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Component Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **ARAG Decision** | **CTRLA** (Inherent Control-based Adaptive RAG) | Determines retrieval necessity by inspecting LLM embedding-space features (honesty + confidence directions); no separate classifier model; plug-and-play with any LLM; proven superior to statistical-uncertainty methods (ACL 2025 Findings) |
| **Retrieval Relevance** | Unified semantic alignment: `R(q,d) = α·cos + β·BM25 + γ·Behavior + δ·Freshness` | Multi-signal explicit relevance scoring; user behavior signal from search logs (ProRBP, Alipay production); temporal decay for freshness; all weights tunable via DMA feedback loop |
| **Embedding** | `text-embedding-3-large` (3072d) → quantized to binary | Higher dimensionality captures finer relevance distinctions; binary quantization reduces storage 32× while preserving 95%+ of ranking quality |
| **Vector DB** | Qdrant (binary quantization support) | Supports binary vectors natively; stores relevance metadata as payload; enables metadata-filtered retrieval with joint relevance scoring |
| **Reranker** | **AdaRankLLM**: Zero-shot listwise LLM reranker + Passage Dropout | Listwise ranking captures inter-document relationships (unlike pointwise cross-encoders); passage dropout mechanism explicitly identifies and discards irrelevant passages; achieves optimal performance with significantly reduced context overhead (AdaRankLLM, arXiv 2026) |
| **User Behavior** | ProRBP: Retrieved behavior neighbors from search logs | Identifies implicit relevance signals from user interaction patterns (clicks, dwell time, reformulations); provides domain-specific knowledge in real-time (deployed in Alipay search at scale) |
| **LLM** | GPT-4o / Claude Sonnet 3.5 | Strong listwise ranking capability; structured output for passage dropout; 200K context for processing large candidate sets |
| **Feedback Learning** | DMA (Dynamic Memory Alignment): PPO-based online learning | 3-level feedback (document, list, response); online adaptation without retraining; modulates retrieval weights, evidence constraint strength, and ARAG confidence threshold continuously |
| **Evidence Constraint** | Explicit evidence constraint in generation logits: `P(token) = softmax(W·h_t + λ·R(q, e_t))` | Transforms evidence from implicit context into core control factor; restricts expression scope to retrieved evidence; prevents hallucination by mathematical constraint, not just prompting |
| **Observability** | Per-query relevance scores; ARAG trigger rate; evidence constraint activation; user satisfaction (implicit + explicit feedback); weight drift alerts |

#### Why These Choices

ERM + ARAG is the frontier of production RAG — it addresses the two fundamental limitations of standard RAG: (1) **retrieving when the model already knows the answer** (wastes context, adds latency, can introduce noise), and (2) **retrieving irrelevant content and treating it as equally authoritative** (causes hallucinations).

**CTRLA** for adaptive retrieval because it's representation-based rather than classifier-based. It extracts honesty and confidence directions from the LLM's own embedding space — no separate model to train, no additional inference step. This is plug-and-play with any LLM and more efficient than prompting-based ARAG methods.

**AdaRankLLM** for reranking because it solves two problems simultaneously: ordering (which documents are most relevant?) and filtering (which documents are irrelevant and should be dropped entirely?). The Passage Dropout mechanism lets the LLM explicitly discard passages, reducing noise and context overhead. On 3 datasets across 8 LLMs, AdaRankLLM achieved optimal performance with reduced context.

**DMA (Dynamic Memory Alignment)** for the continuous feedback loop because it's the only framework that operates at 3 feedback levels simultaneously (document, list, response) and uses PPO to co-adapt retrieval and generation during deployment. This means the system gets better over time from user interactions, not just periodic retraining.

**Evidence-constrained generation** (unified semantic space logit modulation) because prompting alone is insufficient — LLMs can ignore instructions. By mathematically constraining token probabilities with relevance scores, the model cannot generate claims unsupported by evidence. This is the strongest anti-hallucination mechanism available in 2026.

#### Implementation Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|--------------|
| **Phase 1: ERM Foundation** | Month 1–2 | Multi-signal relevance scoring (cos + BM25 + freshness); Qdrant with binary quantization; basic listwise LLM reranker; relevance score logging per query |
| **Phase 2: ARAG Integration** | Month 2–3 | CTRLA honesty/confidence extraction; retrieval trigger decision; A/B test ARAG vs always-retrieve on accuracy and latency; calibrate confidence threshold on 1,000-query eval set |
| **Phase 3: Advanced Reranking** | Month 3–4 | AdaRankLLM with Passage Dropout; ProRBP user behavior signal integration (requires search log pipeline); listwise scoring with inter-document relationship modeling |
| **Phase 4: Evidence Constraints** | Month 4–5 | Evidence-constrained generation (logit modulation); deterministic citation verification; λ tuning per query type; hallucination rate measurement (pre/post λ enforcement) |
| **Phase 5: Online Learning** | Month 5–7 | DMA 3-level feedback collection pipeline; PPO-based weight tuning; A/B test online-adapted weights vs static weights; safety guardrails on weight drift; automated rollback on regression |
| **Phase 6: Production Deploy** | Month 7–8 | Canary deployment (5%→25%→100%); per-query cost model (ARAG skip savings vs ARAG false-skip costs); latency SLOs with and without retrieval; continuous monitoring dashboard |

#### Estimated Monthly Cost at Scale

| Scale | Queries/Day | ARAG Skip Rate | Retrieval Cost | LLM Cost | Total Monthly |
|-------|-------------|----------------|----------------|----------|---------------|
| **Startup** | 5,000 | 35% | $150 (65% retrieved) | $500 | **~$800** |
| **Mid** | 50,000 | 40% | $1,200 | $4,500 | **~$6,500** |
| **Enterprise** | 500,000 | 45% | $8,000 | $35,000 | **~$50,000** |

*ARAG skip rate (percentage of queries answered without retrieval) is the primary cost lever. Each 10% increase in skip rate saves ~$0.0002/query in retrieval cost and ~50ms in latency. CTRLA typically achieves 35–45% skip rates with <1% accuracy degradation. AdaRankLLM passage dropout reduces context tokens by 20–35%, proportionally reducing LLM cost. DMA online learning adds negligible inference cost (<1% overhead).*

#### Key Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **ARAG false negatives** (should retrieve but doesn't) | High | Conservative confidence threshold initially (lower skip rate, higher accuracy); stochastic retrieval (even when confident, retrieve with p=0.05 for monitoring); alert when ARAG-skipped queries show >2% accuracy regression vs always-retrieve |
| **Relevance scoring miscalibration** | Medium | Multi-signal scoring with tunable weights prevents single-signal dominance; nightly offline eval against human-labeled relevance judgments (nDCG@10); DMA weight drift alerts trigger manual review |
| **Evidence constraint too aggressive** (λ too high) | Medium | Start with λ=0.1, increment 0.05/week; monitor fluency metrics alongside hallucination rate; A/B test evidence-constrained vs unconstrained generation |
| **Online learning instability** | High | PPO with conservative clipping; shadow mode for 2 weeks before activating; automated rollback on >5% user satisfaction drop; maximum weight change per update bounded at ±10% |
| **User behavior signal noise** | High | ProRBP filters behavior to "relevant neighbors" only (high dwell time + no immediate reformulation); require minimum 10 interactions before behavior signal activates; behavior signal weighted at γ ≤ 0.15 in relevance scoring |

---

### 10.9 Recommended All-Around Production Stack

**If you can only build one stack** — and you need it to work across the broadest range of use cases with the best quality/cost ratio — this is the 2026 consensus architecture:

```
QUERY → Router (simple/agentic) → Query Rewriting → Hybrid RRF
→ Cross-Encoder Rerank → LLM-as-Judge Top-5 Validation
→ Semantic Cache Check → Generation → Citation Verification → Response
                    ↕
              Neo4j GraphRAG (multi-hop queries)
```

**Component recommendations:**

| Layer | Baseline (Managed) | Self-Hosted Alternative |
|-------|-------------------|------------------------|
| **Framework** | LlamaIndex (ingestion + retrieval) + LangGraph (agentic routing) | LlamaIndex + LangGraph (same, both are open-source) |
| **Embedding** | `voyage-3-large` (1024d) | `BGE-M3` (1024d, vLLM) |
| **Vector DB** | Pinecone Serverless (<10M vectors) → Qdrant Cloud (>10M) | Qdrant (self-hosted) |
| **BM25 / Metadata** | PostgreSQL + pgvector | PostgreSQL + pgvector |
| **Reranker** | Cohere Rerank 3.5 | BGE-Reranker-v2-m3 (ONNX) |
| **GraphRAG** | Neo4j AuraDB (managed) | Neo4j Community Edition |
| **LLM (simple)** | GPT-4o-mini | qwen2.5:14b (Ollama) |
| **LLM (complex/agentic)** | Claude Sonnet 3.5 | Llama 3.1 70B (vLLM) |
| **Cache** | Redis Cloud | Redis (self-hosted) |
| **Eval** | RAGAS + LangSmith | RAGAS + custom harness |
| **Observability** | OpenTelemetry → Datadog/Grafana Cloud | OpenTelemetry → Grafana + Prometheus + Jaeger |

**Why this stack wins:**

1. **LlamaIndex + LangGraph** is the emerging consensus: LlamaIndex for retrieval primitives, LangGraph for agentic orchestration when needed. They compose cleanly.

2. **voyage-3-large + BGE-M3** is the embedding pair: managed when possible, self-hosted when required. Both are 1024d (sweet spot for storage/quality). Both support multilingual.

3. **Qdrant** is the best general-purpose vector DB in 2026: named vectors (dense+sparse in one entity), quantization, RRF built-in, Rust performance, Apache 2.0 license, and a managed cloud option.

4. **Hybrid RRF + Cross-Encoder Rerank + LLM-as-Judge Top-5** is the 3-stage retrieval pipeline that the field has converged on. Boundev hit 0.91 faithfulness. Nic Chin hit 96.8% answer correctness. Appycodes ships this across 4 products. It is the proven architecture.

5. **PostgreSQL is not optional** — you need a relational DB for metadata, ACL, audit trails, user accounts, and eval results. pgvector adds vector search as a bonus. The `tsvector` BM25 integration (Chanakya pattern) gives you lexical search without a second database.

6. **Semantic cache is the single highest-ROI feature** — 60–70% LLM cost reduction (Boundev, Appycodes). Implement it before worrying about model choice or chunking strategy.

---

### 10.10 Emerging Trends for 2027

Based on the trajectory visible in 2025–2026 research and deployments:

#### 1. RAG → Context Engineering (The Unifying Abstraction)

RAG is being absorbed into the broader discipline of **context engineering** — dynamically selecting, organizing, and optimizing ALL background information for the LLM, not just retrieved documents. This includes retrieved chunks, graph subgraphs, tool outputs, user history, system prompts, and conversation state. The 2027 RAG system will be a context orchestrator, not a retriever.

#### 2. Reinforcement Learning for Retrieval (RL-RAG)

The biggest technical shift underway: models that **learn when and how to retrieve through reinforcement learning** (GRPO, PPO), rather than following fixed retrieve-then-generate pipelines. DeepSeek-R1 demonstrated that RL-trained models can autonomously decide retrieval strategies. AgenticRAG-R1 and reasoning-RAG (RLVR for retrieval) are the frontier. By 2027, retrieval strategy will be learned, not configured.

#### 3. Late Interaction Retrieval (ColBERT-style at Scale)

Late interaction models (ColBERT, ColQwen, ColSmol) are becoming production-viable. They store per-token embeddings and compute query-document similarity via MaxSim rather than single-vector cosine. This closes the quality gap between bi-encoders and cross-encoders while keeping retrieval fast. Voyage, Cohere, and Jina all have late-interaction APIs in 2026. By 2027, late interaction will be the default retrieval mechanism for quality-sensitive applications.

#### 4. Unified Retrieval Engines (Vector DB 2.0)

Vector databases are becoming **unified retrieval engines** that handle dense, sparse, late-interaction, graph, and metadata-filtered search in a single query path. Vespa pioneered this architecture. Qdrant, Weaviate, and Elasticsearch are converging on it. By 2027, the "vector DB + BM25 index + graph DB + reranker service" split will collapse into a single serving layer — eliminating synchronization issues and network hops.

#### 5. Speculative / Predictive Retrieval

Instead of waiting for the user's query, the system predicts likely follow-up questions and runs retrieval in the background while the user reads the current response. This hides retrieval latency inside user think-time. Early systems (lookahead retrieval, speculative prefetching) are appearing. By 2027, conversational RAG will shift from reactive to predictive retrieval.

#### 6. GraphRAG as Reasoning Engine (Not Just Context Store)

GraphRAG is evolving from "retrieve a subgraph and stuff it into the prompt" to "reason over the graph structure as a computation layer." Systems like GRAG, GNN-RAG, and PathRAG use graph topology to improve multi-hop reasoning rather than relying on flat text similarity. By 2027, graph traversal will be exposed as a tool action that agents use to trace relationships — not just a pre-computed context expansion.

#### 7. MCP-Native RAG (Retrieval as Interoperable Tool)

The **Model Context Protocol (MCP)** is becoming the standard interface for exposing retrieval capabilities to AI agents. CodeRAG, nexu, Memex, AST-RAG, and Open Deep Wide Research all implement MCP servers. By 2027, "RAG as an MCP tool" will be the default integration pattern — any agent in any framework can call retrieval without custom integration.

#### 8. Streaming + Real-Time Ingestion

Batch ingestion is becoming legacy. Streaming RAG — where documents are ingested, chunked, embedded, and indexed within seconds of creation — is the new baseline. Redpanda/Kafka-based event-driven architectures (oldforks/distributed-rag-system) combined with incremental indexing (SHA-256 change detection) enable sub-minute freshness SLAs.

#### 9. Multimodal Retrieval (Text + Images + Tables + Audio)

Production systems (Chanakya, TechRAG) now treat images, tables, and audio as first-class retrieval units. Vision models extract content at index time. Late-interaction models (ColSmol, ColPali) enable visual document retrieval without OCR. By 2027, multimodal RAG will be table stakes.

#### 10. Cost-Aware Adaptive Routing

The hybrid router pattern (rules → simple → agentic) is being extended with **real-time cost modeling**. The system estimates the expected cost and quality of each path before executing, then selects the cheapest path that meets the quality threshold for that query. This is the natural evolution of ARAG (skip retrieval when confident) to full cost-aware routing across model tiers, retrieval strategies, and cache paths.

#### What to Act On Now

| Trend | Action in 2026 | Impact |
|-------|---------------|--------|
| Hybrid RRF + Rerank | Implement today | +15–20pp accuracy (proven) |
| Semantic Cache | Implement this week | 60–70% LLM cost reduction (proven) |
| Agentic Router (simple/agentic) | Add to roadmap for Q3 2026 | 40–70% cost reduction on agentic traffic |
| MCP Integration | Expose retrieval as MCP tools | Future-proofs your stack; zero marginal cost |
| Late Interaction Retrieval | Evaluate ColQwen/Voyage for top-20% hardest queries | 5–10pp quality on complex queries |
| GraphRAG (Neo4j) | Add Neo4j for multi-hop use cases only | ~10pp on cross-document reasoning |
| RL-RAG | Monitor but don't build yet | Will be built into frameworks by 2027 |
| Streaming Ingestion | Migrate from batch if freshness SLA <1 hour | Required for real-time use cases |

---

### References

1. Nic Chin, "RAG Architecture in Production: Building a 12-Component System at 96.8% Accuracy" (2026)
2. Boundev, "Production RAG Case Study: Shipped in 6 Days" (2026)
3. Appycodes, "Building a Production RAG Pipeline: Chunking, Embeddings, Retrieval, Caching" (2026)
4. Chanakya (Rishabh Jain), "Production RAG at Banking Scale" (2026)
5. Harvey, "Enterprise-Grade RAG Systems" (2025)
6. CG-RAG (Hu et al.), "Research Question Answering by Citation Graph Retrieval-Augmented LLMs" (2025)
7. SciRAG, "Adaptive, Citation-Aware, and Outline-Guided Retrieval and Synthesis for Scientific Literature" (2025)
8. Zhang et al., "cAST: Enhancing Code Retrieval-Augmented Generation with Structural Chunking via AST" (EMNLP 2025)
9. CodeRAG (KDEGroup), "Finding Relevant and Necessary Knowledge for Repository-Level Code Completion" (EMNLP 2025)
10. CTRLA, "Adaptive Retrieval-Augmented Generation via Inherent Control" (ACL 2025)
11. AdaRankLLM, "Rethinking the Necessity of Adaptive Retrieval-Augmented Generation" (2026)
12. DMA, "Dynamic Memory Alignment: Enhancing RAG with Adaptive Human Feedback" (2025)
13. XRAG, "Cross-lingual Retrieval-Augmented Generation" (EMNLP 2025)
14. CrossRAG, "Multilingual Retrieval-Augmented Generation for Knowledge-Intensive Tasks" (2025)
15. Google Research, "Agentic RAG for Gemini Enterprise" (2026)
16. MA-RAG, "Multi-Agent Retrieval-Augmented Generation via Collaborative Chain-of-Thought Reasoning" (2025)
17. Protocol-H, "Building Hierarchical Agentic RAG Systems" (InfoQ, 2026)
18. AgenticRAG, "Agentic Retrieval for Enterprise Knowledge Bases" (2025)
19. TechRAG, "Evidence-Gated Multimodal Agentic RAG for Technical Literature Reasoning" (2026)
20. GraphRAG Survey, "Retrieval-Augmented Generation with Graphs" (2025)
21. oldforks/distributed-rag-system, "Production-Grade RAG Platform" (GitHub, 2026)
22. Ozgur Guler, "10 RAG Shifts Redefining Production AI in 2026" (Microsoft Azure, 2026)
23. Wavenetic, "Private RAG Architecture: A Security-Boundary-First Reference Design" (2026)
24. AI Engineering Blueprint for On-Premises RAG Systems (ICSA 2026)
25. AICost.ai RAG Pipeline Cost Estimator (2026 rates)
26. ZTABS RAG Cost Estimator (2026 rates)
27. Framework comparisons: DeployBase (2025), 8tomic Labs (2025), BrLikhon (2026), Tredence (2026)
