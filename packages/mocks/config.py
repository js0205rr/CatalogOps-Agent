from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias="OPENAI_BASE_URL",
    )
    openai_model: str = Field(default="qwen-turbo", validation_alias="OPENAI_MODEL")
    answer_llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        validation_alias="ANSWER_LLM_TEMPERATURE",
    )
    llm_timeout_seconds: float = Field(
        default=60.0,
        ge=10.0,
        le=600.0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )
    llm_max_retries: int = Field(default=1, ge=0, le=5, validation_alias="LLM_MAX_RETRIES")
    mock_llm: bool = Field(default=True, validation_alias="CATALOGOPS_MOCK_LLM")

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
