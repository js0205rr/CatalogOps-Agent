from __future__ import annotations

import os

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from packages.agent_core.single_graph import run_product_review
from packages.catalog.schemas import ProductInput


def test_mock_mode_runs_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    os.environ["CATALOGOPS_MOCK_LLM"] = "true"

    result = run_product_review(
        ProductInput(
            title="Apple iPhone 15 5G \u624b\u673a 128GB \u9ed1\u8272",
            merchant_category="\u6570\u7801\u5bb6\u7535/\u624b\u673a\u901a\u8baf/\u667a\u80fd\u624b\u673a",
            attributes={
                "\u54c1\u724c": "Apple",
                "\u578b\u53f7": "iPhone 15",
                "\u5b58\u50a8\u5bb9\u91cf": "128GB",
                "\u7f51\u7edc\u5236\u5f0f": "5G",
            },
        )
    )

    assert result.decision == "pass"
    assert result.evidence
