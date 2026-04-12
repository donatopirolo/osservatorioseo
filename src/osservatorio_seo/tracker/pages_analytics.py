"""Async client for Cloudflare Pages Analytics via the GraphQL Analytics API.

Docs: https://developers.cloudflare.com/analytics/graphql-api/

Scope: we only need referrer breakdown for a single zone (OsservatorioSEO
pages.dev domain). The result is aggregated into labeled groups suitable
for Chart 7 of the tracker.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from osservatorio_seo.tracker.models import AnalyticsReferrer

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

# Regex-free source grouping: substring match on lowercase referer host.
# Order matters: first match wins.
_SOURCE_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Google", ("google.",)),
    ("Bing", ("bing.",)),
    ("DuckDuckGo", ("duckduckgo.",)),
    ("Yahoo", ("yahoo.",)),
    (
        "ChatGPT",
        (
            "chat.openai.",
            "openai.",
        ),
    ),
    (
        "Claude",
        (
            "claude.ai",
            "anthropic.",
        ),
    ),
    ("Perplexity", ("perplexity.",)),
    (
        "Gemini",
        (
            "gemini.google.",
            "bard.google.",
        ),
    ),
]


class PagesAnalyticsError(Exception):
    """Raised on any GraphQL error or transport failure."""


class PagesAnalyticsClient:
    """GraphQL client for Cloudflare Pages / Analytics referrer breakdown."""

    def __init__(
        self,
        api_token: str,
        account_id: str,
        zone_id: str,
        timeout_s: int = 30,
    ) -> None:
        self._api_token = api_token
        self._account_id = account_id
        self._zone_id = zone_id
        self._timeout = timeout_s

    async def referrer_share(self, days: int = 30) -> list[AnalyticsReferrer]:
        """Return aggregated referrer share for the last N days."""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        query = """
        query Referrers($zoneId: String!, $start: Time!, $end: Time!) {
          viewer {
            accounts(filter: {accountTag: "ACCOUNT_ID_PLACEHOLDER"}) {
              httpRequestsAdaptiveGroups(
                filter: {
                  zoneTag: $zoneId,
                  datetime_gt: $start,
                  datetime_lt: $end
                },
                limit: 1000
              ) {
                dimensions { refererHost }
                count
              }
            }
          }
        }
        """.replace("ACCOUNT_ID_PLACEHOLDER", self._account_id)

        variables = {
            "zoneId": self._zone_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        body = {"query": query, "variables": variables}
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(GRAPHQL_URL, json=body, headers=headers)

        if resp.status_code >= 400:
            raise PagesAnalyticsError(f"Pages Analytics HTTP {resp.status_code}: {resp.text[:200]}")
        payload = resp.json()
        if payload.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in payload["errors"])
            raise PagesAnalyticsError(f"GraphQL error: {msgs}")

        groups = self._extract_groups(payload)
        return self._aggregate(groups)

    @staticmethod
    def _extract_groups(payload: dict[str, Any]) -> list[tuple[str, int]]:
        """Pull (referer_host, count) tuples out of the GraphQL shape."""
        out: list[tuple[str, int]] = []
        accounts = payload.get("data", {}).get("viewer", {}).get("accounts", [])
        for acct in accounts:
            for row in acct.get("httpRequestsAdaptiveGroups", []):
                host = (row.get("dimensions", {}) or {}).get("refererHost", "") or ""
                count = int(row.get("count", 0) or 0)
                out.append((host.lower(), count))
        return out

    @staticmethod
    def _aggregate(groups: list[tuple[str, int]]) -> list[AnalyticsReferrer]:
        """Aggregate by labeled source; normalize to percentages."""
        buckets: dict[str, int] = {}
        total = 0
        for host, count in groups:
            total += count
            label = "Direct" if not host else None
            if label is None:
                for name, matchers in _SOURCE_GROUPS:
                    if any(m in host for m in matchers):
                        label = name
                        break
            if label is None:
                label = "Other"
            buckets[label] = buckets.get(label, 0) + count

        if total == 0:
            return []

        result = [
            AnalyticsReferrer(source=name, share_pct=round(count / total * 100, 2))
            for name, count in buckets.items()
        ]
        known_order = [
            "Google",
            "Bing",
            "DuckDuckGo",
            "Yahoo",
            "ChatGPT",
            "Claude",
            "Gemini",
            "Perplexity",
            "Direct",
            "Other",
        ]
        result.sort(key=lambda r: known_order.index(r.source) if r.source in known_order else 99)
        return result
