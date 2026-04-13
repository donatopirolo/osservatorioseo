"""Async client for Cloudflare Radar API (v2 endpoints).

Docs: https://developers.cloudflare.com/api/operations/radar-get-ranking-top

Free tier, requires API token with `Zone.Radar Read` permission.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

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

    async def ranking_top(
        self,
        *,
        location: str | None = None,
        limit: int = 10,
        ranking_type: str = "POPULAR",
    ) -> list[dict]:
        """Fetch top N domains globally or for a location.

        Returns list of {rank, domain, categories}.
        """
        params: dict[str, Any] = {"limit": limit, "rankingType": ranking_type}
        if location is not None:
            params["location"] = location
        data = await self._get("/ranking/top", params)
        rows = data["result"].get("top_0", [])
        return [
            {
                "rank": row["rank"],
                "domain": row["domain"],
                "categories": [c["name"] for c in row.get("categories", []) if isinstance(c, dict)],
            }
            for row in rows
        ]

    async def domain_detail(
        self,
        *,
        domain: str,
        location: str | None = None,
    ) -> dict:
        """Fetch rank and bucket for a single domain.

        Returns {rank, bucket} where bucket is always a str (e.g. "200" or ">200000").
        rank may be None when the domain is outside the ranked set.
        """
        params: dict[str, Any] = {}
        if location is not None:
            params["location"] = location
        data = await self._get(f"/ranking/domain/{domain}", params)
        detail = data["result"].get("details_0", {})
        return {
            "rank": detail.get("rank"),
            "bucket": str(detail["bucket"]),
        }

    async def domain_timeseries(
        self,
        *,
        domain: str,
        location: str | None = None,
        date_range: str = "52w",
    ) -> list[dict]:
        """Fetch weekly rank timeseries for a single domain.

        Returns list of {date, rank} sorted chronologically.
        """
        params: dict[str, Any] = {"domains": domain, "dateRange": date_range}
        if location is not None:
            params["location"] = location
        data = await self._get("/ranking/timeseries_groups", params)
        serie = data["result"].get("serie_0", {})
        timestamps = serie.get("timestamps", [])
        ranks = serie.get(domain, [])
        return [{"date": ts, "rank": rank} for ts, rank in zip(timestamps, ranks, strict=False)]

    async def bot_human_timeseries(
        self,
        *,
        location: str | None = None,
        date_range: str = "12w",
    ) -> list[dict]:
        """Fetch human vs bot traffic percentage timeseries.

        Returns list of {date, human_pct, bot_pct}.
        """
        params: dict[str, Any] = {"dateRange": date_range}
        if location is not None:
            params["location"] = location
        data = await self._get("/http/timeseries_groups/bot_class", params)
        serie = data["result"].get("serie_0", {})
        timestamps = serie.get("timestamps", [])
        human = serie.get("human", [])
        bot = serie.get("bot", [])
        return [
            {"date": ts, "human_pct": float(h), "bot_pct": float(b)}
            for ts, h, b in zip(timestamps, human, bot, strict=False)
        ]

    async def ai_bots_user_agent(
        self,
        *,
        location: str | None = None,
        date_range: str = "12w",
        agg_interval: str = "1w",
    ) -> tuple[list[str], list[dict]]:
        """Fetch AI bot traffic breakdown by user-agent.

        Returns (agents_list, points_list) where each point is
        {date, <agent>: pct_str, ...}.
        """
        params: dict[str, Any] = {"dateRange": date_range, "aggInterval": agg_interval}
        if location is not None:
            params["location"] = location
        data = await self._get("/ai/bots/timeseries_groups/user_agent", params)
        serie = data["result"].get("serie_0", {})
        return self._unpack_named_timeseries(serie)

    async def crawl_purpose(
        self,
        *,
        location: str | None = None,
        date_range: str = "12w",
        agg_interval: str = "1w",
    ) -> tuple[list[str], list[dict]]:
        """Fetch AI bot traffic breakdown by crawl purpose.

        Returns (purposes_list, points_list) where each point is
        {date, <purpose>: pct_str, ...}.
        """
        params: dict[str, Any] = {"dateRange": date_range, "aggInterval": agg_interval}
        if location is not None:
            params["location"] = location
        data = await self._get("/ai/bots/timeseries_groups/crawl_purpose", params)
        serie = data["result"].get("serie_0", {})
        return self._unpack_named_timeseries(serie)

    async def industry_summary(
        self,
        *,
        location: str | None = None,
        date_range: str = "28d",
    ) -> list[dict]:
        """Fetch AI bot traffic breakdown by industry.

        Returns list of {industry, pct} sorted descending by pct,
        with "other" always last.
        """
        params: dict[str, Any] = {"dateRange": date_range}
        if location is not None:
            params["location"] = location
        data = await self._get("/ai/bots/summary/industry", params)
        summary = data["result"].get("summary_0", {})
        other_pct = summary.pop("other", None)
        rows = sorted(
            [{"industry": k, "pct": float(v)} for k, v in summary.items()],
            key=lambda r: r["pct"],
            reverse=True,
        )
        if other_pct is not None:
            rows.append({"industry": "other", "pct": float(other_pct)})
        return rows

    async def device_type_timeseries(self, *, location=None, date_range="12w"):
        params = {"dateRange": date_range}
        if location is not None:
            params["location"] = location
        data = await self._get("/http/timeseries_groups/device_type", params)
        serie = data["result"].get("serie_0", {})
        timestamps = serie.get("timestamps", [])
        mobile = serie.get("mobile", [])
        desktop = serie.get("desktop", [])
        return [
            {"date": ts, "mobile_pct": float(m), "desktop_pct": float(d)}
            for ts, m, d in zip(timestamps, mobile, desktop, strict=False)
        ]

    async def os_summary(self, *, location=None, date_range="28d"):
        params = {"dateRange": date_range}
        if location is not None:
            params["location"] = location
        data = await self._get("/http/summary/os", params)
        summary = data["result"].get("summary_0", {})
        other_pct = summary.pop("other", None)
        rows = sorted(
            [{"os": k, "pct": float(v)} for k, v in summary.items()],
            key=lambda r: r["pct"],
            reverse=True,
        )
        if other_pct is not None:
            rows.append({"os": "other", "pct": float(other_pct)})
        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unpack_named_timeseries(serie: dict) -> tuple[list[str], list[dict]]:
        """Convert a serie_0 dict into (keys, [{date, values: {key: float}}])."""
        timestamps = serie.get("timestamps", [])
        keys = [k for k in serie if k != "timestamps"]
        points = []
        for i, ts in enumerate(timestamps):
            values = {}
            for key in keys:
                raw = serie[key]
                values[key] = float(raw[i]) if i < len(raw) else 0.0
            points.append({"date": ts, "values": values})
        return keys, points

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
