from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import merge_evidence, run_node, summarize
from packages.catalog.rules import check_product_title
from packages.catalog.schemas import CategoryPrediction, Evidence, ProductInput


def check_title_compliance(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        issues = list(state.get("compliance_issues") or state.get("issues") or [])
        title_hits = ((state.get("policies") or {}).get("title") or {}).get("hits") or []
        rule_evidence = Evidence(
            evidence_id="rule:title-compliance-v1",
            source="packages/catalog/rules.py",
            source_type="rule",
            quote=(
                "Title compliance checks absolute claims, keyword stuffing, "
                "information sufficiency, and category conflicts."
            ),
            metadata={"evidence_kind": "title_compliance_rule"},
        )
        evidence_ids = ["rule:title-compliance-v1"]
        if title_hits:
            evidence_ids.append(f"policy:{title_hits[0]['chunk_id']}")
        title_issues = check_product_title(
            product,
            prediction,
            evidence_ids=evidence_ids,
        )
        issues.extend(issue.model_dump() for issue in title_issues)
        return {
            "compliance_issues": issues,
            "issues": issues,
            "evidence": merge_evidence(state, rule_evidence.model_dump()),
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "check_title_compliance",
                    "detail": f"title rules found {len(title_issues)} issues",
                },
            ],
        }

    def fallback(exc: Exception) -> dict:
        return {
            "trace": [
                *(state.get("trace") or []),
                {"node": "check_title_compliance", "detail": f"fallback: {exc}"},
            ]
        }

    return run_node(
        state,
        node="check_title_compliance",
        input_summary=summarize((state.get("product") or {}).get("title", "")),
        fn=work,
        fallback=fallback,
    )
