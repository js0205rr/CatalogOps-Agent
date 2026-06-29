from __future__ import annotations

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from packages.agent_core.single_graph import NODES, build_product_review_graph, run_product_review
from packages.catalog.schemas import ProductInput


PHONE = "\u6570\u7801\u5bb6\u7535/\u624b\u673a\u901a\u8baf/\u667a\u80fd\u624b\u673a"
PHONE_CASE = "\u6570\u7801\u914d\u4ef6/\u624b\u673a\u914d\u4ef6/\u624b\u673a\u58f3"
EARBUDS = "\u6570\u7801\u914d\u4ef6/\u97f3\u9891\u8bbe\u5907/\u84dd\u7259\u8033\u673a"
TSHIRT = "\u670d\u9970\u978b\u5305/\u5973\u88c5/T\u6064"


def _invoke(product: ProductInput) -> dict:
    graph = build_product_review_graph()
    return graph.invoke(
        {
            "product_input": product.model_dump(),
            "compliance_issues": [],
            "issues": [],
            "evidence": [],
            "trace": [],
            "tool_trace": [],
            "errors": [],
        }
    )


def _assert_trace_shape(state: dict) -> None:
    expected = [name for name, _node in NODES]
    actual = [item["node"] for item in state["tool_trace"]]

    assert actual == expected
    assert all(item["status"] in {"ok", "error"} for item in state["tool_trace"])
    assert all("latency_ms" in item for item in state["tool_trace"])
    assert all("input_summary" in item for item in state["tool_trace"])
    assert all("output_summary" in item for item in state["tool_trace"])


def test_phone_case_mislisted_as_phone_category() -> None:
    state = _invoke(
        ProductInput(
            sku_id="CASE-1",
            title="iPhone 15 \u624b\u673a\u58f3 \u900f\u660e\u4fdd\u62a4\u5957",
            merchant_category=PHONE,
            attributes={
                "\u54c1\u724c": "Acme",
                "\u9002\u7528\u673a\u578b": "iPhone 15",
                "\u6750\u8d28": "TPU",
                "\u989c\u8272": "\u900f\u660e",
            },
        )
    )

    _assert_trace_shape(state)
    assert state["predicted_category"]["category_id"] == "2002"
    assert any(issue["issue_type"] == "category_mismatch" for issue in state["compliance_issues"])
    assert state["publish_decision"] == "reject"


def test_low_confidence_category_prediction_goes_to_human_review() -> None:
    result = run_product_review(
        ProductInput(
            sku_id="UNKNOWN-1",
            title="\u795e\u79d8\u65b0\u54c1 \u8d85\u503c\u7ec4\u5408",
            merchant_category=PHONE,
            attributes={},
        )
    )

    assert result.seller_category_check.status == "uncertain"
    assert not any(issue.issue_type == "category_mismatch" for issue in result.compliance_issues)
    assert any(issue.issue_type == "low_confidence" for issue in result.compliance_issues)
    assert result.publish_decision == "human_review"


def test_bluetooth_earbuds_missing_required_attribute() -> None:
    result = run_product_review(
        ProductInput(
            sku_id="EAR-1",
            title="Sony \u84dd\u7259\u8033\u673a \u5165\u8033\u5f0f \u964d\u566a",
            merchant_category=EARBUDS,
            attributes={
                "\u54c1\u724c": "Sony",
                "\u578b\u53f7": "WF-1000XM5",
                "\u8fde\u63a5\u65b9\u5f0f": "\u84dd\u7259",
            },
        )
    )

    assert result.predicted_category is not None
    assert result.predicted_category.category_id == "2003"
    assert "\u7eed\u822a\u65f6\u95f4" in result.missing_attributes
    assert result.publish_decision == "needs_revision"


def test_title_contains_absolute_claim() -> None:
    result = run_product_review(
        ProductInput(
            sku_id="TEE-1",
            title=(
                "\u7edd\u5bf9\u7b2c\u4e00 "
                "\u7eaf\u68c9\u5973\u88c5\u77ed\u8896T\u6064 \u767d\u8272"
            ),
            merchant_category=TSHIRT,
            attributes={
                "\u54c1\u724c": "Acme",
                "\u6750\u8d28": "\u7eaf\u68c9",
                "\u5c3a\u7801": "M",
                "\u989c\u8272": "\u767d\u8272",
            },
        )
    )

    assert any(issue.issue_type == "title_violation" for issue in result.compliance_issues)
    assert result.publish_decision == "reject"


def test_normal_product_passes() -> None:
    result = run_product_review(
        ProductInput(
            sku_id="CASE-OK",
            title="iPhone 15 \u624b\u673a\u58f3 TPU \u900f\u660e\u4fdd\u62a4\u5957",
            merchant_category=PHONE_CASE,
            attributes={
                "\u54c1\u724c": "Acme",
                "\u9002\u7528\u673a\u578b": "iPhone 15",
                "\u6750\u8d28": "TPU",
                "\u989c\u8272": "\u900f\u660e",
            },
        )
    )

    assert result.publish_decision == "pass"
    assert result.compliance_issues == []
    assert len(result.tool_trace) == len(NODES)
