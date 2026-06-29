from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import merge_evidence, run_node, summarize
from packages.catalog.schemas import ComplianceIssue, Evidence, ProductInput


def parse_input(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product_input"])
        evidence = Evidence(
            evidence_id=f"product:{product.sku_id}",
            source=product.sku_id,
            source_type="product",
            quote=product.title,
            metadata={"evidence_kind": "product_text"},
        )
        return {
            "product": product.model_dump(),
            "evidence": merge_evidence(state, evidence.model_dump()),
            "compliance_issues": list(state.get("compliance_issues") or []),
            "issues": list(state.get("issues") or []),
            "trace": [
                *(state.get("trace") or []),
                {"node": "parse_input", "detail": "validated product input"},
            ],
        }

    def fallback(exc: Exception) -> dict:
        product = ProductInput(title="Untitled product")
        issue = ComplianceIssue(
            issue_type="low_confidence",
            severity="warning",
            message=f"Input parsing failed; default product used: {exc}",
        )
        return {
            "product": product.model_dump(),
            "compliance_issues": [issue.model_dump()],
            "issues": [issue.model_dump()],
            "trace": [
                *(state.get("trace") or []),
                {"node": "parse_input", "detail": "fallback product used"},
            ],
        }

    return run_node(
        state,
        node="parse_input",
        input_summary=summarize(state.get("product_input", {})),
        fn=work,
        fallback=fallback,
    )
