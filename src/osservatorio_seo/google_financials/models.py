"""Pydantic models for the Google Financials SEO Analyzer subsystem."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Configuration models (loaded from google_financials.yaml)
# ---------------------------------------------------------------------------


class MetricConfig(BaseModel):
    """XBRL tag mapping for a single financial metric."""

    model_config = ConfigDict(extra="forbid")
    tags: list[str]
    namespace: str = "us-gaap"
    label_it: str


class CompanyConfig(BaseModel):
    """Configuration for a single company to monitor."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    cik: str
    enabled: bool = True
    xbrl_namespace: str
    filing_types: list[str] = Field(default_factory=lambda: ["10-K", "10-Q"])
    metrics: dict[str, MetricConfig] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Filing state (tracks already-processed filings)
# ---------------------------------------------------------------------------


class FilingState(BaseModel):
    """Persistent state of processed filings for a company."""

    model_config = ConfigDict(extra="forbid")
    company_id: str
    processed_accessions: set[str] = Field(default_factory=set)
    last_check: datetime | None = None


# ---------------------------------------------------------------------------
# Quarterly financial data
# ---------------------------------------------------------------------------


class QuarterlyMetric(BaseModel):
    """Single financial metric for one quarter."""

    model_config = ConfigDict(extra="forbid")
    label: str
    value_usd_millions: float
    value_prev_quarter_usd_millions: float | None = None
    value_prev_year_usd_millions: float | None = None
    qoq_change_pct: float | None = None
    yoy_change_pct: float | None = None


class SnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edgar_calls: int = 0
    warnings: list[str] = Field(default_factory=list)
    source_url: str = ""


class QuarterlySnapshot(BaseModel):
    """One quarter's worth of financial data for a company."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    company_id: str = "alphabet"
    fiscal_year: int
    fiscal_quarter: int = Field(ge=1, le=4)
    period_end: date
    filing_date: date | None = None
    filing_type: Literal["10-K", "10-Q"]

    # Core metrics — stored as a dict keyed by metric id (e.g. "google_search_revenue").
    # This is flexible enough to support different companies with different metrics.
    metrics: dict[str, QuarterlyMetric] = Field(default_factory=dict)

    # Derived ratios (computed by collector)
    tac_as_pct_of_search_revenue: float | None = None
    search_as_pct_of_total_revenue: float | None = None
    operating_margin_pct: float | None = None

    generated_at: datetime
    metadata: SnapshotMetadata


# ---------------------------------------------------------------------------
# AI-generated analysis
# ---------------------------------------------------------------------------


class SEOImplication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    body: str
    severity: Literal["high", "medium", "low"] = "medium"


class FinancialTakeaway(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    body: str


class QuarterlyAnalysis(BaseModel):
    """AI-generated analysis of SEO implications from quarterly financials."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    company_id: str = "alphabet"
    fiscal_year: int
    fiscal_quarter: int = Field(ge=1, le=4)
    title_it: str
    subtitle_it: str
    executive_summary: list[str] = Field(default_factory=list, max_length=6)
    narrative: str
    seo_implications: list[SEOImplication] = Field(default_factory=list, max_length=8)
    ai_search_impact: str
    correlation_timeline: str
    takeaways: list[FinancialTakeaway] = Field(default_factory=list, max_length=8)
    outlook: str
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0


# ---------------------------------------------------------------------------
# 8-K event filing
# ---------------------------------------------------------------------------


class EventFiling(BaseModel):
    """An 8-K (event) filing with SEO relevance assessment."""

    model_config = ConfigDict(extra="forbid")

    company_id: str = "alphabet"
    accession_number: str
    filing_date: date
    form_type: str = "8-K"
    event_type: str
    title_it: str
    summary_it: str
    seo_relevance: Literal["high", "medium", "low", "none"]
    seo_impact_note: str | None = None
    source_url: str
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0
