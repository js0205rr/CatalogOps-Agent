from __future__ import annotations

from uuid import uuid4

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import run_node, summarize
from packages.catalog.quality_scorer import score_product_quality
from packages.catalog.schemas import (
    CategoryConsistencyResult,
    CategoryPrediction,
    ComplianceIssue,
    Evidence,
    EvidenceCoverage,
    ExtractedAttributes,
    ProductInput,
    ReviewResult,
    RevisionSuggestion,
)


def _decide(issues: list[ComplianceIssue], check: CategoryConsistencyResult) -> str:
    if any(
        issue.issue_type in {"low_confidence", "human_review_reason"}
        for issue in issues
    ):
        return "human_review"
    if any(
        issue.issue_type == "category_mismatch" and issue.severity == "blocker"
        for issue in issues
    ):
        return "reject"
    if any(
        issue.issue_type == "title_violation" and issue.severity == "blocker"
        for issue in issues
    ):
        return "reject"
    if any(issue.severity == "blocker" for issue in issues):
        return "needs_revision"
    if issues or not check.is_consistent:
        return "needs_revision"
    return "pass"


def make_publish_decision(state: CatalogAgentState) -> dict:
    def work() -> dict:
        issues = [
            ComplianceIssue.model_validate(item)
            for item in state.get("compliance_issues") or state.get("issues") or []
        ]
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        check = CategoryConsistencyResult.model_validate(state.get("seller_category_check") or {})
        extracted = ExtractedAttributes.model_validate(state.get("extracted_attributes") or {})
        decision = _decide(issues, check)
        if state.get("publish_decision") == "human_review":
            decision = "human_review"
        evidence = [Evidence.model_validate(item) for item in state.get("evidence") or []]
        quality = score_product_quality(
            check,
            extracted,
            issues,
            evidence,
            missing_attributes=list(state.get("missing_attributes") or []),
        )
        final_trace = [
            *(state.get("trace") or []),
            {"node": "make_publish_decision", "detail": f"decision {decision}"},
        ]
        result = ReviewResult(
            product=ProductInput.model_validate(state["product"]),
            publish_decision=decision,
            quality_score=quality,
            predicted_category=prediction,
            seller_category_check=check,
            extracted_attributes=extracted,
            missing_attributes=list(state.get("missing_attributes") or []),
            compliance_issues=issues,
            human_review_reasons=list(state.get("human_review_reasons") or []),
            rewrite_suggestions=RevisionSuggestion.model_validate(
                state.get("rewrite_suggestions") or {}
            ),
            evidence=evidence,
            evidence_coverage=EvidenceCoverage.model_validate(
                state.get("evidence_coverage") or {}
            ),
            trace_id=str(state.get("trace_id") or f"trace-{uuid4().hex}"),
            trace=final_trace,
            tool_trace=list(state.get("tool_trace") or []),
        )
        return {
            "publish_decision": decision,
            "decision": decision,
            "quality_score": quality.model_dump(),
            "confidence": quality.overall,
            "result": result.model_dump(mode="json"),
            "trace": final_trace,
        }

    def fallback(exc: Exception) -> dict:
        return {
            "publish_decision": "human_review",
            "decision": "human_review",
            "trace": [
                *(state.get("trace") or []),
                {"node": "make_publish_decision", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="make_publish_decision",
        input_summary=summarize(
            {
                "issues": state.get("compliance_issues", []),
                "missing": state.get("missing_attributes", []),
            }
        ),
        fn=work,
        fallback=fallback,
    )
