from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class PublishDecision(str, Enum):
    pass_ = "pass"
    needs_revision = "needs_revision"
    approve = "approve"
    reject = "reject"
    human_review = "human_review"
    uncertain = "uncertain"


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(default="SKU-MOCK-001", min_length=1, max_length=128)
    title: str = Field(default="Untitled product", min_length=1, max_length=300)
    description: str = Field(default="", max_length=5000)
    seller_category: str = Field(default="", max_length=300)
    merchant_category: str = Field(default="", max_length=300)
    attributes: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    locale: str = Field(default="zh-CN", min_length=2, max_length=16)

    @field_validator("sku_id", "title", mode="before")
    @classmethod
    def non_empty_text(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("value must not be empty")
        return value


class CategoryCandidate(BaseModel):
    category_id: str = Field(default="", min_length=1, max_length=128)
    category_path: str = Field(default="", min_length=1, max_length=500)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list)


class CategoryPrediction(BaseModel):
    category_id: str = Field(default="", min_length=1, max_length=128)
    category_path: str = Field(default="", min_length=1, max_length=500)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    candidates: list[CategoryCandidate] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def include_primary_candidate(self) -> "CategoryPrediction":
        if not self.candidates:
            self.candidates = [
                CategoryCandidate(
                    category_id=self.category_id,
                    category_path=self.category_path,
                    confidence=self.confidence,
                    matched_terms=list(self.matched_terms),
                    evidence_ids=list(self.evidence_ids),
                    rationale="primary prediction",
                )
            ]
        return self


class CategoryConsistencyResult(BaseModel):
    seller_category: str = Field(default="", max_length=300)
    predicted_category_id: str = Field(default="", max_length=128)
    predicted_category_path: str = Field(default="", max_length=500)
    status: Literal["match", "close_match", "mismatch", "uncertain"] = "uncertain"
    is_consistent: bool = Field(default=True)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list)


class PolicyChunk(BaseModel):
    chunk_id: str = Field(default="", min_length=1, max_length=256)
    policy_id: str = Field(default="", max_length=256)
    title: str = Field(default="", max_length=300)
    text: str = Field(default="", min_length=1, max_length=4000)
    source: str = Field(default="", max_length=1000)
    category_id: str = Field(default="", max_length=128)
    policy_type: Literal["category", "attribute", "title", "general"] = "general"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedAttributes(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)
    missing_required: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)


class ComplianceIssue(BaseModel):
    issue_id: str = Field(default_factory=lambda: f"issue-{uuid4().hex[:12]}", max_length=128)
    issue_type: Literal[
        "category_mismatch",
        "missing_attribute",
        "title_violation",
        "title_compliance",
        "policy_conflict",
        "low_confidence",
        "human_review_reason",
    ] = "low_confidence"
    severity: Literal["blocker", "warning", "info"] = "warning"
    message: str = Field(default="", min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(default_factory=list)
    matched_span: str = Field(default="", max_length=500)
    suggested_fix: str = Field(default="", max_length=1000)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        return {
            "low": "info",
            "medium": "warning",
            "high": "blocker",
        }.get(value, value)


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev-{uuid4().hex[:12]}", max_length=128)
    source: str = Field(default="", max_length=1000)
    source_type: Literal[
        "taxonomy",
        "policy",
        "attribute_schema",
        "product",
        "rule",
        "retrieval",
    ] = "rule"
    quote: str = Field(default="", max_length=800)
    policy_chunk: PolicyChunk | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = Field(default=1.0, ge=0.0, le=1.0)


class EvidenceCoverageItem(BaseModel):
    issue_id: str
    original_issue_type: str
    status: Literal["covered", "removed", "downgraded"]
    required_evidence: list[str] = Field(default_factory=list)
    matched_evidence_ids: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)


class EvidenceCoverage(BaseModel):
    total_issues: int = Field(default=0, ge=0)
    covered_issues: int = Field(default=0, ge=0)
    removed_issues: int = Field(default=0, ge=0)
    downgraded_issues: int = Field(default=0, ge=0)
    coverage_score: float = Field(default=100.0, ge=0.0, le=100.0)
    items: list[EvidenceCoverageItem] = Field(default_factory=list)


class QualityScore(BaseModel):
    overall: float = Field(default=0.0, ge=0.0, le=100.0)
    category: float = Field(default=0.0, ge=0.0, le=100.0)
    attributes: float = Field(default=0.0, ge=0.0, le=100.0)
    title: float = Field(default=0.0, ge=0.0, le=100.0)
    evidence: float = Field(default=0.0, ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)


class RevisionSuggestion(BaseModel):
    title: str = Field(default="", max_length=300)
    category: str = Field(default="", max_length=500)
    attributes: dict[str, str] = Field(default_factory=dict)
    seller_feedback: list[str] = Field(default_factory=list)
    revised_title: str = Field(default="", max_length=300)
    revised_attributes: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "RevisionSuggestion":
        if not self.title:
            self.title = self.revised_title
        if not self.revised_title:
            self.revised_title = self.title
        if not self.attributes:
            self.attributes = dict(self.revised_attributes)
        if not self.revised_attributes:
            self.revised_attributes = dict(self.attributes)
        if not self.seller_feedback:
            self.seller_feedback = list(self.notes)
        if not self.notes:
            self.notes = list(self.seller_feedback)
        return self


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    product: ProductInput = Field(default_factory=ProductInput)
    publish_decision: PublishDecision = PublishDecision.uncertain
    quality_score: QualityScore = Field(default_factory=QualityScore)
    predicted_category: CategoryPrediction | None = None
    seller_category_check: CategoryConsistencyResult = Field(
        default_factory=CategoryConsistencyResult
    )
    extracted_attributes: ExtractedAttributes = Field(default_factory=ExtractedAttributes)
    missing_attributes: list[str] = Field(default_factory=list)
    compliance_issues: list[ComplianceIssue] = Field(default_factory=list)
    human_review_reasons: list[str] = Field(default_factory=list)
    rewrite_suggestions: RevisionSuggestion = Field(default_factory=RevisionSuggestion)
    evidence: list[Evidence] = Field(default_factory=list)
    evidence_coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)
    trace_id: str = Field(default_factory=lambda: f"trace-{uuid4().hex}")
    trace: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_field_names(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "decision" in data and "publish_decision" not in data:
            data["publish_decision"] = data["decision"]
        if "category_prediction" in data and "predicted_category" not in data:
            data["predicted_category"] = data["category_prediction"]
        if "issues" in data and "compliance_issues" not in data:
            data["compliance_issues"] = data["issues"]
        if "suggestion" in data and "rewrite_suggestions" not in data:
            data["rewrite_suggestions"] = data["suggestion"]
        if "confidence" in data and "quality_score" not in data:
            confidence = data["confidence"]
            data["quality_score"] = {
                "overall": confidence,
                "category": confidence,
                "attributes": confidence,
                "title": confidence,
                "evidence": confidence,
            }
        if isinstance(data.get("extracted_attributes"), dict):
            extracted = data["extracted_attributes"]
            if not any(key in extracted for key in ("values", "missing_required", "confidence")):
                data["extracted_attributes"] = {"values": extracted}
        return data

    @model_validator(mode="after")
    def enforce_evidence_guard(self) -> "ReviewResult":
        known = {item.evidence_id for item in self.evidence}
        guarded: list[ComplianceIssue] = []
        for issue in self.compliance_issues:
            issue.evidence_ids = [
                evidence_id for evidence_id in issue.evidence_ids if evidence_id in known
            ]
            if not issue.evidence_ids and issue.severity == "info":
                continue
            if not issue.evidence_ids and issue.issue_type != "human_review_reason":
                guarded.append(
                    issue.model_copy(
                        update={
                            "severity": "warning",
                            "issue_type": "human_review_reason",
                            "message": f"Evidence missing for prior conclusion: {issue.message}",
                        }
                    )
                )
            else:
                guarded.append(issue)
        self.compliance_issues = guarded
        if not self.human_review_reasons:
            self.human_review_reasons = [
                issue.message
                for issue in self.compliance_issues
                if issue.issue_type == "human_review_reason"
            ]
        if any(
            issue.issue_type in {"low_confidence", "human_review_reason"}
            for issue in self.compliance_issues
        ):
            self.publish_decision = PublishDecision.human_review
        if not self.missing_attributes:
            self.missing_attributes = list(self.extracted_attributes.missing_required)
        return self

    @computed_field
    @property
    def decision(self) -> PublishDecision:
        return self.publish_decision

    @computed_field
    @property
    def confidence(self) -> float:
        return self.quality_score.overall

    @computed_field
    @property
    def category_prediction(self) -> CategoryPrediction | None:
        return self.predicted_category

    @computed_field
    @property
    def issues(self) -> list[ComplianceIssue]:
        return self.compliance_issues

    @computed_field
    @property
    def suggestion(self) -> RevisionSuggestion:
        return self.rewrite_suggestions


class BatchCatalogProfile(BaseModel):
    row_count: int = Field(default=0, ge=0)
    rows: int = Field(default=0, ge=0)
    columns: list[str] = Field(default_factory=list)
    detected_columns: dict[str, str] = Field(default_factory=dict)
    sample_skus: list[str] = Field(default_factory=list)
    missing_rates: dict[str, float] = Field(default_factory=dict)
    duplicate_count: int = Field(default=0, ge=0)
    seller_count: int = Field(default=0, ge=0)
    category_distribution: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sync_row_counts(self) -> "BatchCatalogProfile":
        if not self.row_count:
            self.row_count = self.rows
        if not self.rows:
            self.rows = self.row_count
        return self


class BatchPrecheckIssue(BaseModel):
    row_index: int = Field(default=0, ge=0)
    product_id: str = ""
    seller_id: str = ""
    seller_category: str = ""
    issue_type: Literal[
        "empty_title",
        "empty_category",
        "empty_attributes",
        "title_violation",
    ]
    severity: Literal["blocker", "warning", "info"] = "warning"
    message: str
    matched_span: str = ""


class BatchCategoryPrediction(BaseModel):
    row_index: int = Field(default=0, ge=0)
    product_id: str = ""
    seller_id: str = ""
    seller_category: str = ""
    category_prediction: CategoryPrediction
    category_check: CategoryConsistencyResult
    risk_flags: list[str] = Field(default_factory=list)
    high_risk: bool = False


class BatchMetrics(BaseModel):
    category_mismatch_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    attribute_missing_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    title_issue_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    decision_distribution: dict[str, int] = Field(default_factory=dict)
    top_issue_categories: dict[str, int] = Field(default_factory=dict)
    top_issue_sellers: dict[str, int] = Field(default_factory=dict)


class BatchIssueSummary(BaseModel):
    issue_type: str = Field(default="unknown", min_length=1, max_length=128)
    count: int = Field(default=0, ge=0)
    severity: Literal["blocker", "warning", "info"] = "info"


class BatchAuditReport(BaseModel):
    profile: BatchCatalogProfile = Field(default_factory=BatchCatalogProfile)
    precheck: list[BatchPrecheckIssue] = Field(default_factory=list)
    category_predictions: list[BatchCategoryPrediction] = Field(default_factory=list)
    selected_rows: list[int] = Field(default_factory=list)
    policy_contexts: dict[int, dict[str, Any]] = Field(default_factory=dict)
    reviews: list[ReviewResult] = Field(default_factory=list)
    issue_summary: list[BatchIssueSummary] = Field(default_factory=list)
    metrics: BatchMetrics = Field(default_factory=BatchMetrics)
    report_markdown: str = Field(default="", max_length=100_000)
    trace_id: str = Field(default_factory=lambda: f"batch-{uuid4().hex}")
    trace: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_rows(cls, data: Any) -> Any:
        if isinstance(data, dict) and "rows" in data and "reviews" not in data:
            data = dict(data)
            data["reviews"] = data["rows"]
        return data

    @computed_field
    @property
    def rows(self) -> list[ReviewResult]:
        return self.reviews


AttributeExtraction = ExtractedAttributes
BatchReviewResult = BatchAuditReport
