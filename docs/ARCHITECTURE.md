# CatalogOps-Agent Architecture

CatalogOps-Agent is a rule-first, evidence-backed catalog governance system for
pre-publication ecommerce review. The architecture separates deterministic catalog
rules, policy retrieval, evidence verification, batch governance, and API/UI
delivery so the MVP can run in mock mode while keeping a clear path to real
embedding and Milvus-backed retrieval.

The repository is organized as a small monorepo:

- `apps/api`: FastAPI app, REST routes, and WebSocket trace.
- `apps/web`: React product governance workbench.
- `packages/agent_core`: single-product LangGraph orchestration.
- `packages/catalog`: domain schemas.
- `packages/rag_policy`: policy ingestion, local mock retrieval, embedding retrieval, Milvus boundary, and reranker evaluation.
- `packages/batch_analysis`: CSV profiling, selective full review, aggregation, and report generation.
- `packages/observability`: trace helpers.
- `packages/evaluation`: evaluation exports.
- `packages/mocks`: mock-mode configuration and optional LLM wrapper.

## RAG-as-Policy

Policy retrieval is a tool boundary, not chat memory. Retrieved snippets become
`Evidence` objects and every `ComplianceIssue` must reference evidence before
publication decision. Issues that cannot be supported by evidence are downgraded
before the final decision node.

## Cost Control

The default path is deterministic: taxonomy rules, regex extraction, required-attribute checks, and local policy retrieval. LLM calls are reserved for low-confidence or complex revision suggestions and are skipped in mock mode.

## Evaluation Baseline

The current full formal evaluation runs on 27,548 ecommerce rows across `Books`,
`Clothing & Accessories`, `Electronics`, and `Household`.

- Category accuracy: 89.32%
- Issue macro F1: 0.7728
- Any issue F1: 0.9519
- Attribute missing F1: 0.9147
- Evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Mock-mode LLM calls: 0

Detailed sampled and full metrics are recorded in `docs/EVALUATION.md`.
