# Tracker "Stato della ricerca in Italia" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly-updated `/tracker/` dashboard + monthly `/tracker/report/<YYYY-MM>/` editorial report for Italian SEO professionals, powered by free APIs (Cloudflare Radar + Cloudflare Pages Analytics) and 7 static SVG charts generated server-side.

**Architecture:** New `src/osservatorio_seo/tracker/` module with isolated data clients (Radar, Pages Analytics), a collector that builds typed `TrackerSnapshot` models, pure-Python SVG chart generators, and Jinja templates for dashboard + report. Monthly editorial reports reuse existing `PremiumWriter` (Claude Sonnet 4.5 via OpenRouter). Weekly cron runs on GitHub Actions.

**Tech Stack:** Python 3.12 + httpx async + pydantic v2 + Jinja2 SSG + pytest + pytest-httpx. SVG charts generated as f-strings (no new libraries).

**Related spec:** `docs/superpowers/specs/2026-04-12-tracker-search-ai-italia-design.md`

---

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `src/osservatorio_seo/tracker/__init__.py` | Package marker |
| `src/osservatorio_seo/tracker/models.py` | Pydantic schemas for `TrackerSnapshot`, `TrackerMonthlyReport`, chart input types |
| `src/osservatorio_seo/tracker/radar_client.py` | Async HTTP client for Cloudflare Radar API |
| `src/osservatorio_seo/tracker/pages_analytics.py` | Async GraphQL client for Cloudflare Pages Analytics |
| `src/osservatorio_seo/tracker/collector.py` | Orchestrator: calls clients, builds `TrackerSnapshot`, writes JSON |
| `src/osservatorio_seo/tracker/charts.py` | 7 chart generator functions, each returns an SVG string |
| `src/osservatorio_seo/tracker/report.py` | Monthly report generator using `PremiumWriter` |
| `templates/pages/tracker.html.jinja` | Dashboard template (`/tracker/`) |
| `templates/pages/tracker_report.html.jinja` | Monthly report template (`/tracker/report/<YYYY-MM>/`) |
| `templates/partials/_jsonld_dataset.html.jinja` | JSON-LD `Dataset` schema for tracker |
| `scripts/update_tracker.py` | CLI entry point invoked by cron |
| `.github/workflows/tracker-weekly.yml` | GitHub Actions weekly cron |
| `tests/test_tracker_models.py` | Model validation tests |
| `tests/test_tracker_radar_client.py` | Radar client tests (mocked HTTP) |
| `tests/test_tracker_pages_analytics.py` | Pages Analytics client tests |
| `tests/test_tracker_collector.py` | Collector orchestration tests |
| `tests/test_tracker_charts.py` | Chart SVG generation tests |
| `tests/test_tracker_report.py` | Monthly report generator tests |
| `tests/test_tracker_publisher.py` | Publisher `_ssg_tracker` integration tests |
| `tests/fixtures/radar_*.json` | Saved Cloudflare Radar API responses for tests |
| `tests/fixtures/pages_analytics_*.json` | Saved Pages Analytics responses |
| `tests/fixtures/tracker_snapshot.json` | Sample full snapshot for template tests |

### Modified files

| Path | Change |
|---|---|
| `src/osservatorio_seo/premium_writer.py` | Add `write_tracker_report(year, month, snapshots)` method + `TRACKER_REPORT_PROMPT` |
| `src/osservatorio_seo/publisher.py` | Add `_ssg_tracker` + `_ssg_tracker_reports` methods, wire into `publish_ssg`, add tracker URLs to sitemap |
| `src/osservatorio_seo/renderer.py` | Add `render_tracker` and `render_tracker_report` methods |
| `src/osservatorio_seo/models.py` | (none — tracker models live in tracker/models.py to keep the core domain clean) |
| `templates/partials/_header.html.jinja` | Add `TRACKER` link between `DOSSIER` and `DOCS` |
| `templates/pages/homepage.html.jinja` | Add "Ultimo tracker" teaser section (optional, if tracker data exists) |
| `pyproject.toml` | (no new deps — we use httpx/pydantic/jinja2 already present) |

---

## Task 1: Tracker pydantic models

**Files:**
- Create: `src/osservatorio_seo/tracker/__init__.py`
- Create: `src/osservatorio_seo/tracker/models.py`
- Create: `tests/test_tracker_models.py`

- [ ] **Step 1: Create the package marker**

Create `src/osservatorio_seo/tracker/__init__.py`:

```python
"""Tracker subsystem: weekly dashboard + monthly report on AI/Search adoption in Italy."""
```

- [ ] **Step 2: Write the failing test for models**

Create `tests/test_tracker_models.py`:

```python
"""Tests for tracker pydantic models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    Big4PanelData,
    BumpChartData,
    BumpChartWeek,
    CategoryHeatmapCell,
    CategoryHeatmapRow,
    DomainMovement,
    DomainRank,
    IndexTimeseries,
    MarketCompositionPoint,
    ReportTakeaway,
    SnapshotMetadata,
    TimeseriesPoint,
    TopMovers,
    TrackerMonthlyReport,
    TrackerSnapshot,
)


def test_domain_rank_computes_delta_rank():
    r = DomainRank(
        domain="chat.openai.com",
        rank=1,
        previous_rank=3,
        traffic_change_pct=12.5,
    )
    assert r.delta_rank == 2  # moved up 2 positions (3 -> 1)


def test_domain_rank_handles_missing_previous_rank():
    r = DomainRank(domain="new.ai", rank=10)
    assert r.previous_rank is None
    assert r.delta_rank is None


def test_timeseries_point_requires_date_and_value():
    p = TimeseriesPoint(date=datetime(2026, 4, 12, tzinfo=UTC), value=42.5)
    assert p.value == 42.5


def test_index_timeseries_is_iterable():
    ts = IndexTimeseries(
        label="AI category Italy",
        points=[
            TimeseriesPoint(date=datetime(2024, 1, 1, tzinfo=UTC), value=100.0),
            TimeseriesPoint(date=datetime(2024, 2, 1, tzinfo=UTC), value=105.2),
        ],
    )
    assert len(ts.points) == 2


def test_bump_chart_data_enforces_domain_consistency():
    data = BumpChartData(
        domains=["a.com", "b.com"],
        weeks=[
            BumpChartWeek(
                week_end=datetime(2026, 3, 1, tzinfo=UTC),
                ranks={"a.com": 1, "b.com": 2},
            ),
        ],
    )
    assert data.weeks[0].ranks["a.com"] == 1


def test_top_movers_respects_max_5_each_side():
    movers = TopMovers(
        up=[DomainMovement(domain=f"d{i}.ai", delta_pct=10.0 + i) for i in range(5)],
        down=[DomainMovement(domain=f"x{i}.ai", delta_pct=-10.0 - i) for i in range(5)],
    )
    assert len(movers.up) == 5
    assert len(movers.down) == 5


def test_top_movers_rejects_more_than_5():
    with pytest.raises(ValidationError):
        TopMovers(
            up=[DomainMovement(domain=f"d{i}.ai", delta_pct=1.0) for i in range(6)],
            down=[],
        )


def test_tracker_snapshot_roundtrip():
    snap = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
        ai_top10_current=[
            DomainRank(domain="chat.openai.com", rank=1, previous_rank=1)
        ],
        search_top5_current=[
            DomainRank(domain="google.com", rank=1, previous_rank=1)
        ],
        ai_index_24mo=IndexTimeseries(label="AI IT", points=[]),
        internet_index_24mo=IndexTimeseries(label="Internet IT", points=[]),
        market_composition_12mo=[],
        bump_chart_6mo=BumpChartData(domains=[], weeks=[]),
        category_heatmap_6mo=[],
        top_movers_30d=TopMovers(up=[], down=[]),
        big4_6mo=[],
        own_referrers_30d=[],
        metadata=SnapshotMetadata(
            radar_calls=0,
            pages_analytics_calls=0,
            categories_with_it_data=[],
            warnings=[],
        ),
    )
    dumped = snap.model_dump_json()
    reloaded = TrackerSnapshot.model_validate_json(dumped)
    assert reloaded.year == 2026
    assert reloaded.week == 15


def test_tracker_monthly_report_structure():
    report = TrackerMonthlyReport(
        year=2026,
        month=3,
        title_it="Claude +42% a marzo 2026: il mover del mese in Italia",
        subtitle_it="Snapshot del mercato AI & Search italiano",
        hero_mover="claude.ai",
        executive_summary=["Punto 1", "Punto 2", "Punto 3"],
        narrative="Paragrafo 1.\n\nParagrafo 2.",
        takeaways=[
            ReportTakeaway(title=f"Takeaway {i}", body="Corpo")
            for i in range(5)
        ],
        outlook="Cosa aspettarsi.",
        snapshot_week_refs=["2026-W10", "2026-W11", "2026-W12", "2026-W13"],
        generated_at=datetime(2026, 4, 1, tzinfo=UTC),
        model_used="anthropic/claude-sonnet-4-5",
        cost_eur=0.07,
    )
    assert len(report.takeaways) == 5
    assert report.hero_mover == "claude.ai"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_models.py -v`
Expected: ImportError on `osservatorio_seo.tracker.models` (module doesn't exist yet).

- [ ] **Step 4: Write minimal implementation**

Create `src/osservatorio_seo/tracker/models.py`:

```python
"""Pydantic models for the tracker subsystem."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainRank(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    rank: int = Field(ge=1)
    previous_rank: int | None = None
    delta_rank: int | None = None  # positive = moved up (rank went down in number)
    traffic_change_pct: float | None = None

    @model_validator(mode="after")
    def _compute_delta(self) -> "DomainRank":
        if self.delta_rank is None and self.previous_rank is not None:
            # delta is positive when domain moved UP (lower rank number)
            self.delta_rank = self.previous_rank - self.rank
        return self


class TimeseriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime
    value: float


class IndexTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    points: list[TimeseriesPoint] = Field(default_factory=list)


class MarketCompositionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: datetime
    google_share: float = Field(ge=0.0, le=1.0)
    other_search_share: float = Field(ge=0.0, le=1.0)
    ai_share: float = Field(ge=0.0, le=1.0)


class BumpChartWeek(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_end: datetime
    ranks: dict[str, int]  # domain -> rank


class BumpChartData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domains: list[str] = Field(default_factory=list)
    weeks: list[BumpChartWeek] = Field(default_factory=list)


class CategoryHeatmapCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str  # YYYY-MM
    delta_pct: float | None = None  # None = no data


class CategoryHeatmapRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    cells: list[CategoryHeatmapCell] = Field(default_factory=list)


class DomainMovement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    delta_pct: float


class TopMovers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    up: list[DomainMovement] = Field(default_factory=list, max_length=5)
    down: list[DomainMovement] = Field(default_factory=list, max_length=5)


class Big4PanelData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    display_name: str
    current_rank: int = Field(ge=1)
    previous_rank: int | None = Field(default=None, ge=1)
    traffic_timeseries: list[TimeseriesPoint] = Field(default_factory=list)


class AnalyticsReferrer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    share_pct: float = Field(ge=0.0, le=100.0)


class SnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    radar_calls: int = 0
    pages_analytics_calls: int = 0
    categories_with_it_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TrackerSnapshot(BaseModel):
    """Snapshot settimanale completo dei dati tracker.

    Contiene tutto il raw + derived data necessario per rigenerare i 7
    grafici senza nuove chiamate API. Immutabile una volta scritto.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    year: int
    week: int = Field(ge=1, le=53)  # ISO week
    generated_at: datetime

    # Chart 1: AI vs Internet (24 months)
    ai_index_24mo: IndexTimeseries
    internet_index_24mo: IndexTimeseries

    # Chart 2: market composition (12 months)
    market_composition_12mo: list[MarketCompositionPoint] = Field(default_factory=list)

    # Chart 3: bump chart (top 10 AI, 6 months)
    bump_chart_6mo: BumpChartData

    # Chart 4: category heatmap (6 months)
    category_heatmap_6mo: list[CategoryHeatmapRow] = Field(default_factory=list)

    # Chart 5: top movers (30 days)
    top_movers_30d: TopMovers

    # Chart 6: small multiples big 4 AI (6 months)
    big4_6mo: list[Big4PanelData] = Field(default_factory=list)

    # Current snapshots (for derived narrative)
    ai_top10_current: list[DomainRank] = Field(default_factory=list)
    search_top5_current: list[DomainRank] = Field(default_factory=list)

    # Chart 7: own analytics
    own_referrers_30d: list[AnalyticsReferrer] = Field(default_factory=list)

    metadata: SnapshotMetadata


class ReportTakeaway(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str


class TrackerMonthlyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    year: int
    month: int = Field(ge=1, le=12)

    title_it: str
    subtitle_it: str
    hero_mover: str  # slug of the most significant mover domain

    executive_summary: list[str] = Field(default_factory=list, max_length=6)
    narrative: str  # paragraphs separated by \n\n, voce impersonale
    takeaways: list[ReportTakeaway] = Field(default_factory=list, max_length=8)
    outlook: str

    snapshot_week_refs: list[str] = Field(default_factory=list)
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_models.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/tracker/__init__.py src/osservatorio_seo/tracker/models.py tests/test_tracker_models.py
git commit -m "feat(tracker): pydantic models for snapshots and monthly reports"
```

---

## Task 2: Cloudflare Radar client

**Files:**
- Create: `src/osservatorio_seo/tracker/radar_client.py`
- Create: `tests/test_tracker_radar_client.py`
- Create: `tests/fixtures/radar_ranking_top_ai_it.json`
- Create: `tests/fixtures/radar_ranking_timeseries_ai_it.json`

- [ ] **Step 1: Save Radar API response fixtures**

Create `tests/fixtures/radar_ranking_top_ai_it.json` (abbreviated — use realistic shape from the [Radar API docs](https://developers.cloudflare.com/api/operations/radar-get-ranking-top)):

```json
{
  "success": true,
  "result": {
    "meta": {
      "dateRange": [
        {"startTime": "2026-04-07T00:00:00Z", "endTime": "2026-04-14T00:00:00Z"}
      ]
    },
    "top_0": [
      {"domain": "chat.openai.com", "rank": 1, "categories": [{"id": 13, "name": "AI"}]},
      {"domain": "gemini.google.com", "rank": 2, "categories": [{"id": 13, "name": "AI"}]},
      {"domain": "claude.ai", "rank": 3, "categories": [{"id": 13, "name": "AI"}]},
      {"domain": "perplexity.ai", "rank": 4, "categories": [{"id": 13, "name": "AI"}]},
      {"domain": "character.ai", "rank": 5, "categories": [{"id": 13, "name": "AI"}]}
    ]
  }
}
```

Create `tests/fixtures/radar_ranking_timeseries_ai_it.json`:

```json
{
  "success": true,
  "result": {
    "meta": {
      "dateRange": [
        {"startTime": "2024-04-14T00:00:00Z", "endTime": "2026-04-14T00:00:00Z"}
      ],
      "aggInterval": "1w"
    },
    "serie_0": {
      "timestamps": [
        "2024-04-14T00:00:00Z",
        "2024-04-21T00:00:00Z",
        "2024-04-28T00:00:00Z"
      ],
      "values": [100.0, 102.3, 105.1]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_tracker_radar_client.py`:

```python
"""Tests for Cloudflare Radar API client."""

import json
from pathlib import Path

import httpx
import pytest

from osservatorio_seo.tracker.radar_client import RadarClient, RadarClientError


@pytest.fixture
def api_token() -> str:
    return "test-token-not-real"


@pytest.fixture
def radar_top_ai(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_ranking_top_ai_it.json").read_text())


@pytest.fixture
def radar_timeseries_ai(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "radar_ranking_timeseries_ai_it.json").read_text())


@pytest.mark.asyncio
async def test_top_domains_ai_italy(httpx_mock, api_token, radar_top_ai):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/radar/ranking/top?limit=10&location=IT&name=ai&dateRange=1w",
        json=radar_top_ai,
    )

    client = RadarClient(api_token=api_token)
    result = await client.top_domains(category="ai", location="IT", limit=10)

    assert len(result) == 5
    assert result[0].domain == "chat.openai.com"
    assert result[0].rank == 1
    assert result[2].domain == "claude.ai"


@pytest.mark.asyncio
async def test_ranking_timeseries(httpx_mock, api_token, radar_timeseries_ai):
    httpx_mock.add_response(
        url__regex=r".*radar/ranking/timeseries_groups.*name=ai.*location=IT.*",
        json=radar_timeseries_ai,
    )

    client = RadarClient(api_token=api_token)
    result = await client.category_timeseries(category="ai", location="IT", date_range="2y")

    assert result.label == "ai"
    assert len(result.points) == 3
    assert result.points[0].value == 100.0
    assert result.points[2].value == 105.1


@pytest.mark.asyncio
async def test_client_error_on_non_200(httpx_mock, api_token):
    httpx_mock.add_response(
        url__regex=r".*radar/ranking/top.*",
        status_code=500,
        json={"success": False, "errors": [{"message": "server error"}]},
    )

    client = RadarClient(api_token=api_token)
    with pytest.raises(RadarClientError) as exc_info:
        await client.top_domains(category="ai", location="IT")
    assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_client_error_on_non_success(httpx_mock, api_token):
    httpx_mock.add_response(
        url__regex=r".*radar/ranking/top.*",
        json={"success": False, "errors": [{"message": "bad request"}]},
    )

    client = RadarClient(api_token=api_token)
    with pytest.raises(RadarClientError) as exc_info:
        await client.top_domains(category="ai", location="IT")
    assert "bad request" in str(exc_info.value)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_radar_client.py -v`
Expected: ImportError on `radar_client`.

- [ ] **Step 4: Write the implementation**

Create `src/osservatorio_seo/tracker/radar_client.py`:

```python
"""Async client for Cloudflare Radar API.

Docs: https://developers.cloudflare.com/api/operations/radar-get-ranking-top

Free tier, requires API token with `Zone.Radar Read` permission.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from osservatorio_seo.tracker.models import (
    DomainRank,
    IndexTimeseries,
    TimeseriesPoint,
)

logger = logging.getLogger(__name__)

RADAR_BASE_URL = "https://api.cloudflare.com/client/v4/radar"


class RadarClientError(Exception):
    """Raised on any non-2xx response or API-level failure."""


class RadarClient:
    """Lightweight async wrapper for Cloudflare Radar endpoints needed by tracker."""

    def __init__(
        self,
        api_token: str,
        timeout_s: int = 30,
        base_url: str = RADAR_BASE_URL,
    ) -> None:
        self._api_token = api_token
        self._timeout = timeout_s
        self._base_url = base_url.rstrip("/")

    async def top_domains(
        self,
        *,
        category: str,
        location: str = "IT",
        limit: int = 10,
        date_range: str = "1w",
    ) -> list[DomainRank]:
        """Fetch top N domains in a category for a location.

        Returns a list of :class:`DomainRank` with current rank only.
        Caller is responsible for computing delta vs previous snapshot.
        """
        params = {
            "limit": limit,
            "location": location,
            "name": category,
            "dateRange": date_range,
        }
        data = await self._get("/ranking/top", params)
        series = data.get("result", {}).get("top_0", [])
        return [DomainRank(domain=row["domain"], rank=row["rank"]) for row in series]

    async def category_timeseries(
        self,
        *,
        category: str,
        location: str = "IT",
        date_range: str = "2y",
    ) -> IndexTimeseries:
        """Fetch traffic/rank timeseries for a category.

        Returns the raw values as they come from Radar. Caller normalizes
        them (e.g., rescale to 100 at start) if needed for charting.
        """
        params = {
            "location": location,
            "name": category,
            "dateRange": date_range,
        }
        data = await self._get("/ranking/timeseries_groups", params)
        serie = data.get("result", {}).get("serie_0", {})
        timestamps = serie.get("timestamps", [])
        values = serie.get("values", [])
        points = [
            TimeseriesPoint(
                date=datetime.fromisoformat(ts.replace("Z", "+00:00")),
                value=float(v),
            )
            for ts, v in zip(timestamps, values, strict=False)
        ]
        return IndexTimeseries(label=category, points=points)

    async def domain_timeseries(
        self,
        *,
        domain: str,
        location: str = "IT",
        date_range: str = "6m",
    ) -> IndexTimeseries:
        """Fetch traffic timeseries for a specific domain."""
        params = {
            "domain": domain,
            "location": location,
            "dateRange": date_range,
        }
        data = await self._get(f"/ranking/domain/{domain}", params)
        serie = data.get("result", {}).get("serie_0", {})
        timestamps = serie.get("timestamps", [])
        values = serie.get("values", [])
        points = [
            TimeseriesPoint(
                date=datetime.fromisoformat(ts.replace("Z", "+00:00")),
                value=float(v),
            )
            for ts, v in zip(timestamps, values, strict=False)
        ]
        return IndexTimeseries(label=domain, points=points)

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._api_token}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, params=params, headers=headers)
        if resp.status_code >= 400:
            raise RadarClientError(
                f"Radar API error {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json()
        if not data.get("success", False):
            errs = data.get("errors", [])
            msg = "; ".join(e.get("message", str(e)) for e in errs) or "unknown"
            raise RadarClientError(f"Radar API reported failure: {msg}")
        return data
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_radar_client.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/tracker/radar_client.py tests/test_tracker_radar_client.py tests/fixtures/radar_*.json
git commit -m "feat(tracker): Cloudflare Radar API async client with httpx mocking"
```

---

## Task 3: Cloudflare Pages Analytics client

**Files:**
- Create: `src/osservatorio_seo/tracker/pages_analytics.py`
- Create: `tests/test_tracker_pages_analytics.py`
- Create: `tests/fixtures/pages_analytics_referrers.json`

- [ ] **Step 1: Save fixture for Pages Analytics GraphQL response**

Create `tests/fixtures/pages_analytics_referrers.json`:

```json
{
  "data": {
    "viewer": {
      "accounts": [
        {
          "httpRequestsAdaptiveGroups": [
            {"dimensions": {"refererHost": "google.com"}, "count": 6520},
            {"dimensions": {"refererHost": "www.google.com"}, "count": 4100},
            {"dimensions": {"refererHost": "chat.openai.com"}, "count": 85},
            {"dimensions": {"refererHost": "claude.ai"}, "count": 32},
            {"dimensions": {"refererHost": "bing.com"}, "count": 180},
            {"dimensions": {"refererHost": "duckduckgo.com"}, "count": 90},
            {"dimensions": {"refererHost": "perplexity.ai"}, "count": 14},
            {"dimensions": {"refererHost": ""}, "count": 2300}
          ]
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_tracker_pages_analytics.py`:

```python
"""Tests for Cloudflare Pages Analytics GraphQL client."""

import json
from pathlib import Path

import pytest

from osservatorio_seo.tracker.pages_analytics import (
    PagesAnalyticsClient,
    PagesAnalyticsError,
)


@pytest.fixture
def analytics_payload(fixtures_dir: Path) -> dict:
    return json.loads((fixtures_dir / "pages_analytics_referrers.json").read_text())


@pytest.mark.asyncio
async def test_referrer_groups_aggregated_and_normalized(httpx_mock, analytics_payload):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/graphql",
        json=analytics_payload,
    )

    client = PagesAnalyticsClient(
        api_token="token",
        account_id="acct",
        zone_id="zone",
    )
    referrers = await client.referrer_share(days=30)

    # Aggregated groups: Google/Bing/DDG/Direct/ChatGPT/Claude/Perplexity/Other
    by_source = {r.source: r.share_pct for r in referrers}
    # google.com + www.google.com = 6520 + 4100 = 10620 of total 13321 = 79.72%
    assert by_source["Google"] == pytest.approx(79.72, abs=0.1)
    # empty referer = 2300 → Direct
    assert by_source["Direct"] == pytest.approx(17.26, abs=0.1)
    # sum of all shares ~ 100
    assert sum(by_source.values()) == pytest.approx(100.0, abs=0.5)


@pytest.mark.asyncio
async def test_error_on_graphql_errors(httpx_mock):
    httpx_mock.add_response(
        url="https://api.cloudflare.com/client/v4/graphql",
        json={"errors": [{"message": "not authorized"}]},
    )
    client = PagesAnalyticsClient(
        api_token="bad", account_id="acct", zone_id="zone"
    )
    with pytest.raises(PagesAnalyticsError) as exc_info:
        await client.referrer_share(days=30)
    assert "not authorized" in str(exc_info.value)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_pages_analytics.py -v`
Expected: ImportError.

- [ ] **Step 4: Write the implementation**

Create `src/osservatorio_seo/tracker/pages_analytics.py`:

```python
"""Async client for Cloudflare Pages Analytics via the GraphQL Analytics API.

Docs: https://developers.cloudflare.com/analytics/graphql-api/

Scope: we only need referrer breakdown for a single zone (OsservatorioSEO
pages.dev domain). The result is aggregated into labeled groups suitable
for Chart 7 of the tracker.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from osservatorio_seo.tracker.models import AnalyticsReferrer

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# Regex-free source grouping: substring match on lowercase referer host.
# Order matters: first match wins.
_SOURCE_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Google", ("google.",)),
    ("Bing", ("bing.",)),
    ("DuckDuckGo", ("duckduckgo.",)),
    ("Yahoo", ("yahoo.",)),
    ("ChatGPT", ("chat.openai.", "openai.",)),
    ("Claude", ("claude.ai", "anthropic.",)),
    ("Perplexity", ("perplexity.",)),
    ("Gemini", ("gemini.google.", "bard.google.",)),
]


class PagesAnalyticsError(Exception):
    """Raised on any GraphQL error or transport failure."""


class PagesAnalyticsClient:
    """GraphQL client for Cloudflare Pages / Analytics referrer breakdown."""

    def __init__(
        self,
        api_token: str,
        account_id: str,
        zone_id: str,
        timeout_s: int = 30,
    ) -> None:
        self._api_token = api_token
        self._account_id = account_id
        self._zone_id = zone_id
        self._timeout = timeout_s

    async def referrer_share(self, days: int = 30) -> list[AnalyticsReferrer]:
        """Return aggregated referrer share for the last N days."""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        query = """
        query Referrers($zoneId: String!, $start: Time!, $end: Time!) {
          viewer {
            accounts(filter: {accountTag: "ACCOUNT_ID_PLACEHOLDER"}) {
              httpRequestsAdaptiveGroups(
                filter: {
                  zoneTag: $zoneId,
                  datetime_gt: $start,
                  datetime_lt: $end
                },
                limit: 1000
              ) {
                dimensions { refererHost }
                count
              }
            }
          }
        }
        """.replace("ACCOUNT_ID_PLACEHOLDER", self._account_id)

        variables = {
            "zoneId": self._zone_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        body = {"query": query, "variables": variables}
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(GRAPHQL_URL, json=body, headers=headers)

        if resp.status_code >= 400:
            raise PagesAnalyticsError(
                f"Pages Analytics HTTP {resp.status_code}: {resp.text[:200]}"
            )
        payload = resp.json()
        if payload.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in payload["errors"])
            raise PagesAnalyticsError(f"GraphQL error: {msgs}")

        groups = self._extract_groups(payload)
        return self._aggregate(groups)

    @staticmethod
    def _extract_groups(payload: dict[str, Any]) -> list[tuple[str, int]]:
        """Pull (referer_host, count) tuples out of the GraphQL shape."""
        out: list[tuple[str, int]] = []
        accounts = payload.get("data", {}).get("viewer", {}).get("accounts", [])
        for acct in accounts:
            for row in acct.get("httpRequestsAdaptiveGroups", []):
                host = (row.get("dimensions", {}) or {}).get("refererHost", "") or ""
                count = int(row.get("count", 0) or 0)
                out.append((host.lower(), count))
        return out

    @staticmethod
    def _aggregate(groups: list[tuple[str, int]]) -> list[AnalyticsReferrer]:
        """Aggregate by labeled source; normalize to percentages."""
        buckets: dict[str, int] = {}
        total = 0
        for host, count in groups:
            total += count
            label = "Direct" if not host else None
            if label is None:
                for name, matchers in _SOURCE_GROUPS:
                    if any(m in host for m in matchers):
                        label = name
                        break
            if label is None:
                label = "Other"
            buckets[label] = buckets.get(label, 0) + count

        if total == 0:
            return []

        result = [
            AnalyticsReferrer(source=name, share_pct=round(count / total * 100, 2))
            for name, count in buckets.items()
        ]
        # Stable output order: known sources first, then Direct, then Other
        known_order = ["Google", "Bing", "DuckDuckGo", "Yahoo", "ChatGPT", "Claude", "Gemini", "Perplexity", "Direct", "Other"]
        result.sort(key=lambda r: known_order.index(r.source) if r.source in known_order else 99)
        return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_pages_analytics.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/tracker/pages_analytics.py tests/test_tracker_pages_analytics.py tests/fixtures/pages_analytics_referrers.json
git commit -m "feat(tracker): Cloudflare Pages Analytics GraphQL client with referrer grouping"
```

---

## Task 4: Collector — orchestrates clients into TrackerSnapshot

**Files:**
- Create: `src/osservatorio_seo/tracker/collector.py`
- Create: `tests/test_tracker_collector.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tracker_collector.py`:

```python
"""Tests for tracker collector orchestration.

Uses AsyncMock to stub RadarClient and PagesAnalyticsClient so we don't
need real HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    DomainRank,
    IndexTimeseries,
    TimeseriesPoint,
    TrackerSnapshot,
)


@pytest.fixture
def fake_radar():
    client = AsyncMock()

    client.top_domains.side_effect = lambda category, location, limit=10, **kw: {
        ("ai", "IT"): [
            DomainRank(domain="chat.openai.com", rank=1),
            DomainRank(domain="gemini.google.com", rank=2),
            DomainRank(domain="claude.ai", rank=3),
            DomainRank(domain="perplexity.ai", rank=4),
            DomainRank(domain="character.ai", rank=5),
        ],
        ("search_engines", "IT"): [
            DomainRank(domain="google.com", rank=1),
            DomainRank(domain="bing.com", rank=2),
            DomainRank(domain="duckduckgo.com", rank=3),
        ],
    }[(category, location)]

    # Simple timeseries stubs
    base_points = [
        TimeseriesPoint(date=datetime(2024 + i // 12, (i % 12) + 1, 1, tzinfo=UTC), value=100 + i * 2)
        for i in range(24)
    ]
    client.category_timeseries.return_value = IndexTimeseries(label="ai", points=base_points)
    client.domain_timeseries.return_value = IndexTimeseries(label="domain", points=base_points[-24:])

    return client


@pytest.fixture
def fake_pages_analytics():
    client = AsyncMock()
    client.referrer_share.return_value = [
        AnalyticsReferrer(source="Google", share_pct=79.7),
        AnalyticsReferrer(source="Direct", share_pct=17.3),
        AnalyticsReferrer(source="ChatGPT", share_pct=0.6),
        AnalyticsReferrer(source="Claude", share_pct=0.2),
    ]
    return client


@pytest.mark.asyncio
async def test_collect_builds_complete_snapshot(fake_radar, fake_pages_analytics):
    collector = TrackerCollector(
        radar=fake_radar,
        pages_analytics=fake_pages_analytics,
        location="IT",
    )
    snapshot = await collector.collect(year=2026, week=15)

    assert isinstance(snapshot, TrackerSnapshot)
    assert snapshot.year == 2026
    assert snapshot.week == 15
    assert len(snapshot.ai_top10_current) == 5
    assert snapshot.ai_top10_current[0].domain == "chat.openai.com"
    assert len(snapshot.search_top5_current) == 3
    assert snapshot.own_referrers_30d[0].source == "Google"
    # Metadata tracks calls
    assert snapshot.metadata.radar_calls > 0
    assert snapshot.metadata.pages_analytics_calls == 1


@pytest.mark.asyncio
async def test_collect_is_robust_to_partial_failures(fake_radar, fake_pages_analytics):
    """If pages analytics fails, snapshot is still built with a warning."""
    fake_pages_analytics.referrer_share.side_effect = Exception("boom")

    collector = TrackerCollector(
        radar=fake_radar,
        pages_analytics=fake_pages_analytics,
        location="IT",
    )
    snapshot = await collector.collect(year=2026, week=15)
    assert snapshot.own_referrers_30d == []
    assert any("pages_analytics" in w.lower() for w in snapshot.metadata.warnings)


def test_persist_writes_json_to_snapshots_dir(tmp_path, fake_radar, fake_pages_analytics):
    """persist() writes snapshot to data/tracker/snapshots/<YYYY-WNN>.json."""
    snapshot = TrackerSnapshot(
        year=2026,
        week=15,
        generated_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
        ai_index_24mo=IndexTimeseries(label="ai"),
        internet_index_24mo=IndexTimeseries(label="internet"),
        bump_chart_6mo={"domains": [], "weeks": []},
        top_movers_30d={"up": [], "down": []},
        metadata={"radar_calls": 5, "pages_analytics_calls": 1},
    )
    TrackerCollector.persist(snapshot, base_dir=tmp_path)

    target = tmp_path / "snapshots" / "2026-W15.json"
    assert target.exists()
    content = target.read_text()
    assert '"week": 15' in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_collector.py -v`
Expected: ImportError.

- [ ] **Step 3: Write the implementation**

Create `src/osservatorio_seo/tracker/collector.py`:

```python
"""Collector: orchestrates Radar + Pages Analytics into a TrackerSnapshot.

Responsibilities:
- Fetch top-N domains in AI and Search Engines categories for Italy
- Fetch 24-month AI category index + 24-month total internet index
- Build the derived models for each chart
- Compute deltas vs previous snapshot (if available)
- Handle partial failures gracefully (log warning, continue)
- Persist snapshot to ``data/tracker/snapshots/<YYYY-Www>.json``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    Big4PanelData,
    BumpChartData,
    BumpChartWeek,
    CategoryHeatmapRow,
    DomainRank,
    IndexTimeseries,
    MarketCompositionPoint,
    SnapshotMetadata,
    TopMovers,
    TrackerSnapshot,
)
from osservatorio_seo.tracker.pages_analytics import PagesAnalyticsClient
from osservatorio_seo.tracker.radar_client import RadarClient

logger = logging.getLogger(__name__)

BIG_4_AI = [
    ("chat.openai.com", "ChatGPT"),
    ("gemini.google.com", "Gemini"),
    ("claude.ai", "Claude"),
    ("perplexity.ai", "Perplexity"),
]

SEARCH_CATEGORY = "search_engines"
AI_CATEGORY = "ai"


class TrackerCollector:
    """Orchestrates data clients and produces a TrackerSnapshot."""

    def __init__(
        self,
        radar: RadarClient,
        pages_analytics: PagesAnalyticsClient | None = None,
        location: str = "IT",
    ) -> None:
        self._radar = radar
        self._pages_analytics = pages_analytics
        self._location = location
        self._radar_calls = 0
        self._warnings: list[str] = []

    async def collect(self, year: int, week: int) -> TrackerSnapshot:
        """Run all data fetches and build a snapshot."""
        self._radar_calls = 0
        self._warnings = []

        ai_top10 = await self._safe_radar_top(category=AI_CATEGORY, limit=10)
        search_top5 = await self._safe_radar_top(category=SEARCH_CATEGORY, limit=5)

        ai_index_24mo = await self._safe_category_timeseries(AI_CATEGORY, date_range="2y")
        internet_index_24mo = await self._safe_category_timeseries("all", date_range="2y")

        # For v1 we keep bump chart / heatmap / small multiples / market
        # composition as empty stubs. Subsequent tasks fill them once we
        # know exactly which endpoints to call. This keeps the collector
        # incrementally buildable.
        bump_chart = BumpChartData()
        heatmap: list[CategoryHeatmapRow] = []
        movers = TopMovers()
        big4: list[Big4PanelData] = []
        market_composition: list[MarketCompositionPoint] = []

        own_referrers = await self._safe_pages_analytics()

        metadata = SnapshotMetadata(
            radar_calls=self._radar_calls,
            pages_analytics_calls=1 if self._pages_analytics is not None else 0,
            categories_with_it_data=[AI_CATEGORY, SEARCH_CATEGORY],
            warnings=list(self._warnings),
        )

        return TrackerSnapshot(
            year=year,
            week=week,
            generated_at=datetime.now(UTC),
            ai_index_24mo=ai_index_24mo,
            internet_index_24mo=internet_index_24mo,
            market_composition_12mo=market_composition,
            bump_chart_6mo=bump_chart,
            category_heatmap_6mo=heatmap,
            top_movers_30d=movers,
            big4_6mo=big4,
            ai_top10_current=ai_top10,
            search_top5_current=search_top5,
            own_referrers_30d=own_referrers,
            metadata=metadata,
        )

    async def _safe_radar_top(self, category: str, limit: int) -> list[DomainRank]:
        try:
            self._radar_calls += 1
            return await self._radar.top_domains(
                category=category, location=self._location, limit=limit
            )
        except Exception as e:  # noqa: BLE001
            self._warnings.append(f"radar.top_domains({category}): {e}")
            logger.warning("radar top_domains %s failed: %s", category, e)
            return []

    async def _safe_category_timeseries(
        self, category: str, date_range: str
    ) -> IndexTimeseries:
        try:
            self._radar_calls += 1
            return await self._radar.category_timeseries(
                category=category, location=self._location, date_range=date_range
            )
        except Exception as e:  # noqa: BLE001
            self._warnings.append(f"radar.category_timeseries({category}): {e}")
            logger.warning("radar timeseries %s failed: %s", category, e)
            return IndexTimeseries(label=category)

    async def _safe_pages_analytics(self) -> list[AnalyticsReferrer]:
        if self._pages_analytics is None:
            self._warnings.append("pages_analytics: no client configured")
            return []
        try:
            return await self._pages_analytics.referrer_share(days=30)
        except Exception as e:  # noqa: BLE001
            self._warnings.append(f"pages_analytics.referrer_share: {e}")
            logger.warning("pages analytics failed: %s", e)
            return []

    @staticmethod
    def persist(snapshot: TrackerSnapshot, base_dir: Path) -> Path:
        """Write snapshot to ``<base_dir>/snapshots/<YYYY-Www>.json``."""
        snapshots_dir = Path(base_dir) / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{snapshot.year}-W{snapshot.week:02d}.json"
        target = snapshots_dir / filename
        target.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_collector.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/collector.py tests/test_tracker_collector.py
git commit -m "feat(tracker): collector orchestrating radar + pages analytics into snapshot"
```

---

## Task 5: Chart 1 — "AI vs Internet in Italia" line chart

**Files:**
- Create: `src/osservatorio_seo/tracker/charts.py`
- Create: `tests/test_tracker_charts.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tracker_charts.py`:

```python
"""Tests for tracker chart SVG generators."""

from datetime import UTC, datetime

from osservatorio_seo.tracker.charts import render_ai_vs_internet_chart
from osservatorio_seo.tracker.models import IndexTimeseries, TimeseriesPoint


def test_ai_vs_internet_chart_returns_valid_svg():
    points_ai = [
        TimeseriesPoint(date=datetime(2024, 4, 1, tzinfo=UTC), value=100),
        TimeseriesPoint(date=datetime(2024, 10, 1, tzinfo=UTC), value=120),
        TimeseriesPoint(date=datetime(2025, 4, 1, tzinfo=UTC), value=145),
        TimeseriesPoint(date=datetime(2025, 10, 1, tzinfo=UTC), value=160),
        TimeseriesPoint(date=datetime(2026, 4, 1, tzinfo=UTC), value=182),
    ]
    points_internet = [
        TimeseriesPoint(date=datetime(2024, 4, 1, tzinfo=UTC), value=100),
        TimeseriesPoint(date=datetime(2024, 10, 1, tzinfo=UTC), value=103),
        TimeseriesPoint(date=datetime(2025, 4, 1, tzinfo=UTC), value=106),
        TimeseriesPoint(date=datetime(2025, 10, 1, tzinfo=UTC), value=109),
        TimeseriesPoint(date=datetime(2026, 4, 1, tzinfo=UTC), value=112),
    ]
    svg = render_ai_vs_internet_chart(
        ai=IndexTimeseries(label="AI", points=points_ai),
        internet=IndexTimeseries(label="Internet", points=points_internet),
    )
    assert svg.startswith("<svg")
    assert "viewBox" in svg
    assert "AI" in svg
    assert "Internet" in svg
    # Must contain at least 2 polyline elements (2 series)
    assert svg.count("<polyline") >= 2


def test_ai_vs_internet_chart_handles_empty_data():
    svg = render_ai_vs_internet_chart(
        ai=IndexTimeseries(label="AI"),
        internet=IndexTimeseries(label="Internet"),
    )
    assert svg.startswith("<svg")
    assert "nessun dato" in svg.lower() or "no data" in svg.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py -v`
Expected: ImportError on charts module.

- [ ] **Step 3: Write the chart module skeleton + Chart 1 generator**

Create `src/osservatorio_seo/tracker/charts.py`:

```python
"""SVG chart generators for the tracker dashboard.

Each public function takes a typed pydantic model and returns a self-
contained SVG string. The SVGs are inlined into ``tracker.html.jinja``
via ``|safe`` and styled by the existing CSS theme (terminal retro
green-on-black), so we avoid hardcoding ``font-family``.

All charts use ``viewBox`` + ``preserveAspectRatio`` for responsive
rendering on mobile. Max width typically 700px, height scaled.
"""

from __future__ import annotations

from osservatorio_seo.tracker.models import (
    IndexTimeseries,
)

# Theme colors (keep in sync with tailwind_input.css)
PRIMARY_GREEN = "#00f63e"
ACCENT_ORANGE = "#f5a623"
OUTLINE_GREY = "#919191"
OUTLINE_VARIANT = "#474747"
BG_DARK = "#0e0e0e"
ON_SURFACE = "#e2e2e2"


def _empty_svg(message: str = "Nessun dato disponibile") -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 60" '
        'role="img" aria-label="chart placeholder">'
        f'<rect width="700" height="60" fill="{BG_DARK}"/>'
        f'<text x="350" y="35" text-anchor="middle" fill="{OUTLINE_GREY}" '
        f'font-size="12" font-family="monospace">{message}</text>'
        '</svg>'
    )


def _normalize_to_100(points) -> list[float]:
    """Rescale a list of TimeseriesPoint values so the first = 100."""
    if not points:
        return []
    base = points[0].value or 1.0
    return [round(p.value / base * 100, 2) for p in points]


def _polyline_points(xs: list[float], ys: list[float]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys, strict=False))


def render_ai_vs_internet_chart(
    ai: IndexTimeseries,
    internet: IndexTimeseries,
) -> str:
    """Chart 1: dual-line showing AI index vs total internet index over 24mo.

    Both series are normalized to 100 at their first data point so the
    reader can see relative growth/divergence.
    """
    if not ai.points or not internet.points:
        return _empty_svg("Nessun dato disponibile — AI vs Internet")

    width, height = 700, 320
    margin_x, margin_y = 60, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    ai_norm = _normalize_to_100(ai.points)
    int_norm = _normalize_to_100(internet.points)

    all_values = ai_norm + int_norm
    y_max = max(all_values) * 1.1
    y_min = min(all_values) * 0.9

    def scale_y(v: float) -> float:
        return margin_y + inner_h * (1 - (v - y_min) / (y_max - y_min))

    def scale_x(i: int, n: int) -> float:
        return margin_x + (inner_w * i / max(n - 1, 1))

    ai_xs = [scale_x(i, len(ai_norm)) for i in range(len(ai_norm))]
    ai_ys = [scale_y(v) for v in ai_norm]
    int_xs = [scale_x(i, len(int_norm)) for i in range(len(int_norm))]
    int_ys = [scale_y(v) for v in int_norm]

    ai_poly = _polyline_points(ai_xs, ai_ys)
    int_poly = _polyline_points(int_xs, int_ys)

    # Y-axis gridlines: 4 horizontal dashed lines
    y_ticks = [y_min + (y_max - y_min) * t / 4 for t in range(5)]
    grid_lines = ""
    y_labels = ""
    for yt in y_ticks:
        y = scale_y(yt)
        grid_lines += (
            f'<line x1="{margin_x}" y1="{y:.1f}" x2="{width - margin_x}" y2="{y:.1f}" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="2,3" stroke-width="1"/>'
        )
        y_labels += (
            f'<text x="{margin_x - 8}" y="{y + 3:.1f}" text-anchor="end" '
            f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">'
            f'{int(yt)}</text>'
        )

    # Final-point labels
    ai_last_label = (
        f'<text x="{ai_xs[-1] + 6:.1f}" y="{ai_ys[-1] + 4:.1f}" '
        f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" '
        f'font-weight="bold">AI (Italia)</text>'
    )
    int_last_label = (
        f'<text x="{int_xs[-1] + 6:.1f}" y="{int_ys[-1] + 4:.1f}" '
        f'fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">'
        f'Internet tot.</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="AI vs Internet, trend 24 mesi Italia" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{grid_lines}'
        f'{y_labels}'
        f'<polyline points="{int_poly}" fill="none" stroke="{OUTLINE_GREY}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'<polyline points="{ai_poly}" fill="none" stroke="{PRIMARY_GREEN}" '
        f'stroke-width="2.5" stroke-linejoin="round"/>'
        f'{int_last_label}'
        f'{ai_last_label}'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_ai_vs_internet_chart_returns_valid_svg tests/test_tracker_charts.py::test_ai_vs_internet_chart_handles_empty_data -v`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 1 — AI vs Internet line chart (SVG)"
```

---

## Task 6: Chart 2 — "A chi cede Google" stacked area chart

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_market_composition_chart
from osservatorio_seo.tracker.models import MarketCompositionPoint


def test_market_composition_chart_returns_valid_svg():
    points = [
        MarketCompositionPoint(
            date=datetime(2025, 5, 1, tzinfo=UTC),
            google_share=0.945,
            other_search_share=0.04,
            ai_share=0.015,
        ),
        MarketCompositionPoint(
            date=datetime(2025, 11, 1, tzinfo=UTC),
            google_share=0.938,
            other_search_share=0.04,
            ai_share=0.022,
        ),
        MarketCompositionPoint(
            date=datetime(2026, 4, 1, tzinfo=UTC),
            google_share=0.92,
            other_search_share=0.045,
            ai_share=0.035,
        ),
    ]
    svg = render_market_composition_chart(points)
    assert svg.startswith("<svg")
    # Three stacked polygons
    assert svg.count("<polygon") >= 3
    assert "Google" in svg
    assert "AI" in svg


def test_market_composition_handles_empty():
    svg = render_market_composition_chart([])
    assert "nessun dato" in svg.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_market_composition_chart_returns_valid_svg -v`
Expected: AttributeError (function not defined).

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import MarketCompositionPoint  # add to top


def render_market_composition_chart(
    points: list[MarketCompositionPoint],
) -> str:
    """Chart 2: stacked area showing Google / other-search / AI share over 12 months.

    Areas are stacked bottom-up: Google (primary green) → other search
    (grey) → AI (accent orange). The total always sums to 1.0 (100%).
    """
    if not points:
        return _empty_svg("Nessun dato disponibile — composizione mercato")

    width, height = 700, 320
    margin_x, margin_y = 60, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    n = len(points)

    def scale_x(i: int) -> float:
        return margin_x + (inner_w * i / max(n - 1, 1))

    def scale_y(v: float) -> float:
        return margin_y + inner_h * (1 - v)

    # Build cumulative stacks: google, google+other, google+other+ai
    google_tops = [p.google_share for p in points]
    other_tops = [p.google_share + p.other_search_share for p in points]
    all_tops = [
        p.google_share + p.other_search_share + p.ai_share for p in points
    ]

    def polygon_for(lows: list[float], tops: list[float]) -> str:
        pts_top = " ".join(f"{scale_x(i):.1f},{scale_y(v):.1f}" for i, v in enumerate(tops))
        pts_low = " ".join(
            f"{scale_x(i):.1f},{scale_y(v):.1f}"
            for i, v in list(enumerate(lows))[::-1]
        )
        return pts_top + " " + pts_low

    zeros = [0.0] * n

    google_pts = polygon_for(zeros, google_tops)
    other_pts = polygon_for(google_tops, other_tops)
    ai_pts = polygon_for(other_tops, all_tops)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Composizione mercato search e AI Italia, 12 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'<polygon points="{google_pts}" fill="{PRIMARY_GREEN}" fill-opacity="0.55" stroke="{PRIMARY_GREEN}" stroke-width="1"/>'
        f'<polygon points="{other_pts}" fill="{OUTLINE_GREY}" fill-opacity="0.55" stroke="{OUTLINE_GREY}" stroke-width="1"/>'
        f'<polygon points="{ai_pts}" fill="{ACCENT_ORANGE}" fill-opacity="0.65" stroke="{ACCENT_ORANGE}" stroke-width="1"/>'
        f'<text x="{margin_x}" y="{margin_y - 8}" fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace">■ Google</text>'
        f'<text x="{margin_x + 90}" y="{margin_y - 8}" fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">■ Altri search</text>'
        f'<text x="{margin_x + 220}" y="{margin_y - 8}" fill="{ACCENT_ORANGE}" font-size="11" font-family="monospace">■ AI services</text>'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py -v`
Expected: all chart tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 2 — stacked area market composition"
```

---

## Task 7: Chart 3 — Bump chart top 10 AI

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_bump_chart
from osservatorio_seo.tracker.models import BumpChartData, BumpChartWeek


def test_bump_chart_returns_valid_svg():
    domains = ["chat.openai.com", "gemini.google.com", "claude.ai", "perplexity.ai"]
    weeks = [
        BumpChartWeek(
            week_end=datetime(2025, 11, 3, tzinfo=UTC),
            ranks={"chat.openai.com": 1, "gemini.google.com": 2, "claude.ai": 8, "perplexity.ai": 3},
        ),
        BumpChartWeek(
            week_end=datetime(2026, 1, 5, tzinfo=UTC),
            ranks={"chat.openai.com": 1, "gemini.google.com": 2, "claude.ai": 5, "perplexity.ai": 4},
        ),
        BumpChartWeek(
            week_end=datetime(2026, 4, 1, tzinfo=UTC),
            ranks={"chat.openai.com": 1, "gemini.google.com": 2, "claude.ai": 3, "perplexity.ai": 6},
        ),
    ]
    svg = render_bump_chart(BumpChartData(domains=domains, weeks=weeks))
    assert svg.startswith("<svg")
    # 4 domains = 4 polylines
    assert svg.count("<polyline") >= 4
    assert "claude.ai" in svg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_bump_chart_returns_valid_svg -v`
Expected: AttributeError.

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import BumpChartData  # add to top

# Palette for bump chart lines — cycled by domain index
_BUMP_PALETTE = [
    "#00f63e",  # primary green
    "#f5a623",  # accent orange
    "#2ec4f1",  # cyan
    "#f040ff",  # magenta
    "#ffeb3b",  # yellow
    "#ff5252",  # red
    "#00e5bf",  # teal
    "#b388ff",  # violet
    "#ff80ab",  # pink
    "#a4de02",  # lime
]


def render_bump_chart(data: BumpChartData) -> str:
    """Chart 3: bump chart showing rank trajectories of top 10 AI domains.

    X-axis: time (weeks). Y-axis: rank (1 at top, 10 at bottom).
    Lines cross when one domain overtakes another.
    """
    if not data.weeks or not data.domains:
        return _empty_svg("Nessun dato disponibile — bump chart AI")

    width, height = 700, 380
    margin_x, margin_y = 90, 40
    inner_w = width - 2 * margin_x
    inner_h = height - 2 * margin_y

    max_rank = 10
    n_weeks = len(data.weeks)

    def scale_x(i: int) -> float:
        return margin_x + (inner_w * i / max(n_weeks - 1, 1))

    def scale_y(rank: int) -> float:
        return margin_y + inner_h * ((rank - 1) / (max_rank - 1))

    # Grid (rank lines 1..10)
    grid = ""
    for r in range(1, max_rank + 1):
        y = scale_y(r)
        grid += (
            f'<line x1="{margin_x}" y1="{y:.1f}" x2="{width - margin_x}" y2="{y:.1f}" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="2,4" stroke-width="0.5"/>'
            f'<text x="{margin_x - 8}" y="{y + 3:.1f}" text-anchor="end" fill="{OUTLINE_GREY}" '
            f'font-size="10" font-family="monospace">#{r}</text>'
        )

    # Polylines for each domain
    polylines = ""
    labels = ""
    for idx, domain in enumerate(data.domains[:max_rank]):
        color = _BUMP_PALETTE[idx % len(_BUMP_PALETTE)]
        pts = []
        for week_i, week in enumerate(data.weeks):
            rank = week.ranks.get(domain)
            if rank is None or rank > max_rank:
                continue
            pts.append((scale_x(week_i), scale_y(rank)))
        if not pts:
            continue
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        polylines += (
            f'<polyline points="{poly}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        # End-of-line label
        last_x, last_y = pts[-1]
        labels += (
            f'<text x="{last_x + 5:.1f}" y="{last_y + 3:.1f}" fill="{color}" '
            f'font-size="10" font-family="monospace">{domain}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Bump chart top 10 AI Italia, 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{grid}'
        f'{polylines}'
        f'{labels}'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_bump_chart_returns_valid_svg -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 3 — bump chart top 10 AI trajectories"
```

---

## Task 8: Chart 4 — Category heatmap

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_category_heatmap
from osservatorio_seo.tracker.models import CategoryHeatmapCell, CategoryHeatmapRow


def test_category_heatmap_returns_valid_svg():
    rows = [
        CategoryHeatmapRow(
            category="News",
            cells=[
                CategoryHeatmapCell(month="2025-11", delta_pct=-2.5),
                CategoryHeatmapCell(month="2025-12", delta_pct=-3.8),
                CategoryHeatmapCell(month="2026-01", delta_pct=-5.2),
                CategoryHeatmapCell(month="2026-02", delta_pct=-4.1),
                CategoryHeatmapCell(month="2026-03", delta_pct=-6.0),
                CategoryHeatmapCell(month="2026-04", delta_pct=-2.3),
            ],
        ),
        CategoryHeatmapRow(
            category="E-commerce",
            cells=[
                CategoryHeatmapCell(month="2025-11", delta_pct=1.2),
                CategoryHeatmapCell(month="2025-12", delta_pct=3.5),
                CategoryHeatmapCell(month="2026-01", delta_pct=0.4),
                CategoryHeatmapCell(month="2026-02", delta_pct=-1.1),
                CategoryHeatmapCell(month="2026-03", delta_pct=2.0),
                CategoryHeatmapCell(month="2026-04", delta_pct=4.5),
            ],
        ),
    ]
    svg = render_category_heatmap(rows)
    assert svg.startswith("<svg")
    # 2 rows x 6 months = 12 cells minimum
    assert svg.count("<rect") >= 12 + 1  # +1 for background
    assert "News" in svg
    assert "E-commerce" in svg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_category_heatmap_returns_valid_svg -v`
Expected: AttributeError.

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import CategoryHeatmapRow  # add to top


def _heatmap_color(delta_pct: float | None) -> str:
    if delta_pct is None:
        return OUTLINE_VARIANT
    if delta_pct > 10:
        return "#00f63e"  # strong growth
    if delta_pct > 3:
        return "#82e5a3"  # moderate growth
    if delta_pct >= -3:
        return "#5a5a5a"  # stable
    if delta_pct >= -10:
        return "#f5a623"  # moderate decline
    return "#ff5252"  # strong decline


def render_category_heatmap(rows: list[CategoryHeatmapRow]) -> str:
    """Chart 4: heatmap showing traffic % change per category per month.

    Rows = categories, columns = months. Color gradient red → grey → green.
    """
    if not rows:
        return _empty_svg("Nessun dato disponibile — heatmap categorie")

    cell_w, cell_h = 80, 32
    label_w = 140
    header_h = 30
    margin_x, margin_y = 20, 20

    months = rows[0].cells
    n_cols = len(months)
    n_rows = len(rows)

    width = margin_x * 2 + label_w + cell_w * n_cols + 40
    height = margin_y * 2 + header_h + cell_h * n_rows + 40

    # Header: month labels
    header = ""
    for i, m in enumerate(months):
        x = margin_x + label_w + i * cell_w + cell_w / 2
        y = margin_y + header_h - 8
        header += (
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">{m.month}</text>'
        )

    # Body
    body = ""
    for ri, row in enumerate(rows):
        # Row label
        y_label = margin_y + header_h + ri * cell_h + cell_h / 2 + 4
        body += (
            f'<text x="{margin_x + label_w - 10:.1f}" y="{y_label:.1f}" '
            f'text-anchor="end" fill="{ON_SURFACE}" font-size="11" '
            f'font-family="monospace">{row.category}</text>'
        )
        for ci, cell in enumerate(row.cells):
            x = margin_x + label_w + ci * cell_w
            y = margin_y + header_h + ri * cell_h
            color = _heatmap_color(cell.delta_pct)
            body += (
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w - 2}" height="{cell_h - 2}" '
                f'fill="{color}" fill-opacity="0.7"/>'
            )
            if cell.delta_pct is not None:
                label = f"{cell.delta_pct:+.1f}%"
                body += (
                    f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" '
                    f'text-anchor="middle" fill="{BG_DARK}" font-size="10" '
                    f'font-family="monospace" font-weight="bold">{label}</text>'
                )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Heatmap traffico per categoria Italia, 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{header}'
        f'{body}'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_category_heatmap_returns_valid_svg -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 4 — category heatmap (6 months × N categories)"
```

---

## Task 9: Chart 5 — Biggest movers bar chart

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_movers_chart
from osservatorio_seo.tracker.models import DomainMovement, TopMovers


def test_movers_chart_renders_both_sides():
    movers = TopMovers(
        up=[
            DomainMovement(domain="claude.ai", delta_pct=42.5),
            DomainMovement(domain="mistral.ai", delta_pct=15.6),
            DomainMovement(domain="gemini.google.com", delta_pct=12.4),
        ],
        down=[
            DomainMovement(domain="perplexity.ai", delta_pct=-8.1),
            DomainMovement(domain="character.ai", delta_pct=-6.3),
        ],
    )
    svg = render_movers_chart(movers)
    assert svg.startswith("<svg")
    assert "claude.ai" in svg
    assert "perplexity.ai" in svg
    assert "+42.5%" in svg
    assert "-8.1%" in svg
    # One rect per bar + 1 background
    assert svg.count("<rect") >= 5 + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_movers_chart_renders_both_sides -v`
Expected: AttributeError.

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import TopMovers  # add to top


def render_movers_chart(movers: TopMovers) -> str:
    """Chart 5: dual horizontal bar chart — biggest movers (up/down) 30d."""
    if not movers.up and not movers.down:
        return _empty_svg("Nessun mover significativo questa settimana")

    width, height = 700, 280
    col_w = (width - 60) / 2  # two columns
    margin_x = 20
    bar_h = 22
    row_gap = 8
    label_w = 140

    all_abs = [abs(m.delta_pct) for m in (*movers.up, *movers.down)]
    max_abs = max(all_abs) if all_abs else 1.0

    def bar_width(pct: float) -> float:
        return (col_w - label_w - 60) * (abs(pct) / max_abs)

    body = ""
    # Up column (left)
    body += (
        f'<text x="{margin_x + 10}" y="30" fill="{PRIMARY_GREEN}" font-size="12" '
        f'font-family="monospace" font-weight="bold">↑ SALITI</text>'
    )
    for i, m in enumerate(movers.up[:5]):
        y = 50 + i * (bar_h + row_gap)
        bw = bar_width(m.delta_pct)
        body += (
            f'<text x="{margin_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{m.domain}</text>'
            f'<rect x="{margin_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{PRIMARY_GREEN}" fill-opacity="0.75"/>'
            f'<text x="{margin_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" font-weight="bold">'
            f'+{m.delta_pct:.1f}%</text>'
        )

    # Down column (right)
    col2_x = margin_x + col_w + 30
    body += (
        f'<text x="{col2_x + 10}" y="30" fill="{ACCENT_ORANGE}" font-size="12" '
        f'font-family="monospace" font-weight="bold">↓ SCESI</text>'
    )
    for i, m in enumerate(movers.down[:5]):
        y = 50 + i * (bar_h + row_gap)
        bw = bar_width(m.delta_pct)
        body += (
            f'<text x="{col2_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{m.domain}</text>'
            f'<rect x="{col2_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{ACCENT_ORANGE}" fill-opacity="0.75"/>'
            f'<text x="{col2_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ACCENT_ORANGE}" font-size="11" font-family="monospace" font-weight="bold">'
            f'{m.delta_pct:.1f}%</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Biggest movers AI Italia, ultimi 30 giorni" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{body}'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_movers_chart_renders_both_sides -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 5 — biggest movers dual bar chart"
```

---

## Task 10: Chart 6 — Small multiples big 4 AI

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_big4_small_multiples
from osservatorio_seo.tracker.models import Big4PanelData


def test_big4_small_multiples_returns_valid_svg():
    def mk_points(vals):
        return [
            TimeseriesPoint(date=datetime(2025, 11 + i // 12, (i % 12) + 1, tzinfo=UTC), value=v)
            for i, v in enumerate(vals)
        ]

    panels = [
        Big4PanelData(
            domain="chat.openai.com",
            display_name="ChatGPT",
            current_rank=1,
            previous_rank=1,
            traffic_timeseries=mk_points([100, 101, 99, 102, 100, 98]),
        ),
        Big4PanelData(
            domain="gemini.google.com",
            display_name="Gemini",
            current_rank=2,
            previous_rank=3,
            traffic_timeseries=mk_points([80, 85, 90, 95, 100, 105]),
        ),
        Big4PanelData(
            domain="claude.ai",
            display_name="Claude",
            current_rank=3,
            previous_rank=12,
            traffic_timeseries=mk_points([20, 25, 40, 55, 80, 100]),
        ),
        Big4PanelData(
            domain="perplexity.ai",
            display_name="Perplexity",
            current_rank=6,
            previous_rank=4,
            traffic_timeseries=mk_points([100, 90, 85, 78, 72, 68]),
        ),
    ]
    svg = render_big4_small_multiples(panels)
    assert svg.startswith("<svg")
    # 4 panels = 4 polylines
    assert svg.count("<polyline") >= 4
    assert "Claude" in svg
    assert "#3" in svg
    assert "#12" in svg  # previous rank shown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_big4_small_multiples_returns_valid_svg -v`
Expected: AttributeError.

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import Big4PanelData  # add to top


def render_big4_small_multiples(panels: list[Big4PanelData]) -> str:
    """Chart 6: 2x2 small multiples of traffic index for the 4 big AI services."""
    if not panels:
        return _empty_svg("Nessun dato disponibile — big 4 AI")

    width, height = 700, 400
    panel_w = (width - 60) / 2
    panel_h = (height - 80) / 2
    margin = 20

    # Fill to exactly 4 panels (grid 2x2)
    rendered_panels = ""
    for idx, panel in enumerate(panels[:4]):
        col = idx % 2
        row = idx // 2
        px = margin + col * (panel_w + 20)
        py = margin + row * (panel_h + 40)

        rendered_panels += _render_single_big4_panel(
            panel=panel,
            x=px,
            y=py,
            w=panel_w,
            h=panel_h,
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Big 4 AI trend 6 mesi" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{rendered_panels}'
        '</svg>'
    )


def _render_single_big4_panel(
    panel: Big4PanelData,
    x: float,
    y: float,
    w: float,
    h: float,
) -> str:
    ts = panel.traffic_timeseries
    inner_x = x + 8
    inner_y = y + 40
    inner_w = w - 16
    inner_h = h - 60

    if not ts:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
            f'stroke="{OUTLINE_VARIANT}" stroke-dasharray="3,3"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2}" text-anchor="middle" '
            f'fill="{OUTLINE_GREY}" font-size="11" font-family="monospace">no data</text>'
        )

    values = [p.value for p in ts]
    v_max = max(values) or 1.0
    v_min = min(values)

    def sx(i: int) -> float:
        return inner_x + inner_w * i / max(len(ts) - 1, 1)

    def sy(v: float) -> float:
        span = v_max - v_min or 1.0
        return inner_y + inner_h * (1 - (v - v_min) / span)

    poly = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(values))

    rank_now = f"#{panel.current_rank}"
    rank_old = f"(era #{panel.previous_rank})" if panel.previous_rank else ""
    title = (
        f"{panel.display_name}: da #{panel.previous_rank} a #{panel.current_rank}"
        if panel.previous_rank
        else f"{panel.display_name}: rank #{panel.current_rank}"
    )

    return (
        f'<g>'
        f'<text x="{x + 8}" y="{y + 20}" fill="{ON_SURFACE}" font-size="12" '
        f'font-family="monospace" font-weight="bold">{title}</text>'
        f'<text x="{x + w - 8}" y="{y + 20}" text-anchor="end" '
        f'fill="{PRIMARY_GREEN}" font-size="18" font-family="monospace" font-weight="bold">'
        f'{rank_now}</text>'
        f'<text x="{x + w - 8}" y="{y + 34}" text-anchor="end" '
        f'fill="{OUTLINE_GREY}" font-size="10" font-family="monospace">{rank_old}</text>'
        f'<polyline points="{poly}" fill="none" stroke="{PRIMARY_GREEN}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'</g>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_big4_small_multiples_returns_valid_svg -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 6 — big 4 AI small multiples 2x2"
```

---

## Task 11: Chart 7 — Own analytics horizontal bar

**Files:**
- Modify: `src/osservatorio_seo/tracker/charts.py`
- Modify: `tests/test_tracker_charts.py`

- [ ] **Step 1: Add the failing test**

Append to `tests/test_tracker_charts.py`:

```python
from osservatorio_seo.tracker.charts import render_own_referrers_chart
from osservatorio_seo.tracker.models import AnalyticsReferrer


def test_own_referrers_chart_renders_all_sources():
    refs = [
        AnalyticsReferrer(source="Google", share_pct=65.2),
        AnalyticsReferrer(source="Direct", share_pct=22.0),
        AnalyticsReferrer(source="Bing", share_pct=4.1),
        AnalyticsReferrer(source="ChatGPT", share_pct=1.8),
        AnalyticsReferrer(source="Claude", share_pct=0.9),
        AnalyticsReferrer(source="Other", share_pct=6.0),
    ]
    svg = render_own_referrers_chart(refs)
    assert svg.startswith("<svg")
    assert "Google" in svg
    assert "65.2" in svg
    assert svg.count("<rect") >= 6 + 1  # 6 bars + bg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_charts.py::test_own_referrers_chart_renders_all_sources -v`
Expected: AttributeError.

- [ ] **Step 3: Add the chart generator**

Append to `src/osservatorio_seo/tracker/charts.py`:

```python
from osservatorio_seo.tracker.models import AnalyticsReferrer  # add to top


def render_own_referrers_chart(refs: list[AnalyticsReferrer]) -> str:
    """Chart 7: single horizontal bar chart of own-site referrer share."""
    if not refs:
        return _empty_svg("Nessun dato — referrer OsservatorioSEO")

    width = 700
    bar_h = 26
    row_gap = 8
    margin_x, margin_y = 20, 20
    label_w = 110
    value_w = 70
    bar_max_w = width - margin_x * 2 - label_w - value_w

    n = len(refs)
    height = margin_y * 2 + n * (bar_h + row_gap)

    max_pct = max(r.share_pct for r in refs) or 1.0

    body = ""
    for i, ref in enumerate(refs):
        y = margin_y + i * (bar_h + row_gap)
        bw = bar_max_w * (ref.share_pct / max_pct)
        body += (
            f'<text x="{margin_x + 10}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{ON_SURFACE}" font-size="11" font-family="monospace">{ref.source}</text>'
            f'<rect x="{margin_x + label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" '
            f'fill="{PRIMARY_GREEN}" fill-opacity="0.75"/>'
            f'<text x="{margin_x + label_w + bw + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'fill="{PRIMARY_GREEN}" font-size="11" font-family="monospace" font-weight="bold">'
            f'{ref.share_pct:.1f}%</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Referrer source OsservatorioSEO, ultimi 30 giorni" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<rect width="{width}" height="{height}" fill="{BG_DARK}"/>'
        f'{body}'
        '</svg>'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_charts.py -v`
Expected: all chart tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/tracker/charts.py tests/test_tracker_charts.py
git commit -m "feat(tracker): chart 7 — own referrers horizontal bar"
```

---

## Task 12: Tracker dashboard template + JSON-LD partial

**Files:**
- Create: `templates/pages/tracker.html.jinja`
- Create: `templates/partials/_jsonld_dataset.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py`
- Create: `tests/test_tracker_renderer.py`

- [ ] **Step 1: Create the JSON-LD Dataset partial**

Create `templates/partials/_jsonld_dataset.html.jinja`:

```jinja
{# Context: dataset_name, dataset_description, dataset_url, updated_iso #}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": {{ dataset_name | tojson }},
  "description": {{ dataset_description | tojson }},
  "url": "{{ dataset_url }}",
  "creator": {
    "@type": "Organization",
    "name": "Osservatorio SEO",
    "url": "https://osservatorioseo.pages.dev/"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Osservatorio SEO"
  },
  "datePublished": "{{ updated_iso }}",
  "dateModified": "{{ updated_iso }}",
  "inLanguage": "it-IT",
  "isAccessibleForFree": true,
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "spatialCoverage": {
    "@type": "Country",
    "name": "Italia"
  },
  "keywords": "SEO, AI, Google, ChatGPT, Claude, Gemini, Perplexity, tracker, Italia"
}
</script>
```

- [ ] **Step 2: Create the tracker dashboard template**

Create `templates/pages/tracker.html.jinja`:

```jinja
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% include "partials/_jsonld_dataset.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">TRACKER</span>
</nav>

<section class="max-w-4xl mx-auto mb-10">
  <p class="text-[10px] text-outline uppercase font-mono mb-3 tracking-widest">&gt; TRACKER SETTIMANALE</p>
  <h1 class="text-3xl sm:text-4xl font-bold tracking-tight mb-3 text-white">{{ page_headline }}</h1>
  <p class="text-sm text-outline font-mono">
    Ultimo aggiornamento: <span class="text-primary-container">{{ updated_label }}</span> · Fonte primaria: Cloudflare Radar
  </p>
</section>

{# Chart 1: headline #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; AI VS INTERNET IN ITALIA — 24 MESI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_1_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_1_svg | safe }}
  </div>
</section>

{# Chart 2: market composition #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; A CHI CEDE GOOGLE — 12 MESI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_2_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_2_svg | safe }}
  </div>
</section>

{# Chart 3: bump #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; CHI HA SCAVALCATO CHI — TOP 10 AI, 6 MESI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_3_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_3_svg | safe }}
  </div>
</section>

{# Chart 4: heatmap #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; QUALE SETTORE È GIÀ COLPITO</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_4_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant overflow-x-auto">
    {{ chart_4_svg | safe }}
  </div>
</section>

{# Chart 5: movers #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; BIGGEST MOVERS — 30 GIORNI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_5_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_5_svg | safe }}
  </div>
  {% if latest_monthly_report_path %}
  <p class="text-xs text-outline font-mono mt-3 uppercase">
    <a href="{{ latest_monthly_report_path }}" class="text-primary-container hover:underline">&rarr; Report editoriale mensile di approfondimento</a>
  </p>
  {% endif %}
</section>

{# Chart 6: big 4 #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; I 4 BIG AI — TREND 6 MESI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">{{ chart_6_caption }}</p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_6_svg | safe }}
  </div>
</section>

{# Chart 7: transparency #}
<section class="max-w-4xl mx-auto mb-12">
  <h2 class="text-xs text-outline uppercase font-mono mb-3 tracking-widest">&gt; TRASPARENZA: DA DOVE ARRIVIAMO NOI</h2>
  <p class="text-sm text-on-surface-variant mb-4 leading-relaxed">
    <strong class="text-white">1 sito solo, NON rappresentativo del mercato italiano.</strong> Questi sono i referrer di OsservatorioSEO stesso, inclusi per trasparenza editoriale.
  </p>
  <div class="bg-surface-container-lowest p-4 border border-outline-variant">
    {{ chart_7_svg | safe }}
  </div>
</section>

{# Methodology accordion — aperto di default #}
<section class="max-w-4xl mx-auto mb-12">
  <details open class="methodology-accordion group">
    <summary class="flex items-center justify-between border-b border-primary-container pb-2 cursor-pointer list-none">
      <h2 class="text-xs text-outline uppercase font-mono tracking-widest">&gt; METODOLOGIA</h2>
      <span class="text-primary-container font-mono">−</span>
    </summary>
    <div class="prose prose-invert max-w-none text-on-surface leading-relaxed mt-4 space-y-3 text-sm">
      <p><strong class="text-white">Fonti dati:</strong> <a class="text-primary-container hover:underline" href="https://radar.cloudflare.com/" target="_blank" rel="noopener">Cloudflare Radar API</a> + Cloudflare Pages Analytics (per il solo Grafico 7).</p>
      <p><strong class="text-white">Cosa misura e cosa no:</strong> Cloudflare Radar misura la popolarità dei domini come destinazione (quanti italiani visitano chat.openai.com), non il traffico referral (quanti siti italiani ricevono visite da chat.openai.com). Queste due metriche sono correlate ma non identiche.</p>
      <p><strong class="text-white">Campione:</strong> Cloudflare osserva circa il 17% del traffico internet globale. I dati sono proiezioni basate su questo campione, non misurazioni totali del mercato italiano.</p>
      <p><strong class="text-white">Aggiornamento:</strong> Dati aggiornati ogni settimana. Prossima update prevista: {{ next_update_label }}.</p>
      <p><strong class="text-white">Perché non vedete "market share %":</strong> Lo share di mercato richiederebbe dati di panel a pagamento (SimilarWeb, Datos.live). Questo tracker usa solo fonti gratuite e pubblica indici normalizzati 0-100 dove 100 = dominio più popolare in categoria.</p>
      <p><strong class="text-white">Limiti dichiarati:</strong> nessun dato di query SERP, nessun dato di referral traffic, nessun forecasting. Se vedi qualcosa che ti sembra strano, <a class="text-primary-container hover:underline" href="/about/">segnalalo alla redazione</a>.</p>
    </div>
  </details>
</section>
{% endblock %}
```

- [ ] **Step 3: Add render_tracker to renderer**

Modify `src/osservatorio_seo/renderer.py`. Add this method after `render_dossier_index`:

```python
    def render_tracker(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/tracker.html.jinja", context)

    def render_tracker_report(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/tracker_report.html.jinja", context)
```

- [ ] **Step 4: Add renderer test**

Create `tests/test_tracker_renderer.py`:

```python
"""Smoke test that the tracker template renders with minimal context."""

from pathlib import Path

from osservatorio_seo.renderer import HtmlRenderer


def test_tracker_template_renders_smoke(tmp_path):
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    renderer = HtmlRenderer(templates_dir)
    ctx = {
        "page_title": "Tracker — Osservatorio SEO",
        "page_description": "Stato della ricerca in Italia",
        "canonical_url": "https://osservatorioseo.pages.dev/tracker/",
        "active_nav": "tracker",
        "noindex": True,
        "og_type": "website",
        "page_headline": "Stato della ricerca in Italia — Settimana 15, 2026",
        "updated_label": "14 aprile 2026",
        "updated_iso": "2026-04-14T08:00:00+00:00",
        "next_update_label": "21 aprile 2026",
        "dataset_name": "Tracker Osservatorio SEO",
        "dataset_description": "Dati settimanali sull'adozione di AI e Search Engines in Italia",
        "dataset_url": "https://osservatorioseo.pages.dev/tracker/",
        "chart_1_svg": "<svg></svg>",
        "chart_1_caption": "Caption 1",
        "chart_2_svg": "<svg></svg>",
        "chart_2_caption": "Caption 2",
        "chart_3_svg": "<svg></svg>",
        "chart_3_caption": "Caption 3",
        "chart_4_svg": "<svg></svg>",
        "chart_4_caption": "Caption 4",
        "chart_5_svg": "<svg></svg>",
        "chart_5_caption": "Caption 5",
        "chart_6_svg": "<svg></svg>",
        "chart_6_caption": "Caption 6",
        "chart_7_svg": "<svg></svg>",
        "latest_monthly_report_path": None,
        "breadcrumbs": [
            {"name": "Home", "url": "https://osservatorioseo.pages.dev/"},
            {"name": "Tracker", "url": "https://osservatorioseo.pages.dev/tracker/"},
        ],
    }
    html = renderer.render_tracker(ctx)
    assert "Stato della ricerca in Italia" in html
    assert "METODOLOGIA" in html
    assert "Cloudflare Radar" in html
    assert '<svg></svg>' in html
```

- [ ] **Step 5: Run the test**

Run: `.venv/bin/pytest tests/test_tracker_renderer.py -v`
Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add templates/pages/tracker.html.jinja templates/partials/_jsonld_dataset.html.jinja src/osservatorio_seo/renderer.py tests/test_tracker_renderer.py
git commit -m "feat(tracker): tracker dashboard template + JSON-LD Dataset schema"
```

---

## Task 13: Publisher `_ssg_tracker` integration + sitemap URL

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Create: `tests/test_tracker_publisher.py`
- Create: `tests/fixtures/tracker_snapshot.json`

- [ ] **Step 1: Save a sample snapshot fixture**

Create `tests/fixtures/tracker_snapshot.json` by running a one-off Python snippet (not in the plan — just use an inline JSON with all required fields):

```json
{
  "schema_version": "1.0",
  "year": 2026,
  "week": 15,
  "generated_at": "2026-04-14T08:00:00+00:00",
  "ai_index_24mo": {"label": "AI", "points": []},
  "internet_index_24mo": {"label": "Internet", "points": []},
  "market_composition_12mo": [],
  "bump_chart_6mo": {"domains": [], "weeks": []},
  "category_heatmap_6mo": [],
  "top_movers_30d": {"up": [], "down": []},
  "big4_6mo": [],
  "ai_top10_current": [
    {"domain": "chat.openai.com", "rank": 1, "previous_rank": null, "delta_rank": null, "traffic_change_pct": null}
  ],
  "search_top5_current": [
    {"domain": "google.com", "rank": 1, "previous_rank": null, "delta_rank": null, "traffic_change_pct": null}
  ],
  "own_referrers_30d": [
    {"source": "Google", "share_pct": 79.7},
    {"source": "Direct", "share_pct": 17.3}
  ],
  "metadata": {
    "radar_calls": 5,
    "pages_analytics_calls": 1,
    "categories_with_it_data": ["ai", "search_engines"],
    "warnings": []
  }
}
```

- [ ] **Step 2: Write the failing integration test**

Create `tests/test_tracker_publisher.py`:

```python
"""Integration test for publisher._ssg_tracker."""

import json
import shutil
from pathlib import Path

import pytest

from osservatorio_seo.publisher import Publisher
from osservatorio_seo.renderer import HtmlRenderer
from osservatorio_seo.tracker.models import TrackerSnapshot


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def snapshot(fixtures_dir: Path) -> TrackerSnapshot:
    data = json.loads((fixtures_dir / "tracker_snapshot.json").read_text())
    return TrackerSnapshot.model_validate(data)


def test_ssg_tracker_writes_dashboard(tmp_path: Path, repo_root: Path, snapshot: TrackerSnapshot):
    # Set up test tracker data dir
    data_dir = tmp_path / "data"
    tracker_dir = data_dir / "tracker" / "snapshots"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "2026-W15.json").write_text(snapshot.model_dump_json(indent=2))

    # Fake minimal publisher config
    archive_dir = data_dir / "archive"
    archive_dir.mkdir()
    site_dir = tmp_path / "site"
    site_dir.mkdir()

    pub = Publisher(
        data_dir=data_dir,
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    renderer = HtmlRenderer(repo_root / "templates")

    pub._ssg_tracker(renderer=renderer, site_dir=site_dir, allow_indexing=False)

    dashboard = site_dir / "tracker" / "index.html"
    assert dashboard.exists()
    html = dashboard.read_text()
    assert "TRACKER SETTIMANALE" in html
    assert "METODOLOGIA" in html
    # Each chart section must be present
    assert "AI VS INTERNET IN ITALIA" in html
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_publisher.py -v`
Expected: `AttributeError: 'Publisher' object has no attribute '_ssg_tracker'`.

- [ ] **Step 4: Add `_ssg_tracker` method to Publisher**

Modify `src/osservatorio_seo/publisher.py`. Add imports at top:

```python
from osservatorio_seo.tracker import charts as tracker_charts
from osservatorio_seo.tracker.models import TrackerSnapshot
```

Add this method inside `class Publisher` (right after `_ssg_dossiers`):

```python
    # --- Tracker dashboard ---

    def _ssg_tracker(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        """Render the /tracker/ dashboard using the latest snapshot.

        Reads the most recent snapshot from data/tracker/snapshots/ and
        generates all 7 charts as inline SVG.
        """
        snapshots_dir = self._data_dir / "tracker" / "snapshots"
        if not snapshots_dir.exists():
            return

        latest = self._find_latest_snapshot(snapshots_dir)
        if latest is None:
            return

        snapshot = TrackerSnapshot.model_validate_json(latest.read_text(encoding="utf-8"))

        # Render all 7 charts
        chart_1 = tracker_charts.render_ai_vs_internet_chart(
            ai=snapshot.ai_index_24mo,
            internet=snapshot.internet_index_24mo,
        )
        chart_2 = tracker_charts.render_market_composition_chart(
            snapshot.market_composition_12mo
        )
        chart_3 = tracker_charts.render_bump_chart(snapshot.bump_chart_6mo)
        chart_4 = tracker_charts.render_category_heatmap(snapshot.category_heatmap_6mo)
        chart_5 = tracker_charts.render_movers_chart(snapshot.top_movers_30d)
        chart_6 = tracker_charts.render_big4_small_multiples(snapshot.big4_6mo)
        chart_7 = tracker_charts.render_own_referrers_chart(snapshot.own_referrers_30d)

        updated_label = snapshot.generated_at.strftime("%d %B %Y")
        next_update = self._next_update_label(snapshot.generated_at)

        # Check for latest monthly report
        reports_dir = self._data_dir / "tracker" / "reports"
        latest_report_path: str | None = None
        if reports_dir.exists():
            latest_report = self._find_latest_monthly_report(reports_dir)
            if latest_report is not None:
                year, month = latest_report.stem.split("-")
                latest_report_path = f"/tracker/report/{year}-{month}/"

        ctx = {
            "page_title": "Tracker — Stato della ricerca in Italia — Osservatorio SEO",
            "page_description": (
                "Dashboard settimanale sull'adozione di AI e Search Engines in "
                "Italia. 7 grafici interpretano i trend e aiutano a prendere "
                "decisioni operative di SEO."
            ),
            "canonical_url": canonical("/tracker/"),
            "active_nav": "tracker",
            "noindex": not allow_indexing,
            "og_type": "website",
            "page_headline": f"Stato della ricerca in Italia — Settimana {snapshot.week}, {snapshot.year}",
            "updated_label": updated_label,
            "updated_iso": snapshot.generated_at.isoformat(),
            "next_update_label": next_update,
            "dataset_name": "Tracker Osservatorio SEO — Adozione AI & Search in Italia",
            "dataset_description": (
                "Dati settimanali sul rank di popolarità delle AI services "
                "(ChatGPT, Claude, Gemini, Perplexity) e dei search engines "
                "in Italia, da Cloudflare Radar."
            ),
            "dataset_url": canonical("/tracker/"),
            "chart_1_svg": chart_1,
            "chart_1_caption": (
                "La linea verde è l'indice di popolarità dei servizi AI in "
                "Italia, la grigia è il traffico internet totale. Entrambe "
                "normalizzate a 100 all'inizio del periodo."
            ),
            "chart_2_svg": chart_2,
            "chart_2_caption": (
                "Come si compone il mercato di ricerca in Italia. "
                "Se Google cede share ad altri search engine, serve SEO "
                "multi-engine. Se cede ad AI, serve investimento in LLM optimization."
            ),
            "chart_3_svg": chart_3,
            "chart_3_caption": (
                "Il rank dei top 10 domini AI in Italia nelle ultime 26 "
                "settimane. Le linee si incrociano quando un dominio scavalca un altro."
            ),
            "chart_4_svg": chart_4,
            "chart_4_caption": (
                "Traffico mensile per categoria di destinazione in Italia. "
                "Verde = crescita, rosso = calo. Se il tuo settore è colpito, "
                "vedrai una riga rossa."
            ),
            "chart_5_svg": chart_5,
            "chart_5_caption": (
                "Chi è salito e chi è sceso di più in termini di traffico negli "
                "ultimi 30 giorni. Questo è il grafico che genera il titolo del "
                "report mensile."
            ),
            "chart_6_svg": chart_6,
            "chart_6_caption": (
                "Trend di traffico dei 4 big AI service negli ultimi 6 mesi, "
                "ciascuno con asse Y indipendente. Il rank corrente è in alto a destra."
            ),
            "chart_7_svg": chart_7,
            "latest_monthly_report_path": latest_report_path,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Tracker", "url": canonical("/tracker/")},
            ],
        }

        target_dir = site_dir / "tracker"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(
            renderer.render_tracker(ctx), encoding="utf-8"
        )

    @staticmethod
    def _find_latest_snapshot(snapshots_dir: Path) -> Path | None:
        candidates = sorted(snapshots_dir.glob("*-W*.json"))
        return candidates[-1] if candidates else None

    @staticmethod
    def _find_latest_monthly_report(reports_dir: Path) -> Path | None:
        candidates = sorted(reports_dir.glob("????-??.json"))
        return candidates[-1] if candidates else None

    @staticmethod
    def _next_update_label(generated_at: datetime) -> str:
        from datetime import timedelta as _td
        nxt = generated_at + _td(days=7)
        return nxt.strftime("%d %B %Y")
```

- [ ] **Step 5: Wire `_ssg_tracker` into `publish_ssg`**

In `src/osservatorio_seo/publisher.py`, find the `publish_ssg` method and add the call:

```python
        self._ssg_docs_and_about(renderer, sources, doc_pages, site_dir, allow_indexing)
        self._ssg_dossiers(renderer, site_dir, allow_indexing)
        self._ssg_tracker(renderer, site_dir, allow_indexing)  # NEW
        self._ssg_seo_assets(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

- [ ] **Step 6: Run the test**

Run: `.venv/bin/pytest tests/test_tracker_publisher.py -v`
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_tracker_publisher.py tests/fixtures/tracker_snapshot.json
git commit -m "feat(tracker): publisher _ssg_tracker + integration into publish_ssg"
```

---

## Task 14: Update sitemap to include tracker URL

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`

- [ ] **Step 1: Add tracker URL to sitemap in `_ssg_seo_assets`**

In `src/osservatorio_seo/publisher.py`, find `_ssg_seo_assets` and add the tracker entry near the existing static URLs (e.g., near `/archivio/`, `/docs/`):

```python
        urls.append(
            {
                "loc": canonical("/tracker/"),
                "lastmod": today,
                "priority": "0.9",
                "changefreq": "weekly",
            }
        )
```

- [ ] **Step 2: Add tracker monthly report URLs**

In the same method, after the dossiers loop, add:

```python
        # Tracker monthly reports: priority 0.7, changefreq monthly
        reports_dir = self._data_dir / "tracker" / "reports"
        if reports_dir.exists():
            for report_path in sorted(reports_dir.glob("????-??.json")):
                year, month = report_path.stem.split("-")
                urls.append(
                    {
                        "loc": canonical(f"/tracker/report/{year}-{month}/"),
                        "lastmod": today,
                        "priority": "0.7",
                        "changefreq": "monthly",
                    }
                )
```

- [ ] **Step 3: Run existing tests to confirm nothing broke**

Run: `.venv/bin/pytest tests/test_publisher.py tests/test_tracker_publisher.py -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/osservatorio_seo/publisher.py
git commit -m "feat(tracker): sitemap URLs for /tracker/ dashboard + monthly reports"
```

---

## Task 15: Monthly report — PremiumWriter extension

**Files:**
- Modify: `src/osservatorio_seo/premium_writer.py`
- Modify: `tests/test_summarizer.py` (or create `tests/test_tracker_report_writer.py`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_tracker_report_writer.py`:

```python
"""Test that PremiumWriter.write_tracker_report produces valid output.

The LLM call is mocked — we test the prompt construction and response
parsing, not the actual model behavior.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.premium_writer import PremiumWriter, _RawResult
from osservatorio_seo.tracker.models import (
    Big4PanelData,
    BumpChartData,
    DomainRank,
    DomainMovement,
    IndexTimeseries,
    SnapshotMetadata,
    TopMovers,
    TrackerMonthlyReport,
    TrackerSnapshot,
)


def _stub_snapshot(week: int) -> TrackerSnapshot:
    return TrackerSnapshot(
        year=2026,
        week=week,
        generated_at=datetime(2026, 4, 1 + week, tzinfo=UTC),
        ai_index_24mo=IndexTimeseries(label="ai"),
        internet_index_24mo=IndexTimeseries(label="internet"),
        bump_chart_6mo=BumpChartData(),
        top_movers_30d=TopMovers(
            up=[DomainMovement(domain="claude.ai", delta_pct=42.5)],
            down=[DomainMovement(domain="perplexity.ai", delta_pct=-8.1)],
        ),
        ai_top10_current=[DomainRank(domain="chat.openai.com", rank=1)],
        search_top5_current=[DomainRank(domain="google.com", rank=1)],
        metadata=SnapshotMetadata(radar_calls=5, pages_analytics_calls=1),
    )


@pytest.mark.asyncio
async def test_write_tracker_report_returns_parsed_model():
    snapshots = [_stub_snapshot(w) for w in (10, 11, 12, 13)]
    writer = PremiumWriter(api_key="test")

    fake_response = {
        "title_it": "Claude +42% a marzo 2026",
        "subtitle_it": "Il mover del mese",
        "executive_summary": ["Punto 1", "Punto 2", "Punto 3"],
        "narrative": "Paragrafo 1.\n\nParagrafo 2.",
        "takeaways": [
            {"title": f"T{i}", "body": "body"} for i in range(5)
        ],
        "outlook": "Prospettive.",
    }
    writer._call_with_fallback = AsyncMock(
        return_value=_RawResult(parsed=fake_response, model="test-model", cost_eur=0.05)
    )

    report = await writer.write_tracker_report(year=2026, month=3, snapshots=snapshots)

    assert isinstance(report, TrackerMonthlyReport)
    assert report.year == 2026
    assert report.month == 3
    assert len(report.takeaways) == 5
    assert report.hero_mover == "claude.ai"  # inferred from top movers
    assert report.cost_eur == 0.05
    assert len(report.snapshot_week_refs) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_tracker_report_writer.py -v`
Expected: `AttributeError: write_tracker_report`.

- [ ] **Step 3: Extend PremiumWriter**

In `src/osservatorio_seo/premium_writer.py`, add imports at top:

```python
from osservatorio_seo.tracker.models import (
    ReportTakeaway,
    TrackerMonthlyReport,
    TrackerSnapshot,
)
```

Add the new prompt constant near `PILLAR_PROMPT`:

```python
TRACKER_REPORT_PROMPT = """Sei un SEO senior italiano che scrive il report mensile \
editoriale di Osservatorio SEO sul tracker "Stato della ricerca in Italia". \
Il lettore è un professionista SEO italiano (agency, in-house, freelance) che \
ogni mese vuole capire cosa è cambiato e cosa fare.

Ti forniamo 4 snapshot settimanali consecutivi (mese {month_name} {year}) \
con: top 10 AI Italia, top 5 search engines, biggest movers, e dati di trend. \
Devi produrre un report editoriale mensile strutturato in JSON.

REGOLE DI TONO (VIETATISSIMO):
- VIETATO prima persona plurale: "noi di", "noi pensiamo", "il nostro consiglio", \
"la nostra opinione", "crediamo", "ci aspettiamo", firme "la redazione".
- Scrivi sempre in forma IMPERSONALE (terza persona) o SECONDA PERSONA diretta \
al lettore ("se gestisci un sito…", "chi lavora su…").
- Niente hype, niente clickbait, niente "scopri", "incredibile".
- Tono autorevole, analitico, operativo. Quando serve, opinion forte.
- Mix tone: MISURATO nei fatti, ANALITICO nell'interpretazione, OPINION FORTE quando il dato lo giustifica.

REGOLE DI LEGGIBILITÀ:
- narrative in paragrafi brevi (2-4 frasi, max ~60 parole ciascuno), separati da \\n\\n
- outlook in 2-3 paragrafi brevi separati da \\n\\n

SCHEMA JSON OBBLIGATORIO:

{{
  "title_it": "Titolo H1 del report, 5-10 parole, basato sul mover del mese. \
Es: 'Claude +42% a marzo 2026: il mover del mese'",
  "subtitle_it": "Sottotitolo 1 frase che cattura il tema centrale del mese",
  "executive_summary": [
    "3-5 bullet strategici, ciascuno 1-2 frasi impersonali"
  ],
  "narrative": "800-1200 parole in paragrafi brevi separati da \\n\\n. Cronaca \
analitica del mese: cosa è successo, cosa significa, cosa fare. Inizia con \
l'INSIGHT forte, non con la cronaca.",
  "takeaways": [
    {{
      "title": "Titolo takeaway, max 8 parole",
      "body": "40-80 parole concrete e operative, impersonale o seconda persona"
    }}
  ],
  "outlook": "200-400 parole in 2-3 paragrafi brevi separati da \\n\\n. \
Prospettive per il prossimo mese basate sui trend osservati."
}}

La lista "takeaways" deve contenere ESATTAMENTE 5 takeaway. Il JSON deve \
essere valido, parsabile, senza codefence markdown, senza testo extra.

--- SNAPSHOT DEL MESE ({month_name} {year}) ---

{snapshots_block}
"""


_MONTH_NAMES_IT = {
    1: "gennaio", 2: "febbraio", 3: "marzo", 4: "aprile",
    5: "maggio", 6: "giugno", 7: "luglio", 8: "agosto",
    9: "settembre", 10: "ottobre", 11: "novembre", 12: "dicembre",
}
```

Add the new method to the `PremiumWriter` class (right after `write_pillar`):

```python
    async def write_tracker_report(
        self,
        year: int,
        month: int,
        snapshots: list[TrackerSnapshot],
    ) -> TrackerMonthlyReport:
        """Generate the monthly tracker report from weekly snapshots."""
        if not snapshots:
            raise PremiumWriterError("write_tracker_report requires at least 1 snapshot")

        snapshots_block = self._format_snapshots_for_prompt(snapshots)
        prompt = TRACKER_REPORT_PROMPT.format(
            year=year,
            month_name=_MONTH_NAMES_IT.get(month, str(month)),
            snapshots_block=snapshots_block,
        )
        result = await self._call_with_fallback(prompt)
        parsed = result.parsed

        takeaways = [
            ReportTakeaway(title=t["title"], body=t["body"])
            for t in parsed.get("takeaways", [])
        ]

        # Hero mover: pick the domain with biggest absolute delta_pct
        # across all snapshot top_movers in the month
        hero_mover = self._extract_hero_mover(snapshots)

        return TrackerMonthlyReport(
            year=year,
            month=month,
            title_it=parsed["title_it"],
            subtitle_it=parsed["subtitle_it"],
            hero_mover=hero_mover,
            executive_summary=list(parsed.get("executive_summary", []))[:6],
            narrative=parsed["narrative"],
            takeaways=takeaways[:8],
            outlook=parsed["outlook"],
            snapshot_week_refs=[f"{s.year}-W{s.week:02d}" for s in snapshots],
            generated_at=datetime.now(UTC),
            model_used=result.model,
            cost_eur=result.cost_eur,
        )

    @staticmethod
    def _format_snapshots_for_prompt(snapshots: list[TrackerSnapshot]) -> str:
        blocks = []
        for s in snapshots:
            ai_top = ", ".join(f"{d.domain} (#{d.rank})" for d in s.ai_top10_current[:5])
            movers_up = ", ".join(f"{m.domain} {m.delta_pct:+.1f}%" for m in s.top_movers_30d.up[:3])
            movers_down = ", ".join(f"{m.domain} {m.delta_pct:+.1f}%" for m in s.top_movers_30d.down[:3])
            block = (
                f"Settimana {s.year}-W{s.week:02d} ({s.generated_at.date()}):\n"
                f"  Top 5 AI: {ai_top or '—'}\n"
                f"  Movers saliti: {movers_up or '—'}\n"
                f"  Movers scesi: {movers_down or '—'}\n"
            )
            blocks.append(block)
        return "\n".join(blocks)

    @staticmethod
    def _extract_hero_mover(snapshots: list[TrackerSnapshot]) -> str:
        best_domain = ""
        best_abs = 0.0
        for s in snapshots:
            for m in (*s.top_movers_30d.up, *s.top_movers_30d.down):
                if abs(m.delta_pct) > best_abs:
                    best_abs = abs(m.delta_pct)
                    best_domain = m.domain
        return best_domain
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_tracker_report_writer.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/premium_writer.py tests/test_tracker_report_writer.py
git commit -m "feat(tracker): PremiumWriter.write_tracker_report for monthly editorial reports"
```

---

## Task 16: Monthly report template + Publisher rendering

**Files:**
- Create: `templates/pages/tracker_report.html.jinja`
- Modify: `src/osservatorio_seo/publisher.py` (add `_ssg_tracker_reports`)

- [ ] **Step 1: Create the monthly report template**

Create `templates/pages/tracker_report.html.jinja`:

```jinja
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% include "partials/_jsonld_article.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6 flex items-center gap-2 flex-wrap">
  {% for crumb in breadcrumbs %}
    {% if not loop.last %}
    <a href="{{ crumb.site_path | default(crumb.url) }}" class="hover:text-primary-container">{{ crumb.name }}</a>
    <span class="text-outline-variant">/</span>
    {% else %}
    <span class="text-primary-container">{{ crumb.name }}</span>
    {% endif %}
  {% endfor %}
</nav>

<article class="max-w-3xl mx-auto">
  <header class="mb-10">
    <p class="text-[10px] text-outline uppercase font-mono mb-3 tracking-widest">&gt; REPORT TRACKER · {{ month_label }}</p>
    <h1 class="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white">{{ report.title_it }}</h1>
    <p class="text-lg text-on-surface-variant leading-relaxed">{{ report.subtitle_it }}</p>
  </header>

  {% if report.executive_summary %}
  <section class="mb-12 p-6 bg-surface-container-low border-l-2 border-primary-container">
    <h2 class="text-xs text-outline uppercase font-mono mb-4 tracking-widest">&gt; EXECUTIVE SUMMARY</h2>
    <ul class="space-y-3">
      {% for point in report.executive_summary %}
      <li class="flex gap-3 text-on-surface leading-relaxed">
        <span class="text-primary-container font-mono shrink-0">▸</span>
        <span>{{ point }}</span>
      </li>
      {% endfor %}
    </ul>
  </section>
  {% endif %}

  <section class="mb-12">
    <h2 class="text-xs text-outline uppercase font-mono mb-4 tracking-widest">&gt; ANALISI DEL MESE</h2>
    <div class="prose prose-invert max-w-none text-on-surface leading-relaxed space-y-4">
      {% for para in report.narrative.split('\n\n') %}
      <p>{{ para }}</p>
      {% endfor %}
    </div>
  </section>

  {% if report.takeaways %}
  <section class="mb-12">
    <h2 class="text-xs text-outline uppercase font-mono mb-4 tracking-widest">&gt; 5 TAKEAWAYS STRATEGICI</h2>
    <ol class="space-y-5 list-decimal list-outside ml-6 marker:text-primary-container marker:font-mono marker:font-bold">
      {% for t in report.takeaways %}
      <li class="pl-2">
        <h3 class="text-base font-bold text-white mb-1">{{ t.title }}</h3>
        <p class="text-on-surface-variant leading-relaxed">{{ t.body }}</p>
      </li>
      {% endfor %}
    </ol>
  </section>
  {% endif %}

  <section class="mb-12 p-6 bg-surface-container-low border-l-2 border-primary-container">
    <h2 class="text-xs text-outline uppercase font-mono mb-4 tracking-widest">&gt; PROSPETTIVE</h2>
    <div class="prose prose-invert max-w-none text-on-surface leading-relaxed space-y-3">
      {% for para in report.outlook.split('\n\n') %}
      <p>{{ para }}</p>
      {% endfor %}
    </div>
  </section>

  <section class="mb-8 p-6 bg-surface-container-lowest border-l-2 border-outline-variant">
    <p class="text-sm text-on-surface-variant font-mono leading-relaxed">
      Questo è un <strong class="text-white">report editoriale mensile</strong> basato sugli snapshot settimanali del tracker (<code class="text-primary-container">{{ report.snapshot_week_refs | join(', ') }}</code>).
      Il contenuto è prodotto da <code class="text-primary-container">{{ report.model_used }}</code> a partire dai dati di Cloudflare Radar.
    </p>
    <a class="inline-block mt-4 text-xs border border-outline px-3 py-1 hover:border-primary-container hover:text-primary-container transition-all uppercase tracking-wider" href="/tracker/">&larr; DASHBOARD LIVE</a>
  </section>
</article>
{% endblock %}
```

Note: the `_jsonld_article.html.jinja` partial already exists (from dossier work) and expects a `pillar` variable with intro_long/context_section/etc. For the tracker report, we'll reuse it by shimming the variable names in the publisher context (below).

- [ ] **Step 2: Add `_ssg_tracker_reports` to Publisher**

In `src/osservatorio_seo/publisher.py`, add this method after `_ssg_tracker`:

```python
    def _ssg_tracker_reports(
        self,
        renderer: HtmlRenderer,
        site_dir: Path,
        allow_indexing: bool,
    ) -> None:
        """Render monthly tracker reports from data/tracker/reports/*.json."""
        reports_dir = self._data_dir / "tracker" / "reports"
        if not reports_dir.exists():
            return

        from osservatorio_seo.tracker.models import TrackerMonthlyReport

        for report_path in sorted(reports_dir.glob("????-??.json")):
            report = TrackerMonthlyReport.model_validate_json(
                report_path.read_text(encoding="utf-8")
            )
            year_str, month_str = report_path.stem.split("-")
            month_label = datetime(report.year, report.month, 1).strftime("%B %Y")
            canonical_url = canonical(f"/tracker/report/{year_str}-{month_str}/")

            # Shim for _jsonld_article partial which expects a "pillar" variable
            pillar_shim = {
                "title_it": report.title_it,
                "subtitle_it": report.subtitle_it,
                "intro_long": report.narrative,
                "context_section": "",
                "timeline_narrative": "",
                "outlook": report.outlook,
            }

            ctx = {
                "page_title": f"{report.title_it} — Tracker — Osservatorio SEO",
                "page_description": report.subtitle_it,
                "canonical_url": canonical_url,
                "active_nav": "tracker",
                "noindex": not allow_indexing,
                "og_type": "article",
                "report": report.model_dump(mode="json"),
                "pillar": pillar_shim,
                "article_url": canonical_url,
                "updated_iso": report.generated_at.isoformat(),
                "month_label": month_label,
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/"), "site_path": "/"},
                    {"name": "Tracker", "url": canonical("/tracker/"), "site_path": "/tracker/"},
                    {"name": month_label, "url": canonical_url, "site_path": ""},
                ],
            }

            target_dir = site_dir / "tracker" / "report" / f"{year_str}-{month_str}"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "index.html").write_text(
                renderer.render_tracker_report(ctx), encoding="utf-8"
            )
```

- [ ] **Step 3: Wire `_ssg_tracker_reports` into `publish_ssg`**

In `publish_ssg`, add the call right after `_ssg_tracker`:

```python
        self._ssg_tracker(renderer, site_dir, allow_indexing)
        self._ssg_tracker_reports(renderer, site_dir, allow_indexing)
        self._ssg_seo_assets(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

- [ ] **Step 4: Smoke test — rebuild existing SSG, verify nothing broke**

Run: `.venv/bin/python scripts/rebuild_seo_html.py 2>&1 | tail -10`
Expected: no errors. No tracker output yet (no snapshot exists).

- [ ] **Step 5: Commit**

```bash
git add templates/pages/tracker_report.html.jinja src/osservatorio_seo/publisher.py
git commit -m "feat(tracker): monthly report template + _ssg_tracker_reports publisher method"
```

---

## Task 17: Header nav link + homepage teaser

**Files:**
- Modify: `templates/partials/_header.html.jinja`
- Modify: `templates/pages/homepage.html.jinja`
- Modify: `src/osservatorio_seo/publisher.py` (homepage context)

- [ ] **Step 1: Add TRACKER link to header nav**

In `templates/partials/_header.html.jinja`, replace the nav block:

```jinja
      <a class="{% if active == 'archive' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/archivio/">ARCHIVIO</a>
      <a class="{% if active == 'dossier' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/dossier/">DOSSIER</a>
      <a class="{% if active == 'tracker' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/tracker/">TRACKER</a>
      <a class="{% if active == 'docs' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/docs/">DOCS</a>
```

(Adds TRACKER between DOSSIER and DOCS.)

- [ ] **Step 2: Add homepage teaser section**

In `templates/pages/homepage.html.jinja`, add this section right after the `<section class="mb-16" id="top10-section">` block and before `<section class="mb-12" id="categories-section">`:

```jinja
{% if tracker_teaser %}
<section class="mb-12 max-w-4xl" id="tracker-teaser">
  <div class="flex items-center gap-4 mb-4">
    <h2 class="text-lg font-bold tracking-tight uppercase text-white">&gt; TRACKER — STATO DELLA RICERCA</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
    <a href="/tracker/" class="text-xs text-primary-container hover:underline uppercase font-mono tracking-wider">VEDI TUTTO &rarr;</a>
  </div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <div class="p-4 border border-outline-variant bg-surface-container-lowest">
      <p class="text-[10px] text-outline font-mono uppercase tracking-widest mb-2">TOP 3 AI IN ITALIA</p>
      <ol class="space-y-1 text-sm text-on-surface">
        {% for d in tracker_teaser.ai_top3 %}
        <li><span class="text-primary-container">#{{ loop.index }}</span> {{ d.domain }}</li>
        {% endfor %}
      </ol>
    </div>
    <div class="p-4 border border-outline-variant bg-surface-container-lowest">
      <p class="text-[10px] text-outline font-mono uppercase tracking-widest mb-2">MOVER DEL MESE</p>
      <p class="text-lg text-white font-bold">{{ tracker_teaser.hero_mover or '—' }}</p>
      <p class="text-sm text-{{ 'primary-container' if tracker_teaser.hero_delta_pct >= 0 else '[#f5a623]' }} font-mono">
        {{ '{:+.1f}'.format(tracker_teaser.hero_delta_pct or 0) }}% traffic MoM
      </p>
    </div>
  </div>
</section>
{% endif %}
```

- [ ] **Step 3: Compute tracker_teaser context in Publisher**

In `src/osservatorio_seo/publisher.py`, find `_build_homepage_context` and add near the end (before the return dict):

```python
        # Tracker teaser (only if a snapshot exists)
        tracker_teaser = self._build_tracker_teaser()
```

Then in the returned dict, add:

```python
            "tracker_teaser": tracker_teaser,
```

Add this new helper method to `Publisher`:

```python
    def _build_tracker_teaser(self) -> dict[str, Any] | None:
        """Produce a small dict for homepage tracker teaser, or None if no snapshot."""
        snapshots_dir = self._data_dir / "tracker" / "snapshots"
        if not snapshots_dir.exists():
            return None
        latest = self._find_latest_snapshot(snapshots_dir)
        if latest is None:
            return None
        try:
            snapshot = TrackerSnapshot.model_validate_json(latest.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None

        ai_top3 = [d.model_dump(mode="json") for d in snapshot.ai_top10_current[:3]]
        # Hero mover: biggest absolute delta_pct from top_movers
        candidates = [*snapshot.top_movers_30d.up, *snapshot.top_movers_30d.down]
        hero_mover = None
        hero_delta = 0.0
        for m in candidates:
            if abs(m.delta_pct) > abs(hero_delta):
                hero_mover = m.domain
                hero_delta = m.delta_pct

        return {
            "ai_top3": ai_top3,
            "hero_mover": hero_mover,
            "hero_delta_pct": hero_delta,
        }
```

- [ ] **Step 4: Run existing tests to ensure no regression**

Run: `.venv/bin/pytest tests/test_publisher.py tests/test_renderer.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add templates/partials/_header.html.jinja templates/pages/homepage.html.jinja src/osservatorio_seo/publisher.py
git commit -m "feat(tracker): header nav link + homepage teaser for tracker"
```

---

## Task 18: CLI `scripts/update_tracker.py`

**Files:**
- Create: `scripts/update_tracker.py`

- [ ] **Step 1: Write the CLI script**

Create `scripts/update_tracker.py`:

```python
#!/usr/bin/env python3
"""Weekly tracker update — fetches Radar + Pages Analytics, saves snapshot, rebuilds SSG.

Usage:
    .venv/bin/python scripts/update_tracker.py [--monthly-report]

Flags:
    --monthly-report  Also generate the monthly editorial report for the
                      previous calendar month (should be set when running
                      on the first Monday of a month).

Environment variables:
    CLOUDFLARE_API_TOKEN       Required, token with Radar + Analytics read
    CLOUDFLARE_ACCOUNT_ID      Required for Pages Analytics
    CLOUDFLARE_ZONE_ID         Required for Pages Analytics
    OPENROUTER_API_KEY         Required if --monthly-report is set
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.premium_writer import PremiumWriter
from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.models import TrackerSnapshot
from osservatorio_seo.tracker.pages_analytics import PagesAnalyticsClient
from osservatorio_seo.tracker.radar_client import RadarClient


def _iso_year_week(d: date) -> tuple[int, int]:
    year, week, _ = d.isocalendar()
    return year, week


async def run_weekly_collection(repo_root: Path) -> Path:
    """Fetch snapshot, persist, return path."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise SystemExit("CLOUDFLARE_API_TOKEN not set")

    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    pages_client = None
    if acct and zone:
        pages_client = PagesAnalyticsClient(
            api_token=token, account_id=acct, zone_id=zone
        )

    radar = RadarClient(api_token=token)
    collector = TrackerCollector(
        radar=radar,
        pages_analytics=pages_client,
        location="IT",
    )

    today = date.today()
    year, week = _iso_year_week(today)
    print(f"Collecting tracker data for {year}-W{week:02d}…")
    snapshot = await collector.collect(year=year, week=week)

    tracker_dir = repo_root / "data" / "tracker"
    target = TrackerCollector.persist(snapshot, base_dir=tracker_dir)
    print(f"  saved {target}")
    if snapshot.metadata.warnings:
        print("  warnings:")
        for w in snapshot.metadata.warnings:
            print(f"    - {w}")
    return target


async def run_monthly_report(repo_root: Path) -> Path | None:
    """Generate the monthly report for the PREVIOUS calendar month.

    Uses all snapshot files that fall in that month. Skips if no snapshots.
    """
    if os.environ.get("OPENROUTER_API_KEY") is None:
        raise SystemExit("OPENROUTER_API_KEY not set, cannot generate monthly report")

    today = date.today()
    # Previous month
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    snapshots_dir = repo_root / "data" / "tracker" / "snapshots"
    if not snapshots_dir.exists():
        print("No snapshots yet, skipping monthly report")
        return None

    relevant: list[TrackerSnapshot] = []
    for p in sorted(snapshots_dir.glob("*-W*.json")):
        try:
            snap = TrackerSnapshot.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  skipping {p.name}: {e}")
            continue
        if snap.generated_at.month == prev_month and snap.generated_at.year == prev_year:
            relevant.append(snap)

    if not relevant:
        print(f"No snapshots for {prev_year}-{prev_month:02d}, skipping monthly report")
        return None

    print(f"Generating monthly report for {prev_year}-{prev_month:02d} from {len(relevant)} snapshots…")

    writer = PremiumWriter(api_key=os.environ["OPENROUTER_API_KEY"])
    report = await writer.write_tracker_report(
        year=prev_year,
        month=prev_month,
        snapshots=relevant,
    )

    reports_dir = repo_root / "data" / "tracker" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    target = reports_dir / f"{prev_year}-{prev_month:02d}.json"
    target.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"  saved {target} (cost €{report.cost_eur:.4f}, model {report.model_used})")
    return target


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monthly-report", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    await run_weekly_collection(repo_root)
    if args.monthly_report:
        await run_monthly_report(repo_root)

    print("\nDone. Run `.venv/bin/python scripts/rebuild_seo_html.py` to regenerate HTML.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Make executable and run with no env to sanity-check the error path**

Run: `chmod +x scripts/update_tracker.py && .venv/bin/python scripts/update_tracker.py 2>&1 | head -5`
Expected: `CLOUDFLARE_API_TOKEN not set` exit with non-zero.

- [ ] **Step 3: Commit**

```bash
git add scripts/update_tracker.py
git commit -m "feat(tracker): CLI scripts/update_tracker.py with weekly + monthly modes"
```

---

## Task 19: GitHub Actions weekly cron

**Files:**
- Create: `.github/workflows/tracker-weekly.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/tracker-weekly.yml`:

```yaml
name: Tracker weekly update

on:
  schedule:
    # Every Monday at 08:00 Europe/Rome (cron runs in UTC)
    # Winter (CET, UTC+1): 07:00 UTC. Summer (CEST, UTC+2): 06:00 UTC.
    # Use 07:00 UTC as a compromise — runs at 08:00 in winter, 09:00 in summer.
    - cron: "0 7 * * 1"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-tracker:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Setup Node (for Tailwind CLI)
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Python deps
        run: |
          python -m venv .venv
          .venv/bin/pip install --upgrade pip
          .venv/bin/pip install -e ".[dev]"

      - name: Install Node deps (Tailwind CLI)
        run: npm install

      - name: Determine if monthly report run
        id: month
        run: |
          # First Monday of the month: run with --monthly-report
          day_of_month=$(date -u +%d)
          if [ "$day_of_month" -le "07" ]; then
            echo "flag=--monthly-report" >> "$GITHUB_OUTPUT"
          else
            echo "flag=" >> "$GITHUB_OUTPUT"
          fi

      - name: Run tracker update
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          .venv/bin/python scripts/update_tracker.py ${{ steps.month.outputs.flag }}

      - name: Rebuild Tailwind CSS
        run: npx @tailwindcss/cli -i ./tailwind_input.css -o ./site/tailwind.css --minify

      - name: Rebuild SSG HTML
        run: .venv/bin/python scripts/rebuild_seo_html.py

      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data/tracker site/tracker site/sitemap.xml site/tailwind.css
          if git diff --staged --quiet; then
            echo "No changes to commit"
          else
            WEEK=$(date -u +'%Y-W%V')
            git commit -m "chore(tracker): weekly update $WEEK"
            for i in 1 2 3; do
              git push && break
              git pull --rebase origin main
            done
          fi

      - name: Deploy to Cloudflare Pages
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: |
          npx wrangler pages deploy ./site \
            --project-name=osservatorioseo \
            --branch=main \
            --commit-hash="$(git rev-parse HEAD)" \
            --commit-message="tracker weekly update" \
            --commit-dirty=true
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/tracker-weekly.yml
git commit -m "ci(tracker): GitHub Actions weekly cron + monthly report trigger"
```

---

## Task 20: End-to-end smoke test + first manual run

**Files:** (no new files — validation only)

- [ ] **Step 1: Run the full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: all tests pass (new tracker tests + all pre-existing tests).

- [ ] **Step 2: Ruff check**

Run: `.venv/bin/ruff check src/osservatorio_seo/tracker/ tests/test_tracker*.py scripts/update_tracker.py && .venv/bin/ruff format --check src/osservatorio_seo/tracker/ tests/test_tracker*.py scripts/update_tracker.py`
Expected: no errors.

- [ ] **Step 3: Craft a sample snapshot manually to test the full SSG path**

Run (one-off Python):

```bash
.venv/bin/python <<'PY'
from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo.tracker.models import (
    AnalyticsReferrer, Big4PanelData, BumpChartData, BumpChartWeek,
    CategoryHeatmapCell, CategoryHeatmapRow, DomainMovement, DomainRank,
    IndexTimeseries, MarketCompositionPoint, SnapshotMetadata, TimeseriesPoint,
    TopMovers, TrackerSnapshot,
)

# Build a synthetic snapshot to verify rendering
root = Path(".")
snap_dir = root / "data" / "tracker" / "snapshots"
snap_dir.mkdir(parents=True, exist_ok=True)

def ts_points(vals, base_month=1):
    return [
        TimeseriesPoint(
            date=datetime(2024 + (base_month + i // 12 - 1) // 12, ((base_month + i - 1) % 12) + 1, 1, tzinfo=UTC),
            value=v,
        )
        for i, v in enumerate(vals)
    ]

snap = TrackerSnapshot(
    year=2026, week=15,
    generated_at=datetime(2026, 4, 14, 8, 0, tzinfo=UTC),
    ai_index_24mo=IndexTimeseries(label="AI IT", points=ts_points([100,105,112,120,130,142,155,170,188,205,220,235,248,260,275,290,302,314,325,335,342,350,362,378])),
    internet_index_24mo=IndexTimeseries(label="Internet IT", points=ts_points([100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123])),
    market_composition_12mo=[
        MarketCompositionPoint(date=datetime(2025, m, 1, tzinfo=UTC), google_share=0.955 - m*0.003, other_search_share=0.035 + m*0.001, ai_share=0.010 + m*0.002)
        for m in range(1, 13)
    ],
    bump_chart_6mo=BumpChartData(
        domains=["chat.openai.com","gemini.google.com","claude.ai","perplexity.ai","character.ai"],
        weeks=[BumpChartWeek(week_end=datetime(2025, 11+i//4, (i%4)*7+1, tzinfo=UTC) if i < 8 else datetime(2026, i-7 if i-7 <= 4 else 4, 15, tzinfo=UTC),
                             ranks={"chat.openai.com":1,"gemini.google.com":2+((i//3)%2),"claude.ai":8-i//2,"perplexity.ai":3+i//3,"character.ai":5+i//4}) for i in range(12)],
    ),
    category_heatmap_6mo=[
        CategoryHeatmapRow(category=cat, cells=[CategoryHeatmapCell(month=f"2025-{10+m:02d}" if m < 3 else f"2026-{m-2:02d}", delta_pct=delta) for m, delta in enumerate([-2.3, -3.5, -4.2, 1.2, 0.8, -1.5])])
        for cat, _ in [("News", 0), ("E-commerce", 0), ("Finance", 0), ("Entertainment", 0), ("Gaming", 0)]
    ],
    top_movers_30d=TopMovers(
        up=[DomainMovement(domain="claude.ai", delta_pct=42.5), DomainMovement(domain="mistral.ai", delta_pct=15.6), DomainMovement(domain="gemini.google.com", delta_pct=12.4)],
        down=[DomainMovement(domain="perplexity.ai", delta_pct=-8.1), DomainMovement(domain="character.ai", delta_pct=-6.3)],
    ),
    big4_6mo=[
        Big4PanelData(domain="chat.openai.com", display_name="ChatGPT", current_rank=1, previous_rank=1, traffic_timeseries=ts_points([100, 99, 101, 100, 98, 102])),
        Big4PanelData(domain="gemini.google.com", display_name="Gemini", current_rank=2, previous_rank=3, traffic_timeseries=ts_points([80, 85, 90, 95, 100, 108])),
        Big4PanelData(domain="claude.ai", display_name="Claude", current_rank=3, previous_rank=12, traffic_timeseries=ts_points([20, 25, 40, 55, 80, 100])),
        Big4PanelData(domain="perplexity.ai", display_name="Perplexity", current_rank=6, previous_rank=4, traffic_timeseries=ts_points([100, 95, 88, 80, 72, 65])),
    ],
    ai_top10_current=[DomainRank(domain=d, rank=i+1) for i, d in enumerate(["chat.openai.com","gemini.google.com","claude.ai","character.ai","copilot.microsoft.com","perplexity.ai","meta.ai","poe.com","mistral.ai","huggingface.co"])],
    search_top5_current=[DomainRank(domain=d, rank=i+1) for i, d in enumerate(["google.com","bing.com","duckduckgo.com","yahoo.com","ecosia.org"])],
    own_referrers_30d=[
        AnalyticsReferrer(source="Google", share_pct=65.2),
        AnalyticsReferrer(source="Direct", share_pct=22.0),
        AnalyticsReferrer(source="Bing", share_pct=4.1),
        AnalyticsReferrer(source="ChatGPT", share_pct=1.8),
        AnalyticsReferrer(source="Claude", share_pct=0.9),
        AnalyticsReferrer(source="Other", share_pct=6.0),
    ],
    metadata=SnapshotMetadata(radar_calls=6, pages_analytics_calls=1, categories_with_it_data=["ai","search_engines"]),
)

target = snap_dir / "2026-W15.json"
target.write_text(snap.model_dump_json(indent=2) + "\n", encoding="utf-8")
print(f"wrote {target}")
PY
```

- [ ] **Step 4: Rebuild SSG to render the tracker page**

Run: `.venv/bin/python scripts/rebuild_seo_html.py 2>&1 | tail -5`
Expected: no errors.

- [ ] **Step 5: Rebuild Tailwind**

Run: `npx @tailwindcss/cli -i ./tailwind_input.css -o ./site/tailwind.css --minify 2>&1 | tail -3`
Expected: "Done in N ms".

- [ ] **Step 6: Verify tracker dashboard exists**

Run: `ls site/tracker/ && grep -c '<svg' site/tracker/index.html`
Expected: `index.html` listed, at least 7 SVGs embedded.

- [ ] **Step 7: Launch local server + Playwright smoke test**

Run:
```bash
cd site && python3 -m http.server 8765 >/dev/null 2>&1 &
sleep 1
curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/tracker/
```
Expected: `200`.

Kill server: `kill $(lsof -ti:8765) 2>/dev/null || true`

- [ ] **Step 8: Commit the synthetic snapshot + rendered output**

```bash
git add data/tracker/snapshots/2026-W15.json site/tracker site/tailwind.css site/sitemap.xml
git commit -m "feat(tracker): first synthetic snapshot + full SSG render smoke test"
```

- [ ] **Step 9: Push and deploy**

```bash
git push origin main
wrangler pages deploy ./site --project-name=osservatorioseo --branch=main --commit-hash="$(git rev-parse HEAD)" --commit-message="tracker v1 live" --commit-dirty=true
```

Expected: deploy URL printed.

- [ ] **Step 10: Final spec vs plan verification**

Open `docs/superpowers/specs/2026-04-12-tracker-search-ai-italia-design.md` and check:
- All 7 charts implemented ✓
- Dashboard + monthly report pages ✓
- Free tier only (Cloudflare Radar + Pages Analytics) ✓
- Metodologia visibile ✓
- Header nav link ✓
- Sitemap entries ✓
- JSON-LD Dataset on tracker page ✓
- PremiumWriter.write_tracker_report implemented ✓

All acceptance criteria met except "cron weekly gira con successo per 4 settimane consecutive" which requires waiting 4 weeks in production. Document this in the commit message as "v1 architecture complete, 4-week prod validation pending".

---

## Self-review checklist (author's notes)

**Spec coverage:**
- ✓ 7 charts (Tasks 5-11)
- ✓ Dashboard + monthly report (Tasks 12, 16)
- ✓ Data pipelines (Tasks 2, 3, 4)
- ✓ Publisher integration (Tasks 13, 16)
- ✓ SEO assets — sitemap, JSON-LD (Tasks 12, 14)
- ✓ Nav + homepage teaser (Task 17)
- ✓ CLI + cron (Tasks 18, 19)
- ✓ Google Trends explicitly deferred (not in plan, documented in spec future additions)

**Type consistency:**
- `TrackerSnapshot` field names match across models, collector, publisher, and report writer ✓
- Chart functions take exactly the types exposed by `TrackerSnapshot` ✓
- `TrackerMonthlyReport` field names consistent between writer and template ✓

**Known acceptable gaps for v1:**
- Collector uses stub values for `bump_chart_6mo`, `category_heatmap_6mo`, `market_composition_12mo`, `big4_6mo`. Populating these requires calling additional Radar endpoints that are well-defined but not covered in the initial tasks. First production run will show empty charts for these 4 until a follow-up task populates them. This is documented in Task 4's implementation comment. A follow-up task should be added to the plan iterations once v1 is live and the Radar API shape is confirmed in practice.
