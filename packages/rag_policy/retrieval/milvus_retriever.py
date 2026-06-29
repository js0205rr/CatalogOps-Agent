from __future__ import annotations

from packages.rag_policy.config import PolicyRAGSettings
from packages.rag_policy.embeddings import create_policy_embedder
from packages.rag_policy.schemas import PolicyChunk, PolicyDocType


class MilvusPolicyRetriever:
    def __init__(self, settings: PolicyRAGSettings) -> None:
        if not settings.milvus_uri:
            raise RuntimeError("MILVUS_URI is required when USE_MOCK=false")
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus is required when USE_MOCK=false") from exc
        self.settings = settings
        self.embedder = create_policy_embedder(settings)
        self.client = MilvusClient(uri=settings.milvus_uri)

    def ranked_ids(
        self,
        query: str,
        *,
        doc_type: PolicyDocType | None = None,
        top_k: int = 20,
    ) -> tuple[list[str], dict[str, PolicyChunk]]:
        vector = self.embedder.embed_query(query)
        raw_results = self.client.search(
            collection_name=self.settings.milvus_collection,
            data=[vector],
            anns_field="dense_vector",
            limit=top_k * 2,
            output_fields=["chunk_id", "doc_id", "text", "title", "metadata"],
            search_params={"metric_type": "COSINE"},
        )
        chunks: dict[str, PolicyChunk] = {}
        ids: list[str] = []
        for raw in raw_results[0] if raw_results else []:
            entity = raw.get("entity", raw)
            metadata = entity.get("metadata") or {}
            if doc_type and metadata.get("doc_type") != doc_type:
                continue
            chunk = PolicyChunk(
                doc_id=str(entity.get("doc_id", "")),
                chunk_id=str(entity.get("chunk_id", raw.get("id", ""))),
                text=str(entity.get("text", "")),
                title=str(entity.get("title", "")),
                score=max(0.0, float(raw.get("distance", 0.0))),
                rank=len(ids) + 1,
                source_type=metadata.get("doc_type", "qa"),
                metadata=metadata,
            )
            chunks[chunk.chunk_id] = chunk
            ids.append(chunk.chunk_id)
            if len(ids) >= top_k:
                break
        return ids, chunks
