# CatalogOps Evaluation

This document records the current formal evaluation baseline for CatalogOps-Agent.
The benchmark covers the four Ecommerce Text Classification top-level domains:
`Books`, `Clothing & Accessories`, `Electronics`, and `Household`.

## Evaluation Setup

- Dataset: `dataset/processed/ecommerce_catalogops_mismatch_20pct.csv`
- Full rows: 27,548
- Labels:
  - `category_mismatch`: `attributes.source_category` differs from `seller_category`
  - `attribute_missing`: required attributes for the true/top category are absent
  - `title_issue`: deterministic title policy terms or title-rule violations
  - `any_issue`: union of category mismatch, attribute missing, and title issue
- Mode: mock mode, rule-first, no LLM calls
- Policy ingestion: local deterministic policy index
- Raw batch JSON: skipped for 5,000-row and full runs to avoid large artifacts

Run:

```bash
python scripts/evaluate_catalogops_formal.py --sample-size 5000 --output-dir dataset/processed/evaluation_5000 --skip-raw-batch-report
python scripts/evaluate_catalogops_formal.py --sample-size 999999 --output-dir dataset/processed/evaluation_full --skip-raw-batch-report
```

## Results

| Metric | 400 rows | 5,000 rows | Full 27,548 rows |
| --- | ---: | ---: | ---: |
| Category accuracy | 90.75% | 90.46% | 89.32% |
| Issue macro F1 | 0.8035 | 0.7895 | 0.7728 |
| Category mismatch precision | 0.9385 | 0.9040 | 0.6961 |
| Category mismatch recall | 0.9150 | 0.9680 | 0.9502 |
| Category mismatch F1 | 0.9266 | 0.9349 | 0.8036 |
| Attribute missing precision | 0.9655 | 0.9747 | 0.9688 |
| Attribute missing recall | 0.9333 | 0.8933 | 0.8663 |
| Attribute missing F1 | 0.9492 | 0.9322 | 0.9147 |
| Title issue precision | 0.2195 | 0.1843 | 0.2667 |
| Title issue recall | 1.0000 | 1.0000 | 1.0000 |
| Title issue F1 | 0.3600 | 0.3112 | 0.4211 |
| Any issue precision | 0.9855 | 0.9895 | 0.9780 |
| Any issue recall | 0.9714 | 0.9704 | 0.9272 |
| Any issue F1 | 0.9784 | 0.9799 | 0.9519 |
| Evidence coverage | 100.00% | 100.00% | 100.00% |
| Policy context hit rate | 100.00% | 100.00% | 100.00% |
| Full review rows | 345 | 4,303 | 21,958 |
| Runtime | 15.366s | 185.622s | 964.327s |
| Estimated LLM calls | 0 | 0 | 0 |
| Estimated token cost | $0.00 | $0.00 | $0.00 |

## Interpretation

The full-dataset baseline is strong for broad issue detection and required-attribute
governance: `any_issue` F1 is 0.9519 and `attribute_missing` F1 is 0.9147. Evidence
coverage remains 100%, which confirms that automated review conclusions are backed
by product, taxonomy, attribute-schema, or policy evidence.

The main known weakness is category-mismatch precision on the full dataset. The
5,000-row run is stratified and has a higher mismatch-positive rate, while the full
dataset contains about 20% injected mismatch positives. That class-prior shift makes
false positives more visible in the full run even though category-mismatch recall
remains high at 0.9502.

Title issue detection is intentionally recall-oriented. It catches all labeled title
issues in these runs, but precision remains low because some category-conflict title
rules are conservative and fire on ambiguous cross-category signals.

## Artifacts

- `dataset/processed/evaluation_5000/catalogops_formal_eval_5000_summary.json`
- `dataset/processed/evaluation_5000/catalogops_formal_eval_5000_report.md`
- `dataset/processed/evaluation_5000/catalogops_formal_eval_5000_predictions.csv`
- `dataset/processed/evaluation_full/catalogops_formal_eval_27548_summary.json`
- `dataset/processed/evaluation_full/catalogops_formal_eval_27548_report.md`
- `dataset/processed/evaluation_full/catalogops_formal_eval_27548_predictions.csv`
