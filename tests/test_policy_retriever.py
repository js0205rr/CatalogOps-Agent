from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from packages.rag_policy.service import PolicyRAGService


def test_phone_case_category_retrieves_phone_case_schema(monkeypatch) -> None:
    monkeypatch.setenv("USE_MOCK", "true")
    service = PolicyRAGService()

    chunks = service.retrieve_attribute_schema("数码配件/手机配件/手机壳")

    assert chunks
    assert chunks[0].doc_id == "phone_case_schema"
    assert Path(chunks[0].metadata["file_path"]).name == "phone_case_schema.md"
    assert chunks[0].metadata["doc_type"] == "attribute_schema"
    assert chunks[0].metadata["category"] == "数码配件/手机配件/手机壳"
    assert chunks[0].metadata["effective_date"] == "2026-01-01"
