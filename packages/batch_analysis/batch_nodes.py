from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from packages.agent_core.catalog_rules import predict_category_rule
from packages.agent_core.single_graph import run_product_review
from packages.agent_core.state import BatchReviewState
from packages.catalog.attribute_extractor import check_required_attributes, extract_product_attributes
from packages.catalog.category_predictor import check_category_consistency
from packages.catalog.rules import ABSOLUTE_CLAIMS, MARKETING_TERMS
from packages.catalog.schemas import (
    BatchAuditReport,
    BatchCatalogProfile,
    BatchCategoryPrediction,
    BatchIssueSummary,
    BatchMetrics,
    BatchPrecheckIssue,
    ProductInput,
)


REQUIRED_COLUMNS = (
    "product_id",
    "title",
    "description",
    "seller_category",
    "attributes",
    "seller_id",
    "price",
)
MAX_TITLE_LENGTH = 300
MAX_DESCRIPTION_LENGTH = 5000
ALIASES = {
    "product_id": ("product_id", "sku_id", "sku", "商品id", "商品编码"),
    "title": ("title", "商品标题", "标题"),
    "description": ("description", "商品描述", "描述", "详情"),
    "seller_category": ("seller_category", "merchant_category", "商家类目", "类目"),
    "attributes": ("attributes", "商品属性", "属性"),
    "seller_id": ("seller_id", "merchant_id", "商家id", "卖家id"),
    "price": ("price", "价格", "售价"),
}


def _trace(state: BatchReviewState, node: str, detail: str) -> list[dict[str, Any]]:
    return [*(state.get("trace") or []), {"node": node, "detail": detail}]


def _empty(value: Any) -> bool:
    if isinstance(value, (dict, list, tuple, set)):
        return not value
    return value is None or (
        isinstance(value, str) and value.strip().lower() in {"", "null", "none", "{}"}
    )


def _detect_columns(columns: list[str]) -> dict[str, str]:
    lowered = {column.strip().lower(): column for column in columns}
    detected: dict[str, str] = {}
    for canonical, names in ALIASES.items():
        for name in names:
            if name.lower() in lowered:
                detected[canonical] = lowered[name.lower()]
                break
    return detected


def _parse_attributes(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if not _empty(item)}
    if _empty(value):
        return {}
    text = str(value).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {str(key): item for key, item in parsed.items() if not _empty(item)}
    except json.JSONDecodeError:
        pass
    attributes: dict[str, Any] = {}
    for pair in text.replace("；", ";").split(";"):
        key, separator, item = pair.partition(":")
        if not separator:
            key, separator, item = pair.partition("：")
        if separator and key.strip() and item.strip():
            attributes[key.strip()] = item.strip()
    return attributes


def _normalise_row(
    row: dict[str, Any],
    detected: dict[str, str],
    idx: int,
) -> dict[str, Any]:
    known = set(detected.values())
    attributes = _parse_attributes(row.get(detected.get("attributes", "")))
    for column, value in row.items():
        if column is None or column in known or _empty(value):
            continue
        attributes[str(column)] = value
    product_id = str(row.get(detected.get("product_id", ""), "") or "").strip()
    return {
        "product_id": product_id,
        "title": str(row.get(detected.get("title", ""), "") or "").strip(),
        "description": str(row.get(detected.get("description", ""), "") or "").strip(),
        "seller_category": str(
            row.get(detected.get("seller_category", ""), "") or ""
        ).strip(),
        "attributes": attributes,
        "seller_id": str(row.get(detected.get("seller_id", ""), "") or "").strip(),
        "price": row.get(detected.get("price", ""), ""),
    }


def _row_to_product(row: dict[str, Any], idx: int) -> ProductInput:
    title = (str(row.get("title") or "").strip() or "Untitled product")[:MAX_TITLE_LENGTH]
    description = str(row.get("description") or "")[:MAX_DESCRIPTION_LENGTH]
    seller_category = str(row.get("seller_category") or "").strip()
    return ProductInput(
        sku_id=str(row.get("product_id") or f"ROW-{idx + 1}"),
        title=title,
        description=description,
        seller_category=seller_category,
        merchant_category=seller_category,
        attributes=row.get("attributes") or {},
    )


def profile_catalog_csv(state: BatchReviewState) -> dict[str, Any]:
    path = Path(state["csv_path"])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_rows = [dict(row) for row in reader]
        columns = [column for column in (reader.fieldnames or []) if column is not None]

    detected = _detect_columns(columns)
    rows = [_normalise_row(row, detected, idx) for idx, row in enumerate(raw_rows)]
    row_count = len(rows)
    missing_rates = {
        field: round(sum(_empty(row.get(field)) for row in rows) / row_count, 4)
        if row_count
        else 0.0
        for field in REQUIRED_COLUMNS
    }
    product_ids = [row["product_id"] for row in rows if not _empty(row["product_id"])]
    sellers = {row["seller_id"] for row in rows if not _empty(row["seller_id"])}
    categories = Counter(
        row["seller_category"] or "未填写类目"
        for row in rows
    )
    profile = BatchCatalogProfile(
        row_count=row_count,
        rows=row_count,
        columns=columns,
        detected_columns=detected,
        sample_skus=product_ids[:5],
        missing_rates=missing_rates,
        duplicate_count=len(product_ids) - len(set(product_ids)),
        seller_count=len(sellers),
        category_distribution=dict(categories),
    )
    return {
        "rows": rows,
        "profile": profile.model_dump(),
        "trace": _trace(state, "profile_catalog_csv", f"Loaded {row_count} rows"),
    }


def plan_batch_strategy(state: BatchReviewState) -> dict[str, Any]:
    row_count = len(state.get("rows") or [])
    strategy = {
        "mode": "full_rule_scan" if row_count <= 1000 else "chunked_rule_scan",
        "category_prediction": "lightweight_rules",
        "policy_retrieval": "risk_rows_only",
        "max_rows": row_count,
    }
    return {"strategy": strategy, "trace": _trace(state, "plan_batch_strategy", strategy["mode"])}


def run_batch_precheck(state: BatchReviewState) -> dict[str, Any]:
    issues: list[BatchPrecheckIssue] = []
    for idx, row in enumerate(state.get("rows") or []):
        common = {
            "row_index": idx,
            "product_id": str(row.get("product_id") or ""),
            "seller_id": str(row.get("seller_id") or ""),
            "seller_category": str(row.get("seller_category") or ""),
        }
        if _empty(row.get("title")):
            issues.append(BatchPrecheckIssue(**common, issue_type="empty_title", severity="blocker", message="标题为空"))
        if _empty(row.get("seller_category")):
            issues.append(BatchPrecheckIssue(**common, issue_type="empty_category", severity="warning", message="商家类目为空"))
        if not row.get("attributes"):
            issues.append(BatchPrecheckIssue(**common, issue_type="empty_attributes", severity="warning", message="商品属性为空"))

        title = str(row.get("title") or "")
        absolute_hits = [term for term in ABSOLUTE_CLAIMS if term.lower() in title.lower()]
        marketing_hits = [term for term in MARKETING_TERMS if term.lower() in title.lower()]
        violation_hits = absolute_hits or (marketing_hits if len(marketing_hits) >= 2 else [])
        if violation_hits:
            issues.append(
                BatchPrecheckIssue(
                    **common,
                    issue_type="title_violation",
                    severity="blocker" if absolute_hits else "warning",
                    message="标题命中明显违规或营销堆砌词",
                    matched_span="、".join(violation_hits),
                )
            )
    return {
        "precheck": [issue.model_dump() for issue in issues],
        "trace": _trace(state, "run_batch_precheck", f"Found {len(issues)} precheck issues"),
    }


def run_batch_category_prediction(state: BatchReviewState) -> dict[str, Any]:
    precheck_by_row: dict[int, list[dict[str, Any]]] = {}
    for issue in state.get("precheck") or []:
        precheck_by_row.setdefault(int(issue["row_index"]), []).append(issue)

    predictions: list[dict[str, Any]] = []
    for idx, row in enumerate(state.get("rows") or []):
        product = _row_to_product(row, idx)
        prediction = predict_category_rule(product)
        category_check = check_category_consistency(product.seller_category, prediction)
        extracted = extract_product_attributes(product, prediction.category_path)
        missing_required = check_required_attributes(extracted, prediction.category_path)
        risk_flags: list[str] = []
        if category_check.status == "mismatch":
            risk_flags.append("mismatch")
        if prediction.confidence < 0.65 or category_check.status == "uncertain":
            risk_flags.append("low_confidence")
        if missing_required:
            risk_flags.append("attribute_missing")
        row_issues = precheck_by_row.get(idx, [])
        if any(
            issue["issue_type"] in {"empty_title", "empty_attributes", "title_violation"}
            for issue in row_issues
        ) or missing_required:
            risk_flags.append("high_risk")
        item = BatchCategoryPrediction(
            row_index=idx,
            product_id=product.sku_id,
            seller_id=str(row.get("seller_id") or ""),
            seller_category=product.seller_category,
            category_prediction=prediction,
            category_check=category_check,
            risk_flags=list(dict.fromkeys(risk_flags)),
            high_risk="high_risk" in risk_flags,
        )
        predictions.append(item.model_dump())
    return {
        "category_predictions": predictions,
        "trace": _trace(state, "run_batch_category_prediction", f"Rule-predicted {len(predictions)} rows; LLM calls: 0"),
    }


def selective_policy_retrieval(state: BatchReviewState) -> dict[str, Any]:
    selected = [
        item
        for item in state.get("category_predictions") or []
        if set(item.get("risk_flags") or []) & {"mismatch", "low_confidence", "high_risk"}
    ]
    selected_rows = [int(item["row_index"]) for item in selected]
    contexts: dict[int, dict[str, Any]] = {}
    if selected:
        from packages.rag_policy.schemas import PolicyQuery
        from packages.rag_policy.tools import (
            retrieve_attribute_schema,
            retrieve_category_policy,
            retrieve_title_policy,
        )

        rows = state.get("rows") or []
        for item in selected:
            idx = int(item["row_index"])
            category_path = item["category_prediction"]["category_path"]
            title = str(rows[idx].get("title") or "")
            common = {"query": category_path, "category_path": category_path, "top_k": 3}
            contexts[idx] = {
                "category_policy": retrieve_category_policy(PolicyQuery(**common)).model_dump(mode="json"),
                "attribute_schema": retrieve_attribute_schema(PolicyQuery(**common)).model_dump(mode="json"),
                "title_policy": retrieve_title_policy(
                    PolicyQuery(query=title or category_path, category_path=category_path, top_k=3)
                ).model_dump(mode="json"),
            }
    return {
        "selected_rows": selected_rows,
        "policy_contexts": contexts,
        "trace": _trace(state, "selective_policy_retrieval", f"Retrieved policy for {len(selected_rows)} risk rows"),
    }


def _top(counter: Counter[str], limit: int = 10) -> dict[str, int]:
    return dict(counter.most_common(limit))


def aggregate_batch_issues(state: BatchReviewState) -> dict[str, Any]:
    rows = state.get("rows") or []
    selected_rows = set(state.get("selected_rows") or [])
    reviews_by_row: dict[int, dict[str, Any]] = {}
    for idx in selected_rows:
        result = run_product_review(_row_to_product(rows[idx], idx))
        reviews_by_row[idx] = result.model_dump(mode="json")

    precheck_by_row: dict[int, list[dict[str, Any]]] = {}
    issue_counter: Counter[tuple[str, str]] = Counter()
    for issue in state.get("precheck") or []:
        idx = int(issue["row_index"])
        precheck_by_row.setdefault(idx, []).append(issue)
        issue_counter[(issue["issue_type"], issue["severity"])] += 1
    for result in reviews_by_row.values():
        for issue in result.get("compliance_issues") or result.get("issues") or []:
            issue_counter[(issue.get("issue_type", "unknown"), issue.get("severity", "info"))] += 1

    predictions = state.get("category_predictions") or []
    mismatch_rows = {
        int(item["row_index"]) for item in predictions if item["category_check"]["status"] == "mismatch"
    }
    attribute_rows = {
        idx for idx, issues in precheck_by_row.items() if any(item["issue_type"] == "empty_attributes" for item in issues)
    }
    title_rows = {
        idx for idx, issues in precheck_by_row.items() if any(item["issue_type"] in {"empty_title", "title_violation"} for item in issues)
    }
    for idx, result in reviews_by_row.items():
        if result.get("missing_attributes"):
            attribute_rows.add(idx)
        if any(
            issue.get("issue_type") in {"title_violation", "title_compliance"}
            for issue in result.get("compliance_issues") or []
        ):
            title_rows.add(idx)

    decision_counter: Counter[str] = Counter()
    issue_categories: Counter[str] = Counter()
    issue_sellers: Counter[str] = Counter()
    issue_rows = mismatch_rows | attribute_rows | title_rows | selected_rows
    for idx, row in enumerate(rows):
        decision = reviews_by_row.get(idx, {}).get("publish_decision", "pass")
        decision_counter[str(decision)] += 1
        if idx in issue_rows:
            issue_categories[str(row.get("seller_category") or "未填写类目")] += 1
            issue_sellers[str(row.get("seller_id") or "未填写商家")] += 1

    total = len(rows)
    metrics = BatchMetrics(
        category_mismatch_rate=round(len(mismatch_rows) / total, 4) if total else 0.0,
        attribute_missing_rate=round(len(attribute_rows) / total, 4) if total else 0.0,
        title_issue_rate=round(len(title_rows) / total, 4) if total else 0.0,
        decision_distribution=dict(decision_counter),
        top_issue_categories=_top(issue_categories),
        top_issue_sellers=_top(issue_sellers),
    )
    issue_summary = [
        BatchIssueSummary(issue_type=issue_type, severity=severity, count=count).model_dump()
        for (issue_type, severity), count in sorted(issue_counter.items())
    ]
    return {
        "review_results": list(reviews_by_row.values()),
        "issue_summary": issue_summary,
        "metrics": metrics.model_dump(),
        "trace": _trace(state, "aggregate_batch_issues", f"Aggregated {sum(issue_counter.values())} issues"),
    }


def generate_batch_report(state: BatchReviewState) -> dict[str, Any]:
    profile = BatchCatalogProfile.model_validate(state["profile"])
    metrics = BatchMetrics.model_validate(state.get("metrics") or {})
    summary = [BatchIssueSummary.model_validate(item) for item in state.get("issue_summary") or []]
    report_lines = [
        "# CatalogOps Batch Review Report",
        "",
        f"- Rows: {profile.row_count}",
        f"- Duplicate products: {profile.duplicate_count}",
        f"- Sellers: {profile.seller_count}",
        f"- Risk rows with policy retrieval: {len(state.get('selected_rows') or [])}",
        f"- Category mismatch rate: {metrics.category_mismatch_rate:.2%}",
        f"- Attribute missing rate: {metrics.attribute_missing_rate:.2%}",
        f"- Title issue rate: {metrics.title_issue_rate:.2%}",
        "",
        "## Decision Distribution",
        *[f"- {name}: {count}" for name, count in metrics.decision_distribution.items()],
        "",
        "## Top Issue Categories",
        *([f"- {name}: {count}" for name, count in metrics.top_issue_categories.items()] or ["- None"]),
        "",
        "## Top Issue Sellers",
        *([f"- {name}: {count}" for name, count in metrics.top_issue_sellers.items()] or ["- None"]),
        "",
        "## Issue Summary",
        *([f"- {item.issue_type} / {item.severity}: {item.count}" for item in summary] or ["- No issues found"]),
    ]
    report_markdown = "\n".join(report_lines)
    trace = _trace(state, "generate_batch_report", "Generated markdown batch report")
    result = BatchAuditReport(
        profile=profile,
        precheck=state.get("precheck") or [],
        category_predictions=state.get("category_predictions") or [],
        selected_rows=state.get("selected_rows") or [],
        policy_contexts=state.get("policy_contexts") or {},
        reviews=state.get("review_results") or [],
        issue_summary=summary,
        metrics=metrics,
        report_markdown=report_markdown,
        trace=trace,
    )
    return {"report_markdown": report_markdown, "trace": trace, "result": result.model_dump(mode="json")}
