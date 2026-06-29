from __future__ import annotations

from packages.rag_policy.evaluation.metrics import (
    aggregate_metrics,
    hit_at_k,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from packages.rag_policy.schemas import EvaluationItem, EvaluationReport
from packages.rag_policy.service import PolicyRAGService


class PolicyRAGEvaluator:
    def __init__(self, service: PolicyRAGService | None = None) -> None:
        self.service = service or PolicyRAGService()

    def evaluate(
        self,
        dataset: list[EvaluationItem | dict],
        k_values: list[int] | None = None,
    ) -> EvaluationReport:
        ks = k_values or [1, 3, 5]
        details: list[dict] = []
        per_query: list[dict[str, float]] = []
        for raw in dataset:
            item = EvaluationItem.model_validate(raw)
            result = self.service.policy_qa(item.question, top_k=max(ks))
            retrieved = list(dict.fromkeys(chunk.doc_id for chunk in result.hits))
            relevant = set(item.expected_doc_ids)
            metrics: dict[str, float] = {"mrr": reciprocal_rank(retrieved, relevant)}
            for k in ks:
                metrics[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
                metrics[f"hit@{k}"] = hit_at_k(retrieved, relevant, k)
                metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
            per_query.append(metrics)
            details.append(
                {
                    "question": item.question,
                    "expected_doc_ids": item.expected_doc_ids,
                    "retrieved_doc_ids": retrieved,
                    "metrics": metrics,
                }
            )
        return EvaluationReport(
            total=len(details),
            summary=aggregate_metrics(per_query),
            details=details,
        )
