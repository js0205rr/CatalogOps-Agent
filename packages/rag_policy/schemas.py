from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


PolicyToolName = Literal[
    "retrieve_category_policy",
    "retrieve_attribute_schema",
    "retrieve_title_policy",
    "policy_qa",
]
PolicyDocType = Literal[
    "category_policy",
    "attribute_schema",
    "title_policy",
    "prohibited_claims",
    "qa",
    "taxonomy",
]


class PolicyQuery(BaseModel):
    query: str
    category_id: str = ""
    category_path: str = ""
    doc_type: PolicyDocType | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PolicyChunk(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    score: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    title: str = ""
    rank: int = Field(default=0, ge=0)
    source_type: PolicyDocType = "qa"

    @model_validator(mode="after")
    def ensure_required_metadata(self) -> "PolicyChunk":
        self.metadata.setdefault("doc_type", self.source_type)
        self.metadata.setdefault("category", "all")
        self.metadata.setdefault("effective_date", "unknown")
        return self


PolicyHit = PolicyChunk


class PolicyRetrievalResult(BaseModel):
    tool: PolicyToolName
    query: PolicyQuery
    hits: list[PolicyChunk] = Field(default_factory=list)
    mode: Literal["mock", "hybrid"] = "mock"


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QueryRewriteResult(BaseModel):
    original_query: str
    standalone_query: str
    is_follow_up: bool = False


class MultiQueryResult(BaseModel):
    original_query: str
    complexity: Literal["SIMPLE", "MODERATE", "COMPLEX"] = "SIMPLE"
    queries: list[str] = Field(default_factory=list)


class PolicyQARequest(BaseModel):
    question: str
    category_id: str = ""
    category_path: str = ""
    top_k: int = Field(default=5, ge=1, le=20)
    chat_history: list[ChatTurn] = Field(default_factory=list)


class PolicyQAResult(BaseModel):
    question: str
    answer: str
    hits: list[PolicyChunk] = Field(default_factory=list)
    mode: Literal["mock", "hybrid"] = "mock"
    standalone_query: str = ""
    queries: list[str] = Field(default_factory=list)


class PolicyDocument(BaseModel):
    doc_id: str
    path: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyChunkRecord(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyIngestionResult(BaseModel):
    documents: int = Field(default=0, ge=0)
    chunks: int = Field(default=0, ge=0)
    mode: Literal["mock", "milvus"] = "mock"
    index_path: str = ""


class EvaluationItem(BaseModel):
    question: str
    expected_doc_ids: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    total: int = Field(default=0, ge=0)
    summary: dict[str, float] = Field(default_factory=dict)
    details: list[dict[str, Any]] = Field(default_factory=list)
