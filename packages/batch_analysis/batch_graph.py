from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from packages.batch_analysis.batch_nodes import (
    aggregate_batch_issues,
    generate_batch_report,
    plan_batch_strategy,
    profile_catalog_csv,
    run_batch_category_prediction,
    run_batch_precheck,
    selective_policy_retrieval,
)
from packages.agent_core.state import BatchReviewState
from packages.catalog.schemas import BatchReviewResult


NODES = [
    ("profile_catalog_csv", profile_catalog_csv),
    ("plan_batch_strategy", plan_batch_strategy),
    ("run_batch_precheck", run_batch_precheck),
    ("run_batch_category_prediction", run_batch_category_prediction),
    ("selective_policy_retrieval", selective_policy_retrieval),
    ("aggregate_batch_issues", aggregate_batch_issues),
    ("generate_batch_report", generate_batch_report),
]
TOOL_NODES = {"selective_policy_retrieval"}


def build_batch_review_graph():
    graph = StateGraph(BatchReviewState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for (current, _), (nxt, _) in zip(NODES, NODES[1:]):
        graph.add_edge(current, nxt)
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()


def run_batch_review(
    csv_path: str | Path,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> BatchReviewResult:
    initial: BatchReviewState = {"csv_path": str(csv_path), "trace": []}
    graph = build_batch_review_graph()
    if emit is None:
        final = graph.invoke(initial)
    else:
        final: BatchReviewState = dict(initial)
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
    return BatchReviewResult.model_validate(final["result"])
