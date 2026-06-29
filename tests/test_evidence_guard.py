from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.catalog.schemas import ComplianceIssue, ProductInput, ReviewResult


def test_evidence_guard_downgrades_issue_without_evidence() -> None:
    result = ReviewResult(
        product=ProductInput(sku_id="X", title="测试商品"),
        issues=[
            ComplianceIssue(
                issue_id="i1",
                issue_type="title_violation",
                severity="blocker",
                message="bad title",
                evidence_ids=[],
            )
        ],
        decision="approve",
    )

    assert result.issues[0].issue_type == "human_review_reason"
    assert result.decision == "human_review"
