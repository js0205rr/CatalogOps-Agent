from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder

from apps.api.schemas import (
    BatchReportResponse,
    BatchRunResponse,
    BatchUploadResponse,
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    HealthResponse,
)
from apps.api.store import (
    BATCH_UPLOAD_ROOT,
    DOCUMENT_UPLOAD_ROOT,
    api_store,
    safe_filename,
)
from packages.agent_core.single_graph import run_product_review
from packages.batch_analysis.batch_graph import run_batch_review
from packages.catalog.schemas import BatchAuditReport, ProductInput, ReviewResult
from packages.rag_policy.config import get_policy_rag_settings
from packages.rag_policy.ingestion.indexer import PolicyDocumentIndexer
from packages.rag_policy.ingestion.loader import load_policy_document, load_policy_documents
from packages.rag_policy.schemas import (
    PolicyQARequest,
    PolicyQAResult,
    PolicyQuery,
    PolicyRetrievalResult,
)
from packages.rag_policy.tools import (
    policy_qa,
    retrieve_attribute_schema,
    retrieve_category_policy,
    retrieve_title_policy,
)

router = APIRouter()


def _emit_to_store(run_id: str):
    def emit(event: dict) -> None:
        payload = jsonable_encoder(event.get("payload") or {})
        api_store.add_event(
            run_id,
            event["event"],
            node=str(event.get("node") or ""),
            tool=str(event.get("tool") or ""),
            payload=payload,
        )

    return emit


async def _save_upload(
    file: UploadFile,
    directory: Path,
    *,
    suffix: str,
) -> tuple[str, Path]:
    if not file.filename or not file.filename.lower().endswith(suffix):
        raise HTTPException(status_code=400, detail=f"{suffix.upper()} file required")
    directory.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(file.filename, f"upload-{uuid4().hex}{suffix}")
    path = directory / f"{uuid4().hex}-{filename}"
    path.write_bytes(await file.read())
    return filename, path


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/api/reviews/single", response_model=ReviewResult)
async def api_review_single(product: ProductInput) -> ReviewResult:
    run_id = f"run-{uuid4().hex}"
    emit = _emit_to_store(run_id)
    try:
        result = run_product_review(product, emit)
        result.trace_id = run_id
        api_store.add_event(
            run_id,
            "final_result",
            payload={"result": result.model_dump(mode="json")},
        )
        return result
    except Exception as exc:
        api_store.add_event(run_id, "error", payload={"message": str(exc)})
        raise HTTPException(status_code=500, detail="single review failed") from exc


@router.post("/api/batch/upload", response_model=BatchUploadResponse)
async def api_batch_upload(file: UploadFile = File(...)) -> BatchUploadResponse:
    filename, path = await _save_upload(file, BATCH_UPLOAD_ROOT, suffix=".csv")
    batch_id = api_store.create_batch(filename, path)
    return BatchUploadResponse(batch_id=batch_id, filename=filename)


@router.post("/api/batch/{batch_id}/run", response_model=BatchRunResponse)
async def api_batch_run(batch_id: str) -> BatchRunResponse:
    batch = api_store.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    run_id = f"run-{uuid4().hex}"
    api_store.update_batch(batch_id, status="running", run_id=run_id, error="")
    try:
        report = run_batch_review(batch["path"], _emit_to_store(run_id))
        api_store.update_batch(
            batch_id,
            status="completed",
            report=report.model_dump(mode="json"),
        )
        api_store.add_event(
            run_id,
            "final_result",
            payload={"batch_id": batch_id, "report": report.model_dump(mode="json")},
        )
        return BatchRunResponse(
            batch_id=batch_id,
            run_id=run_id,
            status="completed",
            report=report,
        )
    except Exception as exc:
        api_store.update_batch(batch_id, status="failed", error=str(exc))
        api_store.add_event(run_id, "error", payload={"message": str(exc)})
        raise HTTPException(status_code=500, detail="batch review failed") from exc


@router.get("/api/batch/{batch_id}/report", response_model=BatchReportResponse)
async def api_batch_report(batch_id: str) -> BatchReportResponse:
    batch = api_store.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    report = BatchAuditReport.model_validate(batch["report"]) if batch.get("report") else None
    return BatchReportResponse(
        batch_id=batch_id,
        status=batch["status"],
        run_id=batch.get("run_id") or "",
        report=report,
        error=batch.get("error") or "",
    )


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def api_document_upload(file: UploadFile = File(...)) -> DocumentUploadResponse:
    filename, staged_path = await _save_upload(file, DOCUMENT_UPLOAD_ROOT, suffix=".md")
    final_path = DOCUMENT_UPLOAD_ROOT / filename
    if final_path.exists():
        staged_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="document already exists")
    staged_path.replace(final_path)
    try:
        document = load_policy_document(final_path)
    except (UnicodeDecodeError, ValueError) as exc:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="invalid UTF-8 Markdown document") from exc
    return DocumentUploadResponse(document=document)


@router.post("/api/documents/ingest", response_model=DocumentIngestResponse)
async def api_documents_ingest(
    request: DocumentIngestRequest | None = None,
) -> DocumentIngestResponse:
    request = request or DocumentIngestRequest()
    existing = {document.doc_id for document in load_policy_documents(DOCUMENT_UPLOAD_ROOT)}
    unknown = sorted(set(request.document_ids) - existing)
    if unknown:
        raise HTTPException(status_code=404, detail=f"documents not found: {', '.join(unknown)}")
    result = PolicyDocumentIndexer(get_policy_rag_settings()).index_directory(DOCUMENT_UPLOAD_ROOT)
    return DocumentIngestResponse(result=result)


@router.get("/api/documents", response_model=DocumentListResponse)
async def api_documents() -> DocumentListResponse:
    documents = load_policy_documents(DOCUMENT_UPLOAD_ROOT)
    return DocumentListResponse(documents=documents, count=len(documents))


@router.post("/api/chat/policy", response_model=PolicyQAResult)
async def api_chat_policy(query: PolicyQARequest) -> PolicyQAResult:
    return policy_qa(query)


@router.post("/api/policy/category", response_model=PolicyRetrievalResult)
async def api_category_policy(query: PolicyQuery) -> PolicyRetrievalResult:
    return retrieve_category_policy(query)


@router.post("/api/policy/attributes", response_model=PolicyRetrievalResult)
async def api_attribute_schema(query: PolicyQuery) -> PolicyRetrievalResult:
    return retrieve_attribute_schema(query)


@router.post("/api/policy/title", response_model=PolicyRetrievalResult)
async def api_title_policy(query: PolicyQuery) -> PolicyRetrievalResult:
    return retrieve_title_policy(query)
