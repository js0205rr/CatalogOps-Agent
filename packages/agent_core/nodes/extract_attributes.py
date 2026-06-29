from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import run_node, summarize
from packages.catalog.attribute_extractor import extract_product_attributes
from packages.catalog.schemas import CategoryPrediction, ExtractedAttributes, ProductInput


def extract_attributes(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        extracted = extract_product_attributes(product, prediction.category_path)
        return {
            "extracted_attributes": extracted.model_dump(),
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "extract_attributes",
                    "detail": f"extracted {len(extracted.values)} attributes",
                },
            ],
        }

    def fallback(exc: Exception) -> dict:
        return {
            "extracted_attributes": ExtractedAttributes(confidence=0.0).model_dump(),
            "trace": [
                *(state.get("trace") or []),
                {"node": "extract_attributes", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="extract_attributes",
        input_summary=summarize(state.get("product", {})),
        fn=work,
        fallback=fallback,
    )
