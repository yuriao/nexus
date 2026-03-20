"""
Pydantic v2 schemas shared across all Nexus services.
These are transport/validation schemas; Django models are defined per-service.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─── Enums ───────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    NEWS = "news"
    JOBS = "jobs"
    CRUNCHBASE = "crunchbase"
    LINKEDIN = "linkedin"
    CUSTOM = "custom"


class ReportStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DeliveryChannel(str, Enum):
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


# ─── Company ─────────────────────────────────────────────────────────────────

class CompanySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    sector: str = Field(default="", max_length=100)
    country: str = Field(default="", max_length=100)
    description: str | None = None
    employee_count: int | None = None
    founded_year: int | None = None
    last_crawled_at: datetime | None = None
    crawl_frequency_hours: int = Field(default=24, ge=1, le=8760)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("domain")
    @classmethod
    def normalise_domain(cls, v: str) -> str:
        return v.lower().strip().removeprefix("www.")


# ─── DataPoint ───────────────────────────────────────────────────────────────

class DataPointSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    company_id: int
    source_type: SourceType
    source_url: str
    raw_text: str
    structured_json: dict[str, Any] | None = None
    extracted_at: datetime
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


# ─── Report ──────────────────────────────────────────────────────────────────

class ReportSectionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    report_id: str
    section_type: str
    content: str
    sort_order: int = 0


class ReportSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None  # UUID
    company_id: int
    version: int = 1
    status: ReportStatus = ReportStatus.PENDING
    summary: str | None = None
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    predictions: list[str] = Field(default_factory=list)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    sections: list[ReportSectionSchema] = Field(default_factory=list)


# ─── Agent Run ───────────────────────────────────────────────────────────────

class AgentRunSchema(BaseModel):
    """Represents the payload sent to trigger an agent run."""

    report_id: str
    company_id: int
    company_name: str
    data_point_ids: list[int] = Field(default_factory=list)
    max_iterations: int = Field(default=3, ge=1, le=10)
    model_name: str = "gpt-4o"


# ─── Scraper Result ──────────────────────────────────────────────────────────

class ScraperResultSchema(BaseModel):
    """Unified result returned by all scrapers before DB insertion."""

    company_id: int
    source_type: SourceType
    source_url: str
    title: str | None = None
    raw_text: str
    structured_json: dict[str, Any] | None = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    scraper_name: str | None = None
    error: str | None = None

    @property
    def is_error(self) -> bool:
        return self.error is not None
