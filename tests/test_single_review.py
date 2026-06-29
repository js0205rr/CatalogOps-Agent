from __future__ import annotations

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from packages.agent_core.single_graph import run_product_review
from packages.catalog.schemas import ProductInput


def test_single_product_review_main_path() -> None:
    result = run_product_review(
        ProductInput(
            sku_id="P1002",
            title="\u5168\u7f51\u6700\u4f4e \u7eaf\u68c9\u5973\u88c5\u77ed\u8896T\u6064 \u767d\u8272",
            description="\u57fa\u7840\u6b3e\u4e0a\u8863 \u5c3a\u7801: M",
            merchant_category="\u670d\u9970\u978b\u5305/\u5973\u88c5/T\u6064",
            attributes={"\u6750\u8d28": "\u7eaf\u68c9", "\u5c3a\u7801": "M", "\u989c\u8272": "\u767d\u8272"},
        )
    )

    assert result.category_prediction is not None
    assert result.category_prediction.category_id == "1001"
    assert result.issues
    assert any(issue.issue_type == "title_violation" for issue in result.issues)
    assert result.decision in {"reject", "human_review"}
    assert [item["node"] for item in result.trace][-1] == "make_publish_decision"
