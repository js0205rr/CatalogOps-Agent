from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.rag_policy.config import get_policy_rag_settings
from packages.rag_policy.ingestion.chunker import chunk_policy_document
from packages.rag_policy.ingestion.loader import load_policy_documents
from packages.rag_policy.schemas import PolicyChunk, PolicyDocType


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_]+", lowered)
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    cjk_tokens: list[str] = []
    for run in cjk_runs:
        cjk_tokens.append(run)
        cjk_tokens.extend(run[index : index + 2] for index in range(max(0, len(run) - 1)))
    return latin + cjk_tokens


class LocalPolicyRetriever:
    def __init__(self, policy_dir: Path | None = None) -> None:
        self.policy_dir = policy_dir or get_policy_rag_settings().policy_dir
        self._chunks = self._load_chunks()

    def _load_chunks(self) -> list[dict[str, Any]]:
        documents = load_policy_documents(self.policy_dir)
        return [
            chunk.model_dump()
            for document in documents
            for chunk in chunk_policy_document(document)
        ]

    def ranked_ids(
        self,
        query: str,
        *,
        doc_type: PolicyDocType | None = None,
        category_path: str = "",
        strategy: str = "sparse",
        top_k: int = 20,
    ) -> tuple[list[str], dict[str, PolicyChunk]]:
        query_terms = set(tokenize(f"{query} {category_path}"))
        scored: list[tuple[float, dict[str, Any]]] = []
        for raw in self._chunks:
            metadata = raw["metadata"]
            if doc_type and metadata.get("doc_type") != doc_type:
                continue
            title = str(raw.get("title", ""))
            text = str(raw.get("text", ""))
            category = str(metadata.get("category", ""))
            if strategy == "category":
                score = 0.0
                if category_path and category_path.lower() in category.lower():
                    score += 8.0
                score += len(set(tokenize(category)) & query_terms) * 2.0
                score += len(set(tokenize(title)) & query_terms)
            else:
                haystack_terms = set(tokenize(f"{title} {text}"))
                score = float(len(query_terms & haystack_terms))
                if query.lower() in text.lower():
                    score += 4.0
            if score > 0:
                scored.append((score, raw))
        scored.sort(key=lambda item: item[0], reverse=True)
        chunks: dict[str, PolicyChunk] = {}
        ids: list[str] = []
        for rank, (score, raw) in enumerate(scored[:top_k], start=1):
            source_type = raw["metadata"].get("doc_type", "qa")
            chunk = PolicyChunk(
                doc_id=raw["doc_id"],
                chunk_id=raw["chunk_id"],
                text=raw["text"],
                title=raw.get("title", ""),
                score=score,
                rank=rank,
                source_type=source_type,
                metadata=raw["metadata"],
            )
            chunks[chunk.chunk_id] = chunk
            ids.append(chunk.chunk_id)
        return ids, chunks

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        source_type: str | None = None,
        category_id: str = "",
        category_path: str = "",
    ) -> list[PolicyChunk]:
        del category_id
        ids, chunks = self.ranked_ids(
            query,
            doc_type=source_type,  # type: ignore[arg-type]
            category_path=category_path,
            top_k=top_k,
        )
        return [chunks[chunk_id] for chunk_id in ids]


@lru_cache(maxsize=1)
def get_local_retriever() -> LocalPolicyRetriever:
    return LocalPolicyRetriever()
