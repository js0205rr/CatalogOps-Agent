# CatalogOps Formal Evaluation

- Input: `/notebook/workspace/CatalogOps-Agent/dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`
- Sample size: 5000
- Mock mode: True
- Category accuracy: 90.46%
- Macro F1: 0.7895

## Issue Metrics
- category_mismatch: precision=0.9040, recall=0.9680, f1=0.9349, support=2500
- attribute_missing: precision=0.9747, recall=0.8933, f1=0.9322, support=3750
- title_issue: precision=0.1843, recall=1.0000, f1=0.3112, support=103
- any_issue: precision=0.9895, recall=0.9704, f1=0.9799, support=4388

## Evidence Coverage
- Review issue evidence coverage: 100.00%
- Policy context hit rate: 100.00%
- Avg evidence per review: 13.00
- Issues without evidence: {}

## Runtime Cost
- Elapsed seconds: 185.622
- Rows per second: 26.936414
- Full review rows: 4303
- Estimated LLM calls: 0
- Estimated token cost USD: 0.0