from __future__ import annotations

from typing import Any, TypedDict


class ToolTraceEntry(TypedDict, total=False):
    node: str
    status: str
    input_summary: str
    output_summary: str
    latency_ms: float


class CatalogAgentState(TypedDict, total=False):
    product_input: dict[str, Any]
    product: dict[str, Any]
    predicted_category: dict[str, Any]
    category_prediction: dict[str, Any]
    seller_category_check: dict[str, Any]
    policies: dict[str, Any]
    extracted_attributes: dict[str, Any]
    missing_attributes: list[str]
    compliance_issues: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    evidence_coverage: dict[str, Any]
    human_review_reasons: list[str]
    rewrite_suggestions: dict[str, Any]
    suggestion: dict[str, Any]
    publish_decision: str
    decision: str
    quality_score: dict[str, Any]
    confidence: float
    trace_id: str
    trace: list[dict[str, Any]]
    tool_trace: list[ToolTraceEntry]
    errors: list[dict[str, Any]]
    result: dict[str, Any]


ProductReviewState = CatalogAgentState


class BatchReviewState(TypedDict, total=False):
    csv_path: str
    rows: list[dict[str, Any]]
    profile: dict[str, Any]
    strategy: dict[str, Any]
    precheck: list[dict[str, Any]]
    category_predictions: list[dict[str, Any]]
    selected_rows: list[int]
    policy_contexts: dict[int, dict[str, Any]]
    review_results: list[dict[str, Any]]
    issue_summary: list[dict[str, Any]]
    metrics: dict[str, Any]
    report_markdown: str
    trace: list[dict[str, Any]]
    result: dict[str, Any]
