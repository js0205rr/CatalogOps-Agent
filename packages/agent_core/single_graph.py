from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from packages.agent_core.nodes import (
    check_attribute_completeness,
    check_category_consistency,
    check_title_compliance,
    extract_attributes,
    generate_revision_suggestion,
    make_publish_decision,
    parse_input,
    predict_category,
    retrieve_policy,
    verify_evidence,
)
from packages.agent_core.state import CatalogAgentState
from packages.catalog.schemas import ProductInput, ReviewResult


NODES = [
    ("parse_input", parse_input),
    ("predict_category", predict_category),
    ("check_category_consistency", check_category_consistency),
    ("retrieve_policy", retrieve_policy),
    ("extract_attributes", extract_attributes),
    ("check_attribute_completeness", check_attribute_completeness),
    ("check_title_compliance", check_title_compliance),
    ("generate_revision_suggestion", generate_revision_suggestion),
    ("verify_evidence", verify_evidence),
    ("make_publish_decision", make_publish_decision),
]
TOOL_NODES = {"retrieve_policy"}


def build_product_review_graph():
    graph = StateGraph(CatalogAgentState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for (current, _), (nxt, _) in zip(NODES, NODES[1:]):
        graph.add_edge(current, nxt)
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()


def run_product_review(
    product: ProductInput | dict[str, Any],
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> ReviewResult:
    initial: CatalogAgentState = {
        "product_input": ProductInput.model_validate(product).model_dump(),
        "compliance_issues": [],
        "issues": [],
        "evidence": [],
        "trace": [],
        "tool_trace": [],
        "errors": [],
    }
    graph = build_product_review_graph()
    if emit is None:
        final = graph.invoke(initial)
    else:
        final: CatalogAgentState = dict(initial)
        try:
            for event in graph.stream(initial, stream_mode="updates"):
                for node, update in event.items():
                    emit({"event": "node_start", "node": node, "payload": {}})
                    if node in TOOL_NODES:
                        emit({"event": "tool_start", "tool": node, "payload": {}})
                    if isinstance(update, dict):
                        final.update(update)
                    if node in TOOL_NODES:
                        emit({"event": "tool_end", "tool": node, "payload": update})
                    emit({"event": "node_end", "node": node, "payload": update})
        except Exception as exc:
            emit({"event": "error", "payload": {"message": str(exc)}})
            raise
    result_payload = dict(final["result"])
    result_payload["tool_trace"] = list(final.get("tool_trace") or [])
    result_payload["trace"] = list(final.get("trace") or result_payload.get("trace") or [])
    return ReviewResult.model_validate(result_payload)
