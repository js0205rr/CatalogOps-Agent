# CatalogOps Formal Evaluation

- Input: `/notebook/workspace/CatalogOps-Agent/dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`
- Sample size: 400
- Mock mode: True
- Category accuracy: 55.50%
- Macro F1: 0.6208

## Issue Metrics
- category_mismatch: precision=0.6844, recall=0.7700, f1=0.7247, support=200
- attribute_missing: precision=0.9545, recall=0.5600, f1=0.7059, support=300
- title_issue: precision=0.1286, recall=1.0000, f1=0.2278, support=9
- any_issue: precision=0.9920, recall=0.7057, f1=0.8247, support=350

## Evidence Coverage
- Review issue evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Avg evidence per review: 13.00
- Issues without evidence: {}

## Runtime Cost
- Elapsed seconds: 8.17
- Rows per second: 48.958668
- Full review rows: 249
- Estimated LLM calls: 0
- Estimated token cost USD: 0.0