from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from packages.agent_core.state import CatalogAgentState


def summarize(value: Any, *, limit: int = 220) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def append_trace(
    state: CatalogAgentState,
    *,
    node: str,
    status: str,
    input_summary: str,
    output_summary: str,
    started_at: float,
) -> list[dict[str, Any]]:
    trace = list(state.get("tool_trace") or [])
    trace.append(
        {
            "node": node,
            "status": status,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": round((time.perf_counter() - started_at) * 1000, 3),
        }
    )
    return trace


def append_error(state: CatalogAgentState, *, node: str, error: Exception) -> list[dict[str, Any]]:
    errors = list(state.get("errors") or [])
    errors.append({"node": node, "error": str(error), "type": error.__class__.__name__})
    return errors


def run_node(
    state: CatalogAgentState,
    *,
    node: str,
    input_summary: str,
    fn: Callable[[], dict[str, Any]],
    fallback: Callable[[Exception], dict[str, Any]],
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        updates = fn()
        updates["tool_trace"] = append_trace(
            state,
            node=node,
            status="ok",
            input_summary=input_summary,
            output_summary=summarize(updates),
            started_at=started_at,
        )
        return updates
    except Exception as exc:  # noqa: BLE001
        updates = fallback(exc)
        updates["errors"] = append_error(state, node=node, error=exc)
        updates["tool_trace"] = append_trace(
            state,
            node=node,
            status="error",
            input_summary=input_summary,
            output_summary=summarize(updates),
            started_at=started_at,
        )
        return updates


def merge_issues(state: CatalogAgentState, *new_issues: dict[str, Any]) -> list[dict[str, Any]]:
    return [*(state.get("compliance_issues") or state.get("issues") or []), *new_issues]


def merge_evidence(state: CatalogAgentState, *new_evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [*(state.get("evidence") or []), *new_evidence]

