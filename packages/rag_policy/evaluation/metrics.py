from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return float(bool(set(retrieved[:k]) & relevant))


def hit_rate_at_k(expected_doc_ids: list[str], retrieved_doc_ids: list[str], k: int = 5) -> float:
    return hit_at_k(retrieved_doc_ids, set(expected_doc_ids), k)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0

    def dcg(gains: list[float]) -> float:
        return sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))

    gains = [1.0 if doc_id in relevant else 0.0 for doc_id in retrieved[:k]]
    ideal = [1.0] * min(len(relevant), k)
    return dcg(gains) / dcg(ideal) if ideal else 0.0


def aggregate_metrics(items: list[dict[str, float]]) -> dict[str, float]:
    if not items:
        return {}
    keys = items[0].keys()
    return {key: sum(item[key] for item in items) / len(items) for key in keys}
