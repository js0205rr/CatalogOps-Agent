from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PolicyRAGSettings:
    use_mock: bool
    policy_dir: Path
    local_index_path: Path
    milvus_uri: str
    milvus_collection: str
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-v3"
    embedding_model_path: Path = ROOT / "models" / "all-MiniLM-L6-v2"
    candidate_top_n: int = 12
    rerank_top_m: int = 5
    reranker_mode: str = "lexical"
    rrf_k: int = 60
    max_history_turns: int = 6


@lru_cache(maxsize=1)
def get_policy_rag_settings() -> PolicyRAGSettings:
    use_mock = _env_bool("USE_MOCK", _env_bool("CATALOGOPS_MOCK_LLM", True))
    return PolicyRAGSettings(
        use_mock=use_mock,
        policy_dir=ROOT / "data" / "policy_docs",
        local_index_path=ROOT / "data" / "policy_index.json",
        milvus_uri=os.getenv("MILVUS_URI", "").strip(),
        milvus_collection=os.getenv("MILVUS_COLLECTION", "catalogops_policy_chunks").strip(),
        embedding_provider=os.getenv(
            "POLICY_EMBEDDING_PROVIDER",
            "openai",
        ).strip().lower(),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v3").strip(),
        embedding_model_path=Path(
            os.getenv(
                "POLICY_EMBEDDING_MODEL_PATH",
                str(ROOT / "models" / "all-MiniLM-L6-v2"),
            )
        ),
        candidate_top_n=int(os.getenv("POLICY_CANDIDATE_TOP_N", "12")),
        rerank_top_m=int(os.getenv("POLICY_RERANK_TOP_M", "5")),
        reranker_mode=os.getenv("POLICY_RERANKER_MODE", "lexical").strip().lower(),
        rrf_k=int(os.getenv("POLICY_RRF_K", "60")),
    )
