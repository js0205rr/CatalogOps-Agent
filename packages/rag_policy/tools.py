from __future__ import annotations

from functools import lru_cache

from packages.rag_policy.schemas import (
    PolicyQARequest,
    PolicyQAResult,
    PolicyQuery,
    PolicyRetrievalResult,
)
from packages.rag_policy.service import PolicyRAGService


@lru_cache(maxsize=1)
def get_policy_rag_service() -> PolicyRAGService:
    return PolicyRAGService()


def retrieve_category_policy(query: PolicyQuery) -> PolicyRetrievalResult:
    hits = get_policy_rag_service().retrieve_category_policy(
        query.category_path or query.query,
        top_k=query.top_k,
    )
    return PolicyRetrievalResult(
        tool="retrieve_category_policy",
        query=query,
        hits=hits,
        mode=get_policy_rag_service().mode,  # type: ignore[arg-type]
    )


def retrieve_attribute_schema(query: PolicyQuery) -> PolicyRetrievalResult:
    hits = get_policy_rag_service().retrieve_attribute_schema(
        query.category_path or query.query,
        top_k=query.top_k,
    )
    return PolicyRetrievalResult(
        tool="retrieve_attribute_schema",
        query=query,
        hits=hits,
        mode=get_policy_rag_service().mode,  # type: ignore[arg-type]
    )


def retrieve_title_policy(query: PolicyQuery) -> PolicyRetrievalResult:
    hits = get_policy_rag_service().retrieve_title_policy(
        query.query,
        query.category_path,
        top_k=query.top_k,
    )
    return PolicyRetrievalResult(
        tool="retrieve_title_policy",
        query=query,
        hits=hits,
        mode=get_policy_rag_service().mode,  # type: ignore[arg-type]
    )


def policy_qa(request: PolicyQARequest) -> PolicyQAResult:
    return get_policy_rag_service().policy_qa(
        request.question,
        request.chat_history,
        top_k=request.top_k,
    )
