from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import run_node, summarize
from packages.catalog.category_predictor import (
    check_category_consistency as detect_category_consistency,
)
from packages.catalog.schemas import (
    CategoryConsistencyResult,
    CategoryPrediction,
    ComplianceIssue,
    ProductInput,
)


def check_category_consistency(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        seller_category = product.seller_category or product.merchant_category
        check = detect_category_consistency(seller_category, prediction)
        check.evidence_ids = list(
            dict.fromkeys(
                [*check.evidence_ids, "taxonomy:catalog-v1", f"product:{product.sku_id}"]
            )
        )

        issues = list(state.get("compliance_issues") or state.get("issues") or [])
        if check.status == "mismatch":
            issue = ComplianceIssue(
                issue_id=f"{product.sku_id}:category",
                issue_type="category_mismatch",
                severity="blocker",
                message=(
                    f"Seller category '{seller_category}' does not match predicted category "
                    f"'{prediction.category_path}'."
                ),
                evidence_ids=check.evidence_ids,
                suggested_fix=(
                    f"Move listing to '{prediction.category_path}' or request manual review."
                ),
            )
            issues.append(issue.model_dump())
        elif check.status == "uncertain":
            issue = ComplianceIssue(
                issue_id=f"{product.sku_id}:category_uncertain",
                issue_type="low_confidence",
                severity="warning",
                message=f"Category consistency is uncertain: {check.reason}.",
                evidence_ids=check.evidence_ids,
                suggested_fix=(
                    "Send to manual category review or provide a clearer merchant category."
                ),
            )
            issues.append(issue.model_dump())
        return {
            "seller_category_check": check.model_dump(),
            "compliance_issues": issues,
            "issues": issues,
            "trace": [
                *(state.get("trace") or []),
                {"node": "check_category_consistency", "detail": check.reason},
            ],
        }

    def fallback(exc: Exception) -> dict:
        check = CategoryConsistencyResult(
            is_consistent=False,
            confidence=0.0,
            reason=f"fallback: {exc}",
        )
        return {
            "seller_category_check": check.model_dump(),
            "trace": [
                *(state.get("trace") or []),
                {"node": "check_category_consistency", "detail": check.reason},
            ],
        }

    return run_node(
        state,
        node="check_category_consistency",
        input_summary=summarize(
            {"product": state.get("product"), "predicted_category": state.get("predicted_category")}
        ),
        fn=work,
        fallback=fallback,
    )
