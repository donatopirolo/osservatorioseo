"""Collector: orchestrates EDGAR API calls into QuarterlySnapshots.

Responsibilities:
- Load company config from YAML
- Fetch company facts (XBRL) and extract quarterly metrics
- Compute QoQ and YoY trend deltas
- Compute derived ratios (TAC%, search%, operating margin)
- Detect new filings (10-Q, 10-K, 8-K) via polling
- Persist snapshots, events, and state to git-versioned JSON
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from osservatorio_seo.google_financials.edgar_client import EdgarClient
from osservatorio_seo.google_financials.models import (
    CompanyConfig,
    FilingState,
    MetricConfig,
    QuarterlyMetric,
    QuarterlySnapshot,
    SnapshotMetadata,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "config" / "google_financials.yaml"

# Quarter end dates (approximate — month/day) for fiscal period_end calculation
_QUARTER_END: dict[int, tuple[int, int]] = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}

# Millions divisor
_MILLIONS = 1_000_000


def _pct_change(current: float, previous: float) -> float | None:
    """Compute percentage change, returning None if previous is zero."""
    if previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


class FinancialsCollector:
    """Orchestrates EDGAR data fetches and builds QuarterlySnapshots."""

    def __init__(
        self,
        edgar: EdgarClient,
        config_path: Path | None = None,
    ) -> None:
        self._edgar = edgar
        self._cfg_path = config_path or _DEFAULT_CONFIG
        self._companies: list[CompanyConfig] = self._load_config()
        self._warnings: list[str] = []

    def _load_config(self) -> list[CompanyConfig]:
        if not self._cfg_path.exists():
            logger.warning("google_financials config not found: %s", self._cfg_path)
            return []
        with self._cfg_path.open() as fh:
            data = yaml.safe_load(fh)
        companies = []
        for raw in data.get("companies", []):
            metrics_raw = raw.pop("metrics", {})
            metrics = {
                k: MetricConfig(**v) for k, v in metrics_raw.items()
            }
            companies.append(CompanyConfig(**raw, metrics=metrics))
        return companies

    @property
    def enabled_companies(self) -> list[CompanyConfig]:
        return [c for c in self._companies if c.enabled]

    # ------------------------------------------------------------------
    # Public API: quarterly data
    # ------------------------------------------------------------------

    async def _fetch_all_sources(self, company: CompanyConfig) -> tuple[dict[str, Any], int]:
        """Fetch companyfacts + all needed companyconcept data.

        Returns ``(facts_by_source, edgar_calls)`` where ``facts_by_source``
        maps source keys to XBRL JSON responses.
        """
        facts_by_source: dict[str, Any] = {}
        edgar_calls = 0

        # 1. Fetch companyfacts (us-gaap aggregate)
        facts_by_source["companyfacts"] = await self._edgar.fetch_company_facts(company.cik)
        edgar_calls += 1

        # 2. Fetch companyconcept for each custom-namespace metric tag
        fetched_concepts: set[str] = set()
        for metric_cfg in company.metrics.values():
            if metric_cfg.namespace == "us-gaap":
                continue
            for tag in metric_cfg.tags:
                key = f"{metric_cfg.namespace}:{tag}"
                if key in fetched_concepts:
                    continue
                fetched_concepts.add(key)
                try:
                    concept_data = await self._edgar.fetch_company_concept(
                        company.cik, metric_cfg.namespace, tag
                    )
                    facts_by_source[key] = concept_data
                    edgar_calls += 1
                except Exception as exc:  # noqa: BLE001
                    self._warnings.append(f"companyconcept {key}: {exc}")
                    logger.warning("Failed to fetch concept %s: %s", key, exc)

        return facts_by_source, edgar_calls

    async def collect(
        self,
        company: CompanyConfig,
        fiscal_year: int,
        fiscal_quarter: int,
        *,
        previous_snapshots: list[QuarterlySnapshot] | None = None,
    ) -> QuarterlySnapshot:
        """Fetch XBRL data and build a QuarterlySnapshot for one quarter."""
        self._warnings = []

        facts_by_source, edgar_calls = await self._fetch_all_sources(company)

        metrics = self._extract_all_metrics(
            facts_by_source, company, fiscal_year, fiscal_quarter
        )

        # Compute trends if we have previous snapshots
        if previous_snapshots:
            metrics = self._apply_trends(
                metrics, fiscal_year, fiscal_quarter, previous_snapshots
            )

        # Compute derived ratios
        tac_pct = self._compute_tac_pct(metrics)
        search_pct = self._compute_search_pct(metrics)
        margin_pct = self._compute_margin_pct(metrics)

        # Period end date
        month, day = _QUARTER_END[fiscal_quarter]
        period_end = date(fiscal_year, month, day)

        return QuarterlySnapshot(
            company_id=company.id,
            fiscal_year=fiscal_year,
            fiscal_quarter=fiscal_quarter,
            period_end=period_end,
            filing_type="10-K" if fiscal_quarter == 4 else "10-Q",
            metrics=metrics,
            tac_as_pct_of_search_revenue=tac_pct,
            search_as_pct_of_total_revenue=search_pct,
            operating_margin_pct=margin_pct,
            generated_at=datetime.now(UTC),
            metadata=SnapshotMetadata(
                edgar_calls=edgar_calls,
                warnings=list(self._warnings),
                source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company.cik}.json",
            ),
        )

    async def collect_all_available(
        self,
        company: CompanyConfig,
        since_year: int = 2021,
    ) -> list[QuarterlySnapshot]:
        """Backfill: fetch all available quarters for a company since a given year.

        Returns snapshots sorted chronologically with trends computed.
        """
        if not company.metrics:
            logger.warning("No metrics configured for %s", company.id)
            return []

        facts_by_source, edgar_calls = await self._fetch_all_sources(company)

        # Discover available quarters using the first us-gaap metric (most reliable)
        discovery_metric = None
        for mcfg in company.metrics.values():
            if mcfg.namespace == "us-gaap":
                discovery_metric = mcfg
                break
        if discovery_metric is None:
            discovery_metric = next(iter(company.metrics.values()))

        # Use companyfacts for discovery (us-gaap tags)
        available = self._edgar.list_available_quarters(
            facts_by_source.get("companyfacts", {}),
            tags=discovery_metric.tags,
            namespace=discovery_metric.namespace,
            since_year=since_year,
        )

        snapshots: list[QuarterlySnapshot] = []
        for year, quarter in available:
            self._warnings = []
            metrics = self._extract_all_metrics(
                facts_by_source, company, year, quarter
            )

            if not metrics:
                logger.warning("No metrics found for %s Q%d %d", company.id, quarter, year)
                continue

            metrics = self._apply_trends(metrics, year, quarter, snapshots)

            tac_pct = self._compute_tac_pct(metrics)
            search_pct = self._compute_search_pct(metrics)
            margin_pct = self._compute_margin_pct(metrics)

            month, day = _QUARTER_END[quarter]
            period_end = date(year, month, day)

            snapshot = QuarterlySnapshot(
                company_id=company.id,
                fiscal_year=year,
                fiscal_quarter=quarter,
                period_end=period_end,
                filing_type="10-K" if quarter == 4 else "10-Q",
                metrics=metrics,
                tac_as_pct_of_search_revenue=tac_pct,
                search_as_pct_of_total_revenue=search_pct,
                operating_margin_pct=margin_pct,
                generated_at=datetime.now(UTC),
                metadata=SnapshotMetadata(
                    edgar_calls=edgar_calls if not snapshots else 0,
                    warnings=list(self._warnings),
                    source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{company.cik}.json",
                ),
            )
            snapshots.append(snapshot)

        return snapshots

    # ------------------------------------------------------------------
    # Public API: new filing discovery
    # ------------------------------------------------------------------

    async def check_new_filings(
        self,
        company: CompanyConfig,
        state: FilingState,
    ) -> list[dict[str, Any]]:
        """Check for new filings not yet processed."""
        index = await self._edgar.fetch_filing_index(company.cik)
        return self._edgar.find_new_filings(
            index,
            known_accessions=state.processed_accessions,
            form_types=company.filing_types,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @staticmethod
    def persist(snapshot: QuarterlySnapshot, base_dir: Path) -> Path:
        """Write snapshot to ``<base_dir>/<company_id>/snapshots/<YYYY-QN>.json``."""
        snapshots_dir = base_dir / snapshot.company_id / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{snapshot.fiscal_year}-Q{snapshot.fiscal_quarter}.json"
        target = snapshots_dir / filename
        target.write_text(
            snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        return target

    @staticmethod
    def persist_analysis(analysis_json: str, base_dir: Path, company_id: str, year: int, quarter: int) -> Path:
        """Write AI analysis JSON to ``<base_dir>/<company_id>/analyses/<YYYY-QN>.json``."""
        analyses_dir = base_dir / company_id / "analyses"
        analyses_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{year}-Q{quarter}.json"
        target = analyses_dir / filename
        target.write_text(analysis_json + "\n", encoding="utf-8")
        return target

    @staticmethod
    def persist_event(event_json: str, base_dir: Path, company_id: str, filing_date: str, accn: str) -> Path:
        """Write 8-K event filing to ``<base_dir>/<company_id>/events/<date>_8K_<suffix>.json``."""
        events_dir = base_dir / company_id / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        safe_accn = accn.replace("-", "")[:10]
        filename = f"{filing_date}_8K_{safe_accn}.json"
        target = events_dir / filename
        target.write_text(event_json + "\n", encoding="utf-8")
        return target

    @staticmethod
    def load_all_snapshots(base_dir: Path, company_id: str) -> list[QuarterlySnapshot]:
        """Load all snapshots for a company, sorted chronologically."""
        snapshots_dir = base_dir / company_id / "snapshots"
        if not snapshots_dir.exists():
            return []
        snapshots = []
        for f in sorted(snapshots_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            snapshots.append(QuarterlySnapshot(**data))
        return snapshots

    @staticmethod
    def load_all_analyses(base_dir: Path, company_id: str) -> list[dict[str, Any]]:
        """Load all analyses for a company, sorted chronologically."""
        analyses_dir = base_dir / company_id / "analyses"
        if not analyses_dir.exists():
            return []
        analyses = []
        for f in sorted(analyses_dir.glob("*.json")):
            analyses.append(json.loads(f.read_text(encoding="utf-8")))
        return analyses

    @staticmethod
    def load_state(base_dir: Path, company_id: str) -> FilingState:
        """Load filing state for a company (or create empty state)."""
        state_file = base_dir / company_id / "state.json"
        if state_file.exists():
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return FilingState(**data)
        return FilingState(company_id=company_id)

    @staticmethod
    def save_state(state: FilingState, base_dir: Path) -> Path:
        """Persist filing state."""
        state_dir = base_dir / state.company_id
        state_dir.mkdir(parents=True, exist_ok=True)
        target = state_dir / "state.json"
        target.write_text(
            state.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        return target

    # ------------------------------------------------------------------
    # Internal: metric extraction
    # ------------------------------------------------------------------

    def _extract_all_metrics(
        self,
        facts_by_source: dict[str, dict[str, Any]],
        company: CompanyConfig,
        fiscal_year: int,
        fiscal_quarter: int,
    ) -> dict[str, QuarterlyMetric]:
        """Extract all configured metrics for a quarter.

        ``facts_by_source`` maps a source key to the XBRL JSON:
        - ``"companyfacts"`` → full companyfacts response (us-gaap tags)
        - ``"goog:TagName"`` → individual companyconcept responses
        """
        metrics: dict[str, QuarterlyMetric] = {}
        for metric_id, metric_cfg in company.metrics.items():
            # Choose the right data source based on namespace
            if metric_cfg.namespace == "us-gaap":
                source_data = facts_by_source.get("companyfacts", {})
            else:
                # For custom namespaces, try each tag's companyconcept data
                source_data = None
                for tag in metric_cfg.tags:
                    key = f"{metric_cfg.namespace}:{tag}"
                    if key in facts_by_source:
                        source_data = facts_by_source[key]
                        break
                if source_data is None:
                    self._warnings.append(
                        f"{metric_id}: no concept data fetched for {metric_cfg.namespace}:{metric_cfg.tags}"
                    )
                    continue

            value = self._edgar.extract_quarterly_value(
                source_data,
                tags=metric_cfg.tags,
                namespace=metric_cfg.namespace,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
            )
            if value is None:
                self._warnings.append(
                    f"{metric_id}: no data for {fiscal_year}-Q{fiscal_quarter}"
                )
                continue

            value_millions = round(value / _MILLIONS, 1)
            metrics[metric_id] = QuarterlyMetric(
                label=metric_cfg.label_it,
                value_usd_millions=value_millions,
            )

        return metrics

    def _apply_trends(
        self,
        metrics: dict[str, QuarterlyMetric],
        fiscal_year: int,
        fiscal_quarter: int,
        previous: list[QuarterlySnapshot],
    ) -> dict[str, QuarterlyMetric]:
        """Enrich metrics with QoQ and YoY change percentages."""
        # Find previous quarter snapshot
        if fiscal_quarter == 1:
            prev_year, prev_q = fiscal_year - 1, 4
        else:
            prev_year, prev_q = fiscal_year, fiscal_quarter - 1
        prev_snap = self._find_snapshot(previous, prev_year, prev_q)

        # Find same quarter last year
        yoy_snap = self._find_snapshot(previous, fiscal_year - 1, fiscal_quarter)

        for metric_id, metric in metrics.items():
            if prev_snap and metric_id in prev_snap.metrics:
                prev_val = prev_snap.metrics[metric_id].value_usd_millions
                metric.value_prev_quarter_usd_millions = prev_val
                metric.qoq_change_pct = _pct_change(
                    metric.value_usd_millions, prev_val
                )

            if yoy_snap and metric_id in yoy_snap.metrics:
                yoy_val = yoy_snap.metrics[metric_id].value_usd_millions
                metric.value_prev_year_usd_millions = yoy_val
                metric.yoy_change_pct = _pct_change(
                    metric.value_usd_millions, yoy_val
                )

        return metrics

    @staticmethod
    def _find_snapshot(
        snapshots: list[QuarterlySnapshot],
        year: int,
        quarter: int,
    ) -> QuarterlySnapshot | None:
        for s in snapshots:
            if s.fiscal_year == year and s.fiscal_quarter == quarter:
                return s
        return None

    # ------------------------------------------------------------------
    # Internal: derived ratios
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_tac_pct(metrics: dict[str, QuarterlyMetric]) -> float | None:
        tac = metrics.get("traffic_acquisition_costs")
        search = metrics.get("google_search_revenue")
        if tac and search and search.value_usd_millions > 0:
            return round(tac.value_usd_millions / search.value_usd_millions * 100, 2)
        return None

    @staticmethod
    def _compute_search_pct(metrics: dict[str, QuarterlyMetric]) -> float | None:
        search = metrics.get("google_search_revenue")
        total = metrics.get("total_revenue")
        if search and total and total.value_usd_millions > 0:
            return round(search.value_usd_millions / total.value_usd_millions * 100, 2)
        return None

    @staticmethod
    def _compute_margin_pct(metrics: dict[str, QuarterlyMetric]) -> float | None:
        income = metrics.get("operating_income")
        total = metrics.get("total_revenue")
        if income and total and total.value_usd_millions > 0:
            return round(income.value_usd_millions / total.value_usd_millions * 100, 2)
        return None
