from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.catalog.rules import check_product_title, rewrite_product_title
from packages.catalog.schemas import CategoryPrediction, ExtractedAttributes, ProductInput


PHONE_CASE = "数码配件/手机配件/手机壳"


def _prediction(path: str = PHONE_CASE) -> CategoryPrediction:
    return CategoryPrediction(
        category_id="2002",
        category_path=path,
        confidence=0.9,
        matched_terms=["手机壳"],
        evidence_ids=["taxonomy:catalog-v1"],
    )


def test_title_rules_detect_absolute_claim_and_keyword_stuffing() -> None:
    product = ProductInput(
        sku_id="RULE-1",
        title="全网第一 爆款 热卖 特价 iPhone 15 手机壳",
    )

    issues = check_product_title(product, _prediction(), evidence_ids=["taxonomy:catalog-v1"])

    assert any(issue.issue_id.endswith("absolute_claim") for issue in issues)
    assert any(issue.issue_id.endswith("keyword_stuffing") for issue in issues)


def test_title_rules_detect_category_conflict() -> None:
    product = ProductInput(sku_id="RULE-2", title="蓝牙耳机 主动降噪 续航24小时")

    issues = check_product_title(product, _prediction(), evidence_ids=["taxonomy:catalog-v1"])

    assert any(issue.issue_id.endswith("category_conflict") for issue in issues)


def test_title_category_conflict_respects_ascii_token_boundaries() -> None:
    product = ProductInput(
        sku_id="RULE-BOOK",
        title="A Dance with Dragons review with vividly rendered set pieces",
    )
    prediction = CategoryPrediction(
        category_id="BOOKS-FICTION",
        category_path="Books > Fiction",
        confidence=0.9,
        matched_terms=["fiction"],
        evidence_ids=["taxonomy:catalog-v1"],
    )

    issues = check_product_title(product, prediction, evidence_ids=["taxonomy:catalog-v1"])

    assert not any(issue.issue_id.endswith("category_conflict") for issue in issues)


def test_title_rules_detect_insufficient_title() -> None:
    product = ProductInput(sku_id="RULE-SHORT", title="新品")

    issues = check_product_title(product, _prediction(), evidence_ids=["taxonomy:catalog-v1"])

    assert any(issue.issue_id.endswith("insufficient_title") for issue in issues)


def test_rewrite_product_title_preserves_subject_and_key_attributes() -> None:
    product = ProductInput(
        sku_id="RULE-3",
        title="神器 爆款 iPhone 15 手机壳",
    )
    issues = check_product_title(product, _prediction(), evidence_ids=["taxonomy:catalog-v1"])
    extracted = ExtractedAttributes(
        values={
            "品牌": "Acme",
            "适用型号": "iPhone 15",
            "材质": "TPU",
            "颜色": "透明",
            "功能": "防摔",
        }
    )

    suggestion = rewrite_product_title(product, issues, _prediction(), extracted)

    assert "手机壳" in suggestion.title
    assert "iPhone 15" in suggestion.title
    assert "TPU" in suggestion.title
    assert "神器" not in suggestion.title
    assert suggestion.category == PHONE_CASE
    assert suggestion.attributes["颜色"] == "透明"
    assert suggestion.seller_feedback
