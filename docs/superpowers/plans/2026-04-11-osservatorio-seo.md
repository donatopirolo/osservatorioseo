# OsservatorioSEO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire un hub pubblico SEO/AI news che gira ogni mattina alle 07:00 Europe/Rome via GitHub Actions, recupera notizie da fonti autorevoli, le riassume in italiano via OpenRouter, rileva modifiche a pagine Google (Doc Watcher), e pubblica `feed.json` + frontend statico su Cloudflare Pages.

**Architecture:** Pipeline Python asincrona (fetch → normalize → summarize → rank → publish) eseguita come cron su GitHub Actions. Stato persistito come file committati in git. Output statico servito da Cloudflare Pages. Zero database, zero backend server-side.

**Tech Stack:** Python 3.12, httpx async, feedparser, selectolax, playwright, pdfplumber, difflib, pydantic v2, rapidfuzz, pyyaml, pytest, ruff, GitHub Actions, OpenRouter API (Gemini 2.0 Flash default), HTML + vanilla JS frontend.

**Fasi:**
1. **Foundation** (T1-T3): scaffold, models, config loader
2. **HTTP + Fetchers** (T4-T7): client condiviso, RSS, Scraper, Playwright
3. **Doc Watcher** (T8-T9): state + diff logic
4. **Pipeline Core** (T10-T14): normalizer, dedup, summarizer, ranker, publisher
5. **Wiring** (T15-T17): CLI, initial configs, orchestrator
6. **Frontend** (T18): HTML + CSS + JS
7. **CI/CD** (T19-T20): GitHub Actions workflows
8. **Docs** (T21): README

**Prerequisiti:**
- Python 3.12+ installato localmente
- `git` inizializzato nel repo (già fatto nel commit precedente)
- API key OpenRouter (registrazione su https://openrouter.ai)
- Account GitHub (per push e Actions)
- Account Cloudflare (per Pages, step finale)

**Riferimento spec:** `docs/superpowers/specs/2026-04-11-osservatorio-seo-design.md`

---

## Task 1: Project Scaffold & Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.ruff.toml`
- Create: `src/osservatorio_seo/__init__.py`
- Create: `src/osservatorio_seo/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "osservatorio-seo"
version = "0.1.0"
description = "Hub giornaliero di notizie SEO e AI da fonti autorevoli"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "feedparser>=6.0",
    "httpx>=0.27",
    "selectolax>=0.3",
    "beautifulsoup4>=4.12",
    "playwright>=1.45",
    "html2text>=2024.2",
    "pdfplumber>=0.11",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "rapidfuzz>=3.9",
    "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
    "ruff>=0.5",
]

[project.scripts]
osservatorio-seo = "osservatorio_seo.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.ruff_cache/
.venv/
venv/
dist/
build/
*.egg-info/
.env
.env.local
.DS_Store
.coverage
htmlcov/
```

- [ ] **Step 3: Create `.ruff.toml`**

```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]
```

- [ ] **Step 4: Create `src/osservatorio_seo/__init__.py`**

```python
"""OsservatorioSEO — hub giornaliero di notizie SEO e AI."""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create `src/osservatorio_seo/__main__.py`**

```python
from osservatorio_seo.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Create `tests/__init__.py` (empty) and `tests/conftest.py`**

```python
# tests/conftest.py
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 7: Install and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install --with-deps chromium
ruff --version && pytest --version
```

Expected: `ruff` e `pytest` stampano la versione senza errori.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore .ruff.toml src/ tests/
git commit -m "chore: project scaffold with Python tooling"
```

---

## Task 2: Data Models (Pydantic)

**Files:**
- Create: `src/osservatorio_seo/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.models import (
    DocChange,
    DocWatcherStatus,
    Feed,
    FeedStats,
    Item,
    RawItem,
    Source,
)


def test_source_creation() -> None:
    src = Source(
        id="google_search_central",
        name="Google Search Central Blog",
        authority=10,
        type="official",
        fetcher="rss",
        feed_url="https://developers.google.com/search/blog/rss",
    )
    assert src.authority == 10
    assert src.enabled is True


def test_source_authority_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Source(
            id="x",
            name="x",
            authority=11,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        )


def test_raw_item_minimal() -> None:
    item = RawItem(
        title="March Core Update done",
        url="https://example.com/a",
        source_id="google_search_central",
        published_at=datetime.now(UTC),
        content="Some content here",
    )
    assert item.language_original == "en"


def test_item_full() -> None:
    item = Item(
        id="item_2026-04-11_001",
        title_original="March Core Update done",
        title_it="Il Core Update di marzo è finito",
        summary_it="Google ha completato il rollout.",
        url="https://example.com/a",
        source=Source(
            id="g",
            name="Google",
            authority=10,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category="google_updates",
        tags=["core_update"],
        importance=5,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="google/gemini-2.0-flash",
        raw_hash="sha256:abc",
    )
    assert item.importance == 5


def test_item_importance_range() -> None:
    base = {
        "id": "x",
        "title_original": "x",
        "title_it": "x",
        "summary_it": "x",
        "url": "https://x.com",
        "source": Source(
            id="g", name="G", authority=5, type="official",
            fetcher="rss", feed_url="https://x.com",
        ),
        "category": "google_updates",
        "tags": [],
        "published_at": datetime.now(UTC),
        "fetched_at": datetime.now(UTC),
        "is_doc_change": False,
        "language_original": "en",
        "summarizer_model": "x",
        "raw_hash": "x",
    }
    with pytest.raises(ValidationError):
        Item(**{**base, "importance": 6})
    with pytest.raises(ValidationError):
        Item(**{**base, "importance": 0})


def test_feed_serialization_round_trip() -> None:
    feed = Feed(
        schema_version="1.0",
        generated_at=datetime.now(UTC),
        generated_at_local=datetime.now(UTC),
        timezone="Europe/Rome",
        run_id="2026-04-11-0700",
        stats=FeedStats(
            sources_checked=10,
            sources_failed=0,
            items_collected=15,
            items_after_dedup=12,
            doc_changes_detected=0,
            ai_cost_eur=0.0,
        ),
        top10=[],
        categories={},
        items=[],
        doc_watcher_status=[],
        failed_sources=[],
    )
    dumped = feed.model_dump(mode="json")
    restored = Feed.model_validate(dumped)
    assert restored.schema_version == "1.0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```

Expected: FAIL — "ImportError: cannot import name ... from osservatorio_seo.models".

- [ ] **Step 3: Create `src/osservatorio_seo/models.py`**

```python
"""Pydantic models per OsservatorioSEO."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_models.py -v
```

Expected: tutti i test passano.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/models.py tests/test_models.py
git commit -m "feat(models): pydantic data models for sources, items, and feed"
```

---

## Task 3: Config Loader

**Files:**
- Create: `src/osservatorio_seo/config.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/sources.test.yml`
- Create: `tests/fixtures/doc_watcher.test.yml`

- [ ] **Step 1: Create test fixtures**

`tests/fixtures/sources.test.yml`:
```yaml
sources:
  - id: google_search_central
    name: "Google Search Central Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://developers.google.com/search/blog/rss
    category_hint: google_updates
    enabled: true

  - id: some_scraper_site
    name: "Some Scraper Site"
    authority: 7
    type: media
    fetcher: scraper
    target_url: https://example.com/news
    selectors:
      article: "article.post"
      title: "h2"
      link: "a"
    enabled: true

  - id: disabled_source
    name: "Disabled"
    authority: 5
    type: media
    fetcher: rss
    feed_url: https://example.com/rss
    enabled: false
```

`tests/fixtures/doc_watcher.test.yml`:
```yaml
pages:
  - id: google_spam_policies
    name: "Google Spam Policies"
    url: https://developers.google.com/search/docs/essentials/spam-policies
    selector: "main article"
    type: html
    category: google_docs_change
    importance: 5
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path

import pytest

from osservatorio_seo.config import (
    DocWatcherPage,
    load_doc_watcher,
    load_sources,
    load_settings,
)


def test_load_sources(fixtures_dir: Path) -> None:
    sources = load_sources(fixtures_dir / "sources.test.yml")
    enabled_ids = [s.id for s in sources]
    assert "google_search_central" in enabled_ids
    assert "some_scraper_site" in enabled_ids
    assert "disabled_source" not in enabled_ids


def test_load_doc_watcher(fixtures_dir: Path) -> None:
    pages = load_doc_watcher(fixtures_dir / "doc_watcher.test.yml")
    assert len(pages) == 1
    assert pages[0].id == "google_spam_policies"
    assert pages[0].importance == 5


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        load_settings()


def test_load_settings_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    s = load_settings()
    assert s.openrouter_api_key == "sk-test"
    assert s.summarizer_model == "google/gemini-2.0-flash"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — "cannot import ... from osservatorio_seo.config".

- [ ] **Step 4: Create `src/osservatorio_seo/config.py`**

```python
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
    summarizer_model: str = "google/gemini-2.0-flash"
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_config.py -v
```

Expected: 4 tests passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/config.py tests/test_config.py tests/fixtures/
git commit -m "feat(config): YAML config loader for sources and doc_watcher"
```

---

## Task 4: HTTP Client (shared)

Client async centralizzato con User-Agent rotation, rate limiting per host, retry con backoff. Implementa la policy "Opzione 2" dello spec (no robots.txt, UA browser-like).

**Files:**
- Create: `src/osservatorio_seo/http_client.py`
- Create: `tests/test_http_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_http_client.py
import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.http_client import BROWSER_USER_AGENTS, HttpClient


async def test_get_success(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", text="hello")
    async with HttpClient() as client:
        resp = await client.get("https://example.com/a")
        assert resp.status_code == 200
        assert resp.text == "hello"


async def test_user_agent_is_browser_like(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", text="x")
    async with HttpClient() as client:
        await client.get("https://example.com/a")
    request = httpx_mock.get_request()
    ua = request.headers["user-agent"]
    assert ua in BROWSER_USER_AGENTS
    assert "bot" not in ua.lower()


async def test_retry_on_500(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://example.com/a", status_code=500)
    httpx_mock.add_response(url="https://example.com/a", status_code=200, text="ok")
    async with HttpClient() as client:
        resp = await client.get("https://example.com/a")
        assert resp.status_code == 200


async def test_retry_gives_up_after_max(httpx_mock: HTTPXMock) -> None:
    for _ in range(3):
        httpx_mock.add_response(url="https://example.com/a", status_code=500)
    async with HttpClient() as client:
        with pytest.raises(RuntimeError, match="max retries"):
            await client.get("https://example.com/a")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_http_client.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/http_client.py`**

```python
"""HTTP client async con UA rotation, rate limiting, retry."""
from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from types import TracebackType
from urllib.parse import urlparse

import httpx

BROWSER_USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
]


class HttpClient:
    """Async HTTP client con limiti per host e retry.

    - Ruota User-Agent browser-like
    - Max N concurrent per host (default 3)
    - Delay 1-2s + jitter tra richieste sequenziali sullo stesso host
    - Retry 2x su 5xx e timeout con exponential backoff
    """

    def __init__(
        self,
        max_concurrent_per_host: int = 3,
        timeout_s: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.max_concurrent_per_host = max_concurrent_per_host
        self.max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            follow_redirects=True,
            http2=False,
        )
        self._host_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(max_concurrent_per_host)
        )
        self._host_last_request: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __aenter__(self) -> "HttpClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        host = urlparse(url).netloc
        headers = {
            "User-Agent": random.choice(BROWSER_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,it;q=0.8",
            **kwargs.pop("headers", {}),
        }
        async with self._host_semaphores[host]:
            await self._rate_limit_per_host(host)
            return await self._get_with_retry(url, headers, **kwargs)

    async def _rate_limit_per_host(self, host: str) -> None:
        async with self._host_locks[host]:
            last = self._host_last_request.get(host, 0.0)
            now = asyncio.get_event_loop().time()
            min_delay = 1.0 + random.uniform(0.0, 1.0)
            wait = max(0.0, last + min_delay - now)
            if wait > 0:
                await asyncio.sleep(wait)
            self._host_last_request[host] = asyncio.get_event_loop().time()

    async def _get_with_retry(
        self, url: str, headers: dict, **kwargs
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._client.get(url, headers=headers, **kwargs)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt + random.uniform(0.0, 0.5))
        raise RuntimeError(f"max retries exceeded for {url}: {last_exc}")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_http_client.py -v
```

Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/http_client.py tests/test_http_client.py
git commit -m "feat(http): shared async client with UA rotation and rate limiting"
```

---

## Task 5: Fetcher Base + RSS Fetcher

**Files:**
- Create: `src/osservatorio_seo/fetchers/__init__.py`
- Create: `src/osservatorio_seo/fetchers/base.py`
- Create: `src/osservatorio_seo/fetchers/rss.py`
- Create: `tests/fixtures/sample_feed.xml`
- Create: `tests/test_rss_fetcher.py`

- [ ] **Step 1: Create the fixture RSS file**

`tests/fixtures/sample_feed.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <link>https://example.com</link>
    <description>Sample</description>
    <item>
      <title>March Core Update Finished</title>
      <link>https://example.com/march-core-update</link>
      <description>The March 2026 core update is done rolling out.</description>
      <pubDate>Fri, 11 Apr 2026 03:42:00 GMT</pubDate>
    </item>
    <item>
      <title>New Spam Policy</title>
      <link>https://example.com/new-spam-policy</link>
      <description>Google announces new policies.</description>
      <pubDate>Fri, 11 Apr 2026 05:12:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_rss_fetcher.py
from pathlib import Path

from pytest_httpx import HTTPXMock

from osservatorio_seo.fetchers.rss import RSSFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import Source


async def test_rss_fetch(fixtures_dir: Path, httpx_mock: HTTPXMock) -> None:
    xml = (fixtures_dir / "sample_feed.xml").read_text()
    httpx_mock.add_response(url="https://example.com/feed.xml", text=xml)

    source = Source(
        id="example",
        name="Example",
        authority=7,
        type="media",
        fetcher="rss",
        feed_url="https://example.com/feed.xml",
    )
    async with HttpClient() as client:
        fetcher = RSSFetcher(client)
        items = await fetcher.fetch(source)

    assert len(items) == 2
    assert items[0].title == "March Core Update Finished"
    assert items[0].url == "https://example.com/march-core-update"
    assert items[0].source_id == "example"
    assert items[0].content  # non vuoto


async def test_rss_empty_feed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://example.com/feed.xml",
        text="<?xml version='1.0'?><rss><channel></channel></rss>",
    )
    source = Source(
        id="x", name="x", authority=5, type="media",
        fetcher="rss", feed_url="https://example.com/feed.xml",
    )
    async with HttpClient() as client:
        fetcher = RSSFetcher(client)
        items = await fetcher.fetch(source)
    assert items == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_rss_fetcher.py -v
```

Expected: FAIL (import error).

- [ ] **Step 4: Create `src/osservatorio_seo/fetchers/__init__.py` (empty)**

- [ ] **Step 5: Create `src/osservatorio_seo/fetchers/base.py`**

```python
"""Fetcher interface."""
from __future__ import annotations

from typing import Protocol

from osservatorio_seo.models import RawItem, Source


class Fetcher(Protocol):
    async def fetch(self, source: Source) -> list[RawItem]: ...
```

- [ ] **Step 6: Create `src/osservatorio_seo/fetchers/rss.py`**

```python
"""RSS/Atom fetcher via feedparser."""
from __future__ import annotations

from datetime import UTC, datetime
from time import mktime

import feedparser

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import RawItem, Source


class RSSFetcher:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.feed_url:
            return []
        resp = await self._http.get(source.feed_url)
        parsed = feedparser.parse(resp.text)
        items: list[RawItem] = []
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            url = entry.get("link", "").strip()
            if not title or not url:
                continue
            content = self._extract_content(entry)
            published = self._extract_date(entry)
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source_id=source.id,
                    published_at=published,
                    content=content,
                )
            )
        return items

    @staticmethod
    def _extract_content(entry) -> str:
        for key in ("content", "summary", "description"):
            val = entry.get(key)
            if not val:
                continue
            if isinstance(val, list) and val:
                return str(val[0].get("value", "")).strip()
            return str(val).strip()
        return ""

    @staticmethod
    def _extract_date(entry) -> datetime:
        for key in ("published_parsed", "updated_parsed"):
            struct = entry.get(key)
            if struct:
                return datetime.fromtimestamp(mktime(struct), tz=UTC)
        return datetime.now(UTC)
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_rss_fetcher.py -v
```

Expected: 2 tests passed.

- [ ] **Step 8: Commit**

```bash
git add src/osservatorio_seo/fetchers/ tests/fixtures/sample_feed.xml tests/test_rss_fetcher.py
git commit -m "feat(fetcher): RSS fetcher via feedparser"
```

---

## Task 6: Scraper Fetcher

Generic HTML scraper basato su selettori configurati in `sources.yml`.

**Files:**
- Create: `src/osservatorio_seo/fetchers/scraper.py`
- Create: `tests/fixtures/sample_scraper_page.html`
- Create: `tests/test_scraper_fetcher.py`

- [ ] **Step 1: Create fixture HTML**

`tests/fixtures/sample_scraper_page.html`:
```html
<!DOCTYPE html>
<html>
<head><title>News List</title></head>
<body>
  <main>
    <article class="post">
      <h2><a href="/news/1">First News</a></h2>
      <div class="excerpt">Content of first news</div>
      <time datetime="2026-04-11T03:00:00Z">11 April 2026</time>
    </article>
    <article class="post">
      <h2><a href="https://example.com/news/2">Second News</a></h2>
      <div class="excerpt">Content of second</div>
      <time datetime="2026-04-11T04:30:00Z">11 April 2026</time>
    </article>
  </main>
</body>
</html>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_scraper_fetcher.py
from pathlib import Path

from pytest_httpx import HTTPXMock

from osservatorio_seo.fetchers.scraper import ScraperFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import Source


async def test_scraper_fetch(fixtures_dir: Path, httpx_mock: HTTPXMock) -> None:
    html = (fixtures_dir / "sample_scraper_page.html").read_text()
    httpx_mock.add_response(url="https://example.com/news", text=html)

    source = Source(
        id="example_scraper",
        name="Example Scraper",
        authority=7,
        type="media",
        fetcher="scraper",
        target_url="https://example.com/news",
        selectors={
            "article": "article.post",
            "title": "h2 a",
            "link": "h2 a",
            "content": "div.excerpt",
            "date": "time",
        },
    )
    async with HttpClient() as client:
        fetcher = ScraperFetcher(client)
        items = await fetcher.fetch(source)

    assert len(items) == 2
    assert items[0].title == "First News"
    assert items[0].url == "https://example.com/news/1"  # relative resolved
    assert items[1].url == "https://example.com/news/2"  # absolute preserved
    assert "first" in items[0].content.lower()


async def test_scraper_no_selectors() -> None:
    source = Source(
        id="x", name="x", authority=5, type="media",
        fetcher="scraper", target_url="https://x.com",
    )
    async with HttpClient() as client:
        fetcher = ScraperFetcher(client)
        items = await fetcher.fetch(source)
    assert items == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_scraper_fetcher.py -v
```

Expected: FAIL (import error).

- [ ] **Step 4: Create `src/osservatorio_seo/fetchers/scraper.py`**

```python
"""Generic HTML scraper basato su CSS selector configurati."""
from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urljoin

from dateutil import parser as date_parser
from selectolax.parser import HTMLParser

from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import RawItem, Source


class ScraperFetcher:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.target_url or not source.selectors:
            return []
        resp = await self._http.get(source.target_url)
        tree = HTMLParser(resp.text)
        sel = source.selectors

        articles = tree.css(sel.get("article", "article"))
        items: list[RawItem] = []
        for node in articles:
            title_node = node.css_first(sel.get("title", "h2"))
            link_node = node.css_first(sel.get("link", "a"))
            content_node = node.css_first(sel.get("content", ""))
            date_node = node.css_first(sel.get("date", "time"))

            title = title_node.text(strip=True) if title_node else ""
            raw_link = ""
            if link_node:
                raw_link = link_node.attributes.get("href", "") or ""
            if not title or not raw_link:
                continue

            url = urljoin(source.target_url, raw_link)
            content = content_node.text(strip=True) if content_node else ""
            published = self._extract_date(date_node)

            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source_id=source.id,
                    published_at=published,
                    content=content,
                )
            )
        return items

    @staticmethod
    def _extract_date(node) -> datetime:
        if not node:
            return datetime.now(UTC)
        dt_attr = node.attributes.get("datetime", "")
        if dt_attr:
            try:
                parsed = date_parser.isoparse(dt_attr)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed
            except (ValueError, TypeError):
                pass
        try:
            parsed = date_parser.parse(node.text(strip=True))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed
        except (ValueError, TypeError):
            return datetime.now(UTC)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_scraper_fetcher.py -v
```

Expected: 2 tests passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/fetchers/scraper.py tests/fixtures/sample_scraper_page.html tests/test_scraper_fetcher.py
git commit -m "feat(fetcher): generic HTML scraper with CSS selectors"
```

---

## Task 7: Playwright Fetcher

Fetcher per siti con anti-bot / JS pesante (X, LinkedIn). Il test principale è uno smoke test che verifica l'import e un mock del metodo `fetch` — non lanciamo un vero Chromium in CI dei test unitari (il canary settimanale lo farà contro fonti reali).

**Files:**
- Create: `src/osservatorio_seo/fetchers/playwright_fetcher.py`
- Create: `tests/test_playwright_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_playwright_fetcher.py
import pytest

from osservatorio_seo.fetchers.playwright_fetcher import PlaywrightFetcher
from osservatorio_seo.models import Source


@pytest.fixture
def social_source() -> Source:
    return Source(
        id="test_social",
        name="Test Social",
        authority=8,
        type="social",
        fetcher="playwright",
        target_url="https://x.com/someuser",
        selectors={
            "post": "article[data-testid='tweet']",
            "text": "div[data-testid='tweetText']",
            "link": "a[href*='/status/']",
        },
    )


async def test_playwright_no_target_url() -> None:
    source = Source(
        id="x", name="x", authority=5, type="social",
        fetcher="playwright",
    )
    fetcher = PlaywrightFetcher()
    items = await fetcher.fetch(source)
    assert items == []


async def test_playwright_parses_post_nodes(social_source: Source) -> None:
    fetcher = PlaywrightFetcher()
    fake_html = """
    <html><body>
      <article data-testid="tweet">
        <div data-testid="tweetText">First post text</div>
        <a href="/someuser/status/12345">link</a>
      </article>
      <article data-testid="tweet">
        <div data-testid="tweetText">Second post</div>
        <a href="/someuser/status/67890">link</a>
      </article>
    </body></html>
    """
    items = fetcher._parse_html(fake_html, social_source)
    assert len(items) == 2
    assert items[0].title.startswith("First post")
    assert "status/12345" in items[0].url
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_playwright_fetcher.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/fetchers/playwright_fetcher.py`**

```python
"""Playwright-based fetcher per siti con anti-bot (X, LinkedIn)."""
from __future__ import annotations

import random
from datetime import UTC, datetime
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from osservatorio_seo.http_client import BROWSER_USER_AGENTS
from osservatorio_seo.models import RawItem, Source


class PlaywrightFetcher:
    def __init__(self, timeout_s: int = 30) -> None:
        self._timeout_ms = timeout_s * 1000

    async def fetch(self, source: Source) -> list[RawItem]:
        if not source.target_url or not source.selectors:
            return []
        html = await self._render_page(source.target_url)
        return self._parse_html(html, source)

    async def _render_page(self, url: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=random.choice(BROWSER_USER_AGENTS),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                )
                page = await context.new_page()
                await page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)  # let JS render
                return await page.content()
            finally:
                await browser.close()

    def _parse_html(self, html: str, source: Source) -> list[RawItem]:
        sel = source.selectors or {}
        tree = HTMLParser(html)
        post_nodes = tree.css(sel.get("post", "article"))
        items: list[RawItem] = []
        for node in post_nodes[:20]:  # limita rumore
            text_node = node.css_first(sel.get("text", ""))
            link_node = node.css_first(sel.get("link", "a"))
            if not text_node or not link_node:
                continue
            text = text_node.text(strip=True)
            href = link_node.attributes.get("href", "") or ""
            if not text or not href:
                continue
            url = urljoin(source.target_url or "", href)
            title = text[:120] + ("..." if len(text) > 120 else "")
            items.append(
                RawItem(
                    title=title,
                    url=url,
                    source_id=source.id,
                    published_at=datetime.now(UTC),
                    content=text,
                )
            )
        return items
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_playwright_fetcher.py -v
```

Expected: 2 tests passed (nessun Chromium lanciato: testiamo solo `_parse_html` e il caso no-url).

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/fetchers/playwright_fetcher.py tests/test_playwright_fetcher.py
git commit -m "feat(fetcher): playwright-based fetcher for anti-bot sites"
```

---

## Task 8: Doc Watcher State Layer

**Files:**
- Create: `src/osservatorio_seo/doc_watcher/__init__.py`
- Create: `src/osservatorio_seo/doc_watcher/state.py`
- Create: `tests/test_doc_watcher_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_watcher_state.py
from pathlib import Path

from osservatorio_seo.doc_watcher.state import StateStore


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    assert store.load_hash("google_spam") is None
    assert store.load_text("google_spam") is None


def test_save_and_load(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save("google_spam", "sha256:abc", "Some content")
    assert store.load_hash("google_spam") == "sha256:abc"
    assert store.load_text("google_spam") == "Some content"


def test_save_diff(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save_diff("google_spam", "2026-04-11", "--- old\n+++ new\n@@\n-a\n+b\n")
    diff_files = list(tmp_path.glob("google_spam_*.diff"))
    assert len(diff_files) == 1
    assert "2026-04-11" in diff_files[0].name
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_doc_watcher_state.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `src/osservatorio_seo/doc_watcher/__init__.py` (empty)**

- [ ] **Step 4: Create `src/osservatorio_seo/doc_watcher/state.py`**

```python
"""Persistenza stato del Doc Watcher (hash, testi, diff)."""
from __future__ import annotations

from pathlib import Path


class StateStore:
    def __init__(self, base_dir: Path) -> None:
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def load_hash(self, page_id: str) -> str | None:
        p = self._dir / f"{page_id}.hash"
        return p.read_text(encoding="utf-8").strip() if p.exists() else None

    def load_text(self, page_id: str) -> str | None:
        p = self._dir / f"{page_id}.txt"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def save(self, page_id: str, hash_value: str, text: str) -> None:
        (self._dir / f"{page_id}.hash").write_text(hash_value, encoding="utf-8")
        (self._dir / f"{page_id}.txt").write_text(text, encoding="utf-8")

    def save_diff(self, page_id: str, date_str: str, diff: str) -> None:
        (self._dir / f"{page_id}_{date_str}.diff").write_text(diff, encoding="utf-8")
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_doc_watcher_state.py -v
```

Expected: 3 tests passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/doc_watcher/ tests/test_doc_watcher_state.py
git commit -m "feat(doc_watcher): state store for hashes, texts, and diffs"
```

---

## Task 9: Doc Watcher Logic (fetch + diff)

**Files:**
- Create: `src/osservatorio_seo/doc_watcher/watcher.py`
- Create: `tests/test_doc_watcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_watcher.py
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocWatcher
from osservatorio_seo.http_client import HttpClient


@pytest.fixture
def page() -> DocWatcherPage:
    return DocWatcherPage(
        id="google_spam_policies",
        name="Google Spam Policies",
        url="https://developers.google.com/spam",
        selector="main article",
        type="html",
        category="google_docs_change",
        importance=5,
    )


async def test_first_run_saves_but_no_change(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://developers.google.com/spam",
        text="<html><body><main><article>Some spam policy v1</article></main></body></html>",
    )
    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        result = await watcher.check(page)

    assert result.changed is False
    assert state.load_hash("google_spam_policies") is not None


async def test_second_run_same_content_no_change(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    html = "<html><body><main><article>Stable content</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        result = await watcher.check(page)
    assert result.changed is False


async def test_second_run_changed_content_detected(
    page: DocWatcherPage, tmp_path: Path, httpx_mock: HTTPXMock
) -> None:
    html_old = "<html><body><main><article>Old text here.</article></main></body></html>"
    html_new = "<html><body><main><article>Old text here. Added new sentence about AI.</article></main></body></html>"
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_old)
    httpx_mock.add_response(url="https://developers.google.com/spam", text=html_new)

    state = StateStore(tmp_path)
    async with HttpClient() as client:
        watcher = DocWatcher(http=client, state=state)
        await watcher.check(page)
        result = await watcher.check(page)

    assert result.changed is True
    assert result.previous_hash != result.current_hash
    assert result.lines_added >= 1
    assert "+" in result.diff


def test_similarity_threshold_ignores_tiny_change() -> None:
    watcher = DocWatcher(http=None, state=None, similarity_threshold=0.003)  # type: ignore[arg-type]
    old = "a" * 10000
    new = old + "b"
    assert watcher._is_significant_change(old, new) is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_doc_watcher.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/doc_watcher/watcher.py`**

```python
"""Doc Watcher: rileva modifiche a pagine di documentazione ufficiale."""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import html2text
from selectolax.parser import HTMLParser

from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.http_client import HttpClient

MAX_DIFF_CHARS = 50_000


@dataclass(frozen=True)
class DocChangeResult:
    page_id: str
    changed: bool
    previous_hash: str | None
    current_hash: str
    diff: str
    lines_added: int
    lines_removed: int
    checked_at: datetime
    new_text: str


class DocWatcher:
    def __init__(
        self,
        http: HttpClient,
        state: StateStore,
        similarity_threshold: float = 0.003,
    ) -> None:
        self._http = http
        self._state = state
        self._similarity_threshold = similarity_threshold
        self._h2t = html2text.HTML2Text()
        self._h2t.ignore_links = True
        self._h2t.ignore_images = True
        self._h2t.body_width = 0

    async def check(self, page: DocWatcherPage) -> DocChangeResult:
        now = datetime.now(UTC)
        if page.type == "pdf":
            raw_text = await self._fetch_pdf(page.url)
        else:
            raw_text = await self._fetch_html(page.url, page.selector)

        new_text = self._normalize(raw_text, page.noise_patterns)
        current_hash = "sha256:" + hashlib.sha256(new_text.encode("utf-8")).hexdigest()
        previous_hash = self._state.load_hash(page.id)
        previous_text = self._state.load_text(page.id)

        if previous_hash is None:
            self._state.save(page.id, current_hash, new_text)
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=None,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        if previous_hash == current_hash:
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=previous_hash,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        if not self._is_significant_change(previous_text or "", new_text):
            self._state.save(page.id, current_hash, new_text)
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=previous_hash,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        diff_lines = list(
            difflib.unified_diff(
                (previous_text or "").splitlines(),
                new_text.splitlines(),
                fromfile="prev",
                tofile="curr",
                n=2,
                lineterm="",
            )
        )
        diff = "\n".join(diff_lines)
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n... [diff truncated]"
        added = sum(1 for L in diff_lines if L.startswith("+") and not L.startswith("+++"))
        removed = sum(1 for L in diff_lines if L.startswith("-") and not L.startswith("---"))

        date_str = now.strftime("%Y-%m-%d")
        self._state.save_diff(page.id, date_str, diff)
        self._state.save(page.id, current_hash, new_text)

        return DocChangeResult(
            page_id=page.id,
            changed=True,
            previous_hash=previous_hash,
            current_hash=current_hash,
            diff=diff,
            lines_added=added,
            lines_removed=removed,
            checked_at=now,
            new_text=new_text,
        )

    async def _fetch_html(self, url: str, selector: str | None) -> str:
        resp = await self._http.get(url)
        tree = HTMLParser(resp.text)
        root = tree.css_first(selector) if selector else tree.body
        html_frag = root.html if root else resp.text
        return self._h2t.handle(html_frag or "")

    async def _fetch_pdf(self, url: str) -> str:
        import io

        import pdfplumber

        resp = await self._http.get(url)
        buf = io.BytesIO(resp.content)
        with pdfplumber.open(buf) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    def _normalize(self, text: str, noise_patterns: list[str]) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        for pattern in noise_patterns:
            text = re.sub(pattern, "", text, flags=re.MULTILINE)
        return text.strip()

    def _is_significant_change(self, old: str, new: str) -> bool:
        if not old:
            return True
        ratio = difflib.SequenceMatcher(None, old, new).ratio()
        return (1.0 - ratio) >= self._similarity_threshold
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_doc_watcher.py -v
```

Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/doc_watcher/watcher.py tests/test_doc_watcher.py
git commit -m "feat(doc_watcher): HTML/PDF fetch + diff detection"
```

---

## Task 10: Normalizer + Deduplicator

**Files:**
- Create: `src/osservatorio_seo/normalizer.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_normalizer.py
from datetime import UTC, datetime, timedelta

from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.normalizer import Normalizer


def mk_source(authority: int = 5) -> Source:
    return Source(
        id=f"src{authority}", name=f"src{authority}",
        authority=authority, type="media", fetcher="rss",
        feed_url="https://example.com/feed",
    )


def mk_raw(url: str, title: str, source_id: str, content: str = "enough content here for normalization") -> RawItem:
    return RawItem(
        title=title, url=url, source_id=source_id,
        published_at=datetime.now(UTC), content=content,
    )


def test_url_tracking_params_removed() -> None:
    norm = Normalizer()
    items = [mk_raw("https://example.com/a?utm_source=x&id=5", "Hello", "s1")]
    out = norm.normalize(items, {"s1": mk_source()})
    assert out[0].url == "https://example.com/a?id=5"


def test_url_trailing_slash_normalized() -> None:
    norm = Normalizer()
    items = [mk_raw("https://example.com/a/", "Hello", "s1")]
    out = norm.normalize(items, {"s1": mk_source()})
    assert out[0].url == "https://example.com/a"


def test_dedup_by_url() -> None:
    norm = Normalizer()
    items = [
        mk_raw("https://example.com/a", "Hello", "s1"),
        mk_raw("https://example.com/a", "Hello again", "s2"),
    ]
    out = norm.normalize(items, {"s1": mk_source(5), "s2": mk_source(9)})
    assert len(out) == 1
    # il duplicato con authority più alta vince
    assert out[0].source_id == "s2"


def test_dedup_by_fuzzy_title() -> None:
    norm = Normalizer()
    items = [
        mk_raw("https://a.com/x", "Google Releases New Core Update for Search", "s1"),
        mk_raw("https://b.com/y", "Google releases new core update for search!", "s2"),
    ]
    out = norm.normalize(items, {"s1": mk_source(5), "s2": mk_source(10)})
    assert len(out) == 1
    assert out[0].source_id == "s2"


def test_filter_too_old() -> None:
    norm = Normalizer(max_age_hours=48)
    old_item = RawItem(
        title="Old", url="https://a.com/old", source_id="s1",
        published_at=datetime.now(UTC) - timedelta(hours=72),
        content="some content",
    )
    out = norm.normalize([old_item], {"s1": mk_source()})
    assert out == []


def test_filter_too_short() -> None:
    norm = Normalizer()
    short = mk_raw("https://a.com/short", "Hi", "s1", content="tiny")
    out = norm.normalize([short], {"s1": mk_source()})
    assert out == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_normalizer.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/normalizer.py`**

```python
"""Normalizzazione URL/titoli + dedup."""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from rapidfuzz import fuzz

from osservatorio_seo.models import RawItem, Source

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid",
}


class Normalizer:
    def __init__(
        self,
        max_age_hours: int = 48,
        min_content_chars: int = 20,
        title_similarity_threshold: int = 85,
    ) -> None:
        self._max_age = timedelta(hours=max_age_hours)
        self._min_content_chars = min_content_chars
        self._title_threshold = title_similarity_threshold

    def normalize(
        self, raw_items: list[RawItem], sources: dict[str, Source]
    ) -> list[RawItem]:
        cleaned: list[RawItem] = []
        now = datetime.now(UTC)
        for item in raw_items:
            if len(item.content) < self._min_content_chars:
                continue
            if now - item.published_at > self._max_age:
                continue
            cleaned.append(
                item.model_copy(
                    update={
                        "url": self._canonical_url(item.url),
                        "title": self._clean_title(item.title),
                    }
                )
            )

        deduped = self._dedup_by_url(cleaned, sources)
        deduped = self._dedup_by_title(deduped, sources)
        return deduped

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url)
        query = [(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS]
        path = parsed.path.rstrip("/") or "/"
        return urlunparse(parsed._replace(query=urlencode(query), path=path, fragment=""))

    @staticmethod
    def _clean_title(title: str) -> str:
        import html

        title = html.unescape(title)
        title = re.sub(r"\s+", " ", title).strip()
        return title

    def _dedup_by_url(
        self, items: list[RawItem], sources: dict[str, Source]
    ) -> list[RawItem]:
        best: dict[str, RawItem] = {}
        for item in items:
            existing = best.get(item.url)
            if existing is None:
                best[item.url] = item
                continue
            if sources[item.source_id].authority > sources[existing.source_id].authority:
                best[item.url] = item
        return list(best.values())

    def _dedup_by_title(
        self, items: list[RawItem], sources: dict[str, Source]
    ) -> list[RawItem]:
        kept: list[RawItem] = []
        for item in items:
            duplicate_idx: int | None = None
            for i, existing in enumerate(kept):
                score = fuzz.ratio(item.title.lower(), existing.title.lower())
                if score >= self._title_threshold:
                    duplicate_idx = i
                    break
            if duplicate_idx is None:
                kept.append(item)
                continue
            existing = kept[duplicate_idx]
            if sources[item.source_id].authority > sources[existing.source_id].authority:
                kept[duplicate_idx] = item
        return kept
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_normalizer.py -v
```

Expected: 6 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/normalizer.py tests/test_normalizer.py
git commit -m "feat(normalizer): URL canonicalization + dedup by URL and fuzzy title"
```

---

## Task 11: OpenRouter Client + Summarizer

Client AI con fallback chain e due prompt distinti (summarizer normale + doc-change).

**Files:**
- Create: `src/osservatorio_seo/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_summarizer.py
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.models import RawItem, Source
from osservatorio_seo.summarizer import (
    AISummary,
    DocChangeSummary,
    Summarizer,
    SummarizerError,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def mk_raw() -> RawItem:
    return RawItem(
        title="March 2026 core update done",
        url="https://example.com/a",
        source_id="google_search_central",
        published_at=datetime.now(UTC),
        content="Google announced today that the March 2026 core update is fully rolled out.",
    )


def mk_source() -> Source:
    return Source(
        id="google_search_central",
        name="Google Search Central Blog",
        authority=10,
        type="official",
        fetcher="rss",
        feed_url="https://example.com/feed",
    )


def mock_response(payload: dict) -> dict:
    return {
        "choices": [
            {"message": {"content": json.dumps(payload)}}
        ],
        "usage": {"prompt_tokens": 500, "completion_tokens": 80},
        "model": "google/gemini-2.0-flash",
    }


async def test_summarize_item_success(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response({
            "title_it": "Core update marzo 2026 completato",
            "summary_it": "Google ha completato il rollout del core update di marzo 2026.",
            "category": "google_updates",
            "tags": ["core_update", "ranking"],
            "importance": 5,
        }),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert isinstance(result, AISummary)
    assert result.importance == 5
    assert "marzo" in result.summary_it.lower()


async def test_summarize_item_retries_on_malformed_json(httpx_mock: HTTPXMock) -> None:
    # prima risposta: JSON malformato
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json={"choices": [{"message": {"content": "NOT JSON"}}], "usage": {}},
    )
    # retry: JSON corretto
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response({
            "title_it": "Test",
            "summary_it": "Test summary.",
            "category": "google_updates",
            "tags": [],
            "importance": 3,
        }),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert result.importance == 3


async def test_summarize_falls_back_to_next_model(httpx_mock: HTTPXMock) -> None:
    # primo modello fallisce (errore)
    httpx_mock.add_response(url=OPENROUTER_URL, status_code=500)
    httpx_mock.add_response(url=OPENROUTER_URL, status_code=500)
    # fallback model risponde ok
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response({
            "title_it": "Fallback ok",
            "summary_it": "Riassunto dal fallback model.",
            "category": "ai_models",
            "tags": [],
            "importance": 2,
        }),
    )
    summarizer = Summarizer(
        api_key="sk-test",
        primary_model="google/gemini-2.0-flash",
        fallback_models=["anthropic/claude-haiku-4.5"],
    )
    result = await summarizer.summarize_item(mk_raw(), mk_source())
    assert result.importance == 2


async def test_summarize_doc_change(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=OPENROUTER_URL,
        json=mock_response({
            "title_it": "⚠️ Google ha aggiornato Spam Policies",
            "summary_it": "Aggiunta nuova sezione sul scaled content abuse.",
            "tags": ["spam_policies"],
            "importance": 5,
        }),
    )
    summarizer = Summarizer(api_key="sk-test")
    result = await summarizer.summarize_doc_change(
        page_name="Google Spam Policies",
        page_url="https://developers.google.com/spam",
        diff="+new section about scaled content\n-old sentence removed",
    )
    assert isinstance(result, DocChangeSummary)
    assert result.title_it.startswith("⚠️")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_summarizer.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/summarizer.py`**

```python
"""AI summarizer via OpenRouter con fallback chain."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from osservatorio_seo.models import CategoryId, RawItem, Source

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ITEM_PROMPT = """Sei un analista SEO senior italiano. Devi riassumere una notizia \
per un hub giornaliero di SEO e AI. Il lettore è un professionista SEO.

Regole:
- Rispondi SEMPRE in JSON valido con lo schema esatto sotto
- summary_it: 2-4 frasi in italiano, niente hype, niente "scopri", niente "incredibile". \
Tono asciutto e informativo.
- Non ripetere il titolo nel summary.
- Se la notizia è marketing/PR vuoto, importance=1.
- category: scegli UNA tra [google_updates, ai_models, ai_overviews_llm_seo, \
technical_seo, content_eeat, tools_platforms, industry_news]
- tags: 1-4 tag snake_case in inglese
- importance: 1-5 (5 = core update / cambio di regole / release major)
- title_it: traduci il titolo in italiano naturale (non letterale)

Schema output:
{{"title_it": "string", "summary_it": "string", "category": "string", \
"tags": ["string"], "importance": int}}

Notizia:
Titolo: {title}
Fonte: {source_name} (autorevolezza {authority}/10, tipo {source_type})
Pubblicato: {published_at}
URL: {url}
Contenuto (primi 3000 caratteri):
{content}
"""

DOC_CHANGE_PROMPT = """Sei un analista SEO senior italiano. Una pagina ufficiale è \
stata modificata. Analizza SOLO il diff sotto e spiega in italiano cosa è cambiato \
e perché importa a un SEO.

Regole:
- JSON valido con schema sotto
- summary_it: 2-4 frasi. Dì CONCRETAMENTE cosa è stato aggiunto, rimosso, o \
riformulato. Non dire "sono stati fatti aggiornamenti".
- Se il cambio è solo cosmetico/stylistic, importance=1 e dillo.
- importance 5 = nuova regola o restrizione, cambio di policy, nuova feature documentata.

Schema:
{{"title_it": "string (inizia con ⚠️, max 80 char)", "summary_it": "string", \
"tags": ["string"], "importance": int}}

Pagina: {page_name}
URL: {page_url}
Diff unificato:
{diff}
"""


class AISummary(BaseModel):
    title_it: str
    summary_it: str
    category: CategoryId
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: int = Field(ge=1, le=5)
    model_used: str
    cost_eur: float


class DocChangeSummary(BaseModel):
    title_it: str
    summary_it: str
    tags: list[str] = Field(default_factory=list, max_length=8)
    importance: int = Field(ge=1, le=5)
    model_used: str
    cost_eur: float


class SummarizerError(Exception):
    pass


# Rough pricing per milione di token (input / output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-2.0-flash": (0.075, 0.30),
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "openai/gpt-5-mini": (0.25, 2.0),
}
USD_TO_EUR = 0.92


@dataclass
class _RawResult:
    parsed: dict[str, Any]
    model: str
    cost_eur: float


class Summarizer:
    def __init__(
        self,
        api_key: str,
        primary_model: str = "google/gemini-2.0-flash",
        fallback_models: list[str] | None = None,
        max_retries_per_model: int = 2,
    ) -> None:
        self._api_key = api_key
        self._primary = primary_model
        self._fallbacks = fallback_models or [
            "anthropic/claude-haiku-4.5",
            "openai/gpt-5-mini",
        ]
        self._max_retries = max_retries_per_model

    async def summarize_item(self, raw: RawItem, source: Source) -> AISummary:
        prompt = ITEM_PROMPT.format(
            title=raw.title,
            source_name=source.name,
            authority=source.authority,
            source_type=source.type,
            published_at=raw.published_at.isoformat(),
            url=raw.url,
            content=raw.content[:3000],
        )
        result = await self._call_with_fallback(prompt)
        return AISummary(
            model_used=result.model,
            cost_eur=result.cost_eur,
            **result.parsed,
        )

    async def summarize_doc_change(
        self, page_name: str, page_url: str, diff: str
    ) -> DocChangeSummary:
        prompt = DOC_CHANGE_PROMPT.format(
            page_name=page_name, page_url=page_url, diff=diff
        )
        result = await self._call_with_fallback(prompt)
        return DocChangeSummary(
            model_used=result.model,
            cost_eur=result.cost_eur,
            **result.parsed,
        )

    async def _call_with_fallback(self, prompt: str) -> _RawResult:
        models = [self._primary, *self._fallbacks]
        last_error: Exception | None = None
        for model in models:
            try:
                return await self._call_model(model, prompt)
            except Exception as e:  # noqa: BLE001
                logger.warning("model %s failed: %s", model, e)
                last_error = e
        raise SummarizerError(f"all models failed: {last_error}")

    async def _call_model(self, model: str, prompt: str) -> _RawResult:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "HTTP-Referer": "https://github.com/osservatorioseo",
            "X-Title": "OsservatorioSEO",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(self._max_retries):
                resp = await client.post(OPENROUTER_URL, headers=headers, json=body)
                if resp.status_code >= 500:
                    if attempt < self._max_retries - 1:
                        continue
                    raise SummarizerError(f"server error {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                except (KeyError, json.JSONDecodeError) as e:
                    if attempt < self._max_retries - 1:
                        logger.warning("malformed JSON from %s, retrying: %s", model, e)
                        continue
                    raise SummarizerError(f"malformed JSON from {model}") from e
                usage = data.get("usage", {}) or {}
                cost = self._compute_cost(
                    model,
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
                return _RawResult(parsed=parsed, model=model, cost_eur=cost)
            raise SummarizerError("retries exhausted")

    @staticmethod
    def _compute_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
        usd = (prompt_tokens / 1_000_000) * in_price + (
            completion_tokens / 1_000_000
        ) * out_price
        return usd * USD_TO_EUR
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_summarizer.py -v
```

Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/summarizer.py tests/test_summarizer.py
git commit -m "feat(summarizer): OpenRouter integration with fallback chain"
```

---

## Task 12: Ranker

**Files:**
- Create: `src/osservatorio_seo/ranker.py`
- Create: `tests/test_ranker.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ranker.py
from datetime import UTC, datetime, timedelta

from osservatorio_seo.models import Item, Source
from osservatorio_seo.ranker import Ranker


def mk_item(
    item_id: str,
    importance: int,
    authority: int,
    category: str = "google_updates",
    is_doc_change: bool = False,
    hours_ago: float = 1.0,
) -> Item:
    return Item(
        id=item_id,
        title_original=item_id,
        title_it=item_id,
        summary_it="summary",
        url=f"https://example.com/{item_id}",
        source=Source(
            id=f"src-{item_id}", name="src", authority=authority,
            type="official", fetcher="rss", feed_url="https://x.com",
        ),
        category=category,  # type: ignore[arg-type]
        tags=[],
        importance=importance,
        published_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        fetched_at=datetime.now(UTC),
        is_doc_change=is_doc_change,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def test_higher_importance_ranks_first() -> None:
    items = [
        mk_item("low", importance=1, authority=5),
        mk_item("high", importance=5, authority=5),
    ]
    r = Ranker()
    top10, by_cat = r.rank(items)
    assert top10[0] == "high"


def test_doc_change_bonus() -> None:
    items = [
        mk_item("normal", importance=5, authority=10, category="google_updates"),
        mk_item("doc", importance=5, authority=10, category="google_docs_change", is_doc_change=True),
    ]
    top10, _ = Ranker().rank(items)
    assert top10[0] == "doc"


def test_top10_limits_to_ten() -> None:
    items = [mk_item(f"i{i}", importance=3, authority=5) for i in range(20)]
    top10, _ = Ranker().rank(items)
    assert len(top10) == 10


def test_categories_populated() -> None:
    items = [
        mk_item("a", 3, 5, category="google_updates"),
        mk_item("b", 4, 5, category="ai_models"),
        mk_item("c", 2, 5, category="google_updates"),
    ]
    _, by_cat = Ranker().rank(items)
    assert by_cat["google_updates"] == ["a", "c"]  # order by score desc
    assert by_cat["ai_models"] == ["b"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_ranker.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/ranker.py`**

```python
"""Ranker: scoring e top-10."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import NamedTuple

from osservatorio_seo.models import Item

CATEGORY_BONUS: dict[str, int] = {
    "google_updates": 5,
    "google_docs_change": 10,
    "ai_models": 3,
}


class RankedOutput(NamedTuple):
    top10: list[str]
    categories: dict[str, list[str]]


class Ranker:
    def rank(self, items: list[Item]) -> RankedOutput:
        scored = [(item, self._score(item)) for item in items]
        scored.sort(key=lambda t: t[1], reverse=True)

        top10 = [item.id for item, _ in scored[:10]]

        by_cat: dict[str, list[str]] = defaultdict(list)
        for item, _ in scored:
            by_cat[item.category].append(item.id)

        return RankedOutput(top10=top10, categories=dict(by_cat))

    @staticmethod
    def _score(item: Item) -> int:
        now = datetime.now(UTC)
        age_hours = (now - item.published_at).total_seconds() / 3600
        freshness = 5 if age_hours < 6 else (2 if age_hours < 24 else 0)
        doc_bonus = 20 if item.is_doc_change else 0
        cat_bonus = CATEGORY_BONUS.get(item.category, 0)
        return (
            item.importance * 10
            + item.source.authority
            + freshness
            + doc_bonus
            + cat_bonus
        )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ranker.py -v
```

Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/ranker.py tests/test_ranker.py
git commit -m "feat(ranker): scoring function with top-10 and categories"
```

---

## Task 13: Publisher

**Files:**
- Create: `src/osservatorio_seo/publisher.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_publisher.py
import json
from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo.models import Feed, FeedStats, Item, Source
from osservatorio_seo.publisher import Publisher


def mk_item(item_id: str) -> Item:
    return Item(
        id=item_id,
        title_original=item_id,
        title_it=item_id,
        summary_it="s",
        url=f"https://example.com/{item_id}",
        source=Source(
            id="s", name="S", authority=5, type="official",
            fetcher="rss", feed_url="https://x.com",
        ),
        category="google_updates",
        tags=[],
        importance=3,
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def mk_feed() -> Feed:
    return Feed(
        generated_at=datetime.now(UTC),
        generated_at_local=datetime.now(UTC),
        timezone="Europe/Rome",
        run_id="2026-04-11-0700",
        stats=FeedStats(
            sources_checked=1, sources_failed=0, items_collected=1,
            items_after_dedup=1, doc_changes_detected=0, ai_cost_eur=0.01,
        ),
        top10=["a"],
        categories={"google_updates": ["a"]},
        items=[mk_item("a")],
        doc_watcher_status=[],
        failed_sources=[],
    )


def test_publish_writes_feed_and_archive(tmp_path: Path) -> None:
    pub = Publisher(data_dir=tmp_path, archive_dir=tmp_path / "archive")
    feed = mk_feed()
    pub.publish(feed)
    feed_file = tmp_path / "feed.json"
    assert feed_file.exists()
    data = json.loads(feed_file.read_text())
    assert data["run_id"] == "2026-04-11-0700"
    archive_files = list((tmp_path / "archive").glob("*.json"))
    assert len(archive_files) == 1


def test_publish_copies_to_site_data(tmp_path: Path) -> None:
    site_dir = tmp_path / "site" / "data"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir,
    )
    pub.publish(mk_feed())
    assert (site_dir / "feed.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_publisher.py -v
```

Expected: FAIL (import error).

- [ ] **Step 3: Create `src/osservatorio_seo/publisher.py`**

```python
"""Publisher: scrive feed.json, archivi, e copia verso site/."""
from __future__ import annotations

import shutil
from pathlib import Path

from osservatorio_seo.models import Feed


class Publisher:
    def __init__(
        self,
        data_dir: Path,
        archive_dir: Path,
        site_data_dir: Path | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._archive_dir = Path(archive_dir)
        self._site_data_dir = Path(site_data_dir) if site_data_dir else None

    def publish(self, feed: Feed) -> Path:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._archive_dir.mkdir(parents=True, exist_ok=True)

        feed_json = feed.model_dump_json(indent=2)
        feed_file = self._data_dir / "feed.json"
        feed_file.write_text(feed_json, encoding="utf-8")

        date_str = feed.generated_at_local.strftime("%Y-%m-%d")
        archive_file = self._archive_dir / f"{date_str}.json"
        archive_file.write_text(feed_json, encoding="utf-8")

        if self._site_data_dir:
            self._site_data_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(feed_file, self._site_data_dir / "feed.json")

        return feed_file
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_publisher.py -v
```

Expected: 2 tests passed.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): write feed.json, archive, and site/data copy"
```

---

## Task 14: Pipeline Orchestrator + CLI

Unico punto in cui tutti i componenti vengono composti. Integration test con fixture.

**Files:**
- Create: `src/osservatorio_seo/pipeline.py`
- Create: `src/osservatorio_seo/cli.py`
- Create: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: Create `src/osservatorio_seo/pipeline.py`**

```python
"""Orchestratore: chiama fetcher → normalizer → summarizer → ranker → publisher."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from osservatorio_seo.config import (
    DocWatcherPage,
    Settings,
    load_doc_watcher,
    load_sources,
)
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.doc_watcher.watcher import DocChangeResult, DocWatcher
from osservatorio_seo.fetchers.base import Fetcher
from osservatorio_seo.fetchers.playwright_fetcher import PlaywrightFetcher
from osservatorio_seo.fetchers.rss import RSSFetcher
from osservatorio_seo.fetchers.scraper import ScraperFetcher
from osservatorio_seo.http_client import HttpClient
from osservatorio_seo.models import (
    DocChange,
    DocWatcherStatus,
    FailedSource,
    Feed,
    FeedStats,
    Item,
    RawItem,
    Source,
)
from osservatorio_seo.normalizer import Normalizer
from osservatorio_seo.publisher import Publisher
from osservatorio_seo.ranker import Ranker
from osservatorio_seo.summarizer import AISummary, DocChangeSummary, Summarizer

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        sources_path: Path,
        doc_watcher_path: Path,
        site_data_dir: Path | None = None,
    ) -> None:
        self._settings = settings
        self._sources_path = sources_path
        self._doc_watcher_path = doc_watcher_path
        self._site_data_dir = site_data_dir

    async def run(self) -> Feed:
        now_utc = datetime.now(UTC)
        now_local = now_utc.astimezone(ROME_TZ)
        run_id = now_local.strftime("%Y-%m-%d-%H%M")

        sources = load_sources(self._sources_path)
        doc_pages = load_doc_watcher(self._doc_watcher_path)

        async with HttpClient(
            max_concurrent_per_host=self._settings.max_concurrent_per_host,
            timeout_s=self._settings.request_timeout_s,
        ) as http:
            fetchers: dict[str, Fetcher] = {
                "rss": RSSFetcher(http),
                "scraper": ScraperFetcher(http),
                "playwright": PlaywrightFetcher(self._settings.playwright_timeout_s),
            }
            raw_items, failed_sources = await self._fetch_all(sources, fetchers)

            state = StateStore(self._settings.state_dir)
            doc_watcher = DocWatcher(http=http, state=state)
            doc_results, doc_statuses = await self._check_doc_pages(doc_pages, doc_watcher)

        normalizer = Normalizer()
        sources_by_id = {s.id: s for s in sources}
        normalized = normalizer.normalize(raw_items, sources_by_id)

        summarizer = Summarizer(
            api_key=self._settings.openrouter_api_key,
            primary_model=self._settings.summarizer_model,
            fallback_models=self._settings.fallback_models,
        )
        items, ai_cost = await self._summarize_all(normalized, sources_by_id, summarizer)

        doc_items, doc_cost = await self._summarize_doc_changes(
            doc_results, doc_pages, summarizer
        )
        items.extend(doc_items)
        ai_cost += doc_cost

        ranker = Ranker()
        ranked = ranker.rank(items)

        stats = FeedStats(
            sources_checked=len(sources),
            sources_failed=len(failed_sources),
            items_collected=len(raw_items),
            items_after_dedup=len(normalized),
            doc_changes_detected=sum(1 for r in doc_results if r.changed),
            ai_cost_eur=round(ai_cost, 4),
        )
        feed = Feed(
            generated_at=now_utc,
            generated_at_local=now_local,
            timezone="Europe/Rome",
            run_id=run_id,
            stats=stats,
            top10=ranked.top10,
            categories=ranked.categories,
            items=items,
            doc_watcher_status=doc_statuses,
            failed_sources=failed_sources,
        )

        publisher = Publisher(
            data_dir=self._settings.data_dir,
            archive_dir=self._settings.archive_dir,
            site_data_dir=self._site_data_dir,
        )
        publisher.publish(feed)
        return feed

    async def _fetch_all(
        self, sources: list[Source], fetchers: dict[str, Fetcher]
    ) -> tuple[list[RawItem], list[FailedSource]]:
        raw_items: list[RawItem] = []
        failed: list[FailedSource] = []

        async def fetch_one(src: Source) -> None:
            fetcher = fetchers.get(src.fetcher)
            if fetcher is None:
                failed.append(FailedSource(id=src.id, error=f"no fetcher for {src.fetcher}"))
                return
            try:
                items = await asyncio.wait_for(
                    fetcher.fetch(src),
                    timeout=self._settings.fetcher_timeout_s,
                )
                raw_items.extend(items)
            except Exception as e:  # noqa: BLE001
                logger.warning("source %s failed: %s", src.id, e)
                failed.append(FailedSource(id=src.id, error=type(e).__name__ + ": " + str(e)[:200]))

        await asyncio.gather(*(fetch_one(s) for s in sources))
        return raw_items, failed

    async def _check_doc_pages(
        self, pages: list[DocWatcherPage], watcher: DocWatcher
    ) -> tuple[list[DocChangeResult], list[DocWatcherStatus]]:
        results: list[DocChangeResult] = []
        statuses: list[DocWatcherStatus] = []
        for page in pages:
            try:
                r = await watcher.check(page)
                results.append(r)
                statuses.append(
                    DocWatcherStatus(
                        page_id=page.id, last_checked=r.checked_at, changed=r.changed
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("doc page %s failed: %s", page.id, e)
        return results, statuses

    async def _summarize_all(
        self,
        normalized: list[RawItem],
        sources_by_id: dict[str, Source],
        summarizer: Summarizer,
    ) -> tuple[list[Item], float]:
        items: list[Item] = []
        total_cost = 0.0
        import hashlib

        for idx, raw in enumerate(sorted(normalized, key=lambda r: r.published_at), start=1):
            source = sources_by_id[raw.source_id]
            try:
                summary = await summarizer.summarize_item(raw, source)
            except Exception as e:  # noqa: BLE001
                logger.warning("summarize failed for %s: %s", raw.url, e)
                continue
            date_str = datetime.now(ROME_TZ).strftime("%Y-%m-%d")
            items.append(
                Item(
                    id=f"item_{date_str}_{idx:03d}",
                    title_original=raw.title,
                    title_it=summary.title_it,
                    summary_it=summary.summary_it,
                    url=raw.url,
                    source=source,
                    category=summary.category,
                    tags=summary.tags,
                    importance=summary.importance,
                    published_at=raw.published_at,
                    fetched_at=datetime.now(UTC),
                    is_doc_change=False,
                    language_original=raw.language_original,
                    summarizer_model=summary.model_used,
                    raw_hash="sha256:" + hashlib.sha256(raw.content.encode()).hexdigest()[:16],
                )
            )
            total_cost += summary.cost_eur
        return items, total_cost

    async def _summarize_doc_changes(
        self,
        results: list[DocChangeResult],
        pages: list[DocWatcherPage],
        summarizer: Summarizer,
    ) -> tuple[list[Item], float]:
        items: list[Item] = []
        total_cost = 0.0
        pages_by_id = {p.id: p for p in pages}

        for idx, r in enumerate(results, start=1):
            if not r.changed:
                continue
            page = pages_by_id[r.page_id]
            try:
                summary = await summarizer.summarize_doc_change(
                    page_name=page.name, page_url=page.url, diff=r.diff
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("doc change summary failed for %s: %s", page.id, e)
                continue
            date_str = datetime.now(ROME_TZ).strftime("%Y-%m-%d")
            items.append(
                Item(
                    id=f"doc_{date_str}_{idx:03d}",
                    title_original=page.name,
                    title_it=summary.title_it,
                    summary_it=summary.summary_it,
                    url=page.url,
                    source=Source(
                        id="doc_watcher",
                        name="OsservatorioSEO Doc Watcher",
                        authority=10,
                        type="doc_change",
                        fetcher="rss",
                    ),
                    category=page.category,
                    tags=summary.tags,
                    importance=summary.importance,
                    published_at=r.checked_at,
                    fetched_at=r.checked_at,
                    is_doc_change=True,
                    doc_change=DocChange(
                        page_id=page.id,
                        previous_hash=r.previous_hash or "",
                        current_hash=r.current_hash,
                        lines_added=r.lines_added,
                        lines_removed=r.lines_removed,
                    ),
                    summarizer_model=summary.model_used,
                    raw_hash=r.current_hash,
                )
            )
            total_cost += summary.cost_eur
        return items, total_cost
```

- [ ] **Step 2: Create `src/osservatorio_seo/cli.py`**

```python
"""CLI entrypoint."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from osservatorio_seo.config import load_settings
from osservatorio_seo.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="osservatorio-seo")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Run the daily pipeline")
    refresh.add_argument("--sources", type=Path, default=Path("config/sources.yml"))
    refresh.add_argument("--doc-watcher", type=Path, default=Path("config/doc_watcher.yml"))
    refresh.add_argument("--site-data", type=Path, default=Path("site/data"))

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "refresh":
        settings = load_settings()
        pipeline = Pipeline(
            settings=settings,
            sources_path=args.sources,
            doc_watcher_path=args.doc_watcher,
            site_data_dir=args.site_data,
        )
        feed = asyncio.run(pipeline.run())
        print(f"OK — {len(feed.items)} items, top10={len(feed.top10)}, cost={feed.stats.ai_cost_eur}€")
        sys.exit(0)
```

- [ ] **Step 3: Create `tests/fixtures/sources.smoke.yml`**

Singola fonte RSS, usata per il test end-to-end del pipeline (evita chiamate non moccate).

```yaml
sources:
  - id: google_search_central
    name: "Google Search Central Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://developers.google.com/search/blog/rss
    category_hint: google_updates
    enabled: true
```

- [ ] **Step 4: Write smoke test for pipeline**

Il test genera un RSS XML con date dinamiche (now) per evitare che il Normalizer filtri gli item come "troppo vecchi" (>48h).

```python
# tests/test_pipeline_smoke.py
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from osservatorio_seo.config import Settings
from osservatorio_seo.pipeline import Pipeline
from osservatorio_seo.summarizer import AISummary


@pytest.fixture
def smoke_settings(tmp_path: Path) -> Settings:
    return Settings(
        openrouter_api_key="sk-test",
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        state_dir=tmp_path / "data" / "state" / "doc_watcher",
    )


def build_rss_with_current_dates() -> str:
    now_rfc = format_datetime(datetime.now(UTC))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Smoke</title>
  <link>https://example.com</link>
  <description>Smoke</description>
  <item>
    <title>Core update rollout finished</title>
    <link>https://example.com/core-update</link>
    <description>Detailed content about the March 2026 core update rollout finishing today with notable impact.</description>
    <pubDate>{now_rfc}</pubDate>
  </item>
</channel></rss>"""


async def test_pipeline_end_to_end(
    smoke_settings: Settings,
    fixtures_dir: Path,
    tmp_path: Path,
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://developers.google.com/search/blog/rss",
        text=build_rss_with_current_dates(),
    )
    httpx_mock.add_response(
        url="https://developers.google.com/search/docs/essentials/spam-policies",
        text="<html><body><main><article>Stable content for doc watcher first run.</article></main></body></html>",
    )

    fake_summary = AISummary(
        title_it="Titolo IT di prova",
        summary_it="Riassunto in italiano di almeno venti caratteri.",
        category="google_updates",
        tags=["core_update"],
        importance=5,
        model_used="google/gemini-2.0-flash",
        cost_eur=0.001,
    )

    pipeline = Pipeline(
        settings=smoke_settings,
        sources_path=fixtures_dir / "sources.smoke.yml",
        doc_watcher_path=fixtures_dir / "doc_watcher.test.yml",
        site_data_dir=tmp_path / "site" / "data",
    )

    with patch(
        "osservatorio_seo.summarizer.Summarizer.summarize_item",
        new=AsyncMock(return_value=fake_summary),
    ):
        feed = await pipeline.run()

    assert feed.stats.sources_checked == 1
    assert feed.stats.items_collected >= 1
    assert (smoke_settings.data_dir / "feed.json").exists()
    assert (tmp_path / "site" / "data" / "feed.json").exists()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_pipeline_smoke.py -v
```

Expected: test passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/pipeline.py src/osservatorio_seo/cli.py tests/test_pipeline_smoke.py tests/fixtures/sources.smoke.yml
git commit -m "feat(pipeline): end-to-end orchestrator and CLI"
```

---

## Task 15: Initial Production Configs

**Files:**
- Create: `config/sources.yml`
- Create: `config/doc_watcher.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `config/sources.yml`**

```yaml
# Fonti v1 di OsservatorioSEO.
# authority: 1-10 (10 = fonte ufficiale, 9 = media di riferimento, etc.)
# fetcher: rss | scraper | playwright

sources:
  # === UFFICIALI ===
  - id: google_search_central_blog
    name: "Google Search Central Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://developers.google.com/search/blog/rss
    category_hint: google_updates
    enabled: true

  - id: google_search_status_dashboard
    name: "Google Search Status Dashboard"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://status.search.google.com/incidents.rss
    category_hint: google_updates
    enabled: true

  - id: openai_blog
    name: "OpenAI Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://openai.com/blog/rss.xml
    category_hint: ai_models
    enabled: true

  - id: anthropic_news
    name: "Anthropic News"
    authority: 10
    type: official
    fetcher: scraper
    target_url: https://www.anthropic.com/news
    selectors:
      article: "a[href*='/news/']"
      title: "h3, h2"
      link: ""
    category_hint: ai_models
    enabled: true

  - id: google_deepmind_blog
    name: "Google DeepMind Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://deepmind.google/blog/rss.xml
    category_hint: ai_models
    enabled: true

  - id: bing_webmaster_blog
    name: "Bing Webmaster Blog"
    authority: 9
    type: official
    fetcher: rss
    feed_url: https://blogs.bing.com/webmaster/feed
    category_hint: technical_seo
    enabled: true

  # === MEDIA DI SETTORE ===
  - id: search_engine_land
    name: "Search Engine Land"
    authority: 9
    type: media
    fetcher: rss
    feed_url: https://searchengineland.com/feed
    category_hint: industry_news
    enabled: true

  - id: search_engine_journal
    name: "Search Engine Journal"
    authority: 8
    type: media
    fetcher: rss
    feed_url: https://www.searchenginejournal.com/feed/
    category_hint: industry_news
    enabled: true

  - id: search_engine_roundtable
    name: "Search Engine Roundtable"
    authority: 9
    type: media
    fetcher: rss
    feed_url: https://www.seroundtable.com/feed.xml
    category_hint: google_updates
    enabled: true

  # === VOCI INDIPENDENTI ===
  - id: growth_memo_kevin_indig
    name: "Growth Memo (Kevin Indig)"
    authority: 9
    type: independent
    fetcher: rss
    feed_url: https://www.growth-memo.com/feed
    category_hint: ai_overviews_llm_seo
    enabled: true

  - id: glenn_gabe_hifpm
    name: "Glenn Gabe — HIFPM"
    authority: 9
    type: independent
    fetcher: rss
    feed_url: https://www.gsqi.com/marketing-blog/feed/
    category_hint: google_updates
    enabled: true

  - id: ipullrank_blog
    name: "iPullRank Blog (Mike King)"
    authority: 8
    type: independent
    fetcher: rss
    feed_url: https://ipullrank.com/feed
    category_hint: ai_overviews_llm_seo
    enabled: true

  # === TOOL VENDOR ===
  - id: ahrefs_blog
    name: "Ahrefs Blog"
    authority: 8
    type: tool_vendor
    fetcher: rss
    feed_url: https://ahrefs.com/blog/feed/
    category_hint: tools_platforms
    enabled: true

  - id: semrush_blog
    name: "Semrush Blog"
    authority: 7
    type: tool_vendor
    fetcher: rss
    feed_url: https://www.semrush.com/blog/feed/
    category_hint: tools_platforms
    enabled: true

  - id: sistrix_blog
    name: "Sistrix Blog"
    authority: 9
    type: tool_vendor
    fetcher: rss
    feed_url: https://www.sistrix.com/blog/feed/
    category_hint: google_updates
    enabled: true

  - id: moz_blog
    name: "Moz Blog"
    authority: 8
    type: tool_vendor
    fetcher: rss
    feed_url: https://moz.com/posts/rss/blog
    category_hint: technical_seo
    enabled: true

  # === AI LABS ===
  - id: meta_ai_blog
    name: "Meta AI Blog"
    authority: 9
    type: official
    fetcher: rss
    feed_url: https://ai.meta.com/blog/rss
    category_hint: ai_models
    enabled: true

  - id: mistral_ai_blog
    name: "Mistral AI News"
    authority: 8
    type: official
    fetcher: scraper
    target_url: https://mistral.ai/news
    selectors:
      article: "article, a[href*='/news/']"
      title: "h2, h3"
      link: ""
    category_hint: ai_models
    enabled: true

  - id: perplexity_blog
    name: "Perplexity Blog"
    authority: 8
    type: official
    fetcher: scraper
    target_url: https://www.perplexity.ai/hub
    selectors:
      article: "a[href*='/hub/']"
      title: "h2, h3"
      link: ""
    category_hint: ai_overviews_llm_seo
    enabled: true

  - id: huggingface_blog
    name: "Hugging Face Blog"
    authority: 8
    type: official
    fetcher: rss
    feed_url: https://huggingface.co/blog/feed.xml
    category_hint: ai_models
    enabled: true

  # === WEB / PLATFORM ===
  - id: web_dev
    name: "web.dev"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://web.dev/feed.xml
    category_hint: technical_seo
    enabled: true

  - id: chrome_developers_blog
    name: "Chrome Developers Blog"
    authority: 10
    type: official
    fetcher: rss
    feed_url: https://developer.chrome.com/feeds/blog.xml
    category_hint: technical_seo
    enabled: true

  # === SOCIAL (playwright) ===
  - id: searchliaison_x
    name: "Danny Sullivan (SearchLiaison) on X"
    authority: 10
    type: social
    fetcher: playwright
    target_url: https://x.com/searchliaison
    selectors:
      post: "article[data-testid='tweet']"
      text: "div[data-testid='tweetText']"
      link: "a[href*='/status/']"
    category_hint: google_updates
    enabled: true
```

- [ ] **Step 2: Create `config/doc_watcher.yml`**

```yaml
# Pagine sorvegliate dal Doc Watcher.
# Quando il contenuto cambia (ignoring whitespace cosmetico), genera un item
# nel feed con badge "⚠️ Google ha aggiornato ..." e summary del diff.

pages:
  - id: google_spam_policies
    name: "Google Spam Policies"
    url: https://developers.google.com/search/docs/essentials/spam-policies
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 5

  - id: google_helpful_content
    name: "Google Helpful Content"
    url: https://developers.google.com/search/docs/fundamentals/creating-helpful-content
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 5

  - id: google_quality_rater_guidelines
    name: "Google Quality Rater Guidelines (PDF)"
    url: https://services.google.com/fh/files/misc/hsw-sqevaluatorguidelines.pdf
    type: pdf
    category: google_docs_change
    importance: 5

  - id: google_ai_features_guidance
    name: "Google AI Features SEO Guidance"
    url: https://developers.google.com/search/docs/appearance/ai-features
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 4

  - id: googlebot_docs
    name: "Googlebot Documentation"
    url: https://developers.google.com/search/docs/crawling-indexing/googlebot
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 3

  - id: google_crawlers_overview
    name: "Overview of Google Crawlers"
    url: https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 4

  - id: structured_data_docs
    name: "Google Structured Data Supported"
    url: https://developers.google.com/search/docs/appearance/structured-data
    selector: "main article, main"
    type: html
    category: google_docs_change
    importance: 3

  - id: openai_usage_policies
    name: "OpenAI Usage Policies"
    url: https://openai.com/policies/usage-policies/
    selector: "main"
    type: html
    category: google_docs_change
    importance: 3

  - id: anthropic_usage_policies
    name: "Anthropic Usage Policy"
    url: https://www.anthropic.com/legal/aup
    selector: "main"
    type: html
    category: google_docs_change
    importance: 3
```

- [ ] **Step 3: Create `.env.example`**

```
# Copy to .env and fill in your real API key.
# OpenRouter: https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- [ ] **Step 4: Commit**

```bash
git add config/ .env.example
git commit -m "chore(config): initial sources.yml and doc_watcher.yml for v1"
```

---

## Task 16: Frontend (HTML + CSS + JS)

**Files:**
- Create: `site/index.html`
- Create: `site/styles.css`
- Create: `site/app.js`

- [ ] **Step 1: Create `site/index.html`**

```html
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>OsservatorioSEO — News giornaliere su SEO e AI</title>
<meta name="description" content="Hub giornaliero di notizie SEO e AI aggiornato alle 07:00. Raccoglie fonti autorevoli, riassume in italiano, e rileva modifiche alle policy Google." />
<link rel="canonical" href="/" />
<meta property="og:title" content="OsservatorioSEO" />
<meta property="og:description" content="News giornaliere SEO e AI, riassunte dall'AI." />
<meta property="og:type" content="website" />
<link rel="stylesheet" href="styles.css" />
</head>
<body>
<header>
  <div class="container">
    <h1>OsservatorioSEO</h1>
    <p class="tagline">News giornaliere SEO e AI · aggiornato ogni mattina alle 07:00</p>
    <p class="meta" id="meta"></p>
  </div>
</header>

<main class="container">
  <input type="search" id="search" placeholder="Cerca nei titoli o nei riassunti..." />

  <section id="top10-section">
    <h2>🔥 Top 10 del giorno</h2>
    <div id="top10"></div>
  </section>

  <section id="categories-section">
    <h2>📚 Tutto per categoria</h2>
    <div id="categories"></div>
  </section>

  <section id="failed" hidden>
    <h2>⚠️ Fonti con problemi</h2>
    <ul id="failed-list"></ul>
  </section>
</main>

<footer>
  <div class="container">
    <p>Dati: <a href="data/feed.json">feed.json</a> · <a href="https://github.com/">GitHub</a></p>
  </div>
</footer>

<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `site/styles.css`**

```css
:root {
  --bg: #fafafa;
  --fg: #1a1a1a;
  --muted: #666;
  --card-bg: #fff;
  --card-border: #e0e0e0;
  --accent: #0066cc;
  --warn-bg: #fff8e1;
  --warn-border: #ffc107;
  --star: #f5a623;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f0f0f;
    --fg: #e0e0e0;
    --muted: #888;
    --card-bg: #1a1a1a;
    --card-border: #333;
    --accent: #66b3ff;
    --warn-bg: #2a1f00;
    --warn-border: #ffc107;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--fg);
  line-height: 1.5;
}
.container { max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }
header { border-bottom: 1px solid var(--card-border); }
header h1 { margin: 0 0 0.25rem 0; font-size: 1.8rem; }
.tagline { margin: 0; color: var(--muted); font-size: 0.95rem; }
.meta { margin: 0.5rem 0 0 0; color: var(--muted); font-size: 0.85rem; }
#search {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  background: var(--card-bg);
  color: var(--fg);
  margin: 1rem 0;
}
h2 { margin: 2rem 0 1rem 0; font-size: 1.4rem; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 1.25rem;
  margin-bottom: 1rem;
}
.card.doc-change {
  background: var(--warn-bg);
  border-color: var(--warn-border);
}
.card h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; }
.card .source-line { color: var(--muted); font-size: 0.85rem; margin: 0 0 0.75rem 0; }
.card .stars { color: var(--star); }
.card .summary { margin: 0 0 0.75rem 0; }
.card a.readmore {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.9rem;
}
.card a.readmore:hover { text-decoration: underline; }
details {
  margin-bottom: 0.75rem;
  border: 1px solid var(--card-border);
  border-radius: 8px;
  padding: 0.5rem 1rem;
  background: var(--card-bg);
}
details summary {
  cursor: pointer;
  font-weight: 600;
  padding: 0.5rem 0;
}
details[open] summary { margin-bottom: 0.75rem; }
footer {
  border-top: 1px solid var(--card-border);
  margin-top: 3rem;
  padding: 1.5rem 0;
  color: var(--muted);
  font-size: 0.85rem;
}
footer a { color: var(--accent); }
.tag {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  margin-right: 0.25rem;
  background: var(--card-border);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--muted);
}
```

- [ ] **Step 3: Create `site/app.js`**

```javascript
(async function () {
  const FEED_URL = "data/feed.json";

  const CATEGORY_LABELS = {
    google_updates: "Google Updates",
    google_docs_change: "Google Docs Change ⚠️",
    ai_models: "AI Models",
    ai_overviews_llm_seo: "AI Overviews & LLM SEO",
    technical_seo: "Technical SEO",
    content_eeat: "Content & E-E-A-T",
    tools_platforms: "Tools & Platforms",
    industry_news: "Industry News",
  };

  let feed = null;

  try {
    const resp = await fetch(FEED_URL, { cache: "no-cache" });
    if (!resp.ok) throw new Error("feed fetch failed: " + resp.status);
    feed = await resp.json();
  } catch (e) {
    document.querySelector("main").innerHTML =
      '<p style="color: #cc0000;">Impossibile caricare il feed: ' + e.message + "</p>";
    return;
  }

  renderMeta(feed);
  renderTop10(feed);
  renderCategories(feed);
  renderFailed(feed);
  setupSearch(feed);

  const params = new URLSearchParams(window.location.search);
  const tag = params.get("tag");
  if (tag) applyTagFilter(feed, tag);
})();

function renderMeta(feed) {
  const local = new Date(feed.generated_at_local);
  const dateStr = local.toLocaleDateString("it-IT", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const timeStr = local.toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const s = feed.stats;
  document.getElementById("meta").textContent =
    `${dateStr}, ${timeStr} · ${s.sources_checked} fonti · ${s.items_after_dedup} notizie · €${s.ai_cost_eur.toFixed(3)} costo AI`;
}

function renderCard(item) {
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  const srcType = item.is_doc_change ? "doc-change" : "";
  const tags = (item.tags || []).map((t) => `<span class="tag">${escape(t)}</span>`).join("");
  return `
    <div class="card ${srcType}" data-item-id="${escape(item.id)}" data-tags="${(item.tags || []).join(",")}">
      <h3>${escape(item.title_it)}</h3>
      <p class="source-line">${escape(item.source.name)} · <span class="stars">${stars}</span></p>
      <p class="summary">${escape(item.summary_it)}</p>
      <p>${tags}</p>
      <a class="readmore" href="${escape(item.url)}" target="_blank" rel="noopener">→ ${hostname(item.url)}</a>
    </div>
  `;
}

function renderTop10(feed) {
  const container = document.getElementById("top10");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  container.innerHTML = feed.top10.map((id) => renderCard(byId[id])).filter(Boolean).join("");
}

function renderCategories(feed) {
  const container = document.getElementById("categories");
  const byId = Object.fromEntries(feed.items.map((i) => [i.id, i]));
  const catContainers = Object.entries(feed.categories).map(([catId, ids]) => {
    const label = CATEGORY_LABELS[catId] || catId;
    const cards = ids.map((id) => renderCard(byId[id])).filter(Boolean).join("");
    return `
      <details>
        <summary>${label} (${ids.length})</summary>
        ${cards}
      </details>
    `;
  });
  container.innerHTML = catContainers.join("");
}

function renderFailed(feed) {
  if (!feed.failed_sources || feed.failed_sources.length === 0) return;
  const section = document.getElementById("failed");
  section.hidden = false;
  const list = document.getElementById("failed-list");
  list.innerHTML = feed.failed_sources
    .map((f) => `<li><code>${escape(f.id)}</code>: ${escape(f.error)}</li>`)
    .join("");
}

function setupSearch(feed) {
  const input = document.getElementById("search");
  input.addEventListener("input", () => {
    const q = input.value.toLowerCase().trim();
    document.querySelectorAll(".card").forEach((card) => {
      const text = card.textContent.toLowerCase();
      card.style.display = !q || text.includes(q) ? "" : "none";
    });
  });
}

function applyTagFilter(feed, tag) {
  document.querySelectorAll(".card").forEach((card) => {
    const tags = (card.dataset.tags || "").split(",");
    card.style.display = tags.includes(tag) ? "" : "none";
  });
}

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function hostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}
```

- [ ] **Step 4: Smoke test manuale frontend**

Genera un feed.json fittizio con il CLI in modalità dry-run non è previsto in v1, quindi crea un feed.json minimale a mano per testare l'HTML:

```bash
mkdir -p site/data
cat > site/data/feed.json <<'EOF'
{
  "schema_version": "1.0",
  "generated_at": "2026-04-11T05:00:00Z",
  "generated_at_local": "2026-04-11T07:00:00+02:00",
  "timezone": "Europe/Rome",
  "run_id": "2026-04-11-0700",
  "stats": {"sources_checked": 3, "sources_failed": 0, "items_collected": 2, "items_after_dedup": 2, "doc_changes_detected": 0, "ai_cost_eur": 0.012},
  "top10": ["a", "b"],
  "categories": {"google_updates": ["a"], "ai_models": ["b"]},
  "items": [
    {"id": "a", "title_original": "Core update done", "title_it": "Core update completato", "summary_it": "Google ha completato il rollout del core update.", "url": "https://example.com/a", "source": {"id": "g", "name": "Google Search Central", "authority": 10, "type": "official", "fetcher": "rss", "enabled": true}, "category": "google_updates", "tags": ["core_update"], "importance": 5, "published_at": "2026-04-11T03:00:00Z", "fetched_at": "2026-04-11T05:00:00Z", "is_doc_change": false, "language_original": "en", "summarizer_model": "google/gemini-2.0-flash", "raw_hash": "sha256:abc"},
    {"id": "b", "title_original": "New model", "title_it": "Nuovo modello AI", "summary_it": "Anthropic ha rilasciato un nuovo modello.", "url": "https://example.com/b", "source": {"id": "a", "name": "Anthropic News", "authority": 10, "type": "official", "fetcher": "scraper", "enabled": true}, "category": "ai_models", "tags": ["claude"], "importance": 4, "published_at": "2026-04-11T04:00:00Z", "fetched_at": "2026-04-11T05:00:00Z", "is_doc_change": false, "language_original": "en", "summarizer_model": "google/gemini-2.0-flash", "raw_hash": "sha256:def"}
  ],
  "doc_watcher_status": [],
  "failed_sources": []
}
EOF

# Serve static files
python -m http.server -d site 8080
```

Apri http://localhost:8080 nel browser e verifica:
- Header con data, ora, stats visibili
- Top 10 mostra le 2 card
- Categorie collassabili funzionano
- Dark mode segue le preferenze di sistema
- La search filtra le card in tempo reale

Poi rimuovi il feed.json di test:
```bash
rm site/data/feed.json
```

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat(frontend): static HTML + vanilla JS card renderer"
```

---

## Task 17: GitHub Actions — Daily Refresh Workflow

**Files:**
- Create: `.github/workflows/daily-refresh.yml`

- [ ] **Step 1: Create `.github/workflows/daily-refresh.yml`**

```yaml
name: Daily Refresh

on:
  schedule:
    # GitHub Actions cron è UTC. 07:00 Europe/Rome = 05:00 UTC (DST) / 06:00 UTC (winter).
    # Scheduliamo entrambi e lo step "Check local time" salta il run sbagliato.
    - cron: "0 5 * * *"
    - cron: "0 6 * * *"
  workflow_dispatch: {}

concurrency:
  group: daily-refresh
  cancel-in-progress: false

jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
      issues: write
    steps:
      - name: Check local time
        id: time_check
        run: |
          HOUR=$(TZ=Europe/Rome date +%H)
          echo "current Rome hour: $HOUR"
          if [ "$HOUR" != "07" ] && [ "${{ github.event_name }}" != "workflow_dispatch" ]; then
            echo "skip=true" >> $GITHUB_OUTPUT
          fi

      - name: Checkout
        if: steps.time_check.outputs.skip != 'true'
        uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Setup Python
        if: steps.time_check.outputs.skip != 'true'
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        if: steps.time_check.outputs.skip != 'true'
        run: |
          python -m pip install --upgrade pip
          pip install -e .
          python -m playwright install --with-deps chromium

      - name: Run refresh
        if: steps.time_check.outputs.skip != 'true'
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          TZ: Europe/Rome
        run: python -m osservatorio_seo refresh

      - name: Commit and push
        if: steps.time_check.outputs.skip != 'true'
        run: |
          git config user.name "osservatorioseo-bot"
          git config user.email "bot@osservatorioseo.local"
          git add data/ site/data/
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore(feed): refresh $(TZ=Europe/Rome date +%Y-%m-%d)"
            git push
          fi

      - name: Open issue on failure
        if: failure() && steps.time_check.outputs.skip != 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const date = new Date().toISOString().split('T')[0];
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[osservatorioseo] Workflow failed ${date}`,
              body: `Daily refresh failed on ${date}.\n\nSee run: ${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`,
              labels: ['bug', 'automated']
            });
```

- [ ] **Step 2: Validate YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/daily-refresh.yml'))" && echo "OK"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily-refresh.yml
git commit -m "ci: daily refresh workflow with DST handling and failure alerts"
```

---

## Task 18: GitHub Actions — CI + Smoke Workflows

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/smoke-real-sources.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest -v
```

- [ ] **Step 2: Create `.github/workflows/smoke-real-sources.yml`**

```yaml
name: Smoke Real Sources

on:
  schedule:
    - cron: "0 8 * * 1"  # Monday 08:00 UTC
  workflow_dispatch: {}

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -e .
      - name: Probe 3 real RSS sources
        run: |
          python <<'PY'
          import asyncio
          from pathlib import Path
          from osservatorio_seo.config import load_sources
          from osservatorio_seo.fetchers.rss import RSSFetcher
          from osservatorio_seo.http_client import HttpClient

          CANARY_IDS = {"google_search_central_blog", "search_engine_roundtable", "web_dev"}

          async def main():
              sources = [s for s in load_sources(Path("config/sources.yml")) if s.id in CANARY_IDS]
              assert sources, "no canary sources found"
              async with HttpClient() as client:
                  fetcher = RSSFetcher(client)
                  for src in sources:
                      items = await fetcher.fetch(src)
                      print(f"{src.id}: {len(items)} items")
                      assert len(items) > 0, f"{src.id} returned 0 items!"

          asyncio.run(main())
          PY
      - name: Open issue on failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            const date = new Date().toISOString().split('T')[0];
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `[osservatorioseo] Canary smoke test failed ${date}`,
              body: `Weekly smoke test against real sources failed. One or more parsers may have broken due to upstream HTML changes.\n\nSee run: ${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`,
              labels: ['bug', 'parser', 'automated']
            });
```

- [ ] **Step 3: Validate both YAMLs**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/smoke-real-sources.yml'))" && echo "OK"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml .github/workflows/smoke-real-sources.yml
git commit -m "ci: test workflow and weekly canary against real sources"
```

---

## Task 19: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

````markdown
# OsservatorioSEO

Hub giornaliero di notizie **SEO e AI** da fonti autorevoli. Ogni mattina alle 07:00 (Europe/Rome) un workflow GitHub Actions recupera notizie da blog ufficiali (Google, OpenAI, Anthropic), testate di settore (Search Engine Land, Journal, Roundtable), e voci indipendenti. L'AI (via OpenRouter → Gemini 2.0 Flash) le riassume in italiano, e il **Doc Watcher** segnala quando Google aggiorna silenziosamente una pagina di documentazione critica.

L'output è un `feed.json` pubblico consumabile anche da altri tool AI, e una pagina web statica servita da Cloudflare Pages.

## Feature principali

- 🔄 **Aggiornamento automatico** ogni mattina alle 07:00 Europe/Rome
- 🌐 **Fonti multi-tipo**: RSS, HTML scraping, Playwright per anti-bot
- 🇮🇹 **Riassunti in italiano** tono asciutto, no hype
- ⚠️ **Doc Watcher**: rileva modifiche a pagine Google (Spam Policies, Helpful Content, QRG PDF, ecc.)
- 📊 **Top 10 del giorno** + tutto categorizzato (8 categorie)
- 💰 **Costo < €3/mese** grazie a GitHub Actions gratis + Gemini 2.0 Flash economico
- 📁 **Zero database**: tutto è committato in git, archivio storico versionato gratis
- 🔁 **Resiliente**: graceful degradation, issue automatiche su failure, canary settimanale

## Architettura

```
GitHub Actions (cron 07:00) → Python pipeline → feed.json → Cloudflare Pages
```

Pipeline:
1. **Fetcher** — RSS/Scraper/Playwright paralleli, User-Agent browser-like, rate limit per host
2. **Doc Watcher** — fetch pagine, hash+diff, rileva cambiamenti significativi
3. **Normalizer** — canonicalizza URL, dedup per URL + fuzzy title
4. **Summarizer** — OpenRouter con fallback chain (Gemini Flash → Claude Haiku → GPT-5 Mini)
5. **Ranker** — scoring per top-10 e raggruppamento categorie
6. **Publisher** — scrive `data/feed.json`, archivio giornaliero, commit+push

## Quick start locale

```bash
git clone https://github.com/<your-user>/osservatorioseo.git
cd osservatorioseo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install --with-deps chromium

cp .env.example .env
# modifica .env con la tua API key OpenRouter

export $(cat .env | xargs)
python -m osservatorio_seo refresh
```

## Deploy

### 1. GitHub
- Fork/clona il repo
- Aggiungi secret `OPENROUTER_API_KEY` in Settings → Secrets and variables → Actions
- Il workflow `daily-refresh.yml` partirà automaticamente alle 07:00 Rome

### 2. Cloudflare Pages
- Vai su Cloudflare Pages → Create a project → Connect to GitHub
- Build output directory: `site/`
- Build command: (vuoto)
- Deploy

## Testing

```bash
pytest -v
ruff check .
ruff format --check .
```

## Configurazione

- `config/sources.yml` — lista fonti (aggiungi/rimuovi/disabilita)
- `config/doc_watcher.yml` — pagine sorvegliate

## Struttura progetto

```
osservatorioseo/
├── src/osservatorio_seo/   # codice Python
├── config/                 # YAML config
├── data/                   # feed.json + archive + state (committato dal bot)
├── site/                   # frontend statico
├── tests/                  # pytest suite
└── .github/workflows/      # CI/CD
```

## Roadmap

- [ ] Chatbot interattivo che legge il feed al volo
- [ ] Newsletter email giornaliera
- [ ] Notifiche Telegram/Slack sui doc changes
- [ ] Espansione Doc Watcher a Bing, Perplexity, Meta AI
- [ ] RSS output del feed stesso

## Contenuti e policy

OsservatorioSEO pubblica solo **titolo + nostro riassunto + link alla fonte**. Nessun testo integrale, massima attribuzione, traffico mandato indietro alle fonti. Se sei titolare di una fonte e vuoi essere rimosso, apri un'issue — rispondiamo entro 24h.

## License

MIT — vedi `LICENSE`.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with overview, setup, and deploy instructions"
```

---

## Final Verification

- [ ] **Step 1: Run full test suite**

```bash
source .venv/bin/activate
ruff check .
ruff format --check .
pytest -v
```

Expected: tutto verde.

- [ ] **Step 2: End-to-end manual run (richiede OPENROUTER_API_KEY)**

```bash
export OPENROUTER_API_KEY=sk-or-v1-xxxxx
python -m osservatorio_seo refresh
```

Expected:
- Nessuna eccezione non gestita
- File `data/feed.json` creato, contiene `items` > 0
- File `data/archive/YYYY-MM-DD.json` creato
- File `site/data/feed.json` creato (copia)
- Directory `data/state/doc_watcher/` contiene 9 file `.hash` + 9 file `.txt` (prima esecuzione, nessun change)
- Output CLI: `OK — N items, top10=10, cost=0.0X€`

- [ ] **Step 3: Verifica frontend servito localmente**

```bash
python -m http.server -d site 8080
```

Apri http://localhost:8080, verifica:
- Meta header con data e stats
- Top 10 popolato
- Categorie collassabili popolate
- Search filtra in tempo reale
- Link agli articoli funzionano

- [ ] **Step 4: Commit del primo feed reale**

```bash
git add data/ site/data/feed.json
git commit -m "chore(feed): first real refresh"
```

- [ ] **Step 5: Push su GitHub**

```bash
git remote add origin git@github.com:<your-user>/osservatorioseo.git
git branch -M main
git push -u origin main
```

- [ ] **Step 6: Verifica workflow GitHub Actions**

- Settings → Secrets → aggiungi `OPENROUTER_API_KEY`
- Actions → Daily Refresh → `Run workflow` (trigger manuale)
- Attendi completion, verifica che `data/feed.json` sia stato committato
- Se fallisce, controlla l'issue automatica e leggi i log

- [ ] **Step 7: Deploy Cloudflare Pages**

- Cloudflare dashboard → Pages → Create
- Connect repo `osservatorioseo`
- Build output directory: `site`
- Deploy
- Visita `https://osservatorioseo.pages.dev` (o dominio custom)

---

## Criteri di accettazione finale

Il progetto è "v1 done" quando:

1. ✅ `ruff check` + `pytest` passano completamente
2. ✅ `python -m osservatorio_seo refresh` in locale produce un `feed.json` valido con items reali
3. ✅ Il workflow GitHub Actions `daily-refresh` gira con successo almeno una volta via `workflow_dispatch`
4. ✅ Il frontend è accessibile su Cloudflare Pages e mostra correttamente il feed
5. ✅ Almeno una pagina del Doc Watcher ha il suo state iniziale committato in `data/state/doc_watcher/`
6. ✅ Il costo AI reale del primo run è ≤ €0.10
7. ✅ L'issue automatica su failure funziona (testabile forzando un errore, es. rimuovendo temporaneamente una env var)
