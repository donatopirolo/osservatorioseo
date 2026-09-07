"""Caricamento configurazione: sources.yml, doc_watcher.yml, env vars."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from osservatorio_seo.models import CategoryId, Source


class DocWatcherPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    url: str
    selector: str | None = None
    type: Literal["html", "pdf"] = "html"
    category: CategoryId = "google_docs_change"
    importance: int = Field(ge=1, le=5)
    noise_patterns: list[str] = Field(default_factory=list)


class Settings(BaseModel):
    openrouter_api_key: str
    summarizer_model: str = "google/gemini-2.5-flash"
    fallback_models: list[str] = Field(
        default_factory=lambda: [
            "anthropic/claude-haiku-4.5",
            "openai/gpt-5-mini",
        ]
    )
    max_concurrent_per_host: int = 3
    request_timeout_s: int = 15
    playwright_timeout_s: int = 30
    fetcher_timeout_s: int = 90
    data_dir: Path = Path("data")
    state_dir: Path = Path("data/state/doc_watcher")
    archive_dir: Path = Path("data/archive")
    seen_urls_path: Path = Path("data/state/seen_urls.json")
    # Finestra di freschezza del Normalizer: un item con published_at piu'
    # vecchio non entra nel feed. 72h (non 24h) per non perdere le fonti che
    # pubblicano nel weekend o con ritardo; seen_urls.json evita che questo
    # ri-sottoponga al summarizer un item gia' processato in un run precedente.
    normalizer_max_age_hours: int = 72
    # Margine oltre le 72h della finestra: un item puo' restare in
    # `normalized` fino a 72h dalla pubblicazione, quindi la memoria deve
    # sopravvivere almeno cosi' a lungo dal momento in cui l'abbiamo vista.
    seen_url_retention_hours: int = 96


def load_sources(path: Path) -> list[Source]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = [Source.model_validate(s) for s in raw.get("sources", [])]
    return [s for s in sources if s.enabled]


def load_doc_watcher(path: Path) -> list[DocWatcherPage]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [DocWatcherPage.model_validate(p) for p in raw.get("pages", [])]


def load_settings() -> Settings:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    return Settings(openrouter_api_key=api_key)
