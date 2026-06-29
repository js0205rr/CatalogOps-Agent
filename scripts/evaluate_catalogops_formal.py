from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("USE_MOCK", "true")

from pydantic import BaseModel, Field

from packages.batch_analysis.batch_graph import run_batch_review
from packages.catalog.rules import ABSOLUTE_CLAIMS, MARKETING_TERMS
from packages.rag_policy.config import get_policy_rag_settings
from packages.rag_policy.ingestion.indexer import PolicyDocumentIndexer


DEFAULT_INPUT = ROOT / "dataset" / "processed" / "ecommerce_catalogops_mismatch_20pct.csv"
DEFAULT_OUTPUT_DIR = ROOT / "dataset" / "processed" / "evaluation"
ISSUE_TYPES = ("category_mismatch", "attribute_missing", "title_issue", "any_issue")


class BinaryConfusion(BaseModel):
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    support: int = 0
    predicted_positive: int = 0


class FormalEvaluationReport(BaseModel):
    input_csv: str
    sample_csv: str
    output_dir: str
    sample_size: int
    generated_at: str
    use_mock: bool
    label_notes: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_coverage: dict[str, Any] = Field(default_factory=dict)
    runtime_cost: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _json_dict(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _top_category(category_path: str) -> str:
    return str(category_path or "").split(">")[0].strip()


def _truth_category(row: dict[str, str]) -> str:
    attrs = _json_dict(row.get("attributes", ""))
    return str(attrs.get("source_category") or attrs.get("true_category") or "").strip()


def _sample_rows(rows: list[dict[str, str]], sample_size: int) -> list[dict[str, str]]:
    if len(rows) <= sample_size:
        return rows
    buckets: dict[tuple[str, bool], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        true_category = _truth_category(row)
        seller_category = row.get("seller_category", "")
        buckets[(_top_category(true_category), true_category != seller_category)].append(row)
    keys = sorted(buckets)
    per_bucket = max(1, sample_size // max(1, len(keys)))
    sampled: list[dict[str, str]] = []
    used: set[str] = set()
    for key in keys:
        for row in buckets[key][:per_bucket]:
            sampled.append(row)
            used.add(row.get("product_id", ""))
    if len(sampled) < sample_size:
        for row in rows:
            product_id = row.get("product_id", "")
            if product_id in used:
                continue
            sampled.append(row)
            used.add(product_id)
            if len(sampled) >= sample_size:
                break
    return sampled[:sample_size]


def _has_title_issue(title: str) -> bool:
    lowered = title.lower()
    absolute = any(term.lower() in lowered for term in ABSOLUTE_CLAIMS)
    marketing_hits = [term for term in MARKETING_TERMS if term.lower() in lowered]
    return absolute or len(marketing_hits) >= 2


def _required_attributes_for_category(true_category: str) -> list[str]:
    path = ROOT / "data" / "taxonomy" / "required_attributes.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if true_category in payload:
        return [str(item) for item in payload[true_category]]
    top = _top_category(true_category)
    return [str(item) for item in payload.get(top, [])]


def _attribute_missing_truth(row: dict[str, str]) -> bool:
    attrs = _json_dict(row.get("attributes", ""))
    true_category = _truth_category(row) or row.get("seller_category", "")
    required = _required_attributes_for_category(true_category)
    if not required:
        return not bool(attrs)
    normalized_keys = {str(key).strip().lower() for key, value in attrs.items() if str(value).strip()}
    missing = [
        name for name in required if name.strip().lower() not in normalized_keys
    ]
    return bool(missing)


def _expected_flags(row: dict[str, str]) -> dict[str, bool]:
    true_category = _truth_category(row)
    seller_category = row.get("seller_category", "")
    category_mismatch = bool(true_category and true_category != seller_category)
    attribute_missing = _attribute_missing_truth(row)
    title_issue = _has_title_issue(row.get("title", ""))
    return {
        "category_mismatch": category_mismatch,
        "attribute_missing": attribute_missing,
        "title_issue": title_issue,
        "any_issue": category_mismatch or attribute_missing or title_issue,
    }


def _report_predictions(
    report: dict[str, Any],
    row_count: int,
    product_id_to_index: dict[str, int],
) -> dict[int, dict[str, bool]]:
    predictions = {
        idx: {issue_type: False for issue_type in ISSUE_TYPES}
        for idx in range(row_count)
    }
    for item in report.get("category_predictions") or []:
        idx = int(item.get("row_index", 0))
        status = ((item.get("category_check") or {}).get("status") or "")
        if status == "mismatch":
            predictions[idx]["category_mismatch"] = True
    for issue in report.get("precheck") or []:
        idx = int(issue.get("row_index", 0))
        issue_type = issue.get("issue_type")
        if issue_type == "empty_attributes":
            predictions[idx]["attribute_missing"] = True
        if issue_type in {"empty_title", "title_violation"}:
            predictions[idx]["title_issue"] = True
    for review in report.get("reviews") or []:
        product_id = ((review.get("product") or {}).get("sku_id") or "")
        idx = product_id_to_index.get(product_id)
        if idx is None or idx not in predictions:
            continue
        if review.get("missing_attributes"):
            predictions[idx]["attribute_missing"] = True
        for issue in review.get("compliance_issues") or []:
            issue_type = issue.get("issue_type")
            if issue_type == "category_mismatch":
                predictions[idx]["category_mismatch"] = True
            if issue_type == "missing_attribute":
                predictions[idx]["attribute_missing"] = True
            if issue_type in {"title_violation", "title_compliance"}:
                predictions[idx]["title_issue"] = True
    for flags in predictions.values():
        flags["any_issue"] = any(flags[name] for name in ISSUE_TYPES if name != "any_issue")
    return predictions


def _category_accuracy(report: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    total = 0
    correct = 0
    by_category: Counter[str] = Counter()
    correct_by_category: Counter[str] = Counter()
    for item in report.get("category_predictions") or []:
        idx = int(item.get("row_index", 0))
        if idx >= len(rows):
            continue
        true_category = _top_category(_truth_category(rows[idx]))
        predicted = _top_category((item.get("category_prediction") or {}).get("category_path", ""))
        if not true_category or not predicted:
            continue
        total += 1
        by_category[true_category] += 1
        if predicted == true_category:
            correct += 1
            correct_by_category[true_category] += 1
    return {
        "accuracy": round(correct / total, 6) if total else 0.0,
        "correct": correct,
        "total": total,
        "by_category": {
            category: {
                "accuracy": round(correct_by_category[category] / count, 6) if count else 0.0,
                "correct": correct_by_category[category],
                "total": count,
            }
            for category, count in sorted(by_category.items())
        },
    }


def _binary_metrics(expected: list[bool], predicted: list[bool]) -> BinaryConfusion:
    tp = sum(1 for truth, pred in zip(expected, predicted) if truth and pred)
    fp = sum(1 for truth, pred in zip(expected, predicted) if not truth and pred)
    fn = sum(1 for truth, pred in zip(expected, predicted) if truth and not pred)
    tn = sum(1 for truth, pred in zip(expected, predicted) if not truth and not pred)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return BinaryConfusion(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=round(precision, 6),
        recall=round(recall, 6),
        f1=round(f1, 6),
        support=tp + fn,
        predicted_positive=tp + fp,
    )


def _classification_metrics(
    rows: list[dict[str, str]],
    predicted_flags: dict[int, dict[str, bool]],
) -> dict[str, Any]:
    expected_flags = [_expected_flags(row) for row in rows]
    by_issue = {}
    for issue_type in ISSUE_TYPES:
        expected = [flags[issue_type] for flags in expected_flags]
        predicted = [predicted_flags[idx][issue_type] for idx in range(len(rows))]
        by_issue[issue_type] = _binary_metrics(expected, predicted).model_dump()
    macro_f1 = sum(by_issue[name]["f1"] for name in ISSUE_TYPES) / len(ISSUE_TYPES)
    return {
        "by_issue_type": by_issue,
        "macro_f1": round(macro_f1, 6),
        "label_distribution": {
            issue_type: sum(flags[issue_type] for flags in expected_flags)
            for issue_type in ISSUE_TYPES
        },
        "prediction_distribution": {
            issue_type: sum(predicted_flags[idx][issue_type] for idx in range(len(rows)))
            for issue_type in ISSUE_TYPES
        },
    }


def _evidence_coverage(report: dict[str, Any]) -> dict[str, Any]:
    reviews = report.get("reviews") or []
    total_issues = 0
    issues_without_evidence: Counter[str] = Counter()
    total_evidence = 0
    coverage_scores: list[float] = []
    downgraded = 0
    removed = 0
    covered = 0
    for review in reviews:
        evidence = review.get("evidence") or []
        total_evidence += len(evidence)
        coverage = review.get("evidence_coverage") or {}
        if "coverage_score" in coverage:
            coverage_scores.append(float(coverage.get("coverage_score") or 0.0))
        downgraded += int(coverage.get("downgraded_issues") or 0)
        removed += int(coverage.get("removed_issues") or 0)
        covered += int(coverage.get("covered_issues") or 0)
        for issue in review.get("compliance_issues") or []:
            total_issues += 1
            if not issue.get("evidence_ids"):
                issues_without_evidence[str(issue.get("issue_type") or "unknown")] += 1
    contexts = report.get("policy_contexts") or {}
    selected = report.get("selected_rows") or []
    contexts_with_hits = 0
    for context in contexts.values():
        if any((payload or {}).get("hits") for payload in (context or {}).values()):
            contexts_with_hits += 1
    return {
        "review_count": len(reviews),
        "review_issue_count": total_issues,
        "review_issues_without_evidence": dict(issues_without_evidence),
        "review_issue_evidence_coverage": round(
            1 - (sum(issues_without_evidence.values()) / total_issues), 6
        )
        if total_issues
        else 1.0,
        "avg_evidence_per_review": round(total_evidence / len(reviews), 6)
        if reviews
        else 0.0,
        "avg_evidence_coverage_score": round(
            sum(coverage_scores) / len(coverage_scores), 6
        )
        if coverage_scores
        else 0.0,
        "covered_issues": covered,
        "downgraded_issues": downgraded,
        "removed_issues": removed,
        "selected_policy_rows": len(selected),
        "policy_contexts_with_hits": contexts_with_hits,
        "policy_context_hit_rate": round(contexts_with_hits / len(selected), 6)
        if selected
        else 1.0,
    }


def _write_markdown(report: FormalEvaluationReport, path: Path) -> None:
    metrics = report.metrics
    lines = [
        "# CatalogOps Formal Evaluation",
        "",
        f"- Input: `{report.input_csv}`",
        f"- Sample size: {report.sample_size}",
        f"- Mock mode: {report.use_mock}",
        f"- Category accuracy: {metrics['category_accuracy']['accuracy']:.2%}",
        f"- Macro F1: {metrics['issue_classification']['macro_f1']:.4f}",
        "",
        "## Issue Metrics",
    ]
    for issue_type, item in metrics["issue_classification"]["by_issue_type"].items():
        lines.append(
            f"- {issue_type}: precision={item['precision']:.4f}, "
            f"recall={item['recall']:.4f}, f1={item['f1']:.4f}, "
            f"support={item['support']}"
        )
    coverage = report.evidence_coverage
    cost = report.runtime_cost
    lines.extend(
        [
            "",
            "## Evidence Coverage",
            f"- Review issue evidence coverage: {coverage['review_issue_evidence_coverage']:.2%}",
            f"- Policy context hit rate: {coverage['policy_context_hit_rate']:.2%}",
            f"- Avg evidence per review: {coverage['avg_evidence_per_review']:.2f}",
            f"- Issues without evidence: {coverage['review_issues_without_evidence']}",
            "",
            "## Runtime Cost",
            f"- Elapsed seconds: {cost['elapsed_seconds']}",
            f"- Rows per second: {cost['rows_per_second']}",
            f"- Full review rows: {cost['full_review_rows']}",
            f"- Estimated LLM calls: {cost['estimated_llm_calls']}",
            f"- Estimated token cost USD: {cost['estimated_token_cost_usd']}",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_evaluation(
    input_csv: Path,
    output_dir: Path,
    sample_size: int,
    *,
    write_raw_batch_report: bool = True,
) -> FormalEvaluationReport:
    started_at = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    timer = time.perf_counter()
    settings = get_policy_rag_settings()
    ingestion = PolicyDocumentIndexer(settings).index_directory(settings.policy_dir)

    source_rows = _read_csv(input_csv)
    rows = _sample_rows(source_rows, sample_size)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = output_dir / f"catalogops_eval_sample_{len(rows)}.csv"
    _write_csv(sample_path, rows, list(rows[0].keys()) if rows else [])

    batch_report = run_batch_review(sample_path)
    payload = batch_report.model_dump(mode="json")
    product_id_to_index = {
        str(row.get("product_id") or f"ROW-{idx + 1}"): idx
        for idx, row in enumerate(rows)
    }
    predicted_flags = _report_predictions(payload, len(rows), product_id_to_index)
    issue_metrics = _classification_metrics(rows, predicted_flags)
    category_metrics = _category_accuracy(payload, rows)
    elapsed = time.perf_counter() - timer
    coverage = _evidence_coverage(payload)

    prediction_rows = []
    for idx, row in enumerate(rows):
        expected = _expected_flags(row)
        predicted = predicted_flags[idx]
        prediction_rows.append(
            {
                "row_index": idx,
                "product_id": row.get("product_id", ""),
                "seller_category": row.get("seller_category", ""),
                "true_category": _truth_category(row),
                **{f"expected_{key}": value for key, value in expected.items()},
                **{f"predicted_{key}": value for key, value in predicted.items()},
            }
        )

    stem = f"catalogops_formal_eval_{len(rows)}"
    predictions_csv = output_dir / f"{stem}_predictions.csv"
    summary_json = output_dir / f"{stem}_summary.json"
    report_md = output_dir / f"{stem}_report.md"
    raw_batch_json = output_dir / f"{stem}_batch_report.json"
    _write_csv(predictions_csv, prediction_rows, list(prediction_rows[0].keys()) if prediction_rows else [])
    if write_raw_batch_report:
        raw_batch_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    outputs = {
        "summary_json": str(summary_json),
        "report_markdown": str(report_md),
        "predictions_csv": str(predictions_csv),
    }
    if write_raw_batch_report:
        outputs["raw_batch_report_json"] = str(raw_batch_json)

    report = FormalEvaluationReport(
        input_csv=str(input_csv),
        sample_csv=str(sample_path),
        output_dir=str(output_dir),
        sample_size=len(rows),
        generated_at=started_at,
        use_mock=settings.use_mock,
        label_notes={
            "category_mismatch": "Expected positive when attributes.source_category differs from seller_category.",
            "attribute_missing": "Expected positive when required attributes for the true/top category are absent.",
            "title_issue": "Expected positive from deterministic title rule terms.",
            "cost": "Mock/rule-first mode estimates LLM calls and token cost as zero.",
        },
        metrics={
            "category_accuracy": category_metrics,
            "issue_classification": issue_metrics,
            "batch_rates": payload.get("metrics") or {},
            "ingestion": ingestion.model_dump(mode="json"),
        },
        evidence_coverage=coverage,
        runtime_cost={
            "elapsed_seconds": round(elapsed, 3),
            "rows_per_second": round(len(rows) / elapsed, 6) if elapsed else 0.0,
            "selected_policy_rows": len(payload.get("selected_rows") or []),
            "full_review_rows": len(payload.get("reviews") or []),
            "estimated_llm_calls": 0 if settings.use_mock else None,
            "estimated_token_cost_usd": 0.0 if settings.use_mock else None,
        },
        outputs=outputs,
    )
    summary_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _write_markdown(report, report_md)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run formal CatalogOps evaluation for category mismatch, attribute "
            "missing, title issues, evidence coverage, and runtime cost."
        )
    )
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-size", type=int, default=400)
    parser.add_argument(
        "--skip-raw-batch-report",
        action="store_true",
        help="Skip writing the large raw batch report JSON; summary and predictions are still written.",
    )
    args = parser.parse_args()

    report = run_evaluation(
        Path(args.input_csv),
        Path(args.output_dir),
        args.sample_size,
        write_raw_batch_report=not args.skip_raw_batch_report,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
