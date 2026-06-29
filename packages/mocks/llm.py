from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from packages.mocks.config import get_settings


def get_chat_model(*, temperature: float | None = None) -> BaseChatModel:
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai_api_key or "sk-mock",
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=0.2 if temperature is None else temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def get_answer_chat_model() -> BaseChatModel:
    return get_chat_model(temperature=get_settings().answer_llm_temperature)

