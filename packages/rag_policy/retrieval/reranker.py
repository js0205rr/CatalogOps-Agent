from __future__ import annotations

import numpy as np

from packages.rag_policy.config import PolicyRAGSettings, get_policy_rag_settings
from packages.rag_policy.embeddings import PolicyEmbedder, create_policy_embedder
from packages.rag_policy.retrieval.local_retriever import tokenize
from packages.rag_policy.schemas import PolicyChunk


class PolicyChunkReranker:
    def __init__(
        self,
        settings: PolicyRAGSettings | None = None,
        embedder: PolicyEmbedder | None = None,
    ) -> None:
        self.settings = settings or get_policy_rag_settings()
        self.mode = self.settings.reranker_mode.lower()
        self._embedder = embedder

    def rerank(self, query: str, chunks: list[PolicyChunk], top_m: int = 5) -> list[PolicyChunk]:
        if self.mode in {"none", "off", "disabled"}:
            return [
                chunk.model_copy(update={"rank": rank})
                for rank, chunk in enumerate(chunks[:top_m], start=1)
            ]
        if self.mode == "semantic":
            return self._semantic_rerank(query, chunks, top_m)
        query_terms = set(tokenize(query))
        ranked: list[tuple[float, PolicyChunk]] = []
        for chunk in chunks:
            text_terms = set(tokenize(f"{chunk.title} {chunk.text}"))
            overlap = len(query_terms & text_terms)
            category = str(chunk.metadata.get("category", ""))
            category_bonus = 2.0 if category and category.lower() in query.lower() else 0.0
            score = float(chunk.score) + overlap * 0.2 + category_bonus
            ranked.append((score, chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            chunk.model_copy(update={"score": round(score, 6), "rank": rank})
            for rank, (score, chunk) in enumerate(ranked[:top_m], start=1)
        ]

    def _semantic_rerank(
        self,
        query: str,
        chunks: list[PolicyChunk],
        top_m: int,
    ) -> list[PolicyChunk]:
        if not chunks:
            return []
        embedder = self._embedder or create_policy_embedder(self.settings)
        query_vector = np.asarray(embedder.embed_query(query), dtype=np.float32)
        chunk_texts = [f"{chunk.title}\n{chunk.text}" for chunk in chunks]
        chunk_vectors = np.asarray(embedder.embed_documents(chunk_texts), dtype=np.float32)
        similarities = chunk_vectors @ query_vector
        ranked = []
        for chunk, similarity in zip(chunks, similarities):
            score = float(chunk.score) + max(0.0, float(similarity)) * 2.0
            ranked.append((score, chunk))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [
            chunk.model_copy(update={"score": round(score, 6), "rank": rank})
            for rank, (score, chunk) in enumerate(ranked[:top_m], start=1)
        ]
