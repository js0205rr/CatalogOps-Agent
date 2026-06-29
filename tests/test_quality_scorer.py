from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.catalog.quality_scorer import calculate_quality_score, score_product_quality
from packages.catalog.schemas import (
    CategoryConsistencyResult,
    ComplianceIssue,
    Evidence,
    ExtractedAttributes,
)


def test_quality_score_is_zero_to_one_hundred() -> None:
    score = score_product_quality(
        CategoryConsistencyResult(status="match", confidence=0.95, is_consistent=True),
        ExtractedAttributes(values={"品牌": "Acme", "颜色": "透明"}),
        [],
        [Evidence(evidence_id="ev-1", source="taxonomy", source_type="taxonomy")],
    )

    assert 0 <= score.overall <= 100
    assert score.category >= 90
    assert score.title == 100


def test_calculate_quality_score_uses_weighted_components() -> None:
    score = calculate_quality_score(100, 80, 60, 40)

    assert score.overall == 77


def test_quality_score_penalizes_missing_attributes_and_title_issue() -> None:
    issue = ComplianceIssue(
        issue_type="title_violation",
        severity="blocker",
        message="absolute claim",
        evidence_ids=["ev-1"],
    )
    score = score_product_quality(
        CategoryConsistencyResult(status="close_match", confidence=0.8, is_consistent=True),
        ExtractedAttributes(values={"品牌": "Acme"}, missing_required=["颜色"]),
        [issue],
        [Evidence(evidence_id="ev-1", source="policy", source_type="policy")],
        missing_attributes=["颜色"],
    )

    assert score.attributes == 50
    assert score.title < 100
    assert score.evidence == 100
