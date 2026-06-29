from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("USE_MOCK", "true")

from packages.batch_analysis.batch_graph import run_batch_review
from packages.rag_policy.config import get_policy_rag_settings
from packages.rag_policy.ingestion.indexer import PolicyDocumentIndexer


DEFAULT_INPUT = ROOT / "dataset" / "processed" / "ecommerce_catalogops_mismatch_sample_2000.csv"
DEFAULT_OUTPUT_DIR = ROOT / "dataset" / "processed" / "batch_runs"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _sample_rows(rows: list[dict[str, str]], sample_size: int) -> list[dict[str, str]]:
    if len(rows) <= sample_size:
        return rows
    by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_category[row.get("seller_category", "")].append(row)
    categories = sorted(by_category)
    per_category = max(1, sample_size // max(1, len(categories)))
    sampled: list[dict[str, str]] = []
    for category in categories:
        sampled.extend(by_category[category][:per_category])
    if len(sampled) < sample_size:
        used = {row.get("product_id") for row in sampled}
        sampled.extend(row for row in rows if row.get("product_id") not in used)
    return sampled[:sample_size]


def _policy_hit_stats(policy_contexts: dict[Any, Any]) -> dict[str, Any]:
    doc_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    doc_type_counter: Counter[str] = Counter()
    empty_contexts = 0
    for context in policy_contexts.values():
        context_has_hit = False
        for retrieval_name, payload in (context or {}).items():
            hits = payload.get("hits") or []
            if hits:
                context_has_hit = True
            for hit in hits:
                doc_counter[str(hit.get("doc_id") or "")] += 1
                metadata = hit.get("metadata") or {}
                category_counter[str(metadata.get("category") or "")] += 1
                doc_type_counter[str(metadata.get("doc_type") or retrieval_name)] += 1
        if not context_has_hit:
            empty_contexts += 1
    return {
        "empty_policy_contexts": empty_contexts,
        "top_policy_docs": dict(doc_counter.most_common(20)),
        "hit_categories": dict(category_counter.most_common(20)),
        "hit_doc_types": dict(doc_type_counter.most_common(20)),
    }


def _review_evidence_stats(reviews: list[Any]) -> dict[str, Any]:
    issue_counter: Counter[str] = Counter()
    issue_without_evidence: Counter[str] = Counter()
    decision_counter: Counter[str] = Counter()
    coverage_scores: list[float] = []
    total_evidence = 0
    downgraded = 0
    removed = 0
    covered = 0
    for review in reviews:
        decision_counter[str(review.get("publish_decision", ""))] += 1
        evidence = review.get("evidence") or []
        total_evidence += len(evidence)
        coverage = review.get("evidence_coverage") or {}
        if "coverage_score" in coverage:
            coverage_scores.append(float(coverage.get("coverage_score") or 0.0))
        downgraded += int(coverage.get("downgraded_issues") or 0)
        removed += int(coverage.get("removed_issues") or 0)
        covered += int(coverage.get("covered_issues") or 0)
        for issue in review.get("compliance_issues") or []:
            issue_type = str(issue.get("issue_type") or "unknown")
            issue_counter[issue_type] += 1
            if not issue.get("evidence_ids"):
                issue_without_evidence[issue_type] += 1
    return {
        "review_count": len(reviews),
        "total_evidence_items": total_evidence,
        "avg_evidence_per_review": round(total_evidence / len(reviews), 4) if reviews else 0.0,
        "avg_evidence_coverage_score": round(sum(coverage_scores) / len(coverage_scores), 4)
        if coverage_scores
        else 0.0,
        "covered_issues": covered,
        "downgraded_issues": downgraded,
        "removed_issues": removed,
        "decision_distribution": dict(decision_counter),
        "issues": dict(issue_counter),
        "issues_without_evidence": dict(issue_without_evidence),
    }


def run_smoke(input_csv: Path, output_dir: Path, sample_size: int) -> dict[str, Any]:
    start = time.perf_counter()
    settings = get_policy_rag_settings()
    ingestion = PolicyDocumentIndexer(settings).index_directory(settings.policy_dir)

    rows = _read_csv(input_csv)
    sampled = _sample_rows(rows, sample_size)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = output_dir / f"ecommerce_policy_smoke_{len(sampled)}.csv"
    _write_csv(sample_path, sampled, list(sampled[0].keys()) if sampled else [])

    result = run_batch_review(sample_path)
    payload = result.model_dump(mode="json")
    summary = {
        "input_csv": str(input_csv),
        "sample_csv": str(sample_path),
        "sample_size": len(sampled),
        "elapsed_seconds": round(time.perf_counter() - start, 3),
        "ingestion": ingestion.model_dump(mode="json"),
        "profile": payload.get("profile"),
        "selected_policy_rows": len(payload.get("selected_rows") or []),
        "metrics": payload.get("metrics"),
        "issue_summary": payload.get("issue_summary"),
        "policy_hit_stats": _policy_hit_stats(payload.get("policy_contexts") or {}),
        "review_evidence_stats": _review_evidence_stats(payload.get("reviews") or []),
        "trace": payload.get("trace"),
    }

    summary_path = output_dir / f"ecommerce_policy_smoke_{len(sampled)}_summary.json"
    report_path = output_dir / f"ecommerce_policy_smoke_{len(sampled)}_report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(payload.get("report_markdown") or "", encoding="utf-8")
    summary["outputs"] = {"summary_json": str(summary_path), "report_markdown": str(report_path)}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest policy docs and run a four-class batch evidence smoke test."
    )
    parser.add_argument("--input-csv", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-size", type=int, default=200)
    args = parser.parse_args()
    summary = run_smoke(Path(args.input_csv), Path(args.output_dir), args.sample_size)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
