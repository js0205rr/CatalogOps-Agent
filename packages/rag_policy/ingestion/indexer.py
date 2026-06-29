from __future__ import annotations

import json
from pathlib import Path

from packages.rag_policy.config import PolicyRAGSettings, get_policy_rag_settings
from packages.rag_policy.embeddings import create_policy_embedder
from packages.rag_policy.ingestion.chunker import chunk_policy_document
from packages.rag_policy.ingestion.loader import load_policy_documents
from packages.rag_policy.schemas import PolicyChunkRecord, PolicyIngestionResult


class PolicyDocumentIndexer:
    def __init__(self, settings: PolicyRAGSettings | None = None) -> None:
        self.settings = settings or get_policy_rag_settings()

    def index_directory(self, policy_dir: str | Path | None = None) -> PolicyIngestionResult:
        documents = load_policy_documents(policy_dir or self.settings.policy_dir)
        chunks = [chunk for document in documents for chunk in chunk_policy_document(document)]
        if self.settings.use_mock:
            self._write_local_index(chunks)
            return PolicyIngestionResult(
                documents=len(documents),
                chunks=len(chunks),
                mode="mock",
                index_path=str(self.settings.local_index_path),
            )
        self._write_milvus(chunks)
        return PolicyIngestionResult(
            documents=len(documents),
            chunks=len(chunks),
            mode="milvus",
            index_path=self.settings.milvus_collection,
        )

    def _write_local_index(self, chunks: list[PolicyChunkRecord]) -> None:
        self.settings.local_index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [chunk.model_dump(mode="json") for chunk in chunks]
        self.settings.local_index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_milvus(self, chunks: list[PolicyChunkRecord]) -> None:
        if not self.settings.milvus_uri:
            raise RuntimeError("MILVUS_URI is required when USE_MOCK=false")
        if not chunks:
            return
        try:
            from pymilvus import DataType, MilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus is required when USE_MOCK=false") from exc

        embedder = create_policy_embedder(self.settings)
        vectors = embedder.embed_documents([chunk.text for chunk in chunks])
        client = MilvusClient(uri=self.settings.milvus_uri)
        if not client.has_collection(self.settings.milvus_collection):
            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=256)
            schema.add_field("doc_id", DataType.VARCHAR, max_length=256)
            schema.add_field("text", DataType.VARCHAR, max_length=8192)
            schema.add_field("title", DataType.VARCHAR, max_length=1024)
            schema.add_field("metadata", DataType.JSON)
            schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=len(vectors[0]))
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="dense_vector",
                index_type="AUTOINDEX",
                metric_type="COSINE",
            )
            client.create_collection(
                collection_name=self.settings.milvus_collection,
                schema=schema,
                index_params=index_params,
            )
        rows = [
            {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "text": chunk.text,
                "title": chunk.title,
                "metadata": chunk.metadata,
                "dense_vector": vector,
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        if rows:
            client.upsert(collection_name=self.settings.milvus_collection, data=rows)
