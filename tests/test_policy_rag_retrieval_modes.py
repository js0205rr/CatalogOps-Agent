from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from packages.rag_policy.config import PolicyRAGSettings
from packages.rag_policy.retrieval.reranker import PolicyChunkReranker
from packages.rag_policy.schemas import PolicyChunk


def _settings(reranker_mode: str) -> PolicyRAGSettings:
    return PolicyRAGSettings(
        use_mock=True,
        policy_dir=Path("data/policy_docs"),
        local_index_path=Path("data/policy_index.json"),
        milvus_uri="",
        milvus_collection="catalogops_policy_chunks",
        embedding_provider="minilm",
        embedding_model_path=Path("models/all-MiniLM-L6-v2"),
        reranker_mode=reranker_mode,
    )


def test_none_reranker_preserves_candidate_order() -> None:
    chunks = [
        PolicyChunk(doc_id="a", chunk_id="a:1", text="alpha", score=0.2),
        PolicyChunk(doc_id="b", chunk_id="b:1", text="beta", score=0.9),
    ]

    ranked = PolicyChunkReranker(_settings("none")).rerank("beta", chunks, top_m=2)

    assert [chunk.doc_id for chunk in ranked] == ["a", "b"]
    assert [chunk.rank for chunk in ranked] == [1, 2]


def test_lexical_reranker_uses_query_overlap() -> None:
    chunks = [
        PolicyChunk(doc_id="a", chunk_id="a:1", text="generic policy", score=0.2),
        PolicyChunk(doc_id="b", chunk_id="b:1", text="smartphone required attributes", score=0.2),
    ]

    ranked = PolicyChunkReranker(_settings("lexical")).rerank(
        "smartphone required attributes",
        chunks,
        top_m=2,
    )

    assert ranked[0].doc_id == "b"
