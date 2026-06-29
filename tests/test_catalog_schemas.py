from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from pydantic import ValidationError

from packages.catalog.schemas import CategoryCandidate, ProductInput, ReviewResult


def test_product_input_accepts_valid_input() -> None:
    product = ProductInput(
        sku_id="SKU-1",
        title="Cotton shirt",
        seller_category="Apparel/Shirts",
        attributes={"brand": "Acme"},
    )

    assert product.sku_id == "SKU-1"
    assert product.title == "Cotton shirt"
    assert product.attributes["brand"] == "Acme"


def test_product_input_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        ProductInput(title="")


def test_category_candidate_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        CategoryCandidate(category_id="1001", category_path="Apparel/Shirts", confidence=1.5)


def test_review_result_exposes_required_audit_fields() -> None:
    result = ReviewResult(product=ProductInput(title="Cotton shirt"))

    assert result.publish_decision == "uncertain"
    assert result.quality_score.overall == 0.0
    assert result.predicted_category is None
    assert result.seller_category_check.is_consistent is True
    assert result.missing_attributes == []
    assert result.compliance_issues == []
    assert result.rewrite_suggestions.revised_title == ""
    assert result.evidence == []
    assert result.trace_id.startswith("trace-")
