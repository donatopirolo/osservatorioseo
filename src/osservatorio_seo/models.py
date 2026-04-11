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


class FAQEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str


class DeepAnalysis(BaseModel):
    """Analisi editoriale estesa generata da un modello premium per item 5-stelle.

    Tutti i campi sono stringhe/liste già pronte per essere renderizzate nel
    template. Non contiene logica di business: solo contenuto.
    """

    model_config = ConfigDict(extra="forbid")

    detailed_description: str  # 500-700 parole, articleBody SEO
    implications: list[str] = Field(default_factory=list, max_length=6)
    examples: list[str] = Field(default_factory=list, max_length=4)
    testing_steps: list[str] = Field(default_factory=list, max_length=8)
    faqs: list[FAQEntry] = Field(default_factory=list, max_length=8)
    editorial_commentary: str  # commento editoriale "mix tone"
    premium_model_used: str
    cost_eur: float = 0.0


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
    deep_analysis: DeepAnalysis | None = None


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


class PillarTakeaway(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class Pillar(BaseModel):
    """Pillar page / dossier editoriale su un tag trasversale.

    Contiene contenuto premium generato via Claude Sonnet 4.5 che non è
    riconducibile a un singolo item ma sintetizza una posizione editoriale
    su un tema (es. core_update, e_e_a_t, googlebot). Gli item a cui la
    pillar si riferisce sono linkati via ``item_refs`` con dati minimi
    per rendering (no duplicazione del contenuto).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    tag: str  # slug tag originale, es. "core_update"
    slug: str  # slug URL, es. "core-update"
    title_it: str  # es. "Core Update: il dossier di Osservatorio SEO"
    subtitle_it: str  # hook breve 1 frase
    intro_long: str  # 800-1200 parole, paragrafi brevi
    context_section: str  # 400-600 parole, contesto storico / perché importa
    timeline_narrative: str  # 400-600 parole, narrazione cronologica
    takeaways: list[PillarTakeaway] = Field(default_factory=list, max_length=8)
    outlook: str  # 200-400 parole, prospettive future
    item_refs: list[str] = Field(default_factory=list)  # item.id linkati
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0


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
