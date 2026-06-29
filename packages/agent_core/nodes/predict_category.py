from __future__ import annotations

from packages.agent_core.catalog_rules import predict_category_rule
from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import merge_evidence, run_node, summarize
from packages.catalog.schemas import CategoryPrediction, Evidence, ProductInput


def predict_category(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = predict_category_rule(product)
        evidence = Evidence(
            evidence_id="taxonomy:catalog-v1",
            source="data/taxonomy/catalog_taxonomy.json",
            source_type="taxonomy",
            quote=(
                f"{prediction.category_path}; "
                f"matched terms: {', '.join(prediction.matched_terms)}"
            ),
            score=prediction.confidence,
            metadata={"evidence_kind": "category_prediction"},
        )
        payload = prediction.model_dump()
        return {
            "predicted_category": payload,
            "category_prediction": payload,
            "evidence": merge_evidence(state, evidence.model_dump()),
            "trace": [
                *(state.get("trace") or []),
                {"node": "predict_category", "detail": prediction.category_path},
            ],
        }

    def fallback(exc: Exception) -> dict:
        prediction = CategoryPrediction(
            category_id="unknown",
            category_path="unknown",
            confidence=0.0,
            matched_terms=[],
            evidence_ids=[],
        )
        payload = prediction.model_dump()
        return {
            "predicted_category": payload,
            "category_prediction": payload,
            "trace": [
                *(state.get("trace") or []),
                {"node": "predict_category", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="predict_category",
        input_summary=summarize(state.get("product", {})),
        fn=work,
        fallback=fallback,
    )
