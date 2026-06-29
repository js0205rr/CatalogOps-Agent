from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.catalog.schemas import BatchAuditReport
from packages.rag_policy.schemas import PolicyDocument, PolicyIngestionResult


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "catalogops-agent"
    mock_ready: bool = True


class RootResponse(BaseModel):
    service: str = "catalogops-agent"
    docs: str = "/docs"


class BatchUploadResponse(BaseModel):
    batch_id: str
    filename: str
    status: Literal["uploaded"] = "uploaded"


class BatchRunResponse(BaseModel):
    batch_id: str
    run_id: str
    status: Literal["completed"]
    report: BatchAuditReport


class BatchReportResponse(BaseModel):
    batch_id: str
    status: Literal["uploaded", "running", "completed", "failed"]
    run_id: str = ""
    report: BatchAuditReport | None = None
    error: str = ""


class DocumentUploadResponse(BaseModel):
    document: PolicyDocument
    status: Literal["uploaded"] = "uploaded"


class DocumentIngestRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class DocumentIngestResponse(BaseModel):
    status: Literal["completed"] = "completed"
    result: PolicyIngestionResult


class DocumentListResponse(BaseModel):
    documents: list[PolicyDocument] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class RunEvent(BaseModel):
    event: Literal[
        "node_start",
        "node_end",
        "tool_start",
        "tool_end",
        "error",
        "final_result",
    ]
    run_id: str
    ts: float
    node: str = ""
    tool: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
