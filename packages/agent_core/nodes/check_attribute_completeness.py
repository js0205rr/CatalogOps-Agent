from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import merge_evidence, merge_issues, run_node, summarize
from packages.catalog.attribute_extractor import check_required_attributes
from packages.catalog.schemas import (
    CategoryPrediction,
    ComplianceIssue,
    Evidence,
    ExtractedAttributes,
)


def check_attribute_completeness(state: CatalogAgentState) -> dict:
    def work() -> dict:
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        extracted = ExtractedAttributes.model_validate(state.get("extracted_attributes") or {})
        attr_hits = ((state.get("policies") or {}).get("attribute") or {}).get("hits") or []
        missing = check_required_attributes(extracted, prediction.category_path, attr_hits)
        issues = list(state.get("compliance_issues") or state.get("issues") or [])
        schema_evidence = Evidence(
            evidence_id="attribute-schema:required-attributes-v1",
            source="data/taxonomy/required_attributes.json",
            source_type="attribute_schema",
            quote=f"{prediction.category_path}; required attributes: {', '.join(missing)}",
            metadata={
                "evidence_kind": "attribute_schema",
                "category": prediction.category_path,
            },
        )
        evidence_ids = [schema_evidence.evidence_id]
        if attr_hits:
            evidence_ids = [f"policy:{attr_hits[0]['chunk_id']}"]
        for name in missing:
            issues = merge_issues(
                {**state, "compliance_issues": issues},
                ComplianceIssue(
                    issue_id=f"attribute:{name}",
                    issue_type="missing_attribute",
                    severity="blocker",
                    message=f"Missing required category attribute: {name}",
                    evidence_ids=evidence_ids,
                    suggested_fix=f"Provide attribute '{name}'.",
                ).model_dump(),
            )
        extracted.missing_required = missing
        return {
            "extracted_attributes": extracted.model_dump(),
            "missing_attributes": missing,
            "compliance_issues": issues,
            "issues": issues,
            "evidence": merge_evidence(state, schema_evidence.model_dump()),
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "check_attribute_completeness",
                    "detail": f"missing {len(missing)} attributes",
                },
            ],
        }

    def fallback(exc: Exception) -> dict:
        return {
            "missing_attributes": [],
            "trace": [
                *(state.get("trace") or []),
                {"node": "check_attribute_completeness", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="check_attribute_completeness",
        input_summary=summarize(state.get("extracted_attributes", {})),
        fn=work,
        fallback=fallback,
    )
