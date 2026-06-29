from __future__ import annotations

import re

from packages.rag_policy.schemas import MultiQueryResult


class PolicyMultiQueryProcessor:
    def process(self, query: str) -> MultiQueryResult:
        parts = [
            part.strip()
            for part in re.split(r"[，,；;。]|\b以及\b|\b并且\b|\b和\b", query)
            if part.strip()
        ]
        if len(parts) >= 3:
            complexity = "COMPLEX"
            limit = 5
        elif len(parts) == 2 or len(query) > 40:
            complexity = "MODERATE"
            limit = 3
        else:
            complexity = "SIMPLE"
            limit = 1
        queries = list(dict.fromkeys([query, *parts]))[:limit]
        return MultiQueryResult(
            original_query=query,
            complexity=complexity,
            queries=queries or [query],
        )
