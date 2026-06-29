# CatalogOps Formal Evaluation

- Input: `/notebook/workspace/CatalogOps-Agent/dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`
- Sample size: 27548
- Mock mode: True
- Category accuracy: 89.32%
- Macro F1: 0.7728

## Issue Metrics
- category_mismatch: precision=0.6961, recall=0.9502, f1=0.8036, support=5663
- attribute_missing: precision=0.9688, recall=0.8663, f1=0.9147, support=21920
- title_issue: precision=0.2667, recall=1.0000, f1=0.4211, support=567
- any_issue: precision=0.9780, recall=0.9272, f1=0.9519, support=23160

## Evidence Coverage
- Review issue evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Avg evidence per review: 13.00
- Issues without evidence: {}

## Runtime Cost
- Elapsed seconds: 964.327
- Rows per second: 28.56707
- Full review rows: 21958
- Estimated LLM calls: 0
- Estimated token cost USD: 0.0