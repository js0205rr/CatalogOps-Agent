from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from packages.catalog.schemas import (
    CategoryCandidate,
    CategoryConsistencyResult,
    CategoryPrediction,
)
from packages.catalog.taxonomy import (
    find_category_by_path,
    get_taxonomy_tree,
    is_parent_child_path,
    normalize_category_path,
    split_category_path,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATEGORY_MODEL_PATH = ROOT / "models" / "clothing_minilm_linearsvm.joblib"
DEFAULT_EMBEDDING_MODEL_PATH = ROOT / "models" / "all-MiniLM-L6-v2"
MODEL_EVIDENCE_ID = "model:clothing-minilm-linearsvm"
GENERIC_CLOTHING_PATH = "Clothing & Accessories > Apparel"


class MockCategoryModel:
    def predict(self, text: str, taxonomy_tree: list[dict[str, Any]]) -> CategoryPrediction:
        del text, taxonomy_tree
        candidate = CategoryCandidate(
            category_id="unknown",
            category_path="unknown",
            confidence=0.32,
            matched_terms=[],
            rationale="mock fallback candidate",
            evidence_ids=[],
        )
        return CategoryPrediction(
            category_id=candidate.category_id,
            category_path=candidate.category_path,
            confidence=candidate.confidence,
            matched_terms=[],
            candidates=[candidate],
            evidence_ids=[],
        )


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _flatten_attributes(attributes: dict[str, Any] | None) -> str:
    if not attributes:
        return ""
    return " ".join(
        f"{key} {value}" for key, value in attributes.items() if value not in (None, "")
    )


def _category_terms(item: dict[str, Any]) -> list[str]:
    raw_terms = item.get("keywords") or item.get("terms") or []
    return [str(keyword) for keyword in raw_terms if str(keyword).strip()]


def _term_in_text(term: str, text: str) -> bool:
    normalized = term.strip().lower()
    if not normalized:
        return False
    if normalized.isascii():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            text,
            re.IGNORECASE,
        ) is not None
    return normalized in text


def _keyword_score(text: str, item: dict[str, Any]) -> tuple[float, list[str]]:
    keywords = _category_terms(item)
    matched = [keyword for keyword in keywords if _term_in_text(keyword, text)]
    score = sum(max(1.0, min(3.0, len(keyword) / 3.0)) for keyword in matched)
    return score, matched


def _product_text(title: str, description: str, attributes: dict[str, Any] | None) -> str:
    return (
        f"Title: {title}\n"
        f"Description: {description[:3000]}\n"
        f"Attributes: {_flatten_attributes(attributes)}"
    )


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))


class LocalMiniLMEncoder:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self._sentence_model: Any | None = None
        self._tokenizer: Any | None = None
        self._transformer_model: Any | None = None
        try:
            from sentence_transformers import SentenceTransformer

            self._sentence_model = SentenceTransformer(str(model_path), device="cpu")
        except ImportError:
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

    def encode_one(self, text: str) -> np.ndarray:
        if self._sentence_model is not None:
            embedding = self._sentence_model.encode(
                [text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return np.asarray(embedding, dtype=np.float32)

        import torch
        import torch.nn.functional as functional

        if self._tokenizer is None or self._transformer_model is None:
            raise RuntimeError("local MiniLM encoder is not initialized")

        with torch.no_grad():
            encoded = self._tokenizer(
                [text],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            output = self._transformer_model(**encoded)
            token_embeddings = output.last_hidden_state
            attention_mask = encoded["attention_mask"].unsqueeze(-1).float()
            pooled = (token_embeddings * attention_mask).sum(dim=1)
            pooled = pooled / attention_mask.sum(dim=1).clamp(min=1e-9)
            pooled = functional.normalize(pooled, p=2, dim=1)
            return pooled.cpu().numpy().astype(np.float32)


class SupervisedCategoryModel:
    def __init__(self, artifact_path: Path, embedding_model_path: Path) -> None:
        import joblib

        artifact = joblib.load(artifact_path)
        self.artifact_path = artifact_path
        self.estimator = artifact["estimator"]
        self.label_encoder = artifact["label_encoder"]
        self.encoder = LocalMiniLMEncoder(embedding_model_path)

    def predict(
        self,
        title: str,
        description: str,
        attributes: dict[str, Any] | None,
        taxonomy_tree: list[dict[str, Any]],
    ) -> CategoryPrediction:
        text = _product_text(title, description, attributes)
        embedding = self.encoder.encode_one(text)
        scores = self._scores(embedding)
        order = np.argsort(-scores)
        candidates: list[CategoryCandidate] = []
        for index in order[:3]:
            path = str(self.label_encoder.inverse_transform([int(index)])[0])
            category = find_category_by_path(path, taxonomy_tree) or {}
            confidence = self._confidence(scores, int(index), order)
            candidates.append(
                CategoryCandidate(
                    category_id=str(category.get("category_id", path)),
                    category_path=path,
                    confidence=confidence,
                    matched_terms=[],
                    rationale="MiniLM embedding + supervised LinearSVM category model",
                    evidence_ids=[MODEL_EVIDENCE_ID],
                )
            )

        best = candidates[0]
        return CategoryPrediction(
            category_id=best.category_id,
            category_path=best.category_path,
            confidence=best.confidence,
            matched_terms=[],
            candidates=candidates,
            evidence_ids=[MODEL_EVIDENCE_ID],
        )

    def _scores(self, embedding: np.ndarray) -> np.ndarray:
        if hasattr(self.estimator, "predict_proba"):
            return np.asarray(self.estimator.predict_proba(embedding)[0], dtype=np.float32)
        scores = self.estimator.decision_function(embedding)
        return np.asarray(scores[0] if np.asarray(scores).ndim > 1 else scores, dtype=np.float32)

    def _confidence(self, scores: np.ndarray, index: int, order: np.ndarray) -> float:
        if hasattr(self.estimator, "predict_proba"):
            return float(max(0.0, min(0.98, scores[index])))
        if len(order) <= 1:
            return 0.6
        margin = float(scores[index] - scores[int(order[1])])
        return float(max(0.45, min(0.95, 0.45 + _sigmoid(margin) * 0.5)))


@lru_cache(maxsize=1)
def _load_supervised_model() -> SupervisedCategoryModel | None:
    if not _env_bool("USE_CATEGORY_MODEL", False):
        return None
    artifact_path = Path(os.getenv("CATEGORY_MODEL_PATH", str(DEFAULT_CATEGORY_MODEL_PATH)))
    embedding_path = Path(
        os.getenv("CATEGORY_EMBEDDING_MODEL_PATH", str(DEFAULT_EMBEDDING_MODEL_PATH))
    )
    if not artifact_path.exists() or not embedding_path.exists():
        return None
    try:
        return SupervisedCategoryModel(artifact_path, embedding_path)
    except Exception:
        return None


def _predict_with_supervised_model(
    title: str,
    description: str,
    attributes: dict[str, Any] | None,
    taxonomy_tree: list[dict[str, Any]],
) -> CategoryPrediction | None:
    model = _load_supervised_model()
    if model is None:
        return None
    prediction = model.predict(title, description, attributes, taxonomy_tree)
    if prediction.confidence < _env_float("CATEGORY_MODEL_MIN_CONFIDENCE", 0.6):
        return None
    return prediction


def _merge_agreeing_predictions(
    keyword_prediction: CategoryPrediction,
    model_prediction: CategoryPrediction,
) -> CategoryPrediction:
    candidates = [
        keyword_prediction.candidates[0],
        *[
            candidate
            for candidate in model_prediction.candidates
            if candidate.category_path != keyword_prediction.category_path
        ],
    ][:3]
    evidence_ids = sorted(
        set(keyword_prediction.evidence_ids) | set(model_prediction.evidence_ids)
    )
    return keyword_prediction.model_copy(
        update={
            "confidence": max(keyword_prediction.confidence, model_prediction.confidence),
            "candidates": candidates,
            "evidence_ids": evidence_ids,
        }
    )


def _should_use_model_over_keywords(
    keyword_prediction: CategoryPrediction,
    model_prediction: CategoryPrediction,
) -> bool:
    if normalize_category_path(keyword_prediction.category_path) == normalize_category_path(
        model_prediction.category_path
    ):
        return True
    if normalize_category_path(keyword_prediction.category_path) == GENERIC_CLOTHING_PATH:
        return True
    return keyword_prediction.confidence < _env_float("CATEGORY_RULE_HIGH_CONFIDENCE", 0.82)


def predict_category(
    title: str,
    description: str = "",
    attributes: dict[str, Any] | None = None,
    *,
    taxonomy_tree: list[dict[str, Any]] | None = None,
    mock_model: MockCategoryModel | None = None,
) -> CategoryPrediction:
    tree = taxonomy_tree or get_taxonomy_tree()
    text = f"{title} {description} {_flatten_attributes(attributes)}".lower()
    candidates: list[CategoryCandidate] = []
    for item in tree:
        score, matched = _keyword_score(text, item)
        if score <= 0:
            continue
        confidence = min(0.98, 0.62 + score * 0.08 + min(len(matched), 3) * 0.04)
        candidates.append(
            CategoryCandidate(
                category_id=str(item.get("category_id", "")),
                category_path=str(item.get("category_path", "")),
                confidence=confidence,
                matched_terms=matched,
                rationale=f"keyword match: {', '.join(matched)}",
                evidence_ids=["taxonomy:category-keywords"],
            )
        )

    if candidates:
        candidates = sorted(
            candidates,
            key=lambda item: (item.confidence, len(item.matched_terms)),
            reverse=True,
        )
        best = candidates[0]
        keyword_prediction = CategoryPrediction(
            category_id=best.category_id,
            category_path=best.category_path,
            confidence=best.confidence,
            matched_terms=best.matched_terms,
            candidates=candidates[:3],
            evidence_ids=["taxonomy:category-keywords"],
        )

        model_prediction = _predict_with_supervised_model(title, description, attributes, tree)
        if model_prediction is not None:
            if normalize_category_path(model_prediction.category_path) == normalize_category_path(
                keyword_prediction.category_path
            ):
                return _merge_agreeing_predictions(keyword_prediction, model_prediction)
            if _should_use_model_over_keywords(keyword_prediction, model_prediction):
                return model_prediction
            keyword_prediction.candidates = [
                *keyword_prediction.candidates[:2],
                model_prediction.candidates[0],
            ]
        return keyword_prediction

    model_prediction = _predict_with_supervised_model(title, description, attributes, tree)
    if model_prediction is not None:
        return model_prediction

    return (mock_model or MockCategoryModel()).predict(text, tree)


def check_category_consistency(
    seller_category: str,
    predicted_category: CategoryPrediction,
    taxonomy_tree: list[dict[str, Any]] | None = None,
) -> CategoryConsistencyResult:
    tree = taxonomy_tree or get_taxonomy_tree()
    seller = normalize_category_path(seller_category)
    predicted = normalize_category_path(predicted_category.category_path)
    seller_exists = find_category_by_path(seller, tree) is not None if seller else False
    predicted_exists = find_category_by_path(predicted, tree) is not None if predicted else False

    if not seller or not predicted or predicted_category.confidence < 0.45:
        status = "uncertain"
        reason = "missing category or low-confidence prediction"
        confidence = min(predicted_category.confidence, 0.4)
    elif seller == predicted:
        status = "match"
        reason = "seller category exactly matches predicted category"
        confidence = predicted_category.confidence
    elif is_parent_child_path(seller, predicted):
        status = "close_match"
        reason = "seller category and predicted category are parent-child neighbors"
        confidence = min(predicted_category.confidence, 0.82)
    else:
        status = "mismatch"
        reason = "seller category differs from predicted taxonomy category"
        confidence = predicted_category.confidence

    return CategoryConsistencyResult(
        seller_category=seller,
        predicted_category_id=predicted_category.category_id,
        predicted_category_path=predicted,
        status=status,
        is_consistent=status in {"match", "close_match"},
        confidence=confidence,
        reason=reason,
        evidence_ids=list(predicted_category.evidence_ids),
    )
