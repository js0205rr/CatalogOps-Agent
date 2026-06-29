# CatalogOps-Agent

CatalogOps-Agent is a rule-first, evidence-backed product catalog governance system for pre-publication ecommerce review. It combines LangGraph multi-agent orchestration, category prediction, required-attribute validation, Hybrid RAG policy retrieval, evidence verification, batch CSV governance reports, and FastAPI/React operator workflows.

The MVP focuses on text and CSV catalog data. It does not audit images, does not execute model-generated code, and keeps mock mode available for deterministic local and notebook experiments. LLM usage is reserved for low-confidence cases or complex explanations; the default review path uses taxonomy rules, MiniLM/LinearSVM category assets, attribute rules, policy retrieval, and evidence checks before any model call.

Every publish decision is tied to evidence. Issues without sufficient evidence are downgraded to uncertain or human-review paths instead of being treated as final automated conclusions.

## Current Baseline

Formal evaluation now runs on the four Ecommerce Text Classification top-level domains: `Books`, `Clothing & Accessories`, `Electronics`, and `Household`. The full benchmark uses `dataset/processed/ecommerce_catalogops_mismatch_20pct.csv` with 27,548 rows and a controlled category-mismatch injection rate of about 20%.

Latest full-run mock-mode baseline:

| Metric | Full dataset |
| --- | ---: |
| Rows | 27,548 |
| Category accuracy | 89.32% |
| Issue macro F1 | 0.7728 |
| Category mismatch precision / recall / F1 | 0.6961 / 0.9502 / 0.8036 |
| Attribute missing precision / recall / F1 | 0.9688 / 0.8663 / 0.9147 |
| Title issue precision / recall / F1 | 0.2667 / 1.0000 / 0.4211 |
| Any issue precision / recall / F1 | 0.9780 / 0.9272 / 0.9519 |
| Evidence coverage | 100.00% |
| Policy context hit rate | 100.00% |
| Full review rows | 21,958 |
| Runtime | 964.327s |
| Estimated LLM calls / token cost | 0 / $0.00 |

See `docs/EVALUATION.md` for 400-row, 5,000-row, and full-dataset comparisons.

## Project Layout

- `apps/api`: FastAPI app, REST endpoints, WebSocket trace.
- `apps/web`: React operator workbench.
- `packages/agent_core`: single-product LangGraph review workflow.
- `packages/catalog`: Pydantic domain schemas.
- `packages/rag_policy`: policy retrieval, ingestion, local mock retriever, and RAG tools.
- `packages/batch_analysis`: batch CSV profiling, selective review, and report generation.
- `packages/observability`: trace helpers.
- `packages/evaluation`: evaluation exports and metrics.
- `packages/mocks`: mock-mode settings and optional LLM wrappers.
- `data`: sample products, taxonomy, policy docs, and eval data.
- `scripts`: local CLI utilities.
- `tests`: smoke and workflow tests.
- `docs`: specification, architecture, and demo script.


## API

- `GET /health`
- `POST /api/reviews/single`
- `POST /api/batch/upload`
- `POST /api/batch/{batch_id}/run`
- `GET /api/batch/{batch_id}/report`
- `POST /api/documents/upload`
- `POST /api/documents/ingest`
- `GET /api/documents`
- `POST /api/chat/policy`
- `POST /api/policy/category`
- `POST /api/policy/attributes`
- `POST /api/policy/title`
- `WebSocket /api/runs/{run_id}/events`

Mock mode is enabled by default through `CATALOGOPS_MOCK_LLM=true`, so the basic product review, batch review, policy retrieval, and smoke tests do not require API keys, Milvus, or PostgreSQL.

Policy document ingestion:

```bash
python scripts/ingest_policy_docs.py
```

`USE_MOCK=true` writes a deterministic local policy index without Milvus or embedding services.
Set `USE_MOCK=false`, `MILVUS_URI`, and `POLICY_EMBEDDING_PROVIDER=minilm` to ingest
policy chunks into Milvus with the local MiniLM model.

Policy retrieval evaluation:

```bash
python scripts/evaluate_policy_rag_retrieval.py
```

Without `MILVUS_URI`, the script evaluates local retrieval/reranker variants and skips
Milvus variants. With `MILVUS_URI` set, it ingests policy docs and compares Milvus
dense retrieval with `none`, `lexical`, and `semantic` reranker modes.

Catalog governance formal evaluation:

```bash
python scripts/evaluate_catalogops_formal.py --sample-size 5000 --output-dir dataset/processed/evaluation_5000 --skip-raw-batch-report
python scripts/evaluate_catalogops_formal.py --sample-size 999999 --output-dir dataset/processed/evaluation_full --skip-raw-batch-report
```

`--skip-raw-batch-report` keeps summary, markdown report, and prediction CSV while avoiding very large raw batch JSON files.
