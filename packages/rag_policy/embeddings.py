from __future__ import annotations

from typing import Protocol

import numpy as np

from packages.rag_policy.config import PolicyRAGSettings


class PolicyEmbedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class OpenAIPolicyEmbedder:
    def __init__(self, model: str) -> None:
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "langchain-openai is required for POLICY_EMBEDDING_PROVIDER=openai"
            ) from exc
        self._embedder = OpenAIEmbeddings(model=model)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedder.embed_query(text)


class MiniLMPolicyEmbedder:
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._sentence_model = None
        self._tokenizer = None
        self._transformer_model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._sentence_model is None and self._tokenizer is None:
            self._load()
        if self._sentence_model is not None:
            vectors = self._sentence_model.encode(
                texts,
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return np.asarray(vectors, dtype=np.float32).tolist()
        return self._encode_with_transformers(texts)

    def _load(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._sentence_model = SentenceTransformer(self.model_path, local_files_only=True)
            return
        except Exception:
            self._sentence_model = None
        try:
            from transformers import AutoModel, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
            self._transformer_model = AutoModel.from_pretrained(
                self.model_path,
                local_files_only=True,
            )
            self._transformer_model.eval()
        except Exception as exc:
            raise RuntimeError(
                "sentence-transformers or transformers+torch is required for "
                "POLICY_EMBEDDING_PROVIDER=minilm"
            ) from exc

    def _encode_with_transformers(self, texts: list[str]) -> list[list[float]]:
        import torch

        vectors: list[np.ndarray] = []
        for start in range(0, len(texts), 32):
            batch = texts[start : start + 32]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            )
            with torch.no_grad():
                output = self._transformer_model(**encoded)
                token_embeddings = output.last_hidden_state
                attention_mask = encoded["attention_mask"].unsqueeze(-1).float()
                pooled = (token_embeddings * attention_mask).sum(dim=1)
                pooled = pooled / attention_mask.sum(dim=1).clamp(min=1e-9)
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors.extend(pooled.cpu().numpy().astype(np.float32))
        return [vector.tolist() for vector in vectors]


def create_policy_embedder(settings: PolicyRAGSettings) -> PolicyEmbedder:
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIPolicyEmbedder(settings.embedding_model)
    if provider in {"minilm", "local_minilm"}:
        if not settings.embedding_model_path.exists():
            raise RuntimeError(
                f"MiniLM policy embedding model not found: {settings.embedding_model_path}"
            )
        return MiniLMPolicyEmbedder(str(settings.embedding_model_path))
    raise RuntimeError(f"Unsupported POLICY_EMBEDDING_PROVIDER={settings.embedding_provider!r}")
