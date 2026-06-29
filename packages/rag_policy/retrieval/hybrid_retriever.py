from __future__ import annotations

from packages.rag_policy.config import PolicyRAGSettings, get_policy_rag_settings
from packages.rag_policy.retrieval.local_retriever import LocalPolicyRetriever
from packages.rag_policy.retrieval.reranker import PolicyChunkReranker
from packages.rag_policy.retrieval.rrf import reciprocal_rank_fusion
from packages.rag_policy.schemas import PolicyChunk, PolicyDocType


class HybridPolicyRetriever:
    def __init__(self, settings: PolicyRAGSettings | None = None) -> None:
        self.settings = settings or get_policy_rag_settings()
        self.local = LocalPolicyRetriever(self.settings.policy_dir)
        self.reranker = PolicyChunkReranker(self.settings)
        self.milvus = None
        if not self.settings.use_mock:
            from packages.rag_policy.retrieval.milvus_retriever import MilvusPolicyRetriever

            self.milvus = MilvusPolicyRetriever(self.settings)

    def search(
        self,
        queries: list[str],
        *,
        category_path: str = "",
        doc_type: PolicyDocType | None = None,
        top_k: int = 5,
    ) -> list[PolicyChunk]:
        ranked_lists: list[list[str]] = []
        chunk_map: dict[str, PolicyChunk] = {}
        for query in queries:
            if self.milvus is not None:
                ids, chunks = self.milvus.ranked_ids(
                    query,
                    doc_type=doc_type,
                    top_k=self.settings.candidate_top_n,
                )
                ranked_lists.append(ids)
                chunk_map.update(chunks)
            for strategy in ("sparse", "category"):
                ids, chunks = self.local.ranked_ids(
                    query,
                    doc_type=doc_type,
                    category_path=category_path,
                    strategy=strategy,
                    top_k=self.settings.candidate_top_n,
                )
                ranked_lists.append(ids)
                chunk_map.update(chunks)
        fused = reciprocal_rank_fusion(
            ranked_lists,
            k=self.settings.rrf_k,
            top_n=self.settings.candidate_top_n,
        )
        candidates = [
            chunk_map[chunk_id].model_copy(update={"score": score, "rank": rank})
            for rank, (chunk_id, score) in enumerate(fused, start=1)
            if chunk_id in chunk_map
        ]
        return self.reranker.rerank(queries[0], candidates, top_m=top_k)
