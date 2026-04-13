"""Pydantic models for the tracker v3 subsystem."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TimeseriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    value: float


class TrendsPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    values: dict[str, int]


class TrendsTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keywords: list[str] = Field(default_factory=list)
    points: list[TrendsPoint] = Field(default_factory=list)
    averages: dict[str, int] = Field(default_factory=dict)


class TopDomainEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rank: int = Field(ge=1)
    domain: str
    categories: list[str] = Field(default_factory=list)
    timeseries: list[TimeseriesPoint] = Field(default_factory=list)


class AIPlatformEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str
    label: str
    type: str
    rank: int | None = None
    bucket: str


class BotHumanPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    human_pct: float
    bot_pct: float


class BotHumanTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: list[BotHumanPoint] = Field(default_factory=list)


class AIBotPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    values: dict[str, float]


class AIBotsTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agents: list[str] = Field(default_factory=list)
    points: list[AIBotPoint] = Field(default_factory=list)


class CrawlPurposePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    values: dict[str, float]


class CrawlPurposeTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purposes: list[str] = Field(default_factory=list)
    points: list[CrawlPurposePoint] = Field(default_factory=list)


class DeviceTypePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: datetime
    mobile_pct: float
    desktop_pct: float


class DeviceTypeTimeseries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: list[DeviceTypePoint] = Field(default_factory=list)


class OSEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    os: str
    pct: float


class IndustryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    industry: str
    pct: float


class SnapshotMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    radar_calls: int = 0
    warnings: list[str] = Field(default_factory=list)


class TrackerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "3.0"
    year: int
    week: int = Field(ge=1, le=53)
    generated_at: datetime

    top10_it: list[TopDomainEntry] = Field(default_factory=list)
    top10_global: list[TopDomainEntry] = Field(default_factory=list)
    ai_platforms_it: list[AIPlatformEntry] = Field(default_factory=list)
    ai_platforms_global: list[AIPlatformEntry] = Field(default_factory=list)
    trends_it: TrendsTimeseries = Field(default_factory=TrendsTimeseries)
    trends_global: TrendsTimeseries = Field(default_factory=TrendsTimeseries)
    bot_human_it: BotHumanTimeseries = Field(default_factory=BotHumanTimeseries)
    bot_human_global: BotHumanTimeseries = Field(default_factory=BotHumanTimeseries)
    ai_bots_ua_it: AIBotsTimeseries = Field(default_factory=AIBotsTimeseries)
    ai_bots_ua_global: AIBotsTimeseries = Field(default_factory=AIBotsTimeseries)
    crawl_purpose_it: CrawlPurposeTimeseries = Field(default_factory=CrawlPurposeTimeseries)
    crawl_purpose_global: CrawlPurposeTimeseries = Field(default_factory=CrawlPurposeTimeseries)
    industry_it: list[IndustryEntry] = Field(default_factory=list)
    industry_global: list[IndustryEntry] = Field(default_factory=list)
    device_type_it: DeviceTypeTimeseries = Field(default_factory=DeviceTypeTimeseries)
    device_type_global: DeviceTypeTimeseries = Field(default_factory=DeviceTypeTimeseries)
    os_it: list[OSEntry] = Field(default_factory=list)
    os_global: list[OSEntry] = Field(default_factory=list)
    metadata: SnapshotMetadata


class ReportTakeaway(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    body: str


class TrackerMonthlyReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2.0"
    year: int
    month: int = Field(ge=1, le=12)
    title_it: str
    subtitle_it: str
    hero_mover: str
    executive_summary: list[str] = Field(default_factory=list, max_length=6)
    narrative: str
    takeaways: list[ReportTakeaway] = Field(default_factory=list, max_length=8)
    outlook: str
    snapshot_week_refs: list[str] = Field(default_factory=list)
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0
