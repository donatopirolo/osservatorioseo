"""Tests for tracker chart SVG generators."""

from datetime import UTC, datetime

from osservatorio_seo.tracker.charts import (
    render_ai_vs_internet_chart,
    render_big4_small_multiples,
    render_bump_chart,
    render_category_heatmap,
    render_market_composition_chart,
    render_movers_chart,
    render_own_referrers_chart,
)
from osservatorio_seo.tracker.models import (
    AnalyticsReferrer,
    Big4PanelData,
    BumpChartData,
    BumpChartWeek,
    CategoryHeatmapCell,
    CategoryHeatmapRow,
    DomainMovement,
    IndexTimeseries,
    MarketCompositionPoint,
    TimeseriesPoint,
    TopMovers,
)

# --- Chart 1: AI vs Internet ---


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
    assert svg.count("<polyline") >= 2


def test_ai_vs_internet_chart_handles_empty_data():
    svg = render_ai_vs_internet_chart(
        ai=IndexTimeseries(label="AI"),
        internet=IndexTimeseries(label="Internet"),
    )
    assert svg.startswith("<svg")
    assert "nessun dato" in svg.lower() or "no data" in svg.lower()


# --- Chart 2: Market composition ---


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
    assert svg.count("<polygon") >= 3
    assert "Google" in svg
    assert "AI" in svg


def test_market_composition_handles_empty():
    svg = render_market_composition_chart([])
    assert "nessun dato" in svg.lower()


# --- Chart 3: Bump chart ---


def test_bump_chart_returns_valid_svg():
    domains = ["chat.openai.com", "gemini.google.com", "claude.ai", "perplexity.ai"]
    weeks = [
        BumpChartWeek(
            week_end=datetime(2025, 11, 3, tzinfo=UTC),
            ranks={
                "chat.openai.com": 1,
                "gemini.google.com": 2,
                "claude.ai": 8,
                "perplexity.ai": 3,
            },
        ),
        BumpChartWeek(
            week_end=datetime(2026, 1, 5, tzinfo=UTC),
            ranks={
                "chat.openai.com": 1,
                "gemini.google.com": 2,
                "claude.ai": 5,
                "perplexity.ai": 4,
            },
        ),
        BumpChartWeek(
            week_end=datetime(2026, 4, 1, tzinfo=UTC),
            ranks={
                "chat.openai.com": 1,
                "gemini.google.com": 2,
                "claude.ai": 3,
                "perplexity.ai": 6,
            },
        ),
    ]
    svg = render_bump_chart(BumpChartData(domains=domains, weeks=weeks))
    assert svg.startswith("<svg")
    assert svg.count("<polyline") >= 4
    assert "claude.ai" in svg


# --- Chart 4: Category heatmap ---


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
    assert svg.count("<rect") >= 12 + 1  # +1 for background
    assert "News" in svg
    assert "E-commerce" in svg


# --- Chart 5: Biggest movers ---


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
    assert svg.count("<rect") >= 5 + 1


# --- Chart 6: Big 4 small multiples ---


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
    assert svg.count("<polyline") >= 4
    assert "Claude" in svg
    assert "#3" in svg
    assert "#12" in svg


# --- Chart 7: Own referrers ---


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
