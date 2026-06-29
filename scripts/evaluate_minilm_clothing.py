from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from packages.agent_core.catalog_rules import predict_category_rule
from packages.catalog.category_predictor import check_category_consistency
from packages.catalog.schemas import ProductInput
from packages.catalog.taxonomy import load_category_keywords


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "all-MiniLM-L6-v2"
DEFAULT_LABELS_PATH = ROOT / "dataset" / "processed" / "clothing_labels.csv"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_labels(path: Path) -> dict[str, dict[str, str]]:
    return {row["product_id"]: row for row in _read_csv(path)}


def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_attributes(value: str) -> dict[str, str]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(item) for key, item in data.items() if item not in (None, "")}


def _row_to_product(row: dict[str, str]) -> ProductInput:
    seller_category = row.get("seller_category", "")
    return ProductInput(
        sku_id=row.get("product_id") or "unknown",
        title=(row.get("title") or "Untitled product")[:300],
        description=(row.get("description") or "")[:5000],
        seller_category=seller_category,
        merchant_category=seller_category,
        attributes=_parse_attributes(row.get("attributes", "")),
    )


def _clothing_category_docs() -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for item in load_category_keywords():
        path = str(item.get("category_path", ""))
        if not path.startswith("Clothing & Accessories > "):
            continue
        keywords = ", ".join(str(keyword) for keyword in item.get("keywords", []))
        docs.append(
            {
                "category_id": str(item.get("category_id", "")),
                "category_path": path,
                "text": f"{path}. Product category keywords: {keywords}.",
            }
        )
    return docs


def _metrics(counts: Counter[str]) -> dict[str, Any]:
    total = sum(counts.values())
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {
        "confusion": dict(counts),
        "actual_mismatch_rate": round((counts["tp"] + counts["fn"]) / total, 4) if total else 0,
        "predicted_mismatch_rate": round((counts["tp"] + counts["fp"]) / total, 4) if total else 0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _prediction_metrics(
    rows: list[dict[str, str]],
    labels: dict[str, dict[str, str]],
    predicted_paths: list[str],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    category_correct = 0
    for row, predicted_path in zip(rows, predicted_paths):
        label = labels.get(row.get("product_id", ""), {})
        gold = label.get("gold_category", "")
        actual_mismatch = _is_true(label.get("synthetic_mismatch", ""))
        seller_category = row.get("seller_category", "")
        predicted_mismatch = seller_category.strip() != predicted_path.strip()
        if predicted_path.strip() == gold.strip():
            category_correct += 1
        if actual_mismatch and predicted_mismatch:
            counts["tp"] += 1
        elif actual_mismatch and not predicted_mismatch:
            counts["fn"] += 1
        elif not actual_mismatch and predicted_mismatch:
            counts["fp"] += 1
        else:
            counts["tn"] += 1
    return {
        "category_accuracy": round(category_correct / len(rows), 4) if rows else 0,
        "mismatch_detection": _metrics(counts),
    }


def evaluate(csv_path: Path, labels_path: Path, model_path: Path, batch_size: int) -> dict[str, Any]:
    start = time.perf_counter()
    rows = _read_csv(csv_path)
    labels = _load_labels(labels_path)
    products = [_row_to_product(row) for row in rows]

    rule_paths: list[str] = []
    rule_statuses: Counter[str] = Counter()
    for product in products:
        prediction = predict_category_rule(product)
        check = check_category_consistency(product.seller_category, prediction)
        rule_paths.append(prediction.category_path)
        rule_statuses[check.status] += 1

    categories = _clothing_category_docs()
    model = SentenceTransformer(str(model_path), device="cpu")
    label_embeddings = model.encode(
        [item["text"] for item in categories],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    product_texts = [
        f"{row.get('title', '')}. {row.get('description', '')[:3000]}. Attributes: {row.get('attributes', '')}"
        for row in rows
    ]
    product_embeddings = model.encode(
        product_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    scores = np.asarray(product_embeddings) @ np.asarray(label_embeddings).T
    order = np.argsort(-scores, axis=1)
    minilm_paths = [categories[int(indexes[0])]["category_path"] for indexes in order]
    margins = [
        float(scores[row_index, indexes[0]] - scores[row_index, indexes[1]])
        if len(indexes) > 1
        else 0.0
        for row_index, indexes in enumerate(order)
    ]

    hybrid_paths = [
        minilm_path if margin >= 0.015 else rule_path
        for rule_path, minilm_path, margin in zip(rule_paths, minilm_paths, margins)
    ]

    result = {
        "csv_path": str(csv_path),
        "row_count": len(rows),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "model_path": str(model_path),
        "rule": _prediction_metrics(rows, labels, rule_paths),
        "minilm": _prediction_metrics(rows, labels, minilm_paths),
        "hybrid_margin_0_015": _prediction_metrics(rows, labels, hybrid_paths),
        "diagnostics": {
            "rule_status_counts": dict(rule_statuses),
            "minilm_margin_avg": round(float(np.mean(margins)), 4) if margins else 0,
            "minilm_margin_p50": round(float(np.median(margins)), 4) if margins else 0,
            "minilm_top_categories": dict(Counter(minilm_paths).most_common(10)),
            "rule_top_categories": dict(Counter(rule_paths).most_common(10)),
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MiniLM baseline on Clothing data.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_PATH))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = evaluate(Path(args.csv), Path(args.labels), Path(args.model_path), args.batch_size)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
