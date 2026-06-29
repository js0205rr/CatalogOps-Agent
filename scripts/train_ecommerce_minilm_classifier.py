from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CLEAN_CSV = ROOT / "dataset" / "processed" / "ecommerce_catalogops_clean.csv"
DEFAULT_MISMATCH_CSV = ROOT / "dataset" / "processed" / "ecommerce_catalogops_mismatch_20pct.csv"
DEFAULT_LABELS_CSV = ROOT / "dataset" / "processed" / "ecommerce_labels.csv"
DEFAULT_TAXONOMY_JSON = ROOT / "dataset" / "processed" / "ecommerce_taxonomy.json"
DEFAULT_MODEL_PATH = ROOT / "models" / "all-MiniLM-L6-v2"
DEFAULT_OUTPUT = ROOT / "dataset" / "processed" / "model_eval" / "ecommerce_supervised_minilm.json"
DEFAULT_LOGREG_ARTIFACT = ROOT / "models" / "ecommerce_minilm_logreg.joblib"
DEFAULT_SVM_ARTIFACT = ROOT / "models" / "ecommerce_minilm_linearsvm.joblib"

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Clothing & Accessories": (
        "apparel",
        "clothing",
        "wear",
        "shirt",
        "dress",
        "shoe",
        "saree",
        "kurta",
        "jeans",
        "sunglasses",
        "bag",
        "cotton",
        "fashion",
    ),
    "Electronics": (
        "mobile",
        "phone",
        "smartphone",
        "laptop",
        "tablet",
        "camera",
        "bluetooth",
        "wireless",
        "headphone",
        "speaker",
        "charger",
        "battery",
        "usb",
        "memory card",
        "television",
        "led tv",
    ),
    "Household": (
        "home",
        "kitchen",
        "decor",
        "wall",
        "furniture",
        "bedsheet",
        "curtain",
        "cookware",
        "bottle",
        "container",
        "cleaning",
        "storage",
        "mattress",
        "painting",
        "lamp",
    ),
    "Books": (
        "book",
        "novel",
        "author",
        "paperback",
        "hardcover",
        "edition",
        "publisher",
        "story",
        "guide",
        "exam",
        "dictionary",
        "textbook",
        "volume",
        "chapter",
        "biography",
    ),
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_labels(path: Path) -> dict[str, dict[str, str]]:
    return {row["product_id"]: row for row in _read_csv(path)}


def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _product_text(row: dict[str, str], max_description_chars: int) -> str:
    return (
        f"Title: {row.get('title', '')}\n"
        f"Description: {row.get('description', '')[:max_description_chars]}\n"
        f"Attributes: {row.get('attributes', '')}"
    )


def _load_taxonomy(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("taxonomy must be a list")
    return [dict(item) for item in data]


def _category_docs(taxonomy: list[dict[str, Any]]) -> list[dict[str, str]]:
    docs: list[dict[str, str]] = []
    for item in taxonomy:
        path = str(item.get("category_path", ""))
        keywords = ", ".join(str(keyword) for keyword in item.get("keywords", []))
        docs.append(
            {
                "category_id": str(item.get("category_id", path)),
                "category_path": path,
                "text": f"{path}. Product category keywords: {keywords}.",
            }
        )
    return docs


class MiniLMEncoder:
    def __init__(self, model_path: Path, *, max_length: int = 256) -> None:
        self.model_path = model_path
        self.max_length = max_length
        self.backend = "sentence_transformers"
        self._sentence_model: Any | None = None
        self._tokenizer: Any | None = None
        self._transformer_model: Any | None = None
        try:
            from sentence_transformers import SentenceTransformer

            self._sentence_model = SentenceTransformer(str(model_path), device="cpu")
        except ImportError:
            self.backend = "transformers"
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                local_files_only=True,
            )
            self._transformer_model = AutoModel.from_pretrained(
                str(model_path),
                local_files_only=True,
            )
            self._transformer_model.eval()

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        normalize_embeddings: bool = True,
        show_progress_bar: bool = False,
    ) -> np.ndarray:
        if self._sentence_model is not None:
            return np.asarray(
                self._sentence_model.encode(
                    texts,
                    batch_size=batch_size,
                    normalize_embeddings=normalize_embeddings,
                    show_progress_bar=show_progress_bar,
                ),
                dtype=np.float32,
            )
        return self._encode_with_transformers(
            texts,
            batch_size=batch_size,
            normalize_embeddings=normalize_embeddings,
        )

    def _encode_with_transformers(
        self,
        texts: list[str],
        *,
        batch_size: int,
        normalize_embeddings: bool,
    ) -> np.ndarray:
        import torch
        import torch.nn.functional as functional

        if self._tokenizer is None or self._transformer_model is None:
            raise RuntimeError("transformers backend was not initialized")

        batches: list[np.ndarray] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                encoded = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                output = self._transformer_model(**encoded)
                token_embeddings = output.last_hidden_state
                attention_mask = encoded["attention_mask"].unsqueeze(-1).float()
                pooled = (token_embeddings * attention_mask).sum(dim=1)
                pooled = pooled / attention_mask.sum(dim=1).clamp(min=1e-9)
                if normalize_embeddings:
                    pooled = functional.normalize(pooled, p=2, dim=1)
                batches.append(pooled.cpu().numpy().astype(np.float32))
        return np.vstack(batches) if batches else np.empty((0, 384), dtype=np.float32)


def _rule_predictions(rows: list[dict[str, str]]) -> list[str]:
    predictions: list[str] = []
    for row in rows:
        text = f"{row.get('title', '')} {row.get('description', '')} {row.get('attributes', '')}".lower()
        scored: list[tuple[float, str]] = []
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1.0 + min(2.0, len(keyword) / 10.0) for keyword in keywords if keyword in text)
            if score:
                scored.append((score, category))
        if scored:
            scored.sort(reverse=True)
            predictions.append(scored[0][1])
        else:
            predictions.append("Household")
    return predictions


def _cosine_predictions(
    product_embeddings: np.ndarray,
    label_embeddings: np.ndarray,
    categories: list[dict[str, str]],
) -> tuple[list[str], list[float]]:
    scores = np.asarray(product_embeddings) @ np.asarray(label_embeddings).T
    order = np.argsort(-scores, axis=1)
    paths = [categories[int(indexes[0])]["category_path"] for indexes in order]
    margins = [
        float(scores[row_index, indexes[0]] - scores[row_index, indexes[1]])
        if len(indexes) > 1
        else 0.0
        for row_index, indexes in enumerate(order)
    ]
    return paths, margins


def _category_metrics(
    gold_paths: list[str],
    predicted_paths: list[str],
    *,
    labels: list[str],
) -> dict[str, Any]:
    return {
        "category_accuracy": round(float(accuracy_score(gold_paths, predicted_paths)), 4)
        if gold_paths
        else 0.0,
        "macro_f1": round(
            float(f1_score(gold_paths, predicted_paths, labels=labels, average="macro", zero_division=0)),
            4,
        )
        if gold_paths
        else 0.0,
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix(gold_paths, predicted_paths, labels=labels).tolist()
            if gold_paths
            else [],
        },
    }


def _mismatch_metrics(
    rows: list[dict[str, str]],
    labels_by_id: dict[str, dict[str, str]],
    predicted_paths: list[str],
) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for row, predicted_path in zip(rows, predicted_paths):
        label = labels_by_id.get(row.get("product_id", ""), {})
        actual_mismatch = _is_true(label.get("synthetic_mismatch", ""))
        predicted_mismatch = row.get("seller_category", "").strip() != predicted_path.strip()
        if actual_mismatch and predicted_mismatch:
            counts["tp"] += 1
        elif actual_mismatch and not predicted_mismatch:
            counts["fn"] += 1
        elif not actual_mismatch and predicted_mismatch:
            counts["fp"] += 1
        else:
            counts["tn"] += 1

    total = sum(counts.values())
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "confusion": {key: counts[key] for key in ("tp", "fp", "fn", "tn")},
        "actual_mismatch_rate": round((counts["tp"] + counts["fn"]) / total, 4) if total else 0.0,
        "predicted_mismatch_rate": round((counts["tp"] + counts["fp"]) / total, 4) if total else 0.0,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _combined_metrics(
    rows: list[dict[str, str]],
    labels_by_id: dict[str, dict[str, str]],
    predicted_paths: list[str],
    *,
    category_labels: list[str],
) -> dict[str, Any]:
    gold_paths = [
        labels_by_id.get(row.get("product_id", ""), {}).get("gold_category", "")
        for row in rows
    ]
    category = _category_metrics(gold_paths, predicted_paths, labels=category_labels)
    category["mismatch_detection"] = _mismatch_metrics(rows, labels_by_id, predicted_paths)
    return category


def _save_artifact(
    path: Path,
    *,
    estimator: Any,
    label_encoder: LabelEncoder,
    model_path: Path,
    classifier_name: str,
    metrics: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "classifier_name": classifier_name,
            "estimator": estimator,
            "label_encoder": label_encoder,
            "classes": label_encoder.classes_.tolist(),
            "embedding_model_path": str(model_path),
            "text_builder": "title + description[:max_description_chars] + attributes; seller_category excluded",
            "metrics": metrics,
        },
        path,
    )


def train_and_evaluate(
    *,
    clean_csv: Path,
    mismatch_csv: Path,
    labels_csv: Path,
    taxonomy_json: Path,
    model_path: Path,
    output_path: Path,
    logreg_artifact: Path,
    svm_artifact: Path,
    batch_size: int,
    max_description_chars: int,
    save_models: bool,
) -> dict[str, Any]:
    start = time.perf_counter()
    clean_rows = _read_csv(clean_csv)
    mismatch_rows_all = _read_csv(mismatch_csv)
    labels_by_id = _load_labels(labels_csv)
    taxonomy = _load_taxonomy(taxonomy_json)
    category_labels = [str(item["category_path"]) for item in taxonomy]

    train_rows = [
        row for row in clean_rows if labels_by_id.get(row.get("product_id", ""), {}).get("split") == "train"
    ]
    test_rows = [
        row for row in clean_rows if labels_by_id.get(row.get("product_id", ""), {}).get("split") == "test"
    ]
    test_ids = {row["product_id"] for row in test_rows}
    mismatch_rows = [row for row in mismatch_rows_all if row.get("product_id") in test_ids]

    encoder = MiniLMEncoder(model_path)
    train_texts = [_product_text(row, max_description_chars) for row in train_rows]
    test_texts = [_product_text(row, max_description_chars) for row in test_rows]
    mismatch_texts = [_product_text(row, max_description_chars) for row in mismatch_rows]
    train_embeddings = encoder.encode(
        train_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    test_embeddings = encoder.encode(
        test_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    if [row["product_id"] for row in mismatch_rows] == [row["product_id"] for row in test_rows]:
        mismatch_embeddings = test_embeddings
    else:
        mismatch_embeddings = encoder.encode(
            mismatch_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

    train_gold = [labels_by_id[row["product_id"]]["gold_category"] for row in train_rows]
    test_gold = [labels_by_id[row["product_id"]]["gold_category"] for row in test_rows]
    label_encoder = LabelEncoder()
    encoded_y = label_encoder.fit_transform(train_gold)
    logreg = LogisticRegression(max_iter=2000, class_weight="balanced", solver="lbfgs")
    svm = LinearSVC(class_weight="balanced", max_iter=5000, random_state=42)
    logreg.fit(train_embeddings, encoded_y)
    svm.fit(train_embeddings, encoded_y)

    categories = _category_docs(taxonomy)
    label_embeddings = encoder.encode(
        [item["text"] for item in categories],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    test_rule = _rule_predictions(test_rows)
    test_cosine, test_margins = _cosine_predictions(test_embeddings, label_embeddings, categories)
    test_hybrid = [
        cosine if margin >= 0.015 else rule
        for rule, cosine, margin in zip(test_rule, test_cosine, test_margins)
    ]
    test_logreg = label_encoder.inverse_transform(logreg.predict(test_embeddings)).tolist()
    test_svm = label_encoder.inverse_transform(svm.predict(test_embeddings)).tolist()

    mismatch_rule = _rule_predictions(mismatch_rows)
    mismatch_cosine, mismatch_margins = _cosine_predictions(
        mismatch_embeddings,
        label_embeddings,
        categories,
    )
    mismatch_hybrid = [
        cosine if margin >= 0.015 else rule
        for rule, cosine, margin in zip(mismatch_rule, mismatch_cosine, mismatch_margins)
    ]
    mismatch_logreg = label_encoder.inverse_transform(logreg.predict(mismatch_embeddings)).tolist()
    mismatch_svm = label_encoder.inverse_transform(svm.predict(mismatch_embeddings)).tolist()

    category_test = {
        "row_count": len(test_rows),
        "methods": {
            "rule": _category_metrics(test_gold, test_rule, labels=category_labels),
            "minilm_cosine": _category_metrics(test_gold, test_cosine, labels=category_labels),
            "hybrid_margin_0_015": _category_metrics(test_gold, test_hybrid, labels=category_labels),
            "minilm_logreg": _category_metrics(test_gold, test_logreg, labels=category_labels),
            "minilm_linearsvm": _category_metrics(test_gold, test_svm, labels=category_labels),
        },
    }
    mismatch_detection = {
        "scope": "test",
        "row_count": len(mismatch_rows),
        "methods": {
            "rule": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_rule,
                category_labels=category_labels,
            ),
            "minilm_cosine": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_cosine,
                category_labels=category_labels,
            ),
            "hybrid_margin_0_015": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_hybrid,
                category_labels=category_labels,
            ),
            "minilm_logreg": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_logreg,
                category_labels=category_labels,
            ),
            "minilm_linearsvm": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_svm,
                category_labels=category_labels,
            ),
        },
    }
    result = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "inputs": {
            "clean_csv": str(clean_csv),
            "mismatch_csv": str(mismatch_csv),
            "labels_csv": str(labels_csv),
            "taxonomy_json": str(taxonomy_json),
            "model_path": str(model_path),
        },
        "split": {
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
            "mismatch_scope": "test",
        },
        "embedding": {
            "model": "all-MiniLM-L6-v2",
            "backend": encoder.backend,
            "batch_size": batch_size,
            "max_description_chars": max_description_chars,
            "normalized": True,
        },
        "category_test": category_test,
        "mismatch_detection": mismatch_detection,
        "artifacts": {
            "logistic_regression": str(logreg_artifact),
            "linear_svm": str(svm_artifact),
        }
        if save_models
        else {},
        "diagnostics": {
            "train_distribution": dict(Counter(train_gold)),
            "test_distribution": dict(Counter(test_gold)),
            "cosine_margin_avg": round(float(np.mean(mismatch_margins)), 4)
            if mismatch_margins
            else 0.0,
            "cosine_margin_p50": round(float(np.median(mismatch_margins)), 4)
            if mismatch_margins
            else 0.0,
        },
    }

    if save_models:
        _save_artifact(
            logreg_artifact,
            estimator=logreg,
            label_encoder=label_encoder,
            model_path=model_path,
            classifier_name="ecommerce_minilm_logreg",
            metrics={
                "category_test": category_test["methods"]["minilm_logreg"],
                "mismatch_detection": mismatch_detection["methods"]["minilm_logreg"],
            },
        )
        _save_artifact(
            svm_artifact,
            estimator=svm,
            label_encoder=label_encoder,
            model_path=model_path,
            classifier_name="ecommerce_minilm_linearsvm",
            metrics={
                "category_test": category_test["methods"]["minilm_linearsvm"],
                "mismatch_detection": mismatch_detection["methods"]["minilm_linearsvm"],
            },
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate MiniLM classifiers on the unified Ecommerce eval set."
    )
    parser.add_argument("--clean-csv", default=str(DEFAULT_CLEAN_CSV))
    parser.add_argument("--mismatch-csv", default=str(DEFAULT_MISMATCH_CSV))
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_CSV))
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY_JSON))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--logreg-artifact", default=str(DEFAULT_LOGREG_ARTIFACT))
    parser.add_argument("--svm-artifact", default=str(DEFAULT_SVM_ARTIFACT))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-description-chars", type=int, default=1200)
    parser.add_argument("--no-save-models", action="store_true")
    args = parser.parse_args()

    result = train_and_evaluate(
        clean_csv=Path(args.clean_csv),
        mismatch_csv=Path(args.mismatch_csv),
        labels_csv=Path(args.labels),
        taxonomy_json=Path(args.taxonomy),
        model_path=Path(args.model_path),
        output_path=Path(args.output),
        logreg_artifact=Path(args.logreg_artifact),
        svm_artifact=Path(args.svm_artifact),
        batch_size=args.batch_size,
        max_description_chars=args.max_description_chars,
        save_models=not args.no_save_models,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
