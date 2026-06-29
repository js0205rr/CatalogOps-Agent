from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.rag_policy.schemas import PolicyQARequest, PolicyQuery
from packages.rag_policy.tools import (
    policy_qa,
    retrieve_attribute_schema,
    retrieve_category_policy,
    retrieve_title_policy,
)


def test_policy_rag_tools_return_structured_hits() -> None:
    query = PolicyQuery(query="智能手机 必填属性", category_id="2001", top_k=2)

    assert retrieve_category_policy(query).hits
    assert retrieve_attribute_schema(query).hits[0].source_type == "attribute_schema"
    assert retrieve_title_policy(PolicyQuery(query="全网最低 标题", top_k=2)).hits


def test_policy_qa_mock_mode() -> None:
    result = policy_qa(PolicyQARequest(question="标题可以写全网最低吗？"))

    assert result.mode == "mock"
    assert result.hits
    assert "规则" in result.answer or "证据" in result.answer
