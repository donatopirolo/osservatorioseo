"""Tests for google_financials Pydantic models."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from osservatorio_seo.google_financials.models import (
    CompanyConfig,
    EventFiling,
    FilingState,
    MetricConfig,
    QuarterlyAnalysis,
    QuarterlyMetric,
    QuarterlySnapshot,
    SEOImplication,
    SnapshotMetadata,
)


class TestQuarterlyMetric:
    def test_basic_creation(self):
        m = QuarterlyMetric(label="Revenue", value_usd_millions=86310.0)
        assert m.label == "Revenue"
        assert m.value_usd_millions == 86310.0
        assert m.qoq_change_pct is None
        assert m.yoy_change_pct is None

    def test_with_deltas(self):
        m = QuarterlyMetric(
            label="Search Revenue",
            value_usd_millions=63073.0,
            value_prev_year_usd_millions=53886.0,
            yoy_change_pct=17.04,
        )
        assert m.yoy_change_pct == 17.04

    def test_roundtrip_json(self):
        m = QuarterlyMetric(label="TAC", value_usd_millions=14123.5, qoq_change_pct=3.2)
        data = json.loads(m.model_dump_json())
        m2 = QuarterlyMetric(**data)
        assert m2.label == m.label
        assert m2.qoq_change_pct == m.qoq_change_pct

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            QuarterlyMetric(label="X", value_usd_millions=1.0, unknown_field="bad")


class TestQuarterlySnapshot:
    def test_basic_creation(self):
        snap = QuarterlySnapshot(
            company_id="alphabet",
            fiscal_year=2025,
            fiscal_quarter=4,
            period_end=date(2025, 12, 31),
            filing_type="10-K",
            metrics={
                "total_revenue": QuarterlyMetric(
                    label="Fatturato totale",
                    value_usd_millions=96469.0,
                ),
            },
            generated_at=datetime.now(UTC),
            metadata=SnapshotMetadata(edgar_calls=1),
        )
        assert snap.fiscal_quarter == 4
        assert "total_revenue" in snap.metrics

    def test_quarter_bounds(self):
        with pytest.raises(ValidationError):
            QuarterlySnapshot(
                fiscal_year=2025,
                fiscal_quarter=5,  # invalid
                period_end=date(2025, 12, 31),
                filing_type="10-K",
                generated_at=datetime.now(UTC),
                metadata=SnapshotMetadata(),
            )

    def test_roundtrip_json(self):
        snap = QuarterlySnapshot(
            fiscal_year=2024,
            fiscal_quarter=1,
            period_end=date(2024, 3, 31),
            filing_type="10-Q",
            metrics={},
            generated_at=datetime.now(UTC),
            metadata=SnapshotMetadata(),
        )
        data = json.loads(snap.model_dump_json())
        snap2 = QuarterlySnapshot(**data)
        assert snap2.fiscal_year == 2024


class TestQuarterlyAnalysis:
    def test_basic_creation(self):
        analysis = QuarterlyAnalysis(
            fiscal_year=2025,
            fiscal_quarter=4,
            title_it="Search +17%: Alphabet accelera",
            subtitle_it="I ricavi Search crescono del 17% anno su anno",
            narrative="Testo di analisi.",
            seo_implications=[
                SEOImplication(title="TAC in aumento", body="Impatto su...", severity="high")
            ],
            ai_search_impact="Impatto AI...",
            correlation_timeline="Correlazioni...",
            takeaways=[],
            outlook="Prospettive...",
            generated_at=datetime.now(UTC),
            model_used="anthropic/claude-sonnet-4-5",
        )
        assert analysis.company_id == "alphabet"
        assert len(analysis.seo_implications) == 1
        assert analysis.seo_implications[0].severity == "high"


class TestEventFiling:
    def test_basic_creation(self):
        event = EventFiling(
            accession_number="0001652044-25-000099",
            filing_date=date(2025, 3, 15),
            event_type="acquisition",
            title_it="Alphabet acquisisce Wiz",
            summary_it="Acquisizione da $32B nel cloud security.",
            seo_relevance="medium",
            source_url="https://sec.gov/...",
            generated_at=datetime.now(UTC),
            model_used="google/gemini-2.0-flash-001",
        )
        assert event.seo_relevance == "medium"


class TestCompanyConfig:
    def test_creation(self):
        cfg = CompanyConfig(
            id="alphabet",
            name="Alphabet Inc.",
            cik="0001652044",
            xbrl_namespace="goog",
            metrics={
                "total_revenue": MetricConfig(
                    tags=["Revenues"],
                    namespace="us-gaap",
                    label_it="Fatturato totale",
                ),
            },
        )
        assert cfg.enabled is True
        assert len(cfg.metrics) == 1


class TestFilingState:
    def test_empty_state(self):
        state = FilingState(company_id="alphabet")
        assert len(state.processed_accessions) == 0

    def test_roundtrip_json(self):
        state = FilingState(
            company_id="alphabet",
            processed_accessions={"acc-001", "acc-002"},
            last_check=datetime.now(UTC),
        )
        data = json.loads(state.model_dump_json())
        state2 = FilingState(**data)
        assert "acc-001" in state2.processed_accessions
