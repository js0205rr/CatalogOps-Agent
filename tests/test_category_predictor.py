from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

import packages.catalog.category_predictor as category_predictor
from packages.catalog.category_predictor import check_category_consistency, predict_category
from packages.catalog.schemas import CategoryPrediction
from packages.catalog.taxonomy import get_taxonomy_tree


PHONE_CASE = "\u6570\u7801\u914d\u4ef6 > \u624b\u673a\u914d\u4ef6 > \u624b\u673a\u4fdd\u62a4\u58f3"
EARBUDS = "\u6570\u7801\u914d\u4ef6 > \u8033\u673a > \u84dd\u7259\u8033\u673a"
MOP = "\u5bb6\u5c45\u65e5\u7528 > \u6e05\u6d01\u7528\u54c1 > \u62d6\u628a"


def test_predict_category_keyword_hit_returns_high_confidence() -> None:
    prediction = predict_category(
        title="iPhone 15 \u624b\u673a\u4fdd\u62a4\u58f3 \u900f\u660e",
        description="TPU \u4fdd\u62a4\u5957",
        attributes={},
    )

    assert prediction.category_path == PHONE_CASE
    assert prediction.confidence >= 0.72
    assert "\u624b\u673a\u4fdd\u62a4\u58f3" in prediction.matched_terms


def test_predict_category_no_keyword_uses_mock_low_confidence() -> None:
    prediction = predict_category(
        title="\u795e\u79d8\u65b0\u54c1",
        description="\u6ca1\u6709\u660e\u786e\u7c7b\u76ee\u8bcd",
        attributes={},
    )

    assert prediction.confidence < 0.45
    assert prediction.candidates
    assert prediction.candidates[0].rationale == "mock fallback candidate"


def test_predict_category_ascii_keywords_respect_token_boundaries() -> None:
    prediction = predict_category(
        title="The Prophet About the Author Kahlil Gibran",
        description="A classic book by a noted author.",
        attributes={"source_category": "Books"},
    )

    assert prediction.category_path.startswith("Books")
    assert prediction.category_path != "Clothing & Accessories > Innerwear"


def test_supervised_model_can_replace_generic_clothing_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    model_prediction = CategoryPrediction(
        category_id="CLO-TOPS",
        category_path="Clothing & Accessories > Tops",
        confidence=0.82,
        matched_terms=[],
        evidence_ids=["model:clothing-minilm-linearsvm"],
    )
    monkeypatch.setattr(
        category_predictor,
        "_predict_with_supervised_model",
        lambda *args, **kwargs: model_prediction,
    )

    prediction = predict_category(
        title="Cotton apparel garment for daily wear",
        description="Lightweight clothing item",
        attributes={},
    )

    assert prediction.category_path == "Clothing & Accessories > Tops"
    assert prediction.evidence_ids == ["model:clothing-minilm-linearsvm"]


def test_high_confidence_keyword_keeps_priority_over_conflicting_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_prediction = CategoryPrediction(
        category_id="CLO-SHOES",
        category_path="Clothing & Accessories > Shoes",
        confidence=0.88,
        matched_terms=[],
        evidence_ids=["model:clothing-minilm-linearsvm"],
    )
    monkeypatch.setattr(
        category_predictor,
        "_predict_with_supervised_model",
        lambda *args, **kwargs: model_prediction,
    )

    prediction = predict_category(
        title="Girls sunglasses with uv protection",
        description="Durable glasses for kids",
        attributes={},
    )

    assert prediction.category_path == "Clothing & Accessories > Accessories"
    assert prediction.evidence_ids == ["taxonomy:category-keywords"]
    assert any(
        candidate.category_path == "Clothing & Accessories > Shoes"
        for candidate in prediction.candidates
    )


def test_category_consistency_mismatch() -> None:
    prediction = predict_category(
        title="\u84dd\u7259\u8033\u673a \u964d\u566a",
        description="\u5165\u8033\u5f0f",
        attributes={},
    )

    result = check_category_consistency(MOP, prediction, get_taxonomy_tree())

    assert result.status == "mismatch"
    assert result.is_consistent is False


def test_category_consistency_low_confidence_is_uncertain_not_mismatch() -> None:
    prediction = CategoryPrediction(
        category_id="unknown",
        category_path="unknown",
        confidence=0.32,
        matched_terms=[],
    )

    result = check_category_consistency(MOP, prediction, get_taxonomy_tree())

    assert result.status == "uncertain"
    assert result.is_consistent is False


def test_category_consistency_parent_child_close_match() -> None:
    prediction = CategoryPrediction(
        category_id="cat_phone_case",
        category_path=PHONE_CASE,
        confidence=0.9,
        matched_terms=["\u624b\u673a\u4fdd\u62a4\u58f3"],
    )

    result = check_category_consistency(
        "\u6570\u7801\u914d\u4ef6 > \u624b\u673a\u914d\u4ef6",
        prediction,
        get_taxonomy_tree(),
    )

    assert result.status == "close_match"
    assert result.is_consistent is True


def test_category_consistency_sibling_leaf_is_mismatch() -> None:
    prediction = CategoryPrediction(
        category_id="CLO-TOPS",
        category_path="Clothing & Accessories > Tops",
        confidence=0.9,
        matched_terms=["shirt"],
    )

    result = check_category_consistency(
        "Clothing & Accessories > Dresses",
        prediction,
        get_taxonomy_tree(),
    )

    assert result.status == "mismatch"
    assert result.is_consistent is False
