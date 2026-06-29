from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from packages.batch_analysis.batch_graph import run_batch_review


def test_batch_report_generation() -> None:
    root = Path(__file__).resolve().parents[1]
    result = run_batch_review(root / "data" / "sample_products" / "sample_products.csv")

    assert result.profile.rows == 3
    assert result.profile.row_count == 3
    assert result.profile.missing_rates
    assert "CatalogOps Batch Review Report" in result.report_markdown
    assert result.rows
    assert sum(result.metrics.decision_distribution.values()) == 3
    assert 0.0 <= result.metrics.category_mismatch_rate <= 1.0
    assert result.selected_rows
    assert result.policy_contexts
    assert result.trace[-1]["node"] == "generate_batch_report"
