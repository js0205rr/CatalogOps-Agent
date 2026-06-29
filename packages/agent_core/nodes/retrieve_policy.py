from __future__ import annotations

from packages.agent_core.state import CatalogAgentState
from packages.agent_core.nodes.utils import merge_evidence, run_node, summarize
from packages.catalog.schemas import CategoryPrediction, Evidence, ProductInput
from packages.rag_policy.schemas import PolicyQuery
from packages.rag_policy.tools import (
    retrieve_attribute_schema,
    retrieve_category_policy,
    retrieve_title_policy,
)


def retrieve_policy(state: CatalogAgentState) -> dict:
    def work() -> dict:
        product = ProductInput.model_validate(state["product"])
        prediction = CategoryPrediction.model_validate(state["predicted_category"])
        query = PolicyQuery(
            query=f"{product.title} {prediction.category_path}",
            category_id=prediction.category_id,
            category_path=prediction.category_path,
            top_k=3,
        )
        results = {
            "category": retrieve_category_policy(query).model_dump(),
            "attribute": retrieve_attribute_schema(query).model_dump(),
            "title": retrieve_title_policy(query).model_dump(),
        }
        evidence_items = []
        for result in results.values():
            for hit in result.get("hits", []):
                evidence_items.append(
                    Evidence(
                        evidence_id=f"policy:{hit['chunk_id']}",
                        source=hit.get("metadata", {}).get(
                            "file_path",
                            hit.get("doc_id", ""),
                        ),
                        source_type=(
                            "attribute_schema"
                            if hit.get("source_type") == "attribute_schema"
                            else "policy"
                        ),
                        quote=hit.get("text", "")[:800],
                        score=min(1.0, float(hit.get("score", 0.0)) / 10.0),
                        metadata={
                            "doc_id": hit.get("doc_id", ""),
                            "rank": hit.get("rank", 0),
                            "doc_type": hit.get("source_type", ""),
                        },
                    ).model_dump()
                )
        return {
            "policies": results,
            "evidence": merge_evidence(state, *evidence_items),
            "trace": [
                *(state.get("trace") or []),
                {
                    "node": "retrieve_policy",
                    "detail": f"retrieved {len(evidence_items)} chunks",
                },
            ],
        }

    def fallback(exc: Exception) -> dict:
        return {
            "policies": {},
            "trace": [
                *(state.get("trace") or []),
                {"node": "retrieve_policy", "detail": f"fallback: {exc}"},
            ],
        }

    return run_node(
        state,
        node="retrieve_policy",
        input_summary=summarize(state.get("predicted_category", {})),
        fn=work,
        fallback=fallback,
    )
