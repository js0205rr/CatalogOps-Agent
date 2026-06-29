from __future__ import annotations

from packages.rag_policy.schemas import ChatTurn, QueryRewriteResult


class PolicyQueryRewriter:
    def __init__(self, max_history_turns: int = 6) -> None:
        self.max_history_turns = max_history_turns

    def rewrite(self, query: str, chat_history: list[ChatTurn] | None = None) -> QueryRewriteResult:
        history = list(chat_history or [])[-self.max_history_turns :]
        if not history:
            return QueryRewriteResult(
                original_query=query,
                standalone_query=query,
                is_follow_up=False,
            )
        follow_up_markers = ("它", "这个", "该类目", "上述", "那", "是否可以", "怎么办")
        is_follow_up = any(marker in query for marker in follow_up_markers) or len(query) < 12
        if not is_follow_up:
            standalone = query
        else:
            previous_user = next(
                (turn.content for turn in reversed(history) if turn.role == "user"),
                "",
            )
            standalone = f"{previous_user} {query}".strip()
        return QueryRewriteResult(
            original_query=query,
            standalone_query=standalone,
            is_follow_up=is_follow_up,
        )
