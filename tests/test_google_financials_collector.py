"""Tests for the Google Financials collector."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from osservatorio_seo.google_financials.collector import FinancialsCollector, _pct_change
from osservatorio_seo.google_financials.models import (
    FilingState,
    QuarterlyMetric,
    QuarterlySnapshot,
    SnapshotMetadata,
)


class TestPctChange:
    def test_positive_change(self):
        assert _pct_change(110.0, 100.0) == 10.0

    def test_negative_change(self):
        assert _pct_change(90.0, 100.0) == -10.0

    def test_zero_previous(self):
        assert _pct_change(100.0, 0.0) is None

    def test_no_change(self):
        assert _pct_change(100.0, 100.0) == 0.0


class TestDerivedRatios:
    def _make_metrics(self, **kwargs) -> dict[str, QuarterlyMetric]:
        return {
            k: QuarterlyMetric(label=k, value_usd_millions=v)
            for k, v in kwargs.items()
        }

    def test_tac_pct(self):
        metrics = self._make_metrics(
            traffic_acquisition_costs=14000.0,
            google_search_revenue=60000.0,
        )
        result = FinancialsCollector._compute_tac_pct(metrics)
        assert result == pytest.approx(23.33, abs=0.01)

    def test_search_pct(self):
        metrics = self._make_metrics(
            google_search_revenue=60000.0,
            total_revenue=90000.0,
        )
        result = FinancialsCollector._compute_search_pct(metrics)
        assert result == pytest.approx(66.67, abs=0.01)

    def test_margin_pct(self):
        metrics = self._make_metrics(
            operating_income=25000.0,
            total_revenue=90000.0,
        )
        result = FinancialsCollector._compute_margin_pct(metrics)
        assert result == pytest.approx(27.78, abs=0.01)

    def test_missing_metric_returns_none(self):
        metrics = self._make_metrics(traffic_acquisition_costs=14000.0)
        assert FinancialsCollector._compute_tac_pct(metrics) is None


class TestPersistence:
    def test_persist_and_load(self, tmp_path: Path):
        snapshot = QuarterlySnapshot(
            company_id="alphabet",
            fiscal_year=2024,
            fiscal_quarter=2,
            period_end=date(2024, 6, 30),
            filing_type="10-Q",
            metrics={
                "total_revenue": QuarterlyMetric(
                    label="Revenue", value_usd_millions=84742.0
                ),
            },
            generated_at=datetime.now(UTC),
            metadata=SnapshotMetadata(edgar_calls=1),
        )
        target = FinancialsCollector.persist(snapshot, tmp_path)
        assert target.exists()
        assert "2024-Q2.json" in target.name

        loaded = FinancialsCollector.load_all_snapshots(tmp_path, "alphabet")
        assert len(loaded) == 1
        assert loaded[0].fiscal_year == 2024
        assert loaded[0].fiscal_quarter == 2

    def test_state_persist_and_load(self, tmp_path: Path):
        state = FilingState(
            company_id="alphabet",
            processed_accessions={"acc-001", "acc-002"},
            last_check=datetime.now(UTC),
        )
        target = FinancialsCollector.save_state(state, tmp_path)
        assert target.exists()

        loaded = FinancialsCollector.load_state(tmp_path, "alphabet")
        assert "acc-001" in loaded.processed_accessions
        assert loaded.last_check is not None

    def test_empty_state_for_unknown_company(self, tmp_path: Path):
        state = FinancialsCollector.load_state(tmp_path, "unknown_co")
        assert state.company_id == "unknown_co"
        assert len(state.processed_accessions) == 0


class TestTrendComputation:
    def test_apply_trends_qoq(self):
        prev_snapshot = QuarterlySnapshot(
            fiscal_year=2024,
            fiscal_quarter=1,
            period_end=date(2024, 3, 31),
            filing_type="10-Q",
            metrics={
                "total_revenue": QuarterlyMetric(
                    label="Revenue", value_usd_millions=80000.0
                ),
            },
            generated_at=datetime.now(UTC),
            metadata=SnapshotMetadata(),
        )

        # Q2 metrics (10% growth)
        metrics = {
            "total_revenue": QuarterlyMetric(
                label="Revenue", value_usd_millions=88000.0
            ),
        }

        collector = FinancialsCollector.__new__(FinancialsCollector)
        collector._warnings = []
        result = collector._apply_trends(metrics, 2024, 2, [prev_snapshot])

        rev = result["total_revenue"]
        assert rev.value_prev_quarter_usd_millions == 80000.0
        assert rev.qoq_change_pct == 10.0
