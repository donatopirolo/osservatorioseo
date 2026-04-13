"""Collector: orchestrates Radar API calls into a TrackerSnapshot v2.

Responsibilities:
- Load platform config from YAML
- Fetch top-10 domains for IT and global
- Fetch per-domain timeseries for each top-10 entry
- Fetch AI platform details (rank + bucket) for configured platforms
- Fetch bot/human, AI bot UA, crawl purpose, and industry data
- Handle partial failures gracefully (log warning, use empty defaults)
- Persist snapshot to ``<base_dir>/snapshots/<YYYY-Www>.json``
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from osservatorio_seo.tracker.models import (
    AIBotPoint,
    AIBotsTimeseries,
    AIPlatformEntry,
    BotHumanPoint,
    BotHumanTimeseries,
    CrawlPurposePoint,
    CrawlPurposeTimeseries,
    DeviceTypePoint,
    DeviceTypeTimeseries,
    IndustryEntry,
    OSEntry,
    SnapshotMetadata,
    TimeseriesPoint,
    TopDomainEntry,
    TrackerSnapshot,
)

logger = logging.getLogger(__name__)

_DEFAULT_PLATFORMS = Path(__file__).resolve().parents[3] / "config" / "tracker_platforms.yaml"


def _parse_dt(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


class TrackerCollector:
    """Orchestrates data fetches and produces a TrackerSnapshot."""

    def __init__(
        self,
        radar: Any,
        platforms_config: Path | None = None,
    ) -> None:
        self._radar = radar
        self._cfg_path = platforms_config or _DEFAULT_PLATFORMS
        self._platforms: list[dict[str, str]] = self._load_platforms()
        self._warnings: list[str] = []

    def _load_platforms(self) -> list[dict[str, str]]:
        if not self._cfg_path.exists():
            logger.warning("platforms config not found: %s", self._cfg_path)
            return []
        with self._cfg_path.open() as fh:
            data = yaml.safe_load(fh)
        return data.get("platforms", [])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def collect(self, year: int, week: int) -> TrackerSnapshot:
        """Run all data fetches and build a snapshot."""
        self._warnings = []

        top10_it, top10_global = await self._fetch_top10_both()
        ai_platforms_it, ai_platforms_global = await self._fetch_ai_platforms_both()
        bot_human_it, bot_human_global = await self._fetch_bot_human_both()
        ai_bots_it, ai_bots_global = await self._fetch_ai_bots_both()
        crawl_it, crawl_global = await self._fetch_crawl_purpose_both()
        industry_it, industry_global = await self._fetch_industry_both()
        device_it, device_global = await self._fetch_device_type_both()
        os_it, os_global = await self._fetch_os_both()

        metadata = SnapshotMetadata(warnings=list(self._warnings))

        return TrackerSnapshot(
            year=year,
            week=week,
            generated_at=datetime.now(UTC),
            top10_it=top10_it,
            top10_global=top10_global,
            ai_platforms_it=ai_platforms_it,
            ai_platforms_global=ai_platforms_global,
            bot_human_it=bot_human_it,
            bot_human_global=bot_human_global,
            ai_bots_ua_it=ai_bots_it,
            ai_bots_ua_global=ai_bots_global,
            crawl_purpose_it=crawl_it,
            crawl_purpose_global=crawl_global,
            industry_it=industry_it,
            industry_global=industry_global,
            device_type_it=device_it,
            device_type_global=device_global,
            os_it=os_it,
            os_global=os_global,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Section 1: top-10
    # ------------------------------------------------------------------

    async def _fetch_top10_both(
        self,
    ) -> tuple[list[TopDomainEntry], list[TopDomainEntry]]:
        top10_it = await self._safe(self._fetch_top10, "ranking_top(IT)", location="IT", default=[])
        top10_global = await self._safe(
            self._fetch_top10, "ranking_top(global)", location=None, default=[]
        )
        return top10_it, top10_global

    async def _fetch_top10(self, location: str | None) -> list[TopDomainEntry]:
        raw = await self._radar.ranking_top(location=location, limit=10)
        entries: list[TopDomainEntry] = []
        for item in raw:
            domain = item["domain"]
            ts_raw = await self._radar.domain_timeseries(
                domain=domain, location=location, date_range="52w"
            )
            timeseries = [
                TimeseriesPoint(date=_parse_dt(p["date"]), value=float(p["rank"])) for p in ts_raw
            ]
            entries.append(
                TopDomainEntry(
                    rank=item["rank"],
                    domain=domain,
                    categories=item.get("categories", []),
                    timeseries=timeseries,
                )
            )
        return entries

    # ------------------------------------------------------------------
    # Section 2: AI platforms
    # ------------------------------------------------------------------

    async def _fetch_ai_platforms_both(
        self,
    ) -> tuple[list[AIPlatformEntry], list[AIPlatformEntry]]:
        it = await self._safe(
            self._fetch_ai_platforms, "domain_detail platforms(IT)", location="IT", default=[]
        )
        glb = await self._safe(
            self._fetch_ai_platforms,
            "domain_detail platforms(global)",
            location=None,
            default=[],
        )
        return it, glb

    async def _fetch_ai_platforms(self, location: str | None) -> list[AIPlatformEntry]:
        entries: list[AIPlatformEntry] = []
        for platform in self._platforms:
            domain = platform["domain"]
            detail = await self._radar.domain_detail(domain=domain, location=location)
            entries.append(
                AIPlatformEntry(
                    domain=domain,
                    label=platform["label"],
                    type=platform["type"],
                    rank=detail.get("rank"),
                    bucket=str(detail.get("bucket", "")),
                )
            )
        return entries

    # ------------------------------------------------------------------
    # Section 3: bot/human
    # ------------------------------------------------------------------

    async def _fetch_bot_human_both(
        self,
    ) -> tuple[BotHumanTimeseries, BotHumanTimeseries]:
        it = await self._safe(
            self._fetch_bot_human,
            "bot_human_timeseries(IT)",
            location="IT",
            default=BotHumanTimeseries(),
        )
        glb = await self._safe(
            self._fetch_bot_human,
            "bot_human_timeseries(global)",
            location=None,
            default=BotHumanTimeseries(),
        )
        return it, glb

    async def _fetch_bot_human(self, location: str | None) -> BotHumanTimeseries:
        raw = await self._radar.bot_human_timeseries(location=location)
        points = [
            BotHumanPoint(
                date=_parse_dt(p["date"]),
                human_pct=p["human_pct"],
                bot_pct=p["bot_pct"],
            )
            for p in raw
        ]
        return BotHumanTimeseries(points=points)

    # ------------------------------------------------------------------
    # Section 4: AI bot UA + crawl purpose
    # ------------------------------------------------------------------

    async def _fetch_ai_bots_both(
        self,
    ) -> tuple[AIBotsTimeseries, AIBotsTimeseries]:
        it = await self._safe(
            self._fetch_ai_bots, "ai_bots_user_agent(IT)", location="IT", default=AIBotsTimeseries()
        )
        glb = await self._safe(
            self._fetch_ai_bots,
            "ai_bots_user_agent(global)",
            location=None,
            default=AIBotsTimeseries(),
        )
        return it, glb

    async def _fetch_ai_bots(self, location: str | None) -> AIBotsTimeseries:
        agents, raw_points = await self._radar.ai_bots_user_agent(location=location)
        points = [AIBotPoint(date=_parse_dt(p["date"]), values=p["values"]) for p in raw_points]
        return AIBotsTimeseries(agents=agents, points=points)

    async def _fetch_crawl_purpose_both(
        self,
    ) -> tuple[CrawlPurposeTimeseries, CrawlPurposeTimeseries]:
        it = await self._safe(
            self._fetch_crawl_purpose,
            "crawl_purpose(IT)",
            location="IT",
            default=CrawlPurposeTimeseries(),
        )
        glb = await self._safe(
            self._fetch_crawl_purpose,
            "crawl_purpose(global)",
            location=None,
            default=CrawlPurposeTimeseries(),
        )
        return it, glb

    async def _fetch_crawl_purpose(self, location: str | None) -> CrawlPurposeTimeseries:
        purposes, raw_points = await self._radar.crawl_purpose(location=location)
        points = [
            CrawlPurposePoint(date=_parse_dt(p["date"]), values=p["values"]) for p in raw_points
        ]
        return CrawlPurposeTimeseries(purposes=purposes, points=points)

    # ------------------------------------------------------------------
    # Section 5: industry
    # ------------------------------------------------------------------

    async def _fetch_industry_both(
        self,
    ) -> tuple[list[IndustryEntry], list[IndustryEntry]]:
        it = await self._safe(
            self._fetch_industry, "industry_summary(IT)", location="IT", default=[]
        )
        glb = await self._safe(
            self._fetch_industry, "industry_summary(global)", location=None, default=[]
        )
        return it, glb

    async def _fetch_industry(self, location: str | None) -> list[IndustryEntry]:
        raw = await self._radar.industry_summary(location=location)
        return [IndustryEntry(industry=r["industry"], pct=r["pct"]) for r in raw]

    # ------------------------------------------------------------------
    # Section 9: device type + OS
    # ------------------------------------------------------------------

    async def _fetch_device_type_both(self):
        it = await self._safe(self._fetch_device_type, "device_type(IT)", location="IT", default=DeviceTypeTimeseries())
        glb = await self._safe(self._fetch_device_type, "device_type(global)", location=None, default=DeviceTypeTimeseries())
        return it, glb

    async def _fetch_device_type(self, location):
        raw = await self._radar.device_type_timeseries(location=location)
        points = [DeviceTypePoint(date=_parse_dt(p["date"]), mobile_pct=p["mobile_pct"], desktop_pct=p["desktop_pct"]) for p in raw]
        return DeviceTypeTimeseries(points=points)

    async def _fetch_os_both(self):
        it = await self._safe(self._fetch_os, "os_summary(IT)", location="IT", default=[])
        glb = await self._safe(self._fetch_os, "os_summary(global)", location=None, default=[])
        return it, glb

    async def _fetch_os(self, location):
        raw = await self._radar.os_summary(location=location)
        return [OSEntry(os=r["os"], pct=r["pct"]) for r in raw]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _safe(self, fn, label: str, *, default, **kwargs):
        """Call async fn(**kwargs), return default and log warning on failure."""
        try:
            return await fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            msg = f"{label}: {exc}"
            self._warnings.append(msg)
            logger.warning("tracker collector %s", msg)
            return default

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------

    @staticmethod
    def persist(snapshot: TrackerSnapshot, base_dir: Path) -> Path:
        """Write snapshot to ``<base_dir>/snapshots/<YYYY-Www>.json``."""
        snapshots_dir = Path(base_dir) / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{snapshot.year}-W{snapshot.week:02d}.json"
        target = snapshots_dir / filename
        target.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return target
