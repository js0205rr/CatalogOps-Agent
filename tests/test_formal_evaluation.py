from __future__ import annotations

import importlib

import pytest


pytest.importorskip("pydantic")
pytest.importorskip("langgraph")

formal_eval = importlib.import_module("scripts.evaluate_catalogops_formal")


def test_report_predictions_use_sample_product_id_mapping() -> None:
    report = {
        "category_predictions": [
            {"row_index": 0, "category_check": {"status": "mismatch"}},
            {"row_index": 1, "category_check": {"status": "match"}},
        ],
        "precheck": [
            {"row_index": 1, "issue_type": "title_violation"},
        ],
        "reviews": [
            {
                "product": {"sku_id": "ECOM-000020"},
                "missing_attributes": ["brand"],
                "compliance_issues": [
                    {"issue_type": "missing_attribute", "evidence_ids": ["attr-required"]}
                ],
            }
        ],
    }
    product_id_to_index = {
        "ECOM-000007": 0,
        "ECOM-000020": 1,
    }

    predictions = formal_eval._report_predictions(report, 2, product_id_to_index)

    assert predictions[0]["category_mismatch"] is True
    assert predictions[0]["attribute_missing"] is False
    assert predictions[1]["category_mismatch"] is False
    assert predictions[1]["attribute_missing"] is True
    assert predictions[1]["title_issue"] is True
    assert predictions[1]["any_issue"] is True


def test_binary_metrics() -> None:
    metrics = formal_eval._binary_metrics(
        expected=[True, True, False, False],
        predicted=[True, False, True, False],
    )

    assert metrics.tp == 1
    assert metrics.fp == 1
    assert metrics.fn == 1
    assert metrics.tn == 1
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
    assert metrics.f1 == 0.5
