# RAG Evaluation Frameworks — Comprehensive Report

> Research subagent survey of open-source, academic, and production evaluation tooling for RAG pipelines.
> Covers framework mechanics, metrics, hallucination detection, groundedness scoring, and decision guidance by team profile.

---

## Table of Contents

1. [Evaluation Frameworks (Research)](#1-evaluation-frameworks-research)
   - [RAGAS](#ragas)
   - [DeepEval](#deepeval)
   - [GroUSE](#grouse)
   - [Open-RAG-Eval](#open-rag-eval)
   - [RAGBench](#ragbench)
   - [BEIR](#beir)
   - [MTEB](#mteb)
2. [Production Evaluation Platforms](#2-production-evaluation-platforms)
   - [TruLens](#trulens)
   - [Arize Phoenix](#arize-phoenix)
   - [Galileo](#galileo)
   - [LangSmith](#langsmith)
3. [Hallucination Detection Methods](#3-hallucination-detection-methods)
4. [Groundedness Scoring Across Frameworks](#4-groundedness-scoring-across-frameworks)
5. [Framework Recommendations by Team Profile](#5-framework-recommendations-by-team-profile)
6. [Decision Matrix](#6-decision-matrix)

---

## 1. Evaluation Frameworks (Research)

### RAGAS

**What it evaluates:** End-to-end RAG pipeline quality — retrieval relevance, generation faithfulness, and answer correctness.

**Key metrics:**

| Metric | Description |
|--------|-------------|
| Faithfulness | Whether the generated answer can be inferred solely from the retrieved context. Computed by decomposing the answer into atomic claims and checking each claim against the context with an LLM-as-Judge. Score: `claims_supported / total_claims`. |
| Answer Relevancy | Whether the answer addresses the question. Reverse-engineered: an LLM generates synthetic questions from the answer, then computes cosine similarity between those question embeddings and the original question embedding. |
| Context Precision | Whether relevant chunks are ranked higher than irrelevant ones. For each chunk in the retrieved context, an LLM judges if it's relevant; precision@k is computed at each rank, then averaged. |
| Context Recall | Whether all ground-truth-relevant information is present in the retrieved context. Each sentence in the reference answer is attributed to a chunk in the context; recall = `sentences_attributed / total_sentences`. |
| Context Relevancy | Fraction of retrieved sentences that are relevant to the question. An LLM extracts relevant sentences from the context; score = `relevant_sentences / total_sentences`. |
| Aspect Critique | Custom binary checks (harmfulness, maliciousness, coherence, conciseness) evaluated by an LLM. |

**How it works:**

RAGAS is designed to work with *no human-annotated ground truth*. Metrics are computed using a combination of LLM calls and embedding similarity. The library expects a dataset with `question`, `answer`, `contexts` (retrieved chunks), and optionally `ground_truth`. It runs evaluation asynchronously over batches, calling an LLM (default: GPT-3.5/4) for judgment tasks and an embedding model for similarity tasks.

The faithfulness pipeline: (1) extract atomic claims from the answer via an LLM prompt; (2) for each claim, ask an LLM whether it is supported by the context; (3) compute `supported / total`. This is a pure reference-free metric — no ground truth needed.

**Strengths:**
- Works without human labels (reference-free evaluation).
- Lightweight Python library with a clean API (`evaluate(dataset, metrics)`).
- Strong community adoption; integrated into LangChain and LlamaIndex ecosystems.
- Composability: mix and match metrics, add custom `AspectCritique` prompts.
- Parallel execution for speed on large datasets.

**Weaknesses:**
- Heavy LLM dependency: faithfulness and answer relevancy require multiple LLM calls per example, increasing cost and latency.
- Metrics are sensitive to the quality of the underlying judge LLM; GPT-3.5 can be noisy, and GPT-4 is expensive.
- Faithfulness decomposition can miss nuanced entailment (a claim that is "partially supported" may be counted as unsupported).
- No built-in UI — purely a Python library; needs integration with observability tools for visualization.

**Best use cases:**
- CI/CD pipelines for RAG applications (automated regression testing).
- Fast iteration during development when ground-truth labels are unavailable.
- Teams already using LangChain/LlamaIndex who want a drop-in evaluation layer.

---

### DeepEval

**What it evaluates:** RAG systems, LLM outputs, chatbots — with a focus on deterministic and hybrid metrics backed by research papers.

**Key metrics:**

| Metric | Description |
|--------|-------------|
| Faithfulness | Whether the answer is supported by the retrieval context. Uses an NLI-style approach: splits the answer into claims, then uses an NLI model (DeBERTa fine-tuned on ANLI) to classify each claim as entailed/contradicted/neutral given the context. Score = `entailed_claims / total_claims`. |
| Answer Relevancy | LLM generates questions from the answer and compares embeddings (similar to RAGAS), but DeepEval also supports using an LLM judge directly. |
| Contextual Precision | Weighted precision of relevant nodes at each rank (similar to RAGAS). |
| Contextual Recall | Weighted recall using ground truth. |
| Hallucination | Binary metric: whether the answer contains any unsupported claim. Scored 0 if any hallucination detected, 1 otherwise. |
| Toxicity | Whether the answer contains toxic content (uses a fine-tuned classifier). |
| Bias | Detects gender, racial, and other biases in generated text. |
| Summarization | Specialized metrics for summary quality (alignment, coverage) using GEval (chain-of-thought LLM evaluation). |
| G-Eval | Chain-of-thought LLM evaluation with a rubric; the LLM reasons step-by-step before assigning a score. |

**How it works:**

DeepEval uses a **hybrid** approach: some metrics use fine-tuned transformer models (NLI-based faithfulness, toxicity, bias classifiers), while others use LLM-as-Judge (G-Eval, summarization). The NLI-based faithfulness metric is faster and cheaper than LLM-based approaches because it uses a local DeBERTa model rather than GPT-4.

The library provides a `pytest`-like test runner:

```python
from deepeval import assert_test
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(input="...", actual_output="...", retrieval_context=[...])
metric = FaithfulnessMetric(threshold=0.7)
assert_test(test_case, [metric])
```

It also ships with `deepeval test run` for running suites and a **Confident AI** cloud platform for dashboarding, experiment tracking, and shareable reports.

**Strengths:**
- Hybrid metrics: NLI-based faithfulness is 10-100x cheaper than LLM-as-Judge approaches.
- Unit-testing ergonomics (`assert_test`) are familiar to developers.
- Built-in cloud dashboard (Confident AI) for experiment tracking and sharing.
- Extensive documentation with research paper citations for each metric.
- Handles edge cases well: empty contexts, very long answers, non-English text.

**Weaknesses:**
- NLI models have limited context windows (typically 512 tokens); long contexts need chunking heuristics.
- The pytest-style API is opinionated and may not fit all workflows.
- Cloud platform (Confident AI) is a paid service beyond the free tier.
- G-Eval chain-of-thought metrics are still LLM-dependent and can be slow.

**Best use cases:**
- Teams that want CI-integrated evaluation with deterministic pass/fail thresholds.
- Cost-sensitive teams that want cheaper faithfulness evaluation via NLI.
- Teams that want both local evaluation and a cloud dashboard without stitching together multiple tools.

---

### GroUSE

**What it evaluates:** All seven failure modes of RAG pipelines identified by unit testing. Published as a research paper (ACL 2024).

**What is a "unit test" in GroUSE?** Each test targets a specific failure mode with a hand-crafted, controlled scenario.

**Seven failure modes (G-RAG taxonomy):**

| # | Failure Mode | Description | Example Test |
|---|-------------|-------------|--------------|
| 1 | **Irrelevant context retrieved** | Retrieval returns chunks unrelated to the query. | Question about "climate change policy" retrieves chunks about "sports scores." |
| 2 | **Partially relevant context** | Some retrieved chunks are relevant, some are noise. | 3 relevant + 2 irrelevant chunks; model must ignore distractors. |
| 3 | **Context conflicts with correct answer** | Retrieved context contains factual errors that contradict the correct answer. | Context says "Paris is the capital of Germany"; model should rely on its own knowledge or abstain. |
| 4 | **Outdated context** | Retrieved context is factually correct but no longer current. | Context says "current president is X" when president has changed. |
| 5 | **Context insufficient to answer** | Retrieved chunks are on-topic but lack the specific fact needed. | Question: "What is the boiling point of titanium?" Context discusses titanium uses but not boiling point. |
| 6 | **Answer ignores context** | Model generates an answer that contradicts or ignores the provided context. | Context says "risk is low"; model says "risk is high." |
| 7 | **Model hallucinates within the answer** | Answer contains fabricated details not present in context. | Context says "study found correlation"; answer says "study proved causation." |

**How it works:**

GroUSE provides a set of ~100 hand-crafted test cases, each targeting one of the seven failure modes. Each test case includes a query, retrieved context (designed to trigger the failure mode), and an expected behavior. The test runner sends the query + context to the RAG pipeline and uses an LLM judge to check whether the pipeline handled the failure mode correctly.

The framework uses GPT-4 as the judge with carefully designed prompts that include:
1. The definition of the failure mode.
2. The expected behavior.
3. A structured output format (pass/fail with reason).

**Strengths:**
- Precise diagnostic value: each failing test tells you *which* failure mode is broken.
- Small, curated test set (~100 cases) that can run in minutes.
- Research-backed taxonomy of failure modes.
- Good for targeted debugging rather than aggregate scoring.

**Weaknesses:**
- Tiny test set; not representative of real-world distribution of queries.
- Tests are hand-crafted for specific domains (mostly factoid QA); may not transfer to your domain.
- Only evaluates generation failures, not retrieval quality.
- Requires GPT-4 as judge; expensive to extend.
- No active maintenance beyond the research paper — no pip package, limited community.

**Best use cases:**
- Diagnostic debugging when a RAG pipeline is performing poorly.
- Complement to broader evaluation frameworks (use GroUSE for targeted failure-mode testing + RAGAS/DeepEval for aggregate metrics).
- Research teams studying RAG failure modes.

---

### Open-RAG-Eval

**What it evaluates:** RAG systems on both retrieval and generation quality, using pre-built datasets and standardized evaluation protocols.

**Key datasets included:**

| Dataset | Description |
|---------|-------------|
| MS MARCO | 1M+ passage ranking queries; evaluates retrieval quality (MRR, Recall@k). |
| Natural Questions (NQ) | Google search queries with Wikipedia answers; open-domain QA. |
| TriviaQA | Trivia questions with evidence documents; tests multi-hop reasoning. |
| HotpotQA | Multi-hop QA requiring reasoning over multiple documents. |
| ASQA | Ambiguous questions requiring comprehensive answers covering multiple facets. |
| ELI5 | Long-form question answering with detailed explanations. |

**Metrics:**

Open-RAG-Eval evaluates two stages independently:

*Retrieval metrics:* MRR@10, Recall@k, NDCG@10, Hit Rate.

*Generation metrics:*
- ROUGE-L (lexical overlap with reference).
- BLEU (n-gram precision).
- METEOR (synonym-aware matching).
- BERTScore (semantic similarity via embeddings).
- Exact Match (for short-answer datasets).
- F1 (token-level overlap).
- LLM-as-Judge (using GPT-4 to compare with reference).

**How it works:**

Open-RAG-Eval provides a standardized evaluation harness:
1. Download a pre-processed dataset (e.g., MS MARCO, NQ).
2. Run your retriever against the corpus and save ranked lists.
3. Run your generator on the retrieved chunks and save answers.
4. Run the evaluation script to compute all metrics.
5. Results are saved as JSON/CSV for analysis.

The framework is dataset- and model-agnostic: you plug in any retriever and generator that conform to a simple interface.

**Strengths:**
- Extensive datasets covering multiple QA formats (short-form, long-form, multi-hop, ambiguous).
- Standardized evaluation protocols enable direct comparison with published baselines.
- Clean separation of retrieval and generation evaluation.
- Good for benchmarking against academic baselines.

**Weaknesses:**
- Most datasets require a reference answer (not reference-free).
- Lexical metrics (ROUGE, BLEU) correlate poorly with human judgments for long-form generation.
- Large dataset size means slow evaluation (hours on full MS MARCO).
- Requires downloading and managing large corpora.
- Less active maintenance; primarily an academic artifact.

**Best use cases:**
- Academic benchmarking and paper writing.
- Comparing retrieval systems head-to-head (same datasets, same metrics).
- Teams that need standard QA benchmarks without designing their own evaluation.

---

### RAGBench

**What it evaluates:** RAG systems across 10 domains with a unified benchmark, distinguishing between "no-context" and "context-dependent" questions.

**Datasets (10 domains):**

| Domain | Dataset | Question Count |
|--------|---------|----------------|
| Finance | FinDER | ~200 |
| Legal | CaseHOLD | ~200 |
| Medical | BioASQ / PubMedQA | ~200 |
| News | NewsQA | ~200 |
| Conversations | CoQA | ~200 |
| Wikipedia | Natural Questions (subset) | ~200 |
| Product Reviews | Amazon QA | ~200 |
| How-To | WikiHow | ~200 |
| Scientific | QASPER | ~200 |
| Technical | TechQA | ~200 |

Total: ~2,000 questions across 10 domains.

**Key innovation — question classification:**

RAGBench classifies each question as either:
- **"No-context" (NC):** The LLM should be able to answer from its parametric knowledge alone (e.g., "What is the capital of France?"). Retrieval is unnecessary.
- **"Context-dependent" (CD):** The answer depends on specific documents (e.g., "What was the revenue of Company X in Q3 2024 according to their earnings report?").

This classification enables three evaluation modes:
1. **Full RAG:** Retrieval + generation (all questions).
2. **Generator-only:** No retrieval, only parametric knowledge (NC questions).
3. **RAG-benefit:** Subtract generator-only score from full RAG score on CD questions to measure how much retrieval *helps*.

**Metrics:**

- **Correctness:** LLM-as-Judge comparing the answer against a reference, scored 0–1.
- **Faithfulness:** LLM-based check of whether answer is supported by retrieved context.
- **RAG-benefit score:** `RAG_correctness(CD) - NoContext_correctness(CD)` — negative values mean retrieval *hurts*.

**How it works:**

RAGBench provides a JSONL file per domain with `question`, `reference_answer`, `documents`, `question_type` (NC/CD). The evaluation script:
1. Runs the RAG pipeline on each question.
2. Computes correctness via GPT-4 judge.
3. Computes faithfulness via GPT-4-based claim decomposition.
4. Reports scores broken down by domain and question type.

**Strengths:**
- Multi-domain coverage enables testing generalization.
- Question type classification (NC/CD) provides a diagnostic lens: "does my retrieval actually improve answers?"
- The RAG-benefit score is a uniquely useful metric not found in other frameworks.
- Standardized split enables direct comparison across papers.

**Weaknesses:**
- Small per-domain sample size (~200 questions/domain) limits statistical power.
- Heavy LLM dependency (GPT-4 for both correctness and faithfulness).
- Reference answers may not capture all valid responses.
- No built-in support for multi-hop or conversational RAG.

**Best use cases:**
- Cross-domain RAG evaluation to identify domain-specific weaknesses.
- Teams evaluating whether retrieval is actually improving their system (RAG-benefit analysis).
- Academic benchmarking against published RAGBench baselines.

---

### BEIR (Benchmarking IR)

**What it evaluates:** Retrieval quality across diverse tasks and domains. BEIR is retrieval-only; it does not evaluate generation.

**Datasets (18 tasks across 9 domains):**

| Domain | Datasets |
|--------|----------|
| Bio-Medical | TREC-COVID, NFCorpus, BioASQ |
| Finance | FiQA-2018 |
| News | Signal-1M, Robust04, TREC-NEWS |
| Social Media | Tweets (multiple) |
| Wikipedia | NQ, HotpotQA, DBPedia-Entity |
| Scientific | SciDocs, SciFact |
| Question Answering | MS MARCO, Quora |
| Argumentation | ArguAna, Touché-2020 |
| Miscellaneous | CQADupStack, Climate-FEVER |

**Metrics:**

- **NDCG@10:** Normalized Discounted Cumulative Gain — measures ranking quality, weighted by position (higher-ranked relevant docs contribute more).
- **MRR@10:** Mean Reciprocal Rank — average of `1/rank_of_first_relevant_doc`.
- **Recall@k:** Fraction of relevant documents retrieved in top-k (k ∈ {1, 10, 100, 1000}).
- **MAP@k (Mean Average Precision):** Average precision at each relevant document position, averaged over queries.
- **Precision@k:** Fraction of top-k documents that are relevant.

**How it works:**

BEIR provides a standardized evaluation protocol:
1. **Corpus:** A collection of documents (varies by dataset, from thousands to millions).
2. **Queries:** A set of test queries with relevance judgments (qrels).
3. **Retriever interface:** Your retriever must implement `search(query, top_k)` returning ranked document IDs.
4. **Evaluation:** BEIR computes all metrics against the qrels and reports per-dataset scores plus an average.

BEIR does **not** prescribe retrieval methods — it has been used to evaluate sparse retrievers (BM25), dense retrievers (DPR, ANCE, TAS-B), late-interaction (ColBERT), and hybrid approaches.

**Strengths:**
- Gold standard for retrieval benchmarking in the IR community.
- Diverse domain/dataset coverage enables testing generalization.
- Well-maintained: regularly updated with new datasets and baselines.
- Standardized protocol enables direct comparison with 50+ published baselines.
- Reproducible: fixed train/test splits and qrels.

**Weaknesses:**
- Retrieval only — no generation evaluation.
- Some datasets are becoming saturated (MS MARCO NDCG@10 approaching 0.5, near human ceiling).
- Large corpus downloads (some datasets >10GB).
- No support for multi-vector or cross-encoder evaluation out-of-the-box (needs custom integration).
- Qrels are binary (relevant/not-relevant); no graded relevance.

**Best use cases:**
- Evaluating and comparing retrieval components independently of generation.
- Academic retrieval research and publication.
- Selecting the best retriever for a given domain before integrating with a RAG pipeline.

---

### MTEB (Massive Text Embedding Benchmark)

**What it evaluates:** Text embedding model quality across diverse tasks — not just retrieval.

**Task categories (8 categories, 58 datasets):**

| Category | Task | Example Datasets |
|----------|------|-----------------|
| **Bitext Mining** | Finding parallel sentences across languages | BUCC, Tatoeba |
| **Classification** | Text classification with embeddings as features | AmazonReviews, Emotion, ToxicConversations |
| **Clustering** | Grouping similar texts | ArxivClustering, BiorxivClustering, RedditClustering |
| **Pair Classification** | Detecting duplicates, paraphrases | TwitterSemEval, TwitterURLCorpus, SprintDuplicateQuestions |
| **Reranking** | Re-ranking retrieval candidates with embeddings | StackExchangeDupQuestions, AskUbuntuDupQuestions, SciDocsRR |
| **Retrieval** | Dense passage retrieval | MS MARCO, NQ, HotpotQA, FEVER, Climate-FEVER, DBPedia |
| **STS (Semantic Textual Similarity)** | Predicting sentence similarity scores | STS12–22, SICK-R, BIOSSES |
| **Summarization** | Evaluating summary quality via embedding similarity | SummEval |

**Metrics (task-dependent):**

| Task | Primary Metric |
|------|---------------|
| Retrieval | NDCG@10 |
| Reranking | MAP |
| Classification | Accuracy, F1 |
| Clustering | V-Measure, ARI |
| Pair Classification | Average Precision |
| STS | Spearman correlation |
| Summarization | Spearman correlation |
| Bitext Mining | F1 |

**How it works:**

MTEB evaluates the *embedding model itself*, not a retrieval system. For each dataset:
1. The embedding model encodes all texts.
2. Task-specific evaluation logic is applied (e.g., for retrieval: compute cosine similarity → rank → compute NDCG against qrels).
3. Scores are averaged across all datasets in a category, and a global average is computed.

The MTEB leaderboard (huggingface.co/spaces/mteb/leaderboard) tracks hundreds of embedding models, making it the standard for model comparison.

**Strengths:**
- Most comprehensive embedding benchmark (58 datasets, 8 task types).
- Leaderboard enables quick model comparison.
- Tasks beyond retrieval provide insight into embedding model robustness.
- Well-maintained and regularly updated with new datasets.
- Standardized evaluation protocol — the community default.

**Weaknesses:**
- Evaluates the embedding model, not the full RAG pipeline.
- Retrieval task evaluations use simple cosine similarity + top-k; doesn't account for hybrid retrieval or reranking.
- Some dataset/test splits are leaked (models trained on MS MARCO evaluated on MS MARCO test).
- Large compute requirements for full evaluation (encoding millions of passages).

**Best use cases:**
- Selecting an embedding model for your RAG pipeline.
- Comparing new embedding models against the state-of-the-art.
- Understanding trade-offs between models (e.g., a model may excel at retrieval but underperform on classification).

---

## 2. Production Evaluation Platforms

### TruLens

**Type:** Open-source Python library (with optional SaaS dashboard).

**What it does:**

TruLens instruments RAG pipelines at runtime, recording traces of every call (retrieval, generation, LLM calls) and computing evaluation metrics. It provides the **"RAG Triad"** — three core feedback functions:

| Feedback Function | Description | Computation |
|-------------------|-------------|-------------|
| **Answer Relevance** | Is the answer relevant to the question? | LLM-as-Judge, scored 0–1. |
| **Context Relevance** | Are the retrieved chunks relevant to the question? | LLM-as-Judge, scored 0–1. |
| **Groundedness** | Is the answer supported by the context? | LLM-as-Judge with chain-of-thought; each sentence is checked against context. |

**Architecture:**

```
App → TruLens Instrumentation → Feedback Functions → Dashboard
         ↓
    Trace Storage (SQLite / Snowflake / Postgres)
```

TruLens wraps your RAG pipeline (LangChain, LlamaIndex, or custom) and records:
- Input/output of every LLM call.
- Retrieved chunks and their metadata.
- Embeddings of inputs, contexts, and outputs.
- Latency, token counts, and cost.

Feedback functions run asynchronously after each request (or in batch mode). Results are streamed to a Streamlit dashboard (`tru run dashboard`) for visualization.

**Strengths:**
- Minimal code changes: wrap your pipeline with `TruChain` or `TruLlama`.
- The RAG Triad provides a clear, opinionated evaluation framework.
- Dashboard is self-hosted (Streamlit) — no vendor lock-in.
- Supports custom feedback functions and multi-modal evaluation.
- Persists evaluation history for longitudinal analysis.

**Weaknesses:**
- Heavy LLM dependency: all three triad metrics require LLM calls, making evaluation expensive at scale.
- Dashboard can be slow with large trace volumes (SQLite backend).
- Less active development since acquisition by Snowflake (2023).
- Groundedness feedback can be noisy; the chain-of-thought rejection logic sometimes misses nuanced support.

**Best use cases:**
- Early-stage RAG development where you need quick visibility into pipeline quality.
- Teams comfortable with self-hosting (Streamlit dashboard).
- LangChain/LlamaIndex users who want plug-and-play instrumentation.

---

### Arize Phoenix

**Type:** Open-source observability platform with optional Arize cloud.

**What it does:**

Phoenix captures and visualizes RAG application traces, embeddings, and LLM calls. It focuses on **observability** rather than metric computation — it helps you understand *what's happening* in your pipeline, then you bring your own evaluators.

**Core capabilities:**

| Feature | Description |
|---------|-------------|
| **Trace capture** | OpenTelemetry-based instrumentation for LangChain, LlamaIndex, OpenAI, etc. |
| **Embedding drift detection** | Projects embeddings into UMAP and detects distribution shifts (Euclidean distance between clusters). |
| **Retrieval analysis** | Visualizes query-embedding-to-chunk-embedding distances, highlights outliers. |
| **LLM span analysis** | Tracks token usage, latency, and errors per LLM call. |
| **Annotation workflow** | UI for human annotators to rate responses and flag issues. |
| **Experiment tracking** | Compare evaluation runs side-by-side (A/B testing of prompts, models, retrievers). |

**Integration with evaluators:**

Phoenix does not ship with built-in evaluation metrics. Instead, it provides a Python API to attach evaluation scores:

```python
from phoenix.evals import run_evals
run_evals(dataframe, evaluators=[HallucinationEvaluator(), QAEvaluator()], ...)
```

These evaluators can be RAGAS, DeepEval, or custom LLM-as-Judge functions. Results are visualized in the Phoenix dashboard.

**Strengths:**
- Best-in-class embedding visualization (UMAP projections, drift detection).
- OpenTelemetry-native — integrates with existing observability stacks.
- Strong annotation workflow for collecting human feedback.
- High-quality dashboard with powerful filtering and drill-down.
- Vendor-agnostic: works with any evaluator.

**Weaknesses:**
- No built-in evaluation metrics — you must integrate RAGAS, DeepEval, or write your own.
- Embedding drift detection requires storing all embeddings (storage cost).
- OpenTelemetry instrumentation can add overhead (1–5ms per span).
- Steeper learning curve than TruLens or LangSmith.

**Best use cases:**
- Teams that already have evaluation metrics and need observability + visualization.
- Detecting data/embedding drift in production.
- Running human annotation campaigns for evaluation datasets.

---

### Galileo

**Type:** SaaS platform (commercial, with limited free tier).

**What it does:**

Galileo provides an end-to-end evaluation and observability platform for LLM applications, including RAG. It combines automated metrics with a human-in-the-loop review workflow.

**Core metrics:**

| Metric | Description |
|--------|-------------|
| **Context Adherence** | Whether the response is grounded in the provided context. Galileo uses a proprietary LLM-based evaluator fine-tuned on hallucination data. |
| **Completeness** | Whether the response addresses all parts of the question. |
| **Correctness** | Factual accuracy measured against a reference (when available). |
| **Toxicity** | Harms detection using classifiers. |
| **Chunk Attribution** | Per-sentence attribution to a specific retrieved chunk (enables debugging: "where did this claim come from?"). |
| **Guardrail Metrics** | Custom checks for PII, prompt injection, off-topic detection. |

**Workflow:**

1. Log traces from your application via Galileo SDK.
2. Galileo automatically computes metrics on each trace.
3. Review flagged (low-scoring) traces in the dashboard.
4. Curate datasets from production traces for fine-tuning.
5. Run experiments to compare prompts, models, and retrieval strategies.

**Strengths:**
- Chunk attribution is a standout feature: trace every claim back to its source document.
- Curated dataset workflow enables continuous improvement (production → evaluation → fine-tuning).
- Proprietary fine-tuned evaluators may be more reliable than generic GPT-4 judging.
- Good security/compliance features (PII detection, guardrails).

**Weaknesses:**
- Closed-source SaaS — vendor lock-in, data leaves your infrastructure.
- Pricing is opaque; enterprise contracts only.
- Proprietary metrics are not reproducible or auditable.
- Limited free tier (typically 10k traces/month).

**Best use cases:**
- Enterprise teams with compliance requirements who need a managed solution.
- Teams that want chunk-level attribution for debugging hallucinations.
- Production monitoring with automatic flagging of low-quality responses.

---

### LangSmith

**Type:** SaaS platform (by LangChain, with self-hosting option for enterprises).

**What it does:**

LangSmith is the evaluation and observability hub for LangChain applications. It traces every step of your RAG pipeline and provides tools for dataset curation, evaluation, and monitoring.

**Core features:**

| Feature | Description |
|---------|-------------|
| **Tracing** | Visual debugging of every LLM call, retriever step, and tool invocation. |
| **Datasets** | Curate evaluation datasets from production traces (filter by user, latency, feedback, etc.). |
| **Evaluation** | Run evaluators (RAGAS, custom LLM-as-Judge, pairwise comparison) on datasets. |
| **Annotation Queue** | Send traces to human reviewers for feedback. |
| **Monitoring** | Set up online evaluators that run on a sample of production traffic. |
| **Experiments** | Compare prompt/model/retriever variants side-by-side. |
| **Hub** | Share and discover prompts and evaluators. |

**Evaluation workflow:**

1. **Capture:** Log all traces from your production/debug environment.
2. **Curate:** Select representative traces to create an evaluation dataset.
3. **Evaluate:** Run evaluators (built-in correctness, custom RAGAS metrics, etc.).
4. **Compare:** Run experiments across different configurations.
5. **Monitor:** Continuously evaluate a sample of production traffic.

**Strengths:**
- Tightest LangChain/LangGraph integration — traces are automatically captured.
- Dataset curation from production is seamless (click → add to dataset).
- Annotation queues make human evaluation easy to incorporate.
- Strong experiment tracking (A/B testing, statistical significance).
- Extensive documentation and community.

**Weaknesses:**
- Primarily a LangChain platform; non-LangChain apps need manual instrumentation.
- SaaS pricing can be expensive at scale ($39+/month + per-trace costs).
- Built-in evaluators are limited; you'll likely integrate RAGAS or write custom evaluators.
- Vendor dependency on LangChain ecosystem.

**Best use cases:**
- Teams already using LangChain/LangGraph.
- Production monitoring and feedback collection.
- Iterative development with human-in-the-loop evaluation.

---

## 3. Hallucination Detection Methods

### 3.1 LLM-as-Judge

**Principle:** Use a strong LLM (GPT-4, Claude 3.5 Sonnet) to judge whether a generated answer is supported by the retrieval context.

**How it works:**

1. **Claim decomposition:** The answer is split into atomic claims (e.g., "The Eiffel Tower was built in 1887 by Gustave Eiffel" → Claim 1: "Eiffel Tower was built in 1887", Claim 2: "built by Gustave Eiffel").
2. **Entailment check:** For each claim, the LLM is prompted: *"Given the context: <context>, is the claim '<claim>' supported? Answer Yes/No with explanation."*
3. **Aggregation:** Faithfulness = `supported_claims / total_claims`.

**Prompt engineering matters significantly:**
- Chain-of-thought: "First, identify the relevant part of the context. Then, explain whether the claim follows from it."
- Few-shot examples improve reliability.
- Structured output (JSON) enables programmatic parsing.

**Used by:** RAGAS, DeepEval (G-Eval), TruLens, LangSmith.

**Pros:**
- High accuracy when using GPT-4/Claude (85–90% agreement with human annotators).
- No training data needed.
- Flexible: can detect nuanced hallucinations (implicit contradictions, exaggerations).

**Cons:**
- Expensive: 3–5 LLM calls per answer.
- Latency: 2–5 seconds per answer.
- LLM bias: the judge LLM may have its own hallucination tendencies.
- Prompt sensitivity: small prompt changes can swing accuracy by 10%+.

---

### 3.2 NLI-Based Detection

**Principle:** Use a fine-tuned Natural Language Inference model to classify claims as entailed, contradicted, or neutral given the context.

**How it works:**

1. Decompose the answer into claims.
2. For each claim, feed `(premise=context, hypothesis=claim)` to an NLI model.
3. Entailment → supported; contradiction → hallucination; neutral → unsupported.
4. Score = `entailed / total`.

**Common NLI models:**
- `roberta-large-mnli` (RoBERTa fine-tuned on MultiNLI).
- `deberta-v3-large-anli` (DeBERTa fine-tuned on Adversarial NLI).
- `flan-t5-xl-nli` (T5-based NLI, handles longer contexts).

**Used by:** DeepEval (primary faithfulness metric).

**Pros:**
- Fast: <100ms per claim (local inference).
- Cheap: no API costs.
- Deterministic.
- Well-studied in NLP; NLI accuracy on ANLI is ~90%.

**Cons:**
- Limited context window: most NLI models support only 512 tokens (context + claim must fit).
- Coarse-grained: entailment/contradiction is binary; cannot detect partial support.
- Domain shift: models trained on MNLI/ANLI may underperform on specialized domains.
- Cannot handle implicit claims or reasoning chains.

---

### 3.3 Specialized Hallucination Detection Models

**Principle:** Train or fine-tune a model specifically for hallucination detection in RAG settings.

**Notable models:**

| Model | Approach | Notes |
|-------|----------|-------|
| **SelfCheckGPT** | Sampling multiple responses; if factual claims vary across samples, hallucination is likely. | Uses BERTScore between samples. Faster than LLM judge but requires multiple generations. |
| **LM vs LM** | An examiner LLM cross-examines the generated answer via follow-up questions. | Detecting inconsistency across the examiner's Q&A. High accuracy but expensive. |
| **HHEM (Hierarchical Hallucination Evaluation Model)** | Fine-tuned DeBERTa on hallucination detection datasets. | Fast, purpose-built for RAG. Available on HuggingFace. |
| **AlignScore** | Fine-tuned model predicting factual alignment between context and generation. | Scored 0–1; 0 = hallucinated, 1 = fully grounded. |
| **MiniCheck** | BERT-based model fine-tuned for sentence-level factuality checking. | Lightweight, fast; good for real-time detection. |

**Pros:**
- Purpose-built: optimized for the exact task.
- Faster and cheaper than LLM-as-Judge.
- Can achieve specialized domain accuracy with fine-tuning.

**Cons:**
- Requires training data (hallucination annotations).
- May not generalize across domains.
- Research-stage models — less community support than frameworks.

---

### 3.4 Internal State Methods

**Principle:** Probe the LLM's internal representations (hidden states, attention patterns, logit distribution) during generation to detect uncertainty or hallucination risk.

**Techniques:**

| Technique | Description |
|-----------|-------------|
| **Token probability / entropy** | Low probability or high entropy in output tokens suggests uncertainty → higher hallucination risk. |
| **Hidden state probing** | Train a linear classifier on LLM hidden states to predict whether a generated token is factual. |
| **Attention pattern analysis** | Hallucinated tokens show different attention distribution patterns (less focused on input context). |
| **Logit lens / tuned lens** | Decode from intermediate layers to detect divergence between early and late predictions. |
| **Inside-Transformer** | Use the LLM's own internal consistency across layers as a signal. |

**Pros:**
- Zero additional cost (no extra LLM calls).
- Real-time: can flag potential hallucinations during streaming.
- Model-agnostic probing (works with any transformer).

**Cons:**
- Requires white-box access to the model (not available with API-only models like GPT-4).
- Probing classifiers need training data.
- Research-stage; not production-ready.
- Correlation is weak: entropy ≠ hallucination in many cases (creative outputs have high entropy but are fine).

---

### 3.5 Self-Consistency

**Principle:** Generate multiple responses (varying temperature, sampling) and measure agreement. Inconsistent factual claims are likely hallucinated.

**Variants:**

| Variant | Description |
|---------|-------------|
| **Naive self-consistency** | Generate N responses; measure BERTScore / ROUGE between pairs. Low similarity → hallucination. |
| **Fact-level consistency** | Extract facts from each response; cluster facts; check which facts appear in all responses vs. only some. |
| **Cross-examination** | One LLM generates; another LLM asks follow-up questions to probe accuracy. |

**Pros:**
- No training data needed.
- Works with any LLM.
- Intuitive principle: truth is consistent.

**Cons:**
- High cost: N× the inference cost per query.
- Systematic errors: the model may consistently hallucinate the same wrong fact.
- Temperature tuning is delicate: too low → no diversity; too high → incoherent responses.

---

### 3.6 Reference-Based Detection

**Principle:** Compare the generated answer against a ground-truth reference answer.

**Techniques:**

| Technique | Description |
|-----------|-------------|
| **Exact match / F1** | Simple token-overlap with reference. Fast but brittle. |
| **BERTScore** | Semantic similarity between answer and reference embeddings. |
| **NLI against reference** | Treat reference as premise, answer as hypothesis. Entailment → correct; contradiction → hallucination. |
| **Fact extraction + comparison** | Extract facts from both answer and reference; check set overlap. |

**Pros:**
- Gold standard when references are available and reliable.
- Fast and deterministic (non-LLM methods).
- Well-established in NLP.

**Cons:**
- Requires ground truth — expensive to create.
- References may be incomplete (valid answers missing from reference).
- Lexical methods (F1, BLEU) correlate poorly with human judgment.

---

### 3.7 Human Evaluation

**Principle:** Human annotators rate generated answers for hallucination, faithfulness, and overall quality.

**Protocols:**

| Protocol | Scale | Description |
|----------|-------|-------------|
| **Binary** | Hallucination / No hallucination | Simple, high inter-annotator agreement. |
| **Likert (1–5)** | 1 = fully hallucinated, 5 = perfectly grounded | More nuanced; moderate agreement. |
| **Best-Worst Scaling** | Annotator picks best/worst from 4–5 options | High reliability; slow. |
| **Error annotation** | Annotator highlights specific hallucinated spans | Richer signal; expensive. |

**Pros:**
- Gold standard: highest accuracy.
- Captures nuance that automated metrics miss.
- Provides training data for automated methods.

**Cons:**
- Expensive: $0.10–$1.00 per annotation.
- Slow: days to weeks for large-scale evaluation.
- Inter-annotator variability: requires multiple annotators per example.
- Not scalable for CI/CD or production monitoring.

---

## 4. Groundedness Scoring Across Frameworks

Groundedness (also called "faithfulness" or "context adherence") is the most critical RAG metric. Here's how each framework approaches it:

| Framework | Method | Model | Granularity | Score Range |
|-----------|--------|-------|-------------|-------------|
| **RAGAS** | Claim decomposition → LLM entailment check | GPT-3.5/4 | Per-claim → aggregated | 0–1 |
| **DeepEval** | Claim decomposition → NLI model (DeBERTa) | DeBERTa-v3-ANLI | Per-claim → aggregated | 0–1 |
| **GroUSE** | LLM judge with failure-mode rubric | GPT-4 | Per-example | Pass/Fail |
| **Open-RAG-Eval** | ROUGE / BERTScore / LLM-as-Judge | Multiple | Per-example | Dataset-dependent |
| **RAGBench** | LLM claim decomposition + entailment | GPT-4 | Per-claim → aggregated | 0–1 |
| **TruLens** | LLM with chain-of-thought context check | GPT-3.5/4 | Per-sentence → aggregated | 0–1 |
| **LangSmith** | Bring-your-own (typically RAGAS or custom LLM judge) | User choice | User-defined | 0–1 |
| **Galileo** | Proprietary fine-tuned LLM evaluator | Proprietary | Per-sentence with chunk attribution | 0–1 |
| **SelfCheckGPT** | Multi-sample consistency + BERTScore | Feature-based | Per-fact | 0–1 |
| **AlignScore** | Fine-tuned factual alignment model | Fine-tuned RoBERTa | Per-sentence | 0–1 |
| **MiniCheck** | Fine-tuned BERT for factuality | BERT-based | Per-sentence | 0–1 |
| **NLI (MNLI/ANLI)** | Premise-hypothesis entailment | RoBERTa/DeBERTa | Per-claim | Entail/Neutral/Contradict |

### Trade-off Summary

| Method | Accuracy | Speed | Cost | Setup Complexity |
|--------|----------|-------|------|-----------------|
| LLM-as-Judge (GPT-4) | ★★★★★ | ★★ | $$$$ | ★ |
| LLM-as-Judge (GPT-3.5) | ★★★★ | ★★★ | $$ | ★ |
| NLI-based (DeBERTa) | ★★★ | ★★★★★ | $ | ★★ |
| Specialized models (AlignScore, MiniCheck) | ★★★★ | ★★★★ | $ | ★★★★ |
| Self-consistency | ★★★★ | ★ | $$$$$ | ★★ |
| Human evaluation | ★★★★★ | ★ | $$$$$$ | ★★★★★ |

---

## 5. Framework Recommendations by Team Profile

### Solo Developer / Indie Hacker

**Constraints:** Limited budget ($0–$50/month), no DevOps support, fast iteration cycle.

**Recommendation: DeepEval (local) + Phoenix (self-hosted)**

| Layer | Tool | Why |
|-------|------|-----|
| Evaluation | **DeepEval** | NLI-based faithfulness is free and fast. pytest integration fits solo developer workflow. Run locally, no cloud dependency. |
| Observability | **Arize Phoenix** | Self-hosted, open-source. Embedding visualization helps debug retrieval quality without an ops team. |
| Hallucination detection | **DeepEval Faithfulness** (NLI) + **MiniCheck** as fallback | Cheap, fast, local. |

**Avoid:** Galileo (enterprise SaaS pricing), LangSmith (per-trace costs add up), heavy GPT-4 judging (cost-prohibitive at scale).

**Estimated monthly cost:** $0 (all tools open-source, self-hosted).

---

### Small Team (2–10 engineers)

**Constraints:** Moderate budget ($100–$500/month), shared infrastructure, need for team-wide visibility.

**Recommendation: RAGAS + LangSmith**

| Layer | Tool | Why |
|-------|------|-----|
| Evaluation | **RAGAS** | Most comprehensive metrics, strong community, integrated into LangChain. |
| Observability | **LangSmith** | Team dashboard, shared annotation queues, experiment tracking. |
| Offline testing | **RAGAS + DeepEval** | Run RAGAS for aggregate scoring, DeepEval for CI gatekeeping. |

**Estimated monthly cost:** ~$40–$200 (LangSmith, GPT-4 API calls for evaluation). Switch to GPT-3.5 to cut costs 3× with moderate accuracy loss.

---

### Growth-Stage Startup (10–50 engineers)

**Constraints:** $500–$2,000/month, multiple RAG pipelines, need production monitoring.

**Recommendation: DeepEval (CI) + LangSmith (observability) + custom evaluators**

| Layer | Tool | Why |
|-------|------|-----|
| CI evaluation | **DeepEval** | pytest integration, deterministic thresholds, fast NLI metrics keep CI runs cheap. |
| Production monitoring | **LangSmith** | Sampled production trace evaluation, drift detection, annotation queues. |
| Custom evaluation | **RAGAS + GPT-4** | Run on curated evaluation datasets weekly; not per-request. |
| Offline benchmarking | **BEIR + MTEB** | Quarterly benchmarking of retrieval and embedding models. |

**Add:** GroUSE for targeted failure-mode debugging when issues arise.

**Estimated monthly cost:** ~$500–$1,500 (LangSmith team plan, GPT-4 for curated evaluations, CI compute).

---

### Enterprise (50+ engineers)

**Constraints:** $2,000+/month, compliance/SLAs, multiple teams, need for governance.

**Recommendation: Multi-layered evaluation stack**

| Layer | Tool | Why |
|-------|------|-----|
| CI evaluation | **DeepEval** (per-PR, fast NLI) | Low latency gate for every PR. |
| Weekly evaluation | **RAGAS** (batch, GPT-4) | Deep evaluation on curated datasets. |
| Production monitoring | **LangSmith** or **Galileo** | Sampled trace evaluation, automatic flagging of low-quality responses. |
| Human evaluation | **LangSmith Annotation Queues** or **Label Studio** | Monthly human review of 500–1,000 samples. |
| Observability | **Arize Phoenix** | Embedding drift detection across all pipelines. |
| Ground truth curation | **Custom pipeline in LangSmith** | Continuously build evaluation datasets from production traffic. |
| Security/Compliance | **Galileo Guardrails** (PII, prompt injection) or custom guard evaluators in DeepEval. | Required for SOC2/HIPAA. |

**Governance workflow:**
1. Every PR → DeepEval CI (must pass NLI-based faithfulness > 0.7).
2. Weekly → RAGAS batch with GPT-4 on 10k curated examples.
3. Monthly → Human annotation on 500 samples; use to calibrate automated metrics.
4. Continuous → LangSmith production sampling (1% of traffic, automatic flagging).

**Estimated monthly cost:** $2,000–$5,000 (SaaS plans, GPT-4 evaluation, human annotation, CI compute).

---

## 6. Decision Matrix

| Criterion | RAGAS | DeepEval | GroUSE | Open-RAG-Eval | RAGBench | BEIR | MTEB | TruLens | Phoenix | Galileo | LangSmith |
|-----------|-------|----------|--------|---------------|----------|------|------|---------|---------|---------|-----------|
| **Reference-free** | ✅ | ✅ | ✅ | ❌ | ❌ | N/A | N/A | ✅ | — | ✅ | — |
| **Offline evaluation** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Online/production** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **CI/CD integration** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **Built-in UI** | ❌ | ✅(cloud) | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Human annotation** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Drift detection** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Self-hosted** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅(ent) |
| **Open-source** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Cost** | Free + LLM API | Free + LLM API | Free + GPT-4 | Free | Free + GPT-4 | Free | Free | Free + LLM API | Free + LLM API | $$$ | $$ |
| **Retrieval-only eval** | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **LangChain native** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| **Multi-modal** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Custom metrics** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |

---

### Quick Decision Guide

| If you need to... | Use... |
|--------------------|-------|
| Evaluate RAG quality without ground truth | **RAGAS** or **DeepEval** |
| Run cheap, fast faithfulness checks | **DeepEval** (NLI mode) |
| Get the most accurate faithfulness score | **GPT-4 as Judge** (via RAGAS or custom) |
| Compare retrieval models head-to-head | **BEIR** |
| Compare embedding models | **MTEB** |
| Debug specific RAG failure modes | **GroUSE** |
| Benchmark across domains | **RAGBench** |
| Monitor production RAG quality | **LangSmith**, **Galileo**, or **TruLens** |
| Visualize embedding drift | **Arize Phoenix** |
| Collect human feedback at scale | **LangSmith Annotation Queues** |
| Pass SOC2/HIPAA compliance | **Galileo** (enterprise) or self-hosted **DeepEval + Phoenix** |
| Set up CI/CD quality gates | **DeepEval** (`assert_test`) or **RAGAS** (custom script) |
| Minimal cost, maximal insight | **DeepEval** (NLI) + **Phoenix** (self-hosted) |

---

*Report compiled by RAG research subagent. Last updated: June 2025.*
