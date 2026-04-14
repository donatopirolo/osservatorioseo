"""Async client for SEC EDGAR XBRL API.

Fetches financial data for any publicly traded US company via CIK number.
Designed for Alphabet (CIK 0001652044) but fully parametric on CIK.

SEC EDGAR API docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Rate limit: 10 req/s.  No authentication required.
Mandatory: User-Agent header with contact info.
"""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EDGAR_BASE_URL = "https://data.sec.gov"
USER_AGENT = "OsservatorioSEO/1.0 (contact@osservatorioseo.it)"

# Fiscal period codes used in XBRL data
_FP_QUARTERLY = {"Q1", "Q2", "Q3", "Q4"}
_FP_ANNUAL = "FY"

# XBRL entries for flow metrics (revenues, income, cash flows) expose
# both standalone quarterly values (3-month period) and year-to-date
# cumulative values (6/9 months). We must filter by period duration to
# get the right one. Ranges include ~10-day tolerance for fiscal variations.
_DAYS_3M = (80, 100)   # three-month standalone (a single quarter)
_DAYS_6M = (170, 195)  # six-month YTD (through end of Q2)
_DAYS_9M = (260, 285)  # nine-month YTD (through end of Q3)
_DAYS_FY = (350, 380)  # twelve-month (full fiscal year)


def _period_days(entry: dict[str, Any]) -> int | None:
    """Return the duration in days of an XBRL entry, or None if missing/invalid."""
    start = entry.get("start")
    end = entry.get("end")
    if not start or not end:
        return None
    try:
        s = _date.fromisoformat(start)
        e = _date.fromisoformat(end)
    except (TypeError, ValueError):
        return None
    return (e - s).days + 1


class EdgarClientError(Exception):
    """Raised on any non-2xx response or data access failure."""


class EdgarClient:
    """Lightweight async wrapper for SEC EDGAR XBRL endpoints."""

    def __init__(
        self,
        timeout_s: int = 30,
        base_url: str = EDGAR_BASE_URL,
        user_agent: str = USER_AGENT,
    ) -> None:
        self._timeout = timeout_s
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_company_facts(self, cik: str) -> dict[str, Any]:
        """Fetch ALL XBRL facts for a company (single request).

        Returns the full JSON with structure:
        ``{cik, entityName, facts: {<namespace>: {<tag>: {units: ...}}}}``

        This covers standard ``us-gaap`` and ``dei`` tags.  For custom
        extension tags (e.g. ``goog:GoogleSearchAndOtherRevenue``) use
        :meth:`fetch_company_concept` instead.
        """
        padded_cik = cik.lstrip("0").zfill(10)
        path = f"/api/xbrl/companyfacts/CIK{padded_cik}.json"
        return await self._get(path)

    async def fetch_company_concept(
        self,
        cik: str,
        namespace: str,
        tag: str,
    ) -> dict[str, Any]:
        """Fetch a single XBRL concept across all filings.

        This is required for company-specific extension tags (e.g.
        ``goog:GoogleSearchAndOtherRevenue``) which are NOT included in
        the ``companyfacts`` aggregate endpoint.

        Returns: ``{cik, taxonomy, tag, label, units: {USD: [...]}}``
        """
        padded_cik = cik.lstrip("0").zfill(10)
        path = f"/api/xbrl/companyconcept/CIK{padded_cik}/{namespace}/{tag}.json"
        return await self._get(path)

    async def fetch_filing_index(self, cik: str) -> dict[str, Any]:
        """Fetch the filing submission index for a company.

        Returns metadata about all filings (10-K, 10-Q, 8-K, etc.)
        including accession numbers, filing dates, and form types.
        Used for auto-discovery of new filings.
        """
        padded_cik = cik.lstrip("0").zfill(10)
        path = f"/submissions/CIK{padded_cik}.json"
        return await self._get(path)

    # ------------------------------------------------------------------
    # XBRL extraction helpers
    # ------------------------------------------------------------------

    def extract_metric(
        self,
        facts: dict[str, Any],
        *,
        tags: list[str],
        namespace: str,
        fiscal_year: int,
        fiscal_period: str,
        form_type: str | None = None,
        duration_range: tuple[int, int] | None = None,
    ) -> float | None:
        """Extract a single metric value from XBRL data.

        Works with both ``companyfacts`` and ``companyconcept`` response
        formats.  Tries each tag in order; returns value in raw USD
        (not millions) or None if not found.

        ``duration_range`` optionally restricts entries by period length
        in days (``end - start + 1``), e.g. ``(80, 100)`` for 3-month
        standalone quarterly values. Without this filter, YTD cumulative
        entries (6/9 months) may accidentally match a single-quarter query.

        For ``companyfacts`` format:
            ``facts.facts.<namespace>.<tag>.units.USD``

        For ``companyconcept`` format (single-tag responses):
            ``facts.units.USD``  (the tag is already selected)
        """
        # --- companyfacts format: nested under facts.<namespace>.<tag> ---
        ns_facts = facts.get("facts", {}).get(namespace, {})
        for tag in tags:
            tag_data = ns_facts.get(tag)
            if tag_data is None:
                continue
            usd_entries = tag_data.get("units", {}).get("USD", [])
            match = self._find_entry(
                usd_entries,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                form_type=form_type,
                duration_range=duration_range,
            )
            if match is not None:
                return float(match["val"])

        # --- companyconcept format: flat structure with units.USD ---
        if "units" in facts and "facts" not in facts:
            usd_entries = facts.get("units", {}).get("USD", [])
            match = self._find_entry(
                usd_entries,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                form_type=form_type,
                duration_range=duration_range,
            )
            if match is not None:
                return float(match["val"])

        return None

    def extract_quarterly_value(
        self,
        facts: dict[str, Any],
        *,
        tags: list[str],
        namespace: str,
        fiscal_year: int,
        fiscal_quarter: int,
    ) -> float | None:
        """Extract a quarter's standalone value (single-quarter flow, not YTD).

        XBRL 10-Q filings expose both 3-month standalone entries and
        cumulative YTD entries for the same ``fp=Q2/Q3`` period. A naive
        lookup can grab the YTD one and produce wildly wrong numbers
        (e.g. negative revenue when computing ``Q4 = FY - Q2_YTD - Q3_YTD``).

        Strategy:
        1. Prefer the 3-month standalone entry (``end - start ≈ 90 days``).
        2. For Q4 (only FY is reported), compute ``FY - Q3_YTD`` where
           ``Q3_YTD`` is the 9-month cumulative. Fallback to
           ``FY - 3*mean(Q1,Q2,Q3)`` is NOT safe, so if Q3_YTD missing,
           give up.
        3. For Q2/Q3 if 3-month standalone is missing, derive from
           YTD deltas: ``Q2 = Q2_YTD(6mo) - Q1`` etc.
        """
        fp = f"Q{fiscal_quarter}"

        # Step 1: try 3-month standalone entry (the clean case)
        value = self.extract_metric(
            facts,
            tags=tags,
            namespace=namespace,
            fiscal_year=fiscal_year,
            fiscal_period=fp,
            duration_range=_DAYS_3M,
        )
        if value is not None:
            return value

        # Step 2: derive from YTD entries via subtraction
        if fiscal_quarter == 1:
            # Q1 YTD equals Q1 standalone; if 3-month wasn't found,
            # try without duration filter (should still be 3 months).
            return self.extract_metric(
                facts,
                tags=tags,
                namespace=namespace,
                fiscal_year=fiscal_year,
                fiscal_period=fp,
            )

        if fiscal_quarter == 4:
            fy_value = self.extract_metric(
                facts,
                tags=tags,
                namespace=namespace,
                fiscal_year=fiscal_year,
                fiscal_period=_FP_ANNUAL,
                duration_range=_DAYS_FY,
            )
            q3_ytd = self.extract_metric(
                facts,
                tags=tags,
                namespace=namespace,
                fiscal_year=fiscal_year,
                fiscal_period="Q3",
                duration_range=_DAYS_9M,
            )
            if fy_value is not None and q3_ytd is not None:
                return fy_value - q3_ytd
            logger.warning(
                "Cannot derive Q4 %d standalone: FY=%s, Q3_YTD=%s for tags %s",
                fiscal_year,
                fy_value,
                q3_ytd,
                tags,
            )
            return None

        # Q2 or Q3: derive as <current YTD> - <previous YTD>
        prev_q = fiscal_quarter - 1
        cur_duration = _DAYS_6M if fiscal_quarter == 2 else _DAYS_9M
        prev_duration = _DAYS_3M if prev_q == 1 else _DAYS_6M

        cur_ytd = self.extract_metric(
            facts,
            tags=tags,
            namespace=namespace,
            fiscal_year=fiscal_year,
            fiscal_period=fp,
            duration_range=cur_duration,
        )
        prev_ytd = self.extract_metric(
            facts,
            tags=tags,
            namespace=namespace,
            fiscal_year=fiscal_year,
            fiscal_period=f"Q{prev_q}",
            duration_range=prev_duration,
        )
        if cur_ytd is not None and prev_ytd is not None:
            return cur_ytd - prev_ytd
        return None

    def find_new_filings(
        self,
        index: dict[str, Any],
        *,
        known_accessions: set[str],
        form_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Compare filing index against known accessions to find new filings.

        Returns list of dicts with keys: accessionNumber, filingDate, form, primaryDocument.
        """
        recent = index.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        docs = recent.get("primaryDocument", [])

        new_filings = []
        for i, accn in enumerate(accessions):
            if accn in known_accessions:
                continue
            form = forms[i] if i < len(forms) else ""
            if form_types and form not in form_types:
                continue
            new_filings.append({
                "accessionNumber": accn,
                "form": form,
                "filingDate": dates[i] if i < len(dates) else "",
                "primaryDocument": docs[i] if i < len(docs) else "",
            })

        return new_filings

    def list_available_quarters(
        self,
        facts: dict[str, Any],
        *,
        tags: list[str],
        namespace: str,
        since_year: int = 2021,
    ) -> list[tuple[int, int]]:
        """List all (year, quarter) pairs with data available for a given metric.

        Useful for backfill — discovers which quarters have XBRL data.
        Considers any fiscal period tagged Q1-Q3 (regardless of duration,
        since we can derive standalone from YTD) and FY (needed to derive Q4).
        """
        ns_facts = facts.get("facts", {}).get(namespace, {})
        quarters: set[tuple[int, int]] = set()

        for tag in tags:
            tag_data = ns_facts.get(tag)
            if tag_data is None:
                continue
            for entry in tag_data.get("units", {}).get("USD", []):
                fy = entry.get("fy")
                fp = entry.get("fp", "")
                if fy is None or fy < since_year:
                    continue
                if fp in _FP_QUARTERLY:
                    quarters.add((fy, int(fp[1])))
                elif fp == _FP_ANNUAL:
                    # Annual data means Q4 can be derived
                    quarters.add((fy, 4))

        return sorted(quarters)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_entry(
        entries: list[dict[str, Any]],
        *,
        fiscal_year: int,
        fiscal_period: str,
        form_type: str | None = None,
        duration_range: tuple[int, int] | None = None,
    ) -> dict[str, Any] | None:
        """Find the best matching entry for a fiscal period.

        When multiple entries match, prefer the most recent filing date.
        ``duration_range`` optionally filters by ``end - start + 1`` days.
        """
        candidates = []
        for entry in entries:
            if entry.get("fy") != fiscal_year:
                continue
            if entry.get("fp") != fiscal_period:
                continue
            if form_type and entry.get("form") != form_type:
                continue
            if duration_range is not None:
                days = _period_days(entry)
                if days is None or not (duration_range[0] <= days <= duration_range[1]):
                    continue
            candidates.append(entry)

        if not candidates:
            return None

        # Prefer the most recently filed entry (amended filings replace originals)
        candidates.sort(key=lambda e: e.get("filed", ""), reverse=True)
        return candidates[0]

    async def _get(self, path: str) -> dict[str, Any]:
        """Perform a GET request to SEC EDGAR."""
        url = f"{self._base_url}{path}"
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            raise EdgarClientError(
                f"SEC EDGAR error {resp.status_code} for {path}: {resp.text[:300]}"
            )
        return resp.json()
