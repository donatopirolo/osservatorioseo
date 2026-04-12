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
    def _compute_delta(self) -> DomainRank:
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
