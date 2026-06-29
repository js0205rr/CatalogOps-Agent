# CatalogOps Demo Script

## Single Product Review

Run the API and submit a clothing product with an overclaim title and missing brand:

```json
{
  "sku_id": "P1002",
  "title": "best 100% guaranteed cotton shirt white",
  "description": "Basic short sleeve top. Size: M.",
  "seller_category": "Clothing & Accessories > Tops",
  "merchant_category": "Clothing & Accessories > Tops",
  "attributes": {"material": "cotton", "size": "M", "color": "white"}
}
```

Expected result: title violation, missing brand attribute, evidence-backed issues, and `reject` or `human_review`.

## Batch Review

Upload `data/sample_products/sample_products.csv` in the web batch page, or call:

1. `POST /api/batch/upload`
2. `POST /api/batch/{batch_id}/run`
3. `GET /api/batch/{batch_id}/report`

Expected result: CSV profile, selected full-review rows, issue summary, and markdown report.

## Policy Knowledge

Ask whether a title can claim "best" or "100% guaranteed". The policy QA endpoint `POST /api/chat/policy` should return title-policy evidence.
