from __future__ import annotations

from typing import Any

from packages.rag_policy.config import PolicyRAGSettings, get_policy_rag_settings
from packages.rag_policy.retrieval.hybrid_retriever import HybridPolicyRetriever
from packages.rag_policy.retrieval.multi_query import PolicyMultiQueryProcessor
from packages.rag_policy.retrieval.query_rewriter import PolicyQueryRewriter
from packages.rag_policy.schemas import ChatTurn, PolicyChunk, PolicyDocType, PolicyQAResult


class PolicyRAGService:
    def __init__(self, settings: PolicyRAGSettings | None = None) -> None:
        self.settings = settings or get_policy_rag_settings()
        self.retriever = HybridPolicyRetriever(self.settings)
        self.query_rewriter = PolicyQueryRewriter(self.settings.max_history_turns)
        self.multi_query = PolicyMultiQueryProcessor()

    @property
    def mode(self) -> str:
        return "mock" if self.settings.use_mock else "hybrid"

    def retrieve_category_policy(
        self,
        category_path: str,
        *,
        top_k: int = 5,
    ) -> list[PolicyChunk]:
        return self._retrieve(
            f"{category_path} 类目归属 错挂 类目规则",
            category_path=category_path,
            doc_type="category_policy",
            top_k=top_k,
        )

    def retrieve_attribute_schema(
        self,
        category_path: str,
        *,
        top_k: int = 5,
    ) -> list[PolicyChunk]:
        return self._retrieve(
            f"{category_path} 必填属性 属性规范",
            category_path=category_path,
            doc_type="attribute_schema",
            top_k=top_k,
        )

    def retrieve_title_policy(
        self,
        title: str,
        category_path: str,
        *,
        top_k: int = 5,
    ) -> list[PolicyChunk]:
        return self._retrieve(
            f"{title} {category_path} 标题规则 禁止宣传",
            category_path=category_path,
            doc_type="title_policy",
            top_k=top_k,
        )

    def policy_qa(
        self,
        query: str,
        chat_history: list[ChatTurn | dict[str, Any]] | None = None,
        *,
        top_k: int = 5,
    ) -> PolicyQAResult:
        history = [ChatTurn.model_validate(turn) for turn in chat_history or []]
        rewrite = self.query_rewriter.rewrite(query, history)
        expanded = self.multi_query.process(rewrite.standalone_query)
        hits = self.retriever.search(expanded.queries, top_k=top_k)
        if hits:
            citations = "；".join(
                f"{chunk.doc_id}: {chunk.text.splitlines()[0].lstrip('# ').strip()}"
                for chunk in hits[:3]
            )
            answer = f"根据检索到的规则证据：{citations}"
        else:
            answer = "未检索到足够规则证据，结论应降级为 uncertain 或进入人工复核。"
        return PolicyQAResult(
            question=query,
            answer=answer,
            hits=hits,
            mode=self.mode,  # type: ignore[arg-type]
            standalone_query=rewrite.standalone_query,
            queries=expanded.queries,
        )

    def _retrieve(
        self,
        query: str,
        *,
        category_path: str,
        doc_type: PolicyDocType,
        top_k: int,
    ) -> list[PolicyChunk]:
        expanded = self.multi_query.process(query)
        return self.retriever.search(
            expanded.queries,
            category_path=category_path,
            doc_type=doc_type,
            top_k=top_k,
        )
