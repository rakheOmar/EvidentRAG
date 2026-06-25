## 7. Vector Database Infrastructure

### Executive Summary

As of mid-2026, the vector database market has consolidated around eight principal options. Each occupies a distinct point on the spectrum from **embedded library** to **fully managed cloud service**, and from **minimal-ops simplicity** to **billion-scale distributed architecture**. The key insight from 2025–2026 benchmarks: **no single database dominates every dimension**. The right choice depends on your scale, latency budget, team's operational appetite, and whether vector search is primary or secondary to your workload.

---

### 7.1 Qdrant

#### 7.1.1 Architecture
- **Language**: Rust
- **Deployment**: Self-hosted (single binary, Docker/Kubernetes) or Qdrant Cloud (managed)
- **Type**: Server — dedicated vector similarity search engine
- **License**: Apache 2.0

#### 7.1.2 Index Types
- HNSW (primary, tunable via `m`, `ef_construct`, `ef_search`)
- Scalar Quantization (int8), Product Quantization (PQ), Binary Quantization (BQ) — all supported since v1.10+
- On-disk HNSW for large collections beyond RAM
- Sparse vector index (since v1.10)

#### 7.1.3 Hybrid Search
- Native hybrid since v1.10: dense + sparse (BM25-style keywords or learned sparse)
- Reciprocal Rank Fusion (RRF) and score-based blending
- Keyword + vector fusion in a single query with filtering

#### 7.1.4 Scaling
- **Single node sweet spot**: 1M–100M vectors
- **Cluster ceiling**: Billions with horizontal sharding
- **p99 latency at 100M vectors (768d)**: ~18.4ms (self-hosted, HNSW)
- **Linear scaling with sharding**; BQ reduces RAM by ~4× with minor recall loss
- At 500M vectors, p99 ~47ms

#### 7.1.5 Filtering
- **Payload indexing** — explicit indexes on JSON payload fields
- **Filterable HNSW**: Filters integrated into graph traversal (not post-processing), only 15–20% slower than unfiltered queries
- Supports complex conditions: date ranges, nested JSON, geo-queries, high-cardinality metadata
- Consistently benchmarks as best-in-class for filtered ANN search

#### 7.1.6 Strengths
- Lowest tail latency among open-source options (Rust core)
- Best filtered search performance in class
- Single-binary deployment — no external dependencies (cf. Milvus needs etcd, MinIO, Pulsar)
- Excellent memory efficiency (~40% less RAM than Milvus for equivalent recall)
- Strong quantization options reduce cost at scale
- Payload-based multi-tenancy trivial to implement
- Clean Python SDK, REST + gRPC APIs

#### 7.1.7 Weaknesses
- HNSW-only for dense vectors (no IVF, GPU)
- Smaller community than Milvus/Weaviate; fewer blog posts/tutorials
- No built-in embedding/vectorizer modules (bring your own embeddings)
- CPU-only query execution (GPU support only in Qdrant Cloud)
- Less mature multi-tenancy tooling vs. Weaviate's class architecture
- Single-node ceiling ~100M before sharding complexity kicks in

#### 7.1.8 Cost Model
| Tier | Cost |
|---|---|
| Open-source self-hosted | Free (Apache 2.0) |
| Qdrant Cloud free tier | 1GB cluster, free forever, no credit card |
| Qdrant Cloud paid | From ~$0.014/hr per node (~$10/mo base); ~$65/mo for typical cloud cluster |
| Self-hosted on VPS | ~$20–$50/month for moderate workloads |
| Self-hosted at 100M vectors | ~$280/month (EC2) |

#### 7.1.9 Production Adoption
- **Tripadvisor** — powers AI trip planner across 1B+ reviews, reports 2–3× revenue uplift
- **Deutsche Telekom** — multi-agent platform (LMOS), 2M+ conversations across 3 countries
- **Bazaarvoice** — 2.7B review vectors, 100× storage reduction vs. PostgreSQL
- **Flipkart** — real-time multimodal similarity search for Trust & Safety
- **Garden** — 200M+ patent corpus, 10× cost reduction vs. prior managed service
- **Alhena AI** — consolidated from FAISS + Pinecone + Weaviate onto Qdrant Cloud

#### 7.1.10 Best Use Cases
- Complex filtered vector search (e-commerce with category/price/availability filters)
- Latency-critical agent/RAG pipelines (sub-10ms p95 needed)
- Multi-tenant SaaS with per-tenant filtering
- Teams with container ops experience who want strong price-performance
- 1M–100M vector scale (sweet spot)

---

### 7.2 Weaviate

#### 7.2.1 Architecture
- **Language**: Go
- **Deployment**: Self-hosted (Docker/Kubernetes) or Weaviate Cloud (managed, shared + dedicated)
- **Type**: Server — schema-first vector + knowledge graph database
- **License**: BSD-3-Clause

#### 7.2.2 Index Types
- HNSW (primary, tunable `efConstruction`, `maxConnections`)
- Flat (brute-force) index for small collections
- PQ and BQ for vector compression
- No IVF or DiskANN

#### 7.2.3 Hybrid Search
- **Best-in-class hybrid search** — mature BM25 + dense vector fusion
- Built-in `hybrid` search operator (alpha-tunable weighting)
- Sparse + dense fusion natively supported
- RRF and linear combination ranking
- Knowledge graph layer adds entity-based relationships on top of vectors

#### 7.2.4 Scaling
- **Single node**: 1M–50M vectors comfortably
- **Cluster ceiling**: Hundreds of millions (latency degrades >200M without tuning)
- **p99 at 100M vectors**: ~31ms (self-hosted); degrades to ~89ms at 200M without tuning
- Memory-intensive — higher baseline than Qdrant (graph + schema + vectorizer overhead)
- Multi-node replication for HA since v1.18+

#### 7.2.5 Filtering
- `where` filter with GraphQL syntax — supports nested, boolean, date-range
- Filtering is post-ANN in many configurations; can produce empty results with restrictive filters
- Less efficient than Qdrant's filterable HNSW on highly selective filters
- Solid for moderate-selectivity filtering

#### 7.2.6 Strengths
- Most feature-rich hybrid search: BM25 + dense + knowledge graph
- Built-in vectorizer modules (`text2vec-openai`, `text2vec-cohere`, `text2vec-huggingface`, etc.) — no separate embedding pipeline needed
- GraphQL API (excellent for frontend teams) + REST + gRPC
- Strong multi-tenancy via class-based architecture
- Generative search module (RAG endpoints built-in)
- Good developer UX — schema-first with auto-schema from data
- Large community, most Docker pulls in vector DB category

#### 7.2.7 Weaknesses
- Higher memory baseline — needs 4GB+ minimum even for small workloads
- Higher per-vector storage cost at 1536-dim (due to dimension-based pricing on Cloud)
- No GPU query acceleration
- p99 latency lags Qdrant at >10M vectors
- Index build time slower than Qdrant and Milvus
- Filtered search less efficient than Qdrant's payload indexing
- BSL license on some enterprise features

#### 7.2.8 Cost Model
| Tier | Cost |
|---|---|
| Open-source self-hosted | Free (BSD-3) |
| Weaviate Cloud Sandbox | Free (14-day), 100K objects |
| Weaviate Cloud Flex | From $45/month (shared, HA, pay-as-you-go) |
| Weaviate Cloud Plus | From $280/month (dedicated available) |
| Weaviate Cloud Premium | From $400/month (dedicated, 99.95% SLA) |
| Cloud pricing dimensions | Vector dimensions × replication factor; ~$0.095/million dims/month; PQ reduces by ~4×, BQ by ~32× |
| Self-hosted on VPS | ~$25–$50/month |

#### 7.2.9 Production Adoption
- Used across e-commerce, legal tech, media, and enterprise knowledge management
- Strong adoption in European enterprises
- Popular with teams that want an all-in-one RAG stack (embedding + storage + retrieval + generation)
- Major cloud partnership with AWS, GCP, Azure

#### 7.2.10 Best Use Cases
- Hybrid search-first applications (legal search, technical docs, e-commerce where exact phrases matter)
- Teams that want built-in vectorization + RAG in one system
- Knowledge graph + vector hybrid use cases
- GraphQL-native frontend teams
- Moderate scale (1M–50M vectors) with rich schema requirements

---

### 7.3 Milvus

#### 7.3.1 Architecture
- **Language**: Go + C++
- **Deployment**: Self-hosted (requires Kubernetes + etcd + MinIO/S3 + Pulsar/Kafka) or Zilliz Cloud (fully managed)
- **Type**: Cloud-native distributed vector database — separates storage, compute, index, and coordinator nodes
- **License**: Apache 2.0

#### 7.3.2 Index Types
- **Most index types of any vector database**:
  - HNSW (graph-based, memory-resident)
  - IVF_FLAT, IVF_SQ8, IVF_PQ (clustering-based, memory-efficient)
  - DiskANN (disk-based, for very large collections)
  - ScaNN (Google's vector quantization)
  - GPU-accelerated index building (IVF_PQ, HNSW)
- Supports multiple indexes per collection, hot-swappable

#### 7.3.3 Hybrid Search
- Hybrid search since v2.4: full-text + vector
- Sparse + dense vector support
- Multi-vector support (store multiple embeddings per entity)
- Less mature hybrid UX than Weaviate, functional but requires more manual configuration

#### 7.3.4 Scaling
- **Designed for billions**: Proven at 10B+ vectors in production
- **Ingestion**: Up to 150K vectors/sec (2.5× faster than Weaviate, 1.8× faster than Qdrant)
- **Throughput**: 2,400–3,200 QPS with GPU-accelerated IVF_PQ (highest in class)
- **p99 at 100M**: ~25ms (HNSW), ~19ms (IVF_SQ8), ~62ms at 500M
- Cloud-native: horizontal scaling via separate compute/storage tiers
- Tiered storage: hot in-memory, warm on SSD, cold in object storage (S3/MinIO)
- GPU query acceleration available (Zilliz Cloud)

#### 7.3.5 Filtering
- Scalar filtering with bitmap indexes
- Attribute filtering support, but **filters applied as post-processing in many configurations** (40–60% slowdown vs. 15–20% in Qdrant)
- Efficient for broad filters; less so for highly selective ones
- Improvements in v2.5+ for filter pushdown

#### 7.3.6 Strengths
- Most comprehensive index type selection
- Highest ingestion throughput and bulk indexing speed
- GPU-accelerated index building (T4 GPU: 45 min → 3 min for 10M vectors)
- Proven at billion-vector scale in production (NAVER, Bosch, Uber, leboncoin)
- Strong consistency model (configurable)
- Rich ecosystem: Kafka, Spark, Flink integrations
- Active LF AI & Data foundation project (Linux Foundation)

#### 7.3.7 Weaknesses
- **Highest operational complexity** — requires Kubernetes + etcd + MinIO/S3 + Pulsar/Kafka for production
- Minimum viable deployment is heavy: ~$800/month on AWS for HA cluster
- Steep learning curve; "requires a PhD in distributed systems" for tuning
- 6+ GB RAM for standalone mode on 1M vectors (highest footprint)
- Filtered search performance lags Qdrant
- No built-in embedding generation (bring your own or use Zilliz functions)

#### 7.3.8 Cost Model
| Tier | Cost |
|---|---|
| Open-source self-hosted | Free (Apache 2.0) |
| Zilliz Cloud free tier | 5GB storage, 2.5M vCUs/month, up to 5 collections |
| Zilliz Cloud Serverless | From $4/million vCUs; ~$65–$89/month for moderate workloads |
| Zilliz Cloud Dedicated | From $126/GB/month (performance-optimized); as low as $5/million vectors/month (tiered-storage) |
| Zilliz Cloud Enterprise | From $197/month (99.95% SLA, SSO, RBAC, private networking) |
| Self-hosted at scale | ~$310/month for 100M vectors (EC2); ops cost significant |

Pricing restructured October 2025: storage costs reduced 87% ($0.30 → $0.04/GB/month), compute reduced 25%.

#### 7.3.9 Production Adoption
- **NAVER** — South Korea's largest search engine, multimodal search & recsys at billion-scale
- **Bosch** — autonomous driving corner-case retrieval, 80% cost reduction vs. external data collection
- **Uber** — 1.5B+ vector prototype on OpenSearch/Milvus hybrid architecture
- **Leboncoin** — 80M+ ads, visual similarity search, sub-200ms latency
- **Farfetch** — conversational AI product search, benchmarked Milvus as fastest vs. Weaviate, Qdrant, Pinecone
- 42K+ GitHub stars (highest in vector DB category)

#### 7.3.10 Best Use Cases
- Billion-scale vector search (genomics, large-scale recsys, enterprise semantic search over petabytes)
- High write-throughput workloads (real-time ingestion at 100K+ vectors/sec)
- Teams with dedicated MLOps/platform engineering capacity
- GPU-accelerated workloads for maximum throughput
- Multi-tenant, multi-collection deployments at enterprise scale

---

### 7.4 Pinecone

#### 7.4.1 Architecture
- **Language**: Proprietary (Rust/C++)
- **Deployment**: Fully managed cloud only — no self-hosted option
- **Type**: Cloud-managed — serverless-first with Dedicated Read Nodes (DRN) option
- **License**: Proprietary (closed-source)

#### 7.4.2 Index Types
- Proprietary serverless indexing (details not publicly disclosed)
- HNSW-like graph internally (approximate)
- Support for dense + sparse vectors natively
- Binary quantization (BBQ-style) for compression
- No user-exposed index type selection — Pinecone manages index strategy automatically

#### 7.4.3 Hybrid Search
- Native sparse-dense hybrid search
- `pinecone-sparse-english-v0` model for sparse embeddings
- Managed inference for embedding generation
- RRF for result fusion
- Less tunable than Elasticsearch/Weaviate hybrid but fully managed

#### 7.4.4 Scaling
- **Serverless**: Auto-scales to billions of vectors; no capacity planning
- **Consistent p99 latency** across scales — ~22ms at 100M vectors, ~39ms at 500M
- **Dedicated Read Nodes (DRN)**: Provisioned compute for predictable high-QPS workloads
- Scales to 1B+ vectors in production
- Multi-region replication (Standard+)
- Namespace-based multi-tenancy

#### 7.4.5 Filtering
- Metadata filtering with predefined schema
- Support for complex filters (boolean, numeric ranges, arrays, string matching)
- Filtering quality: good but not best-in-class; ~78ms at scale with filters
- Less flexible than Qdrant's payload indexing for highly selective filters
- No explicit payload indexes to configure

#### 7.4.6 Strengths
- **Zero ops** — no infrastructure to manage, deploy, monitor, or scale
- Consistent SLAs and latency across all scales
- Serverless pricing: pay only for what you use (no idle compute cost)
- Excellent developer experience: clean SDK, quick start
- SOC 2, HIPAA (Enterprise), RBAC, SSO
- Multi-cloud: AWS, GCP, Azure
- Strong ecosystem: LangChain, LlamaIndex, OpenAI integrations
- Managed embedding inference included

#### 7.4.7 Weaknesses
- **Closed-source** — vendor lock-in, no self-hosted option ever
- **Cost at scale**: $2,450/month at 100M vectors with query traffic; self-hosted alternatives 3–10× cheaper
- Per-query billing can surprise: $16–$24 per million read units
- 500M vector index runs $6,000–$12,000/month
- No transparency into index algorithm or tuning parameters
- Minimum spend: $50/month (Standard) or $500/month (Enterprise)
- Cannot inspect or customize the storage engine

#### 7.4.8 Cost Model
| Tier | Cost |
|---|---|
| Starter (Free) | 2GB storage, 5 indexes, 2M write units/month, 1M read units/month |
| Standard | $50/month min; $0.33/GB storage; $4/M writes; $16/M reads |
| Enterprise | $500/month min; $0.33/GB storage; $6/M writes; $24/M reads |
| Typical small app (<1M vectors) | ~$35–$60/month |
| 10M vectors + moderate QPS | ~$200–$400/month |
| 100M vectors + production QPS | ~$2,450/month |
| Dedicated Read Nodes (DRN) | Per-node hourly pricing, for sustained high QPS |

Read units scale with namespace size: 1 query = 1 RU per GB of namespace. A 50GB namespace = 50 RUs per query.

#### 7.4.9 Production Adoption
- Widely adopted by startups and mid-size companies for RAG
- Trusted by Notion, Shopify, Gong, Cohere, and thousands of SaaS products
- Default choice for teams that refuse to manage infrastructure
- Popular in VC-funded startups where time-to-market > cost optimization

#### 7.4.10 Best Use Cases
- Teams that want zero infrastructure overhead
- Startups building RAG products without DevOps expertise
- Variable/ bursty traffic patterns (serverless auto-scales down to zero)
- Quick prototyping → production with no architectural change
- Sub-10M vectors with moderate query traffic (cost-efficient range)
- Organizations with compliance requirements (SOC 2, HIPAA) that don't want to self-manage

---

### 7.5 pgvector

#### 7.5.1 Architecture
- **Language**: C (PostgreSQL extension)
- **Deployment**: Any PostgreSQL host — self-managed, RDS, Aurora, Cloud SQL, Supabase, Neon, Timescale, etc.
- **Type**: Database extension — vectors live in standard PostgreSQL tables alongside relational data
- **License**: PostgreSQL license (open source)

#### 7.5.2 Index Types
- **HNSW** (v0.5.0+) — graph-based, memory-resident, tunable (`m`, `ef_construction`, `ef_search`)
- **IVFFlat** (original) — cluster-based, requires training step, disk-friendly
- Half-precision (`halfvec`) — 16-bit floats, halves RAM at ~99% accuracy
- Binary quantization — dramatic memory reduction
- **pgvectorscale** (Timescale extension): StreamingDiskANN — disk-based ANN for 10× larger scale
- SIMD-accelerated distance operations (v0.7.0+)
- Parallel index builds (v0.7.0+, v0.9.0 enhanced)
- Iterative index scans (v0.8.0+) — mitigates post-filter result gaps

#### 7.5.3 Hybrid Search
- **Partial, not native** — requires manual combination of vector + full-text (`tsvector/tsquery`)
- Combine `WHERE` with `ORDER BY embedding <=> query_vector` in SQL
- No built-in fusion (RRF/linear combination) — must implement in application layer
- PostgreSQL full-text search (tsvector) can be combined but requires application-side merging
- Not equivalent to Weaviate/Elasticsearch native hybrid

#### 7.5.4 Scaling
- **Vanilla pgvector ceiling**: ~5M vectors (HNSW in RAM), ~50M with halfvec/pgvectorscale
- **With pgvectorscale (DiskANN)**: 50–500M vectors with performance comparable to dedicated DBs
- **Horizontal scaling**: Via Postgres read replicas, Citus sharding, or PgDog
- **p99 latency**:
  - 1M vectors: ~8ms
  - 10M vectors: ~18ms
  - 50M vectors: ~40ms (vanilla)
  - 100M vectors: ~95ms vanilla, ~22ms with pgvectorscale DiskANN
- Index build is O(n log n), not incremental — full REINDEX at 100M can take hours
- Scales vertically primarily; scale-out via sharding adds complexity

#### 7.5.5 Filtering
- **Full SQL WHERE** — the most expressive filtering of any option
- Combine arbitrary SQL predicates with vector similarity
- Iterative index scans (v0.8.0+) improve filtered recall but are a workaround for post-filtering
- Filtered ANN is pgvector's weakest area — no native filtered-ANN like Qdrant
- Filter selectivity matters: highly selective filters may return few/no results
- ACID transactions — filter and update in the same transaction as business data

#### 7.5.6 Strengths
- **Zero additional infrastructure** if you already run PostgreSQL
- Eliminates data synchronization between transactional DB and vector store
- ACID transactions across business data and embeddings
- Full SQL expressiveness for complex queries
- Mature ecosystem: backups, replication, PITR, monitoring (30+ years of PostgreSQL tooling)
- Managed by every major cloud provider (RDS, Aurora, Cloud SQL, Supabase, Neon)
- Competitive cost: free extension on infrastructure you already pay for
- pgvectorscale extends ceiling to 100M–500M vectors

#### 7.5.7 Weaknesses
- No native hybrid search (must implement fusion in application)
- Filtered ANN is fundamentally limited (post-filtering problem)
- HNSW index must fit in RAM — memory becomes the constraint above ~10M vectors
- Index builds are not incremental — REINDEX required for full rebuilds
- No multi-vector/ColBERT support
- Not designed for ultra-low latency (<10ms p99 consistently)
- Concurrent read/write contention at high QPS
- Vector search competes with OLTP workloads for shared PostgreSQL resources

#### 7.5.8 Cost Model
| Tier | Cost |
|---|---|
| Extension: free (PostgreSQL license) | $0 |
| Self-hosted Postgres | Your existing instance cost |
| Managed Postgres with pgvector | Included in RDS/Aurora/Cloud SQL pricing |
| Supabase | Free tier available; Pro from $25/month |
| Neon | Free tier; Pro from $19/month; serverless auto-scaling |
| Timescale Cloud | Free tier; usage-based pricing |
| 1M vectors @ 1024d on Neon | ~$30/month |
| 50M vectors self-hosted with pgvectorscale | ~$835/month (vs. Pinecone $3,241–$3,889) |

The primary cost advantage: **you're paying for Postgres anyway**. pgvector adds near-zero incremental infrastructure cost for modest vector workloads.

#### 7.5.9 Production Adoption
- **Supabase** — 5,100+ Quivr databases, thousands of pgvector-powered apps
- **Vecstore** — replaced Pinecone + RDS with Neon/pgvector; 200ms → 80ms latency
- **Humata** — 4× cost reduction migrating from Pinecone to Supabase pgvector
- **Firecrawl** — switched from Pinecone/Weaviate; found pgvector equally performant at lower cost
- **Quivr** — 1.6M embeddings, 100K+ files, 22K GitHub stars
- **Euka** — AI-powered creator platform on Supabase pgvector
- **Timescale** — pgvectorscale benchmarks show 28× lower p95 latency and 16× higher QPS than Pinecone at 50M scale

#### 7.5.10 Best Use Cases
- Teams already running PostgreSQL in production (the "default" answer)
- <50M vectors with moderate QPS (<100 queries/sec)
- Workloads requiring transactional consistency between business data and embeddings
- Applications where data already lives in Postgres and adding a new database is unjustified
- EU data residency where keeping everything in one database is a compliance win
- Cost-sensitive deployments wanting to avoid a second infrastructure service
- Use pgvectorscale when crossing 20M+ vectors

---

### 7.6 Elasticsearch

#### 7.6.1 Architecture
- **Language**: Java (Lucene core)
- **Deployment**: Self-hosted (cluster) or Elastic Cloud (managed, including serverless)
- **Type**: Distributed search engine — full-text search + vector search + analytics in one platform
- **License**: Elastic License 2.0 / SSPL (source-available, not OSI open-source)

#### 7.6.2 Index Types
- **HNSW** (via Lucene) — per-segment graph, memory-mapped via OS page cache
- **Better Binary Quantization (BBQ)** — 32× compression with competitive recall
- Scalar quantization (int8)
- Sparse vectors via ELSER (Elastic Learned Sparse EncodeR) — built-in
- External sparse models from HuggingFace (v8.17+)
- Dense vector field (`dense_vector`) for bring-your-own embeddings
- `semantic_text` field — automatic embedding + chunking (simplest path)

#### 7.6.3 Hybrid Search
- **Best-in-class hybrid search ecosystem**:
  - RRF (Reciprocal Rank Fusion) — default, zero-tuning, robust
  - Linear combination — weighted scoring for fine control
  - ELSER sparse retrieval bridges keyword precision and semantic understanding
  - Retriever framework: combine kNN + BM25 + sparse_vector in one query
  - `semantic_text` hybrid — automatic embedding + BM25 fusion
- Named a Leader in 2025 Forrester Wave for Cognitive Search Platforms

#### 7.6.4 Scaling
- **Cluster scaling**: Horizontally via shards and replicas; widely proven at petabyte scale
- **Vector scale**: 500M+ vectors in production (Cypris case: 500M patents)
- **Query throughput**: 10K QPS with sub-50ms p95 (e-commerce production, 500K products)
- **p99 latency**: ~200ms at 300M vectors (1024d, Intercom production); tunable down to 5–10s for 500M vectors
- BBQ quantization critical for >100M vector scale
- Segment + shard tuning essential for large vector indices (force-merge, shard sizing)
- Elastic Cloud Serverless: auto-scaling, no capacity planning

#### 7.6.5 Filtering
- **Native Lucene filter integration** — filters applied during graph walk
- Pre-filtering and post-filtering both supported
- Complex boolean, range, geo, nested filters
- Full Elasticsearch Query DSL expressiveness
- Filter + vector + full-text in one query
- No result-gap problem (unlike pgvector post-filtering)

#### 7.6.6 Strengths
- Most mature production search platform (15+ years of Lucene)
- Unmatched hybrid search: BM25 + dense + sparse (ELSER) + RRF in one engine
- Eliminates separate vector DB + search engine; one platform for lexical, semantic, and analytics
- Deep enterprise feature set: security, RBAC, audit logging, alerting, Kibana dashboards, ML
- Managed inference: deploy embedding models directly in Elasticsearch
- Huge ecosystem: Beats, Logstash, Kibana, APM, connectors
- Proven at scale: Intercom (300M vectors), Cypris (500M vectors), multi-modal search (50M DAU)
- Elastic Cloud Serverless simplifies operations
- Built-in RAG framework, AI Agent Builder, ES|QL for vector search

#### 7.6.7 Weaknesses
- **Not open-source** (SSPL/Elastic License) — controversy since 2021 relicense
- JVM overhead — memory management requires tuning (heap vs. OS page cache)
- Heavier than purpose-built vector DBs for vector-only workloads
- HNSW per-segment architecture means query cost scales with segment count
- 500M vector search needs significant optimization (BBQ, segment tuning, shard sizing)
- More operational complexity than serverless Pinecone for pure vector workloads
- Cost at scale: self-hosted cluster costs significant; Elastic Cloud not cheap
- Learning curve for optimal vector performance (segment merging, JVM tuning, shard strategy)

#### 7.6.8 Cost Model
| Tier | Cost |
|---|---|
| Self-hosted (Elastic License) | Free (source-available) |
| Elastic Cloud Standard | Usage-based; varies by deployment size |
| Elastic Cloud Serverless | Pay-per-use (search + indexing + storage) |
| Self-hosted at 300M vectors | ~$6,000–$12,000/month (unblended) at Intercom; ~$6K with reserved instances |
| Compared to Pinecone at same scale | ~4× cheaper self-hosted (case: 500K products, multi-modal search) |

Exact pricing is opaque; requires Elastic sales for enterprise. Self-hosting is the primary cost lever.

#### 7.6.9 Production Adoption
- **Intercom** — 300M vectors (1024d), ~30ms avg query latency, ~200ms p99
- **Cypris** — 500M patent/research paper vectors, optimized from 60s to 5–10s query time
- **Flockx** — social discovery, 10× search speed improvement, RAG with AI agents
- **LG CNS** — hybrid search improved accuracy from 75% to 95%
- **Tetragon Financial** — $30B hedge fund, migrated from ChromaDB to Elastic Cloud Serverless
- **Contextual AI** — enterprise RAG platform, 90%+ accuracy in production
- **E-commerce platforms** — 30–50M DAU, 500K+ products, 10K QPS, sub-50ms p95

#### 7.6.10 Best Use Cases
- Organizations already running Elasticsearch for search/observability
- Hybrid search where BM25 + sparse + dense fusion is critical
- Full-stack search: lexical + semantic + analytics + SIEM in one platform
- Enterprise environments with existing Elasticsearch operational expertise
- Multi-modal search with rich metadata and full-text requirements
- When you need more than just vector search (logging, APM, security, dashboards)

---

### 7.7 OpenSearch

#### 7.7.1 Architecture
- **Language**: Java (forked from Elasticsearch 7.10, Apache Lucene core)
- **Deployment**: Self-hosted (cluster) or Amazon OpenSearch Service (managed, provisioned + serverless)
- **Type**: Distributed search engine — full-text + vector + analytics
- **License**: Apache 2.0 (fully open-source, Linux Foundation project)

#### 7.7.2 Index Types
- **HNSW** (via Lucene engine) — graph-based, per-segment, memory-mapped
- **HNSW** (via Faiss engine) — GPU support, wider quantization (IVF, PQ options)
- **BBQ** (Lucene Better Binary Quantization, v3.6+) — 32× compression, better recall than Faiss BQ
- IVF (via Faiss) — for very large corpora where graph overhead is prohibitive
- Sparse vectors via neural sparse search (SEISMIC algorithm, v3.3+) — 4× faster than BM25 at billion-scale
- `semantic_text` field type (automatic embedding)
- Multi-vector support
- GPU-accelerated search (planned/emerging)

#### 7.7.3 Hybrid Search
- **Native hybrid search** via neural search plugin:
  - BM25 + k-NN + neural queries combined
  - Score normalization and blending built-in
  - RRF and linear combination
  - Three-tier hybrid: lexical filtering + vector, combined scores, out-of-the-box blending
- Neural sparse search (SEISMIC) bridges keyword and semantic
- Hybrid retrieval consistently shown to reduce hallucination by 80%+ in RAG (OpenSearchCon 2026)

#### 7.7.4 Scaling
- **Cluster scaling**: LINE runs 1,300+ clusters, 10PB data, 11,000+ nodes
- **Vector scale**: Uber prototype 1.5B+ vectors at ~400 dimensions; DataStax benchmarks to 1B+
- **Query throughput**: Uber achieved 2,000 QPS with p99 <120ms on 1.5B vectors (optimized)
- **Ingestion**: 1.5B documents indexed in 2.5 hours (optimized bulk indexing)
- **gRPC support**: 17% throughput improvement, 22% payload size reduction
- OpenSearch Serverless: auto-scaling, OCU-based billing
- Warm/hot/cold storage tiers for cost optimization

#### 7.7.5 Filtering
- Engine-dependent:
  - **Lucene**: Native filter integration, filters during graph walk, no post-filter gap
  - **Faiss**: Post-filtering risk with highly selective filters
  - "Efficient filtering" — intelligent decision-based approach (used by Nexthink)
- Full OpenSearch Query DSL for complex filters
- Pre-filtering and post-filtering both available; Lucene engine preferred for filtered workloads
- Multi-tenant filtering via `tenant_id` keyword fields (Nexthink, Amplitude)

#### 7.7.6 Strengths
- **Apache 2.0** — true open-source, no license concerns (unlike Elasticsearch)
- Linux Foundation governance — vendor-neutral, community-driven
- AWS-managed service: 99.99% SLA, automated scaling, patching
- Rapid innovation: BBQ 32× compression, SEISMIC sparse ANN, gRPC, GPU acceleration roadmap
- Uber, LINE, Amplitude, Freshworks, Nexthink all in production
- Neural search plugin simplifies RAG: auto-embedding, hybrid, multimodal
- OpenSearch Ingestion + ML Commons for batch embedding at scale
- 2.5× faster vector search vs. OpenSearch 1.3 (v3.3+)

#### 7.7.7 Weaknesses
- Java/JVM overhead similar to Elasticsearch
- Lucene vs. Faiss engine choice is a critical architectural decision (not well-documented)
- Faiss engine: post-filtering can produce empty results with selective filters
- SEISMIC sparse search is new (v3.3, late 2025) — less battle-tested than Elastic's ELSER
- Behind Elasticsearch on some features (agentic search maturity, ELSER equivalent)
- AWS-centric: Amazon OpenSearch Service is the primary managed option; multi-cloud support in managed form is limited
- Community smaller than Elasticsearch's
- GPU acceleration still emerging (Uber contributing, not yet GA)

#### 7.7.8 Cost Model
| Tier | Cost |
|---|---|
| Open-source self-hosted | Free (Apache 2.0) |
| Amazon OpenSearch Service (provisioned) | Per instance-hour (e.g., r6g.xlarge.search ~$0.28/hr); Reserved Instances 40–60% cheaper |
| Amazon OpenSearch Serverless | Per OCU (OpenSearch Compute Unit) consumed; good for variable workloads |
| Self-hosted on EC2 | ~$300–$800/month for production cluster |
| Cost note | Provisioned + Reserved Instances significantly cheaper than serverless at sustained high volume |

#### 7.7.9 Production Adoption
- **LINE** — 194M MAU, 1,300+ clusters, 10PB data, 11,000+ nodes; migrating to AI agent workloads
- **Uber** — 1.5B+ vector semantic search prototype, 79% faster ingestion, 52% latency reduction
- **Amplitude** — natural language analytics, 20M+ charts/dashboards, hybrid search
- **Freshworks** — 75K+ customers, petabytes of data, sub-millisecond hybrid search
- **DataStax** — JVector + OpenSearch for billion-scale vector search
- **Nexthink** — AI agent for enterprise IT, 77% first-contact resolution, multi-tenant vector search
- **Integral Ad Science** — 100M+ documents/day, 40–55% performance boost
- **Cabify** — real-time search offloading from Postgres to OpenSearch
- **Intuit** — "default store for all vector needs across Intuit"

#### 7.7.10 Best Use Cases
- AWS-native environments (deep integration with Bedrock, SageMaker, S3, MSK)
- Organizations that want Apache 2.0 open-source vector + search (avoid Elastic license)
- Hybrid search (BM25 + vector + neural) with strong enterprise SLAs
- Large-scale multi-tenant SaaS platforms (Amplitude, Freshworks pattern)
- Teams with existing OpenSearch operational expertise
- Cost-sensitive large-scale deployments (Reserved Instances on AWS)
- Real-time + batch vector workloads on the same cluster

---

### 7.8 LanceDB

#### 7.8.1 Architecture
- **Language**: Rust (core), Python/JavaScript/Node.js SDKs
- **Deployment**: Embedded (runs in-process like SQLite), or LanceDB Cloud (managed, serverless)
- **Type**: Embedded/library — no separate server, daemon, or Docker container required
- **Storage**: Columnar Lance format (file-based, local disk or S3-compatible object storage)
- **License**: Apache 2.0

#### 7.8.2 Index Types
- **IVF_PQ** — fast build, sub-10ms latency at billion-scale, memory-efficient
- **HNSW** — higher recall, incremental updates
- **GPU-accelerated index building** — 5–10× faster than CPU
- Brute-force search for small datasets (<100K vectors)
- Full-text search index (via Tantivy) alongside vector index
- No DiskANN, no ScaNN

#### 7.8.3 Hybrid Search
- **Built-in hybrid search**: Vector similarity + BM25 text score + SQL predicates in one query
- Re-rank with cross-encoder or custom model via user-defined functions
- Full-text search powered by Tantivy (Rust-based, Lucene-compatible)
- SQL interface via DataFusion
- Unique: hybrid search across multimodal data (text + image + video in one table)

#### 7.8.4 Scaling
- **Disk-first architecture**: Scales to billions of vectors on a single machine (not limited by RAM)
- **Columnar format**: Reads only required columns, not entire rows
- **p99 latency**: 1.3ms to search 1B vectors (IVF-PQ, r5.8×large, vendor claim)
- **Ingestion**: 3M 512-dim vectors/minute on single machine (GPU builder)
- **Random access**: ~100× faster than Parquet for vector workloads
- **Fragment-based append model**: Cheap streaming writes, compaction needed for sustained write-heavy workloads
- LanceDB Cloud: S3-backed, auto-scaling serverless

#### 7.8.5 Filtering
- SQL WHERE clauses alongside vector + full-text search
- Columnar format enables efficient filter-on-metadata without reading vector data
- Pre-filtering and post-filtering supported
- Less mature than Qdrant's payload indexing for complex metadata filtering
- Good for simple structured metadata; limited for nested JSON / high-cardinality filters
- Metadata stored alongside vectors in Lance format

#### 7.8.6 Strengths
- **Truly embedded** — zero ops, `pip install lancedb`, point at a directory, done
- Disk-native columnar format — handles datasets larger than RAM
- Multimodal-first: text, images, video, audio, point clouds in one table
- Automatic versioning — every write creates a new version, time-travel queries
- Zero-copy integration with Arrow/Pandas/Polars/DuckDB
- Competitive at billion-scale on single machine (no cluster needed)
- GPU-accelerated index builds
- Free and open-source (Apache 2.0)

#### 7.8.7 Weaknesses
- **Younger ecosystem** — smaller community, fewer tutorials, less StackOverflow content
- Not designed for multi-node distributed search (single-machine or cloud-provisioned)
- Performance tied to disk speed — HDD significantly underperforms vs. NVMe SSD
- Lance format fragmentation requires periodic compaction
- Metadata filtering less sophisticated than Qdrant or Elasticsearch
- No first-party MCP server (community connectors only)
- LanceDB Cloud is newer and less proven than Pinecone/Weaviate Cloud
- No GPU query execution (GPU only for index building)
- Concurrency model for multi-user read/write is less mature than client-server DBs

#### 7.8.8 Cost Model
| Tier | Cost |
|---|---|
| Open-source embedded | Free (Apache 2.0) |
| LanceDB Cloud free tier | 100K vectors |
| LanceDB Cloud Pro | $39/month |
| LanceDB Enterprise | Custom pricing (dedicated support, SSO, governance) |
| Self-hosted (local disk) | $0 (just storage cost) |
| Self-hosted on cloud VM | VM cost only; no per-query or per-vector fees |

Extremely cost-effective: no server, no query fees, storage-cost only. At billion-scale, 10–100× cheaper than always-on vector clusters due to compute/storage separation.

#### 7.8.9 Production Adoption
- **Midjourney** — text-to-image platform, high-traffic large-scale vector search
- **Character.ai** — chatbot platform, multimodal embeddings
- **Runway** — generative AI video, model training pipeline on Lance format
- **WeRide** — autonomous driving
- **Airtable** — product search and AI features
- $30M Series A (July 2025) from Theory Ventures, CRV, Y Combinator, Databricks Ventures
- Total funding: $41M

#### 7.8.10 Best Use Cases
- Embedded RAG in Python/Rust/Node.js applications (no separate service)
- Multimodal AI — text + image + video + audio in one database
- AI/ML training data management with versioning (Lance format)
- Datasets larger than RAM on a single machine
- Serverless/edge deployments with local disk
- CI/CD embedding pipelines where standing up a server is impractical
- Teams already using Arrow/Parquet/DuckDB who want vector search in the same ecosystem
- Prototyping that needs a direct path to production (local dev → LanceDB Cloud)

---

### 7.9 Comparison Tables

#### 7.9.1 Architecture & Deployment

| Database | Type | Language | License | Managed Option | Self-Hosted | Minimum Viable Setup |
|---|---|---|---|---|---|---|
| **Qdrant** | Server | Rust | Apache 2.0 | Qdrant Cloud | Single binary | 2 vCPU / 2 GB |
| **Weaviate** | Server | Go | BSD-3 | Weaviate Cloud | Docker/K8s | 2 vCPU / 4 GB |
| **Milvus** | Distributed DB | Go+C++ | Apache 2.0 | Zilliz Cloud | K8s + etcd + MinIO + Pulsar | 4 vCPU / 8 GB |
| **Pinecone** | Cloud-managed | Proprietary | Proprietary | Pinecone (only) | None | Zero (managed) |
| **pgvector** | DB extension | C | PostgreSQL | Any Postgres host | Any Postgres host | Your existing Postgres |
| **Elasticsearch** | Search engine | Java | Elastic/SSPL | Elastic Cloud | Cluster (JVM) | 4 vCPU / 8 GB |
| **OpenSearch** | Search engine | Java | Apache 2.0 | AWS OpenSearch | Cluster (JVM) | 4 vCPU / 8 GB |
| **LanceDB** | Embedded/lib | Rust | Apache 2.0 | LanceDB Cloud | In-process | Zero (`pip install`) |

#### 7.9.2 Index Types & Compression

| Database | Dense Indexes | Sparse Indexes | Quantization | GPU Accelerated |
|---|---|---|---|---|
| **Qdrant** | HNSW, on-disk HNSW | Yes (v1.10) | Scalar, PQ, BQ | Cloud only |
| **Weaviate** | HNSW, Flat | No (via external) | PQ, BQ | No |
| **Milvus** | HNSW, IVF_FLAT, IVF_SQ8, IVF_PQ, DiskANN, ScaNN | Yes (v2.4) | SQ8, PQ, BQ | Yes (index + query) |
| **Pinecone** | Proprietary (HNSW-like) | Yes (native sparse) | Built-in (managed) | N/A (managed) |
| **pgvector** | HNSW, IVFFlat | No (manual via tsvector) | halfvec, BQ | No |
| **Elasticsearch** | HNSW (Lucene) | ELSER + HuggingFace | BBQ, int8 | No (CPU) |
| **OpenSearch** | HNSW (Lucene), HNSW/IVF (Faiss) | SEISMIC (v3.3) | BBQ, PQ, BQ | Emerging |
| **LanceDB** | IVF_PQ, HNSW | Tantivy (full-text) | PQ | Index build only |

#### 7.9.3 Performance Benchmarks (10M Vectors, 768-dim, HNSW)

| Database | p50 Latency | p99 Latency | Insert Throughput | Recall@10 | RAM |
|---|---|---|---|---|---|
| **Qdrant** | 3.2ms | 18.4ms | 42,000 vec/s | 0.97 | 8.2 GB |
| **Milvus** | 4.1ms | 24.7ms | 38,500 vec/s | 0.94 | 10.1 GB |
| **Weaviate** | 5.8ms | 31.2ms | 31,200 vec/s | 0.95 | 9.5 GB |
| **Pinecone** | 6.4ms | 22.1ms | 18,000 vec/s | 0.96 | Managed |
| **pgvector** | 9.1ms | 58.3ms | 12,400 vec/s | 0.91 | 12.4 GB |

*Sources: Inductivee 2025, Tensoria 2026, GogoAI 2026. All self-hosted benchmarks except Pinecone (serverless). Elasticsearch/OpenSearch/LanceDB not in this specific benchmark suite.*

#### 7.9.4 Latency at Scale (p99, ms)

| Database | 10M Vectors | 100M Vectors | 500M Vectors |
|---|---|---|---|
| **Qdrant** | 6.1 | 18.4 | 47.2 |
| **Milvus** | 7.8 | 24.7 | 61.8 |
| **Weaviate** | 9.2 | 31.2 | 89.4 |
| **Pinecone** | 8.4 | 22.1 | 38.9 |
| **pgvector** | 14.2 | 58.3 | Not recommended |

#### 7.9.5 Hybrid Search & Filtering

| Database | Hybrid Search | Fusion Methods | Filtering Quality | Filter Architecture |
|---|---|---|---|---|
| **Qdrant** | Dense + sparse (v1.10) | RRF, score blend | **Excellent** | Filterable HNSW (in-graph) |
| **Weaviate** | BM25 + dense (mature) | Alpha-weighted, RRF | Good | Post-ANN mostly |
| **Milvus** | Full-text + vector (v2.4) | Manual/config | Adequate | Post-filter (40–60% hit) |
| **Pinecone** | Sparse + dense | RRF | Good | Managed |
| **pgvector** | Manual (tsvector + vector) | None built-in | SQL (powerful but post-filter) | Iterative scan workaround |
| **Elasticsearch** | BM25 + dense + ELSER | RRF, linear, retriever | **Excellent** | Native Lucene filter |
| **OpenSearch** | BM25 + k-NN + neural | RRF, linear, neural plugin | **Excellent** (Lucene) | Engine-dependent |
| **LanceDB** | BM25 + vector + SQL | Linear combination | Good | Columnar metadata filter |

#### 7.9.6 Cost Comparison (Monthly, 10M Vectors @ 1536-dim, Moderate QPS)

| Database | Self-Hosted | Managed Cloud |
|---|---|---|
| **Qdrant** | ~$40–$80 (VPS) | ~$65–$100 |
| **Weaviate** | ~$50–$100 (VPS) | ~$150–$400 (dimension-priced) |
| **Milvus / Zilliz** | ~$100–$300 (cluster) | ~$65–$200 |
| **Pinecone** | N/A | ~$200–$400 |
| **pgvector** | $0–$50 (existing DB) | $30–$80 (Neon/Supabase) |
| **Elasticsearch** | ~$100–$300 (cluster) | ~$200–$500 |
| **OpenSearch** | ~$100–$300 (cluster) | ~$150–$400 (AWS) |
| **LanceDB** | ~$10–$40 (VM + disk) | $39 (Pro tier) |

#### 7.9.7 Production Readiness Summary

| Database | GitHub Stars | Est. Production Scale | Representative Users |
|---|---|---|---|
| **Qdrant** | ~15K | 1M–2.7B vectors | Tripadvisor, Deutsche Telekom, Bazaarvoice, Flipkart |
| **Weaviate** | ~12K | 1M–200M vectors | European enterprises, e-commerce, legal tech |
| **Milvus** | ~42K | 100M–10B+ vectors | NAVER, Bosch, Uber, Leboncoin, Farfetch |
| **Pinecone** | N/A (closed) | 100K–1B+ vectors | Notion, Shopify, Gong, Cohere, thousands of SaaS |
| **pgvector** | ~13K (pgvector) | 10K–500M vectors | Supabase/Neon users, Humata, Firecrawl, Vecstore |
| **Elasticsearch** | N/A | 100K–500M+ vectors | Intercom, Cypris, Flockx, LG CNS, Contextual AI |
| **OpenSearch** | ~10K | 1M–1.5B+ vectors | LINE, Uber, Amplitude, Freshworks, Nexthink |
| **LanceDB** | ~5K | 10K–1B+ vectors | Midjourney, Character.ai, Runway, WeRide, Airtable |

---

### 7.10 Recommendations by Scenario

#### Scenario 1: "I already run PostgreSQL in production"
**Recommendation: pgvector**
- Zero additional infrastructure; vectors live alongside business data
- ACID transactions across embeddings and relational data
- Add pgvectorscale when crossing 20M+ vectors
- Graduate to Qdrant when p99 latency exceeds your SLO (>50M vectors or >50ms)

#### Scenario 2: "I want zero infrastructure to manage"
**Recommendation: Pinecone (serverless)**
- No servers, no scaling, no ops
- Best for startups and teams without DevOps bandwidth
- Watch cost at scale: >10M vectors + moderate QPS gets expensive
- Alternative: LanceDB Cloud (cheaper, newer) or Qdrant Cloud (more control)

#### Scenario 3: "Complex metadata filtering is my core requirement"
**Recommendation: Qdrant**
- Filterable HNSW integrates filters into graph traversal (only 15–20% slowdown)
- Best-in-class for filtered ANN search in all independent benchmarks
- Payload indexing supports nested JSON, date ranges, high-cardinality metadata
- Self-hosted or Qdrant Cloud

#### Scenario 4: "Hybrid search (BM25 + dense vector) is critical"
**Recommendation: Elasticsearch** (or Weaviate if you prefer open-source simplicity)
- Elasticsearch: Most mature hybrid stack — BM25 + ELSER sparse + dense + RRF in one query
- Weaviate: Simpler, open-source, built-in vectorizers, good enough for most cases
- OpenSearch: Apache 2.0 alternative with strong hybrid via neural search plugin

#### Scenario 5: "Billion-vector scale with high write throughput"
**Recommendation: Milvus (self-hosted) or Zilliz Cloud**
- Only option proven at 10B+ vector scale
- GPU-accelerated indexing (45 min → 3 min for 10M vectors)
- Tiered storage: hot-memory, warm-SSD, cold-S3
- Accept the operational complexity; it's justified at this scale

#### Scenario 6: "Multimodal AI — images, video, text together"
**Recommendation: LanceDB**
- Built for multimodal: text, images, video, audio in one columnar table
- Disk-native: scales past RAM on a single machine
- Embedded: `pip install lancedb` and start querying
- Used by Midjourney and Character.ai at production scale

#### Scenario 7: "AWS-native, need Apache 2.0, want hybrid search"
**Recommendation: OpenSearch**
- Deep AWS integration (Bedrock, SageMaker, MSK, S3)
- Apache 2.0 — no license concerns
- Proven at Uber scale (1.5B vectors) and LINE scale (1,300+ clusters)
- Amazon OpenSearch Serverless for variable workloads

#### Scenario 8: "Minimal cost, embedded in my Python app, small-to-medium scale"
**Recommendation: LanceDB** (or ChromaDB for <100K vectors)
- LanceDB: No server, no cost beyond storage, columnar format handles larger-than-RAM
- pgvector: If you already have Postgres, the extension is free

#### Scenario 9: "Full-stack search platform (not just vectors)"
**Recommendation: Elasticsearch** or **OpenSearch**
- Search + observability + security + analytics in one platform
- If you need SIEM, APM, logging, AND vector search — one cluster handles all
- Choose Elasticsearch for managed simplicity and ELSER; OpenSearch for Apache 2.0

---

### 7.11 Decision Flowchart

```
Do you already run PostgreSQL?
├─ YES → Is your vector corpus < 50M?
│   ├─ YES → Start with pgvector. Add pgvectorscale at 20M+.
│   └─ NO  → Do you need complex filtering?
│       ├─ YES → Qdrant (self-hosted or Cloud)
│       └─ NO  → Milvus/Zilliz (billion-scale)
└─ NO  → Is zero-ops your top priority?
    ├─ YES → Pinecone Serverless (cost caveat: 10M+ gets expensive)
    └─ NO  → What matters most?
        ├─ Hybrid search (BM25 + vector) → Elasticsearch or Weaviate
        ├─ Complex filtering → Qdrant
        ├─ Multimodal data → LanceDB
        ├─ Billion-scale + GPU → Milvus
        ├─ AWS ecosystem + Apache 2.0 → OpenSearch
        └─ Embedded, no server, disk-native → LanceDB
```

---

### 7.12 Key Takeaways

1. **pgvector is the correct default for ~80% of teams** — if you have Postgres and <50M vectors, you don't need a separate database. The "you probably don't need a vector database" argument has become defensible in 2026.

2. **Qdrant wins on price-performance for filtered search** — its Rust core and filterable HNSW deliver the best combination of low latency and strong filtering at self-hosted costs.

3. **Milvus is overkill for most, essential for some** — if you genuinely need billion-vector scale with GPU acceleration, Milvus is the answer. Otherwise, the operational cost isn't justified.

4. **Pinecone is the "safe" managed bet** — excellent DX, zero ops, but costs compound at scale. The free tier is genuinely useful for prototyping.

5. **Elasticsearch and OpenSearch are the hybrid search kings** — when you need BM25 + sparse + dense fusion in production, the search engines beat the vector databases.

6. **LanceDB is the dark horse for multimodal and embedded** — its columnar, disk-native, zero-server architecture fills a gap none of the others address.

7. **The gap between pgvector and dedicated vector DBs has narrowed dramatically** — pgvectorscale/StreamingDiskANN pushes the practical ceiling from ~10M to 100M+ vectors, challenging the "you need a dedicated vector DB" assumption.

8. **Test with YOUR data** — benchmarks use standard datasets (SIFT-1M, Cohere-10M, OpenAI ada-002). Your embedding model, dimensions, filter patterns, and concurrency profile will produce different results. Run a proof of concept before committing.
