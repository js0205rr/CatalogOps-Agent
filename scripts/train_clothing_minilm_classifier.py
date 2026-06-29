from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.catalog.schemas import ProductInput
from packages.catalog.taxonomy import load_category_keywords


def _load_rule_predictor() -> Any:
    module_path = ROOT / "packages" / "agent_core" / "catalog_rules.py"
    spec = importlib.util.spec_from_file_location("catalogops_catalog_rules", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load catalog rules from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.predict_category_rule


predict_category_rule = _load_rule_predictor()


DEFAULT_CLEAN_CSV = ROOT / "dataset" / "processed" / "clothing_catalogops_clean.csv"
DEFAULT_MISMATCH_CSV = ROOT / "dataset" / "processed" / "clothing_catalogops_mismatch_20pct.csv"
DEFAULT_LABELS_CSV = ROOT / "dataset" / "processed" / "clothing_labels.csv"
DEFAULT_MODEL_PATH = ROOT / "models" / "all-MiniLM-L6-v2"
DEFAULT_OUTPUT = ROOT / "dataset" / "processed" / "model_eval" / "clothing_supervised_minilm.json"
DEFAULT_LOGREG_ARTIFACT = ROOT / "models" / "clothing_minilm_logreg.joblib"
DEFAULT_SVM_ARTIFACT = ROOT / "models" / "clothing_minilm_linearsvm.joblib"


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


def _product_text(row: dict[str, str]) -> str:
    return (
        f"Title: {row.get('title', '')}\n"
        f"Description: {row.get('description', '')[:3000]}\n"
        f"Attributes: {row.get('attributes', '')}"
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


def _mismatch_counts(
    rows: list[dict[str, str]],
    labels_by_id: dict[str, dict[str, str]],
    predicted_paths: list[str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row, predicted_path in zip(rows, predicted_paths):
        label = labels_by_id.get(row.get("product_id", ""), {})
        actual_mismatch = _is_true(label.get("synthetic_mismatch", ""))
        seller_category = row.get("seller_category", "")
        predicted_mismatch = seller_category.strip() != predicted_path.strip()
        if actual_mismatch and predicted_mismatch:
            counts["tp"] += 1
        elif actual_mismatch and not predicted_mismatch:
            counts["fn"] += 1
        elif not actual_mismatch and predicted_mismatch:
            counts["fp"] += 1
        else:
            counts["tn"] += 1
    return counts


def _mismatch_metrics(counts: Counter[str]) -> dict[str, Any]:
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
    category["mismatch_detection"] = _mismatch_metrics(
        _mismatch_counts(rows, labels_by_id, predicted_paths)
    )
    return category


def _rule_predictions(rows: list[dict[str, str]]) -> list[str]:
    return [predict_category_rule(_row_to_product(row)).category_path for row in rows]


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
            "text_builder": "title + description[:3000] + attributes; seller_category intentionally excluded",
            "metrics": metrics,
        },
        path,
    )


def train_and_evaluate(
    *,
    clean_csv: Path,
    mismatch_csv: Path,
    labels_csv: Path,
    model_path: Path,
    output_path: Path,
    logreg_artifact: Path,
    svm_artifact: Path,
    test_size: float,
    random_state: int,
    batch_size: int,
    mismatch_scope: str,
    save_models: bool,
) -> dict[str, Any]:
    start = time.perf_counter()
    clean_rows = _read_csv(clean_csv)
    mismatch_rows_all = _read_csv(mismatch_csv)
    labels_by_id = _load_labels(labels_csv)

    labeled_rows = [
        row for row in clean_rows if labels_by_id.get(row.get("product_id", ""), {}).get("gold_category")
    ]
    gold_paths = [
        labels_by_id[row["product_id"]]["gold_category"]
        for row in labeled_rows
    ]
    category_labels = sorted(set(gold_paths))
    train_idx, test_idx = train_test_split(
        np.arange(len(labeled_rows)),
        test_size=test_size,
        random_state=random_state,
        stratify=gold_paths,
    )
    train_idx = np.asarray(train_idx)
    test_idx = np.asarray(test_idx)
    test_ids = {labeled_rows[int(index)]["product_id"] for index in test_idx}
    mismatch_rows = (
        [row for row in mismatch_rows_all if row.get("product_id") in test_ids]
        if mismatch_scope == "test"
        else mismatch_rows_all
    )

    encoder = MiniLMEncoder(model_path)
    clean_texts = [_product_text(row) for row in labeled_rows]
    clean_embeddings = encoder.encode(
        clean_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    label_encoder = LabelEncoder()
    encoded_y = label_encoder.fit_transform(gold_paths)
    logreg = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        solver="lbfgs",
    )
    svm = LinearSVC(class_weight="balanced", max_iter=5000, random_state=random_state)
    logreg.fit(clean_embeddings[train_idx], encoded_y[train_idx])
    svm.fit(clean_embeddings[train_idx], encoded_y[train_idx])

    categories = _clothing_category_docs()
    label_embeddings = encoder.encode(
        [item["text"] for item in categories],
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    clean_test_rows = [labeled_rows[int(index)] for index in test_idx]
    clean_test_gold = [gold_paths[int(index)] for index in test_idx]
    clean_test_embeddings = clean_embeddings[test_idx]
    clean_rule_paths = _rule_predictions(clean_test_rows)
    clean_cosine_paths, clean_cosine_margins = _cosine_predictions(
        clean_test_embeddings,
        label_embeddings,
        categories,
    )
    clean_hybrid_paths = [
        cosine_path if margin >= 0.015 else rule_path
        for rule_path, cosine_path, margin in zip(
            clean_rule_paths,
            clean_cosine_paths,
            clean_cosine_margins,
        )
    ]
    clean_logreg_paths = label_encoder.inverse_transform(
        logreg.predict(clean_test_embeddings)
    ).tolist()
    clean_svm_paths = label_encoder.inverse_transform(
        svm.predict(clean_test_embeddings)
    ).tolist()

    mismatch_texts = [_product_text(row) for row in mismatch_rows]
    mismatch_embeddings = encoder.encode(
        mismatch_texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    mismatch_rule_paths = _rule_predictions(mismatch_rows)
    mismatch_cosine_paths, mismatch_cosine_margins = _cosine_predictions(
        mismatch_embeddings,
        label_embeddings,
        categories,
    )
    mismatch_hybrid_paths = [
        cosine_path if margin >= 0.015 else rule_path
        for rule_path, cosine_path, margin in zip(
            mismatch_rule_paths,
            mismatch_cosine_paths,
            mismatch_cosine_margins,
        )
    ]
    mismatch_logreg_paths = label_encoder.inverse_transform(
        logreg.predict(mismatch_embeddings)
    ).tolist()
    mismatch_svm_paths = label_encoder.inverse_transform(
        svm.predict(mismatch_embeddings)
    ).tolist()

    category_test = {
        "row_count": len(clean_test_rows),
        "methods": {
            "rule": _category_metrics(clean_test_gold, clean_rule_paths, labels=category_labels),
            "minilm_cosine": _category_metrics(
                clean_test_gold,
                clean_cosine_paths,
                labels=category_labels,
            ),
            "hybrid_margin_0_015": _category_metrics(
                clean_test_gold,
                clean_hybrid_paths,
                labels=category_labels,
            ),
            "minilm_logreg": _category_metrics(
                clean_test_gold,
                clean_logreg_paths,
                labels=category_labels,
            ),
            "minilm_linearsvm": _category_metrics(
                clean_test_gold,
                clean_svm_paths,
                labels=category_labels,
            ),
        },
    }
    mismatch_detection = {
        "scope": mismatch_scope,
        "row_count": len(mismatch_rows),
        "methods": {
            "rule": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_rule_paths,
                category_labels=category_labels,
            ),
            "minilm_cosine": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_cosine_paths,
                category_labels=category_labels,
            ),
            "hybrid_margin_0_015": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_hybrid_paths,
                category_labels=category_labels,
            ),
            "minilm_logreg": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_logreg_paths,
                category_labels=category_labels,
            ),
            "minilm_linearsvm": _combined_metrics(
                mismatch_rows,
                labels_by_id,
                mismatch_svm_paths,
                category_labels=category_labels,
            ),
        },
    }

    artifacts = {
        "logistic_regression": str(logreg_artifact),
        "linear_svm": str(svm_artifact),
    }
    result = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "inputs": {
            "clean_csv": str(clean_csv),
            "mismatch_csv": str(mismatch_csv),
            "labels_csv": str(labels_csv),
            "model_path": str(model_path),
        },
        "split": {
            "random_state": random_state,
            "test_size": test_size,
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "mismatch_scope": mismatch_scope,
        },
        "embedding": {
            "model": "all-MiniLM-L6-v2",
            "backend": encoder.backend,
            "batch_size": batch_size,
            "normalized": True,
        },
        "category_test": category_test,
        "mismatch_detection": mismatch_detection,
        "artifacts": artifacts if save_models else {},
        "diagnostics": {
            "class_distribution": dict(Counter(gold_paths)),
            "mismatch_distribution": dict(
                Counter(row.get("seller_category", "") for row in mismatch_rows).most_common(10)
            ),
            "cosine_margin_avg": round(float(np.mean(mismatch_cosine_margins)), 4)
            if mismatch_cosine_margins
            else 0.0,
            "cosine_margin_p50": round(float(np.median(mismatch_cosine_margins)), 4)
            if mismatch_cosine_margins
            else 0.0,
        },
    }

    if save_models:
        _save_artifact(
            logreg_artifact,
            estimator=logreg,
            label_encoder=label_encoder,
            model_path=model_path,
            classifier_name="minilm_logreg",
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
            classifier_name="minilm_linearsvm",
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
        description="Train and evaluate MiniLM embedding classifiers for Clothing category prediction."
    )
    parser.add_argument("--clean-csv", default=str(DEFAULT_CLEAN_CSV))
    parser.add_argument("--mismatch-csv", default=str(DEFAULT_MISMATCH_CSV))
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_CSV))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--logreg-artifact", default=str(DEFAULT_LOGREG_ARTIFACT))
    parser.add_argument("--svm-artifact", default=str(DEFAULT_SVM_ARTIFACT))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument(
        "--mismatch-scope",
        choices=["test", "all"],
        default="test",
        help="Use held-out product IDs for leakage-safe mismatch metrics, or all rows for full-set reference.",
    )
    parser.add_argument("--no-save-models", action="store_true")
    args = parser.parse_args()

    result = train_and_evaluate(
        clean_csv=Path(args.clean_csv),
        mismatch_csv=Path(args.mismatch_csv),
        labels_csv=Path(args.labels),
        model_path=Path(args.model_path),
        output_path=Path(args.output),
        logreg_artifact=Path(args.logreg_artifact),
        svm_artifact=Path(args.svm_artifact),
        test_size=args.test_size,
        random_state=args.random_state,
        batch_size=args.batch_size,
        mismatch_scope=args.mismatch_scope,
        save_models=not args.no_save_models,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
