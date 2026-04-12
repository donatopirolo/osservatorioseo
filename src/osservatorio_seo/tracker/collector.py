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

    async def _safe_category_timeseries(self, category: str, date_range: str) -> IndexTimeseries:
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
