from __future__ import annotations

from typing import Any

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import run_node, summarize
from packages.catalog.schemas import (
    ComplianceIssue,
    Evidence,
    EvidenceCoverage,
    EvidenceCoverageItem,
)


TITLE_ISSUE_TYPES = {"title_violation", "title_compliance"}


def _is_product_or_category_prediction(evidence: Evidence) -> bool:
    kind = str(evidence.metadata.get("evidence_kind", ""))
    return (
        kind in {"product_text", "category_prediction"}
        or evidence.source_type == "product"
        or evidence.evidence_id in {"taxonomy:catalog-v1", "taxonomy:category-keywords"}
    )


def _is_attribute_schema(evidence: Evidence) -> bool:
    kind = str(evidence.metadata.get("evidence_kind", ""))
    doc_type = str(evidence.metadata.get("doc_type", ""))
    return evidence.source_type == "attribute_schema" or kind == "attribute_schema" or (
        evidence.source_type == "policy" and doc_type == "attribute_schema"
    )


def _is_title_rule_or_policy(evidence: Evidence) -> bool:
    return evidence.source_type in {"rule", "policy"}


def _evidence_requirements(
    issue: ComplianceIssue,
    linked: list[Evidence],
) -> tuple[list[str], list[str]]:
    if issue.issue_type == "category_mismatch":
        required = ["product_text_or_category_prediction"]
        missing = (
            []
            if any(_is_product_or_category_prediction(item) for item in linked)
            else required
        )
        return required, missing
    if issue.issue_type == "missing_attribute":
        required = ["attribute_schema"]
        missing = [] if any(_is_attribute_schema(item) for item in linked) else required
        return required, missing
    if issue.issue_type in TITLE_ISSUE_TYPES:
        required = ["matched_span", "rule_or_policy"]
        missing: list[str] = []
        if not issue.matched_span.strip():
            missing.append("matched_span")
        if not any(_is_title_rule_or_policy(item) for item in linked):
            missing.append("rule_or_policy")
        return required, missing
    required = ["linked_evidence"]
    return required, [] if linked else required


def _downgrade_issue(issue: ComplianceIssue, missing: list[str]) -> ComplianceIssue:
    return issue.model_copy(
        update={
            "issue_type": "human_review_reason",
            "severity": "warning",
            "message": (
                f"Evidence verification failed ({', '.join(missing)}); "
                f"manual review required: {issue.message}"
            ),
        }
    )


def verify_evidence(state: CatalogAgentState) -> dict[str, Any]:
    def work() -> dict[str, Any]:
        evidence = [Evidence.model_validate(item) for item in state.get("evidence") or []]
        evidence_map = {item.evidence_id: item for item in evidence}
        verified: list[dict[str, Any]] = []
        coverage_items: list[EvidenceCoverageItem] = []
        human_review_reasons: list[str] = []
        covered_count = 0
        removed_count = 0
        downgraded_count = 0

        raw_issues = state.get("compliance_issues") or state.get("issues") or []
        for raw in raw_issues:
            issue = ComplianceIssue.model_validate(raw)
            linked = [
                evidence_map[evidence_id]
                for evidence_id in issue.evidence_ids
                if evidence_id in evidence_map
            ]
            issue.evidence_ids = [item.evidence_id for item in linked]
            required, missing = _evidence_requirements(issue, linked)

            if not missing:
                covered_count += 1
                verified.append(issue.model_dump())
                status = "covered"
            elif issue.severity == "info":
                removed_count += 1
                status = "removed"
            else:
                downgraded = _downgrade_issue(issue, missing)
                downgraded_count += 1
                verified.append(downgraded.model_dump())
                human_review_reasons.append(downgraded.message)
                status = "downgraded"

            coverage_items.append(
                EvidenceCoverageItem(
                    issue_id=issue.issue_id,
                    original_issue_type=issue.issue_type,
                    status=status,  # type: ignore[arg-type]
                    required_evidence=required,
                    matched_evidence_ids=issue.evidence_ids,
                    missing_requirements=missing,
                )
            )

        total = len(raw_issues)
        coverage = EvidenceCoverage(
            total_issues=total,
            covered_issues=covered_count,
            removed_issues=removed_count,
            downgraded_issues=downgraded_count,
            coverage_score=round(covered_count / total * 100, 2) if total else 100.0,
            items=coverage_items,
        )
        updates: dict[str, Any] = {
            "compliance_issues": verified,
            "issues": verified,
            "evidence_coverage": coverage.model_dump(),
            "human_review_reasons": human_review_reasons,
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "verify_evidence",
                    "detail": (
                        f"covered {covered_count}/{total}; removed {removed_count}; "
                        f"downgraded {downgraded_count}"
                    ),
                },
            ],
        }
        if downgraded_count:
            updates["publish_decision"] = "human_review"
            updates["decision"] = "human_review"
        return updates

    def fallback(exc: Exception) -> dict[str, Any]:
        return {
            "publish_decision": "human_review",
            "decision": "human_review",
            "human_review_reasons": [f"Evidence verification failed: {exc}"],
            "evidence_coverage": EvidenceCoverage(coverage_score=0.0).model_dump(),
            "trace": [
                *(state.get("trace") or []),
                {"node": "verify_evidence", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="verify_evidence",
        input_summary=summarize(
            {
                "issues": state.get("compliance_issues", []),
                "evidence": state.get("evidence", []),
            }
        ),
        fn=work,
        fallback=fallback,
    )
