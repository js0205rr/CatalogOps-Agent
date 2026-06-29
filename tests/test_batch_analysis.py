from __future__ import annotations

import csv
import json

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from packages.batch_analysis import batch_nodes
from packages.agent_core.catalog_rules import predict_category_rule
from packages.catalog.schemas import ProductInput


def _write_catalog_csv(tmp_path):
    path = tmp_path / "catalog.csv"
    fields = [
        "product_id",
        "title",
        "description",
        "seller_category",
        "attributes",
        "seller_id",
        "price",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "product_id": "P-1",
                "title": "iPhone 15 透明手机壳",
                "description": "TPU 防摔保护壳",
                "seller_category": "数码配件/手机配件/手机壳",
                "attributes": json.dumps({"材质": "TPU", "颜色": "透明"}, ensure_ascii=False),
                "seller_id": "S-1",
                "price": "39.9",
            }
        )
        writer.writerow(
            {
                "product_id": "P-1",
                "title": "",
                "description": "",
                "seller_category": "",
                "attributes": "",
                "seller_id": "S-2",
                "price": "9.9",
            }
        )
    return path


def test_profile_and_precheck(tmp_path) -> None:
    state = {"csv_path": str(_write_catalog_csv(tmp_path)), "trace": []}
    profiled = batch_nodes.profile_catalog_csv(state)
    profile = profiled["profile"]

    assert profile["row_count"] == 2
    assert profile["duplicate_count"] == 1
    assert profile["seller_count"] == 2
    assert profile["missing_rates"]["title"] == 0.5
    assert profile["category_distribution"]["未填写类目"] == 1

    checked = batch_nodes.run_batch_precheck({**state, **profiled})
    issue_types = {item["issue_type"] for item in checked["precheck"]}
    assert {"empty_title", "empty_category", "empty_attributes"} <= issue_types


def test_category_prediction_is_lightweight_and_selection_is_risk_only(
    tmp_path,
    monkeypatch,
) -> None:
    state = {"csv_path": str(_write_catalog_csv(tmp_path)), "trace": []}
    state.update(batch_nodes.profile_catalog_csv(state))
    state.update(batch_nodes.run_batch_precheck(state))

    def fail_full_review(*args, **kwargs):
        raise AssertionError("category prediction must not call full review or LLM")

    monkeypatch.setattr(batch_nodes, "run_product_review", fail_full_review)
    state.update(batch_nodes.run_batch_category_prediction(state))
    assert len(state["category_predictions"]) == 2

    class RetrievalResult:
        def model_dump(self, **kwargs):
            return {"hits": [], "mode": "mock"}

    from packages.rag_policy import tools

    calls: list[str] = []

    def retrieve(query):
        calls.append(query.category_path)
        return RetrievalResult()

    monkeypatch.setattr(tools, "retrieve_category_policy", retrieve)
    monkeypatch.setattr(tools, "retrieve_attribute_schema", retrieve)
    monkeypatch.setattr(tools, "retrieve_title_policy", retrieve)
    selected = batch_nodes.selective_policy_retrieval(state)

    assert selected["selected_rows"] == [0, 1]
    assert len(calls) == 6


def test_category_prediction_clips_long_batch_descriptions(tmp_path) -> None:
    path = tmp_path / "long_description.csv"
    fields = [
        "product_id",
        "title",
        "description",
        "seller_category",
        "attributes",
        "seller_id",
        "price",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "product_id": "LONG-1",
                "title": "Cotton shirt",
                "description": "shirt " * 1200,
                "seller_category": "Clothing & Accessories > Tops",
                "attributes": "{}",
                "seller_id": "seller-long",
                "price": "",
            }
        )

    state = {"csv_path": str(path), "trace": []}
    state.update(batch_nodes.profile_catalog_csv(state))
    result = batch_nodes.run_batch_category_prediction(state)

    assert result["category_predictions"][0]["product_id"] == "LONG-1"


def test_batch_category_prediction_covers_ecommerce_domains(tmp_path) -> None:
    path = tmp_path / "ecommerce_domains.csv"
    fields = [
        "product_id",
        "title",
        "description",
        "seller_category",
        "attributes",
        "seller_id",
        "price",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "product_id": "ELEC-1",
                "title": "Bluetooth wireless earbuds with charging case",
                "description": "portable earphones speaker audio",
                "seller_category": "Electronics",
                "attributes": "{}",
                "seller_id": "seller-1",
                "price": "",
            }
        )
        writer.writerow(
            {
                "product_id": "HOME-1",
                "title": "Kitchen storage container jar set",
                "description": "household kitchen dining container",
                "seller_category": "Household",
                "attributes": "{}",
                "seller_id": "seller-2",
                "price": "",
            }
        )
        writer.writerow(
            {
                "product_id": "BOOK-1",
                "title": "Exam preparation study guide textbook",
                "description": "academic solved papers question bank",
                "seller_category": "Books",
                "attributes": "{}",
                "seller_id": "seller-3",
                "price": "",
            }
        )

    state = {"csv_path": str(path), "trace": []}
    state.update(batch_nodes.profile_catalog_csv(state))
    result = batch_nodes.run_batch_category_prediction(state)
    paths = [
        item["category_prediction"]["category_path"]
        for item in result["category_predictions"]
    ]

    assert paths == [
        "Electronics > Audio",
        "Household > Kitchen & Dining",
        "Books > Academic & Exam Prep",
    ]


def test_agent_core_category_rule_respects_ascii_token_boundaries() -> None:
    prediction = predict_category_rule(
        ProductInput(
            sku_id="BOOK-BOUNDARY",
            title="The Prophet About the Author Kahlil Gibran",
            description="A classic book by a noted author.",
            seller_category="Books",
            attributes={"source_category": "Books"},
        )
    )

    assert prediction.category_path.startswith("Books")
    assert prediction.category_path != "Clothing & Accessories > Innerwear"
