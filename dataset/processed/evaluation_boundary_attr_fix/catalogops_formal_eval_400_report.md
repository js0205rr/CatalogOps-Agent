# CatalogOps Formal Evaluation

- Input: `/notebook/workspace/CatalogOps-Agent/dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`
- Sample size: 400
- Mock mode: True
- Category accuracy: 90.75%
- Macro F1: 0.8035

## Issue Metrics
- category_mismatch: precision=0.9385, recall=0.9150, f1=0.9266, support=200
- attribute_missing: precision=0.9655, recall=0.9333, f1=0.9492, support=300
- title_issue: precision=0.2195, recall=1.0000, f1=0.3600, support=9
- any_issue: precision=0.9855, recall=0.9714, f1=0.9784, support=350

## Evidence Coverage
- Review issue evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Avg evidence per review: 13.00
- Issues without evidence: {}

## Runtime Cost
- Elapsed seconds: 15.366
- Rows per second: 26.030918
- Full review rows: 345
- Estimated LLM calls: 0
- Estimated token cost USD: 0.0