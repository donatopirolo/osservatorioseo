"""Pydantic models per OsservatorioSEO."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["official", "media", "social", "tool_vendor", "independent", "doc_change"]
FetcherType = Literal["rss", "scraper", "playwright"]
CategoryId = Literal[
    "google_updates",
    "google_docs_change",
    "ai_models",
    "ai_overviews_llm_seo",
    "technical_seo",
    "content_eeat",
    "tools_platforms",
    "industry_news",
]


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    authority: int = Field(ge=1, le=10)
    type: SourceType
    fetcher: FetcherType
    feed_url: str | None = None
    target_url: str | None = None
    selectors: dict[str, str] | None = None
    category_hint: CategoryId | None = None
    enabled: bool = True


class RawItem(BaseModel):
    """Output di un Fetcher, prima di normalizzazione e AI."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    source_id: str
    published_at: datetime
    content: str
    language_original: str = "en"


class DocChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: str
    previous_hash: str
    current_hash: str
    diff_url: str | None = None
    lines_added: int
    lines_removed: int


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title_original: str
    title_it: str
    summary_it: str
    url: str
    source: Source
    category: CategoryId
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: int = Field(ge=1, le=5)
    published_at: datetime
    fetched_at: datetime
    is_doc_change: bool = False
    doc_change: DocChange | None = None
    language_original: str = "en"
    summarizer_model: str
    raw_hash: str


class FeedStats(BaseModel):
    sources_checked: int
    sources_failed: int
    items_collected: int
    items_after_dedup: int
    doc_changes_detected: int
    ai_cost_eur: float


class DocWatcherStatus(BaseModel):
    page_id: str
    last_checked: datetime
    changed: bool


class FailedSource(BaseModel):
    id: str
    error: str
    last_success: datetime | None = None


class Feed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    generated_at_local: datetime
    timezone: str
    run_id: str
    stats: FeedStats
    top10: list[str]
    categories: dict[str, list[str]]
    items: list[Item]
    doc_watcher_status: list[DocWatcherStatus]
    failed_sources: list[FailedSource]
