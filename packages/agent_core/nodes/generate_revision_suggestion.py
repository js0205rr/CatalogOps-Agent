from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import run_node, summarize
from packages.catalog.rules import rewrite_product_title
from packages.catalog.schemas import (
    CategoryPrediction,
    ComplianceIssue,
    ExtractedAttributes,
    ProductInput,
    RevisionSuggestion,
)


def generate_revision_suggestion(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        extracted = ExtractedAttributes.model_validate(state.get("extracted_attributes") or {})
        issues = [
            ComplianceIssue.model_validate(item)
            for item in state.get("compliance_issues") or state.get("issues") or []
        ]
        suggestion = rewrite_product_title(product, issues, prediction, extracted)
        missing = list(state.get("missing_attributes") or [])
        for name in missing:
            suggestion.seller_feedback.append(f"Provide required attribute: {name}")
        suggestion.notes = list(suggestion.seller_feedback)
        payload = suggestion.model_dump()
        return {
            "rewrite_suggestions": payload,
            "suggestion": payload,
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "generate_revision_suggestion",
                    "detail": "revision suggestion generated",
                },
            ],
        }

    def fallback(exc: Exception) -> dict:
        suggestion = RevisionSuggestion(
            seller_feedback=[f"Revision suggestion fallback: {exc}"]
        )
        payload = suggestion.model_dump()
        return {"rewrite_suggestions": payload, "suggestion": payload}

    return run_node(
        state,
        node="generate_revision_suggestion",
        input_summary=summarize(
            {
                "missing": state.get("missing_attributes", []),
                "issues": state.get("compliance_issues", []),
            }
        ),
        fn=work,
        fallback=fallback,
    )
