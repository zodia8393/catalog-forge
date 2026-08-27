from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CrawlStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"


class RenderMode(StrEnum):
    HTTP = "http"
    BROWSER = "browser"
    AUTO = "auto"


class EvidenceSource(StrEnum):
    JSON_LD = "json_ld"
    SOURCE_SELECTOR = "source_selector"
    SEMANTIC_FALLBACK = "semantic_fallback"
    DERIVED = "derived"


class CrawlRunCreate(BaseModel):
    connector: str = Field(default="generic", pattern=r"^[a-z0-9_-]+$")
    start_urls: list[HttpUrl] = Field(min_length=1, max_length=1000)
    max_pages: int = Field(default=100, ge=1, le=10_000)
    render_mode: RenderMode = RenderMode.AUTO

    @field_validator("start_urls")
    @classmethod
    def unique_urls(cls, urls: list[HttpUrl]) -> list[HttpUrl]:
        if len({str(url) for url in urls}) != len(urls):
            raise ValueError("start_urls must be unique")
        return urls


class CrawlRunSummary(BaseModel):
    id: UUID
    connector: str
    status: CrawlStatus
    created_at: datetime
    updated_at: datetime
    queued: int = 0
    running: int = 0
    retrying: int = 0
    succeeded: int = 0
    failed: int = 0
    blocked: int = 0


class TargetMessage(BaseModel):
    target_id: UUID
    run_id: UUID
    url: str
    connector: str
    render_mode: RenderMode
    attempt: int = 0


class FieldEvidence(BaseModel):
    value: Any
    source: EvidenceSource
    confidence: float = Field(ge=0, le=1)
    selector: str | None = None


class ProductRecord(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    target_id: UUID
    source: str
    external_id: str
    canonical_url: str
    title: str
    price_amount: Decimal | None = None
    currency: str | None = None
    availability: str | None = None
    brand: str | None = None
    category: str | None = None
    image_url: str | None = None
    captured_at: datetime = Field(default_factory=utc_now)
    confidence: float = Field(ge=0, le=1)
    dom_fingerprint: str
    field_evidence: dict[str, FieldEvidence]


class ParseOutcome(BaseModel):
    product: ProductRecord | None
    required_field_coverage: float = Field(ge=0, le=1)
    dom_fingerprint: str
    warnings: list[str] = Field(default_factory=list)


class FetchAttemptRecord(BaseModel):
    target_id: UUID
    attempt: int
    status_code: int | None = None
    latency_ms: float
    bytes_received: int = 0
    error_code: str | None = None
    retry_after_seconds: float | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ReviewResolution(BaseModel):
    action: str = Field(pattern=r"^(accept|reject)$")
    note: str = Field(min_length=3, max_length=500)
