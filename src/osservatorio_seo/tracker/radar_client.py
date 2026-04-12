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
        """Fetch top N domains in a category for a location."""
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
        """Fetch traffic/rank timeseries for a category."""
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
            raise RadarClientError(f"Radar API error {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        if not data.get("success", False):
            errs = data.get("errors", [])
            msg = "; ".join(e.get("message", str(e)) for e in errs) or "unknown"
            raise RadarClientError(f"Radar API reported failure: {msg}")
        return data
