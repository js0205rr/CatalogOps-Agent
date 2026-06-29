from __future__ import annotations

from typing import Any

from packages.catalog.schemas import (
    CategoryConsistencyResult,
    ComplianceIssue,
    Evidence,
    ExtractedAttributes,
    QualityScore,
)


QUALITY_WEIGHTS = {
    "category": 0.35,
    "attributes": 0.30,
    "title": 0.20,
    "evidence": 0.15,
}


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _category_score(check: CategoryConsistencyResult) -> float:
    base = {
        "match": 100.0,
        "close_match": 82.0,
        "mismatch": 20.0,
        "uncertain": 45.0,
    }[check.status]
    return _clamp(base * 0.7 + check.confidence * 100 * 0.3)


def _attribute_score(extracted: ExtractedAttributes, missing_attributes: list[str]) -> float:
    present = len([value for value in extracted.values.values() if value])
    missing = len(missing_attributes)
    if present + missing == 0:
        return 50.0
    completeness = present / (present + missing)
    return _clamp(completeness * 100)


def _title_score(issues: list[ComplianceIssue]) -> float:
    title_issues = [issue for issue in issues if issue.issue_type == "title_violation"]
    score = 100.0
    for issue in title_issues:
        score -= 35.0 if issue.severity == "blocker" else 15.0
    return _clamp(score)


def _evidence_score(issues: list[ComplianceIssue], evidence: list[Evidence]) -> float:
    known = {item.evidence_id for item in evidence}
    conclusion_issues = [issue for issue in issues if issue.issue_type != "low_confidence"]
    if not conclusion_issues:
        return 100.0 if evidence else 50.0
    covered = sum(
        1 for issue in conclusion_issues if any(item in known for item in issue.evidence_ids)
    )
    return _clamp(covered / len(conclusion_issues) * 100)


def calculate_quality_score(
    category_accuracy: float,
    attribute_completeness: float,
    title_compliance: float,
    evidence_coverage: float,
    *,
    reasons: list[str] | None = None,
) -> QualityScore:
    category_score = _clamp(category_accuracy)
    attribute_score = _clamp(attribute_completeness)
    title_score = _clamp(title_compliance)
    evidence_score = _clamp(evidence_coverage)
    overall = _clamp(
        category_score * QUALITY_WEIGHTS["category"]
        + attribute_score * QUALITY_WEIGHTS["attributes"]
        + title_score * QUALITY_WEIGHTS["title"]
        + evidence_score * QUALITY_WEIGHTS["evidence"]
    )
    return QualityScore(
        overall=overall,
        category=category_score,
        attributes=attribute_score,
        title=title_score,
        evidence=evidence_score,
        reasons=list(reasons or []),
    )


def score_product_quality(
    category_accuracy: CategoryConsistencyResult | dict[str, Any],
    attribute_completeness: ExtractedAttributes | dict[str, Any],
    title_compliance: list[ComplianceIssue | dict[str, Any]],
    evidence_coverage: list[Evidence | dict[str, Any]],
    *,
    missing_attributes: list[str] | None = None,
) -> QualityScore:
    category = CategoryConsistencyResult.model_validate(category_accuracy)
    extracted = ExtractedAttributes.model_validate(attribute_completeness)
    issues = [ComplianceIssue.model_validate(issue) for issue in title_compliance]
    evidence = [Evidence.model_validate(item) for item in evidence_coverage]

    category_score = _category_score(category)
    attribute_score = _attribute_score(
        extracted,
        list(missing_attributes or extracted.missing_required),
    )
    title_score = _title_score(issues)
    evidence_score = _evidence_score(issues, evidence)
    reasons = [issue.message for issue in issues]
    if missing_attributes or extracted.missing_required:
        missing = missing_attributes or extracted.missing_required
        reasons.append(
            f"Missing required attributes: {', '.join(missing)}"
        )
    return calculate_quality_score(
        category_score,
        attribute_score,
        title_score,
        evidence_score,
        reasons=reasons,
    )
