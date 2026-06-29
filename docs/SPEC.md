# CatalogOps-Agent SPEC

## Objective

CatalogOps-Agent reviews ecommerce product listings before publication. The MVP handles text and CSV only: product title, description, merchant category, and attributes.

The system is rule-first and evidence-first. Category prediction, attribute checks, title policy checks, and policy retrieval run before optional LLM usage. Any automated conclusion that lacks evidence must be downgraded to `uncertain` or `human_review`.

## Single Product Graph

1. `parse_input`
2. `predict_category`
3. `check_category_consistency`
4. `retrieve_policy`
5. `extract_attributes`
6. `check_attribute_completeness`
7. `check_title_compliance`
8. `generate_revision_suggestion`
9. `verify_evidence`
10. `make_publish_decision`

## Batch CSV Graph

1. `profile_catalog_csv`
2. `plan_batch_strategy`
3. `run_batch_precheck`
4. `run_batch_category_prediction`
5. `selective_policy_retrieval`
6. `aggregate_batch_issues`
7. `generate_batch_report`

## Current Evaluation Baseline

The formal benchmark covers `Books`, `Clothing & Accessories`, `Electronics`, and `Household` using `dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`.

Full-dataset mock-mode baseline, 27,548 rows:

- Category accuracy: 89.32%
- Issue macro F1: 0.7728
- Category mismatch precision / recall / F1: 0.6961 / 0.9502 / 0.8036
- Attribute missing precision / recall / F1: 0.9688 / 0.8663 / 0.9147
- Title issue precision / recall / F1: 0.2667 / 1.0000 / 0.4211
- Any issue precision / recall / F1: 0.9780 / 0.9272 / 0.9519
- Evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Runtime: 964.327s
- Estimated LLM calls / token cost: 0 / $0.00

See `docs/EVALUATION.md` for sampled and full-run comparisons.

## Constraints

- The agent must not execute model-generated code.
- Tool inputs and outputs use Pydantic schemas.
- LLM usage is optional and must produce structured JSON with fallback.
- Rules and policy evidence run before LLM calls.
- Conclusions without evidence are downgraded to `uncertain` or `human_review`.
- No multimodal image audit is included in the MVP.
