from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.agent_core.nodes.verify_evidence import verify_evidence
from packages.catalog.schemas import ComplianceIssue, Evidence


def _state(issues: list[ComplianceIssue], evidence: list[Evidence]) -> dict:
    return {
        "compliance_issues": [issue.model_dump() for issue in issues],
        "issues": [issue.model_dump() for issue in issues],
        "evidence": [item.model_dump() for item in evidence],
        "trace": [],
        "tool_trace": [],
    }


def test_category_mismatch_accepts_product_text_evidence() -> None:
    issue = ComplianceIssue(
        issue_type="category_mismatch",
        severity="blocker",
        message="category mismatch",
        evidence_ids=["product:1"],
    )
    evidence = Evidence(
        evidence_id="product:1",
        source="SKU-1",
        source_type="product",
        quote="iPhone 15 手机壳",
        metadata={"evidence_kind": "product_text"},
    )

    result = verify_evidence(_state([issue], [evidence]))

    assert result["compliance_issues"][0]["issue_type"] == "category_mismatch"
    assert result["evidence_coverage"]["covered_issues"] == 1
    assert result["tool_trace"][-1]["node"] == "verify_evidence"


def test_missing_attribute_without_schema_is_downgraded_and_cannot_reject() -> None:
    issue = ComplianceIssue(
        issue_type="missing_attribute",
        severity="high",
        message="missing color",
        evidence_ids=["product:1"],
    )
    evidence = Evidence(
        evidence_id="product:1",
        source="SKU-1",
        source_type="product",
        quote="phone case",
    )

    result = verify_evidence(_state([issue], [evidence]))

    assert result["compliance_issues"][0]["issue_type"] == "human_review_reason"
    assert result["publish_decision"] == "human_review"
    assert result["evidence_coverage"]["downgraded_issues"] == 1


def test_missing_attribute_accepts_attribute_schema_evidence() -> None:
    issue = ComplianceIssue(
        issue_type="missing_attribute",
        severity="blocker",
        message="missing color",
        evidence_ids=["schema:phone-case"],
    )
    evidence = Evidence(
        evidence_id="schema:phone-case",
        source="required_attributes.json",
        source_type="attribute_schema",
        quote="手机壳必填属性：品牌、适用型号、材质、颜色",
    )

    result = verify_evidence(_state([issue], [evidence]))

    assert result["compliance_issues"][0]["issue_type"] == "missing_attribute"
    assert result["evidence_coverage"]["covered_issues"] == 1


def test_low_severity_issue_without_evidence_is_removed() -> None:
    issue = ComplianceIssue(
        issue_type="policy_conflict",
        severity="low",
        message="minor issue",
        evidence_ids=[],
    )

    result = verify_evidence(_state([issue], []))

    assert result["compliance_issues"] == []
    assert result["evidence_coverage"]["removed_issues"] == 1


def test_title_issue_requires_span_and_rule_or_policy() -> None:
    issue = ComplianceIssue(
        issue_type="title_violation",
        severity="blocker",
        message="absolute claim",
        evidence_ids=["rule:title"],
        matched_span="全网第一",
    )
    evidence = Evidence(
        evidence_id="rule:title",
        source="rules.py",
        source_type="rule",
        quote="absolute claims are prohibited",
    )

    result = verify_evidence(_state([issue], [evidence]))

    assert result["compliance_issues"][0]["issue_type"] == "title_violation"
    assert result["evidence_coverage"]["coverage_score"] == 100


def test_title_issue_without_span_is_downgraded() -> None:
    issue = ComplianceIssue(
        issue_type="title_compliance",
        severity="medium",
        message="title issue without span",
        evidence_ids=["rule:title"],
    )
    evidence = Evidence(
        evidence_id="rule:title",
        source="rules.py",
        source_type="rule",
        quote="title rule",
    )

    result = verify_evidence(_state([issue], [evidence]))

    assert result["compliance_issues"][0]["issue_type"] == "human_review_reason"
    assert result["evidence_coverage"]["items"][0]["missing_requirements"] == [
        "matched_span"
    ]
