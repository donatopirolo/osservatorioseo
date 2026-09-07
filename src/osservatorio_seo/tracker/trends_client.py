"""Client for Google Trends data via DataForSEO API.

Provides interest-over-time data for AI platform keywords,
comparing Italy vs global search interest.

Google Trends allows max 5 keywords per query.  When more than 5 are
needed the client makes two calls, keeping the first keyword as an
anchor, and rescales the second batch so all values are comparable.

Docs: https://docs.dataforseo.com/v3/keywords_data/google_trends/explore/live/
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TrendsClientError(Exception):
    """DataForSEO ha risposto ma segnala un errore a livello di task.

    Porta il vero ``status_message`` dell'API, invece del generico "no data
    returned" che il chiamante mostrava finora qualunque fosse la causa
    reale (rate limit, credito esaurito, keyword non valide, ecc.).
    """


DEFAULT_KEYWORDS = ["ChatGPT", "Gemini", "Claude", "Perplexity", "DeepSeek", "Grok"]

# DataForSEO location code for Italy
_LOCATION_IT = 2380
_MAX_KEYWORDS = 5
_API_URL = "https://api.dataforseo.com/v3/keywords_data/google_trends/explore/live"


class TrendsClient:
    """Wrapper around DataForSEO Google Trends endpoint."""

    DEFAULT_KEYWORDS = DEFAULT_KEYWORDS

    def __init__(self, api_key: str, timeout_s: int = 60, max_retries: int = 3) -> None:
        self._api_key = api_key
        self._timeout = timeout_s
        self._max_retries = max_retries

    def fetch_interest(
        self,
        *,
        keywords: list[str] | None = None,
        geo: str = "",
    ) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
        """Fetch interest-over-time for keywords.

        Handles >5 keywords by splitting into batches with the first
        keyword as anchor, then rescaling the extra batch.

        Returns (keywords_list, points_list, averages_dict).
        On any error returns ([], [], {}).
        """
        kws = keywords or self.DEFAULT_KEYWORDS

        if len(kws) <= _MAX_KEYWORDS:
            return self._fetch_batch(kws, geo)

        # Split: first batch = first 5, second batch = anchor + overflow
        anchor = kws[0]
        batch1_kws = kws[:_MAX_KEYWORDS]
        batch2_kws = [anchor] + kws[_MAX_KEYWORDS:]

        kws1, pts1, avg1 = self._fetch_batch(batch1_kws, geo)
        if not kws1:
            return [], [], {}

        kws2, pts2, avg2 = self._fetch_batch(batch2_kws, geo)
        if not kws2:
            # Return batch1 alone if batch2 fails
            return kws1, pts1, avg1

        # Merge batch2 into batch1 by rescaling via anchor
        extra_kws = [k for k in kws2 if k != anchor]
        merged_kws = kws1 + extra_kws

        # Rescale points: for each date, scale extra values by (anchor_b1 / anchor_b2)
        pts2_by_date: dict[str, dict[str, int]] = {}
        for p in pts2:
            key = (
                p["date"].strftime("%Y-%m-%d")
                if isinstance(p["date"], datetime)
                else str(p["date"])
            )
            pts2_by_date[key] = p["values"]

        merged_pts: list[dict[str, Any]] = []
        for p in pts1:
            key = (
                p["date"].strftime("%Y-%m-%d")
                if isinstance(p["date"], datetime)
                else str(p["date"])
            )
            merged_values = dict(p["values"])
            b2_vals = pts2_by_date.get(key, {})
            anchor_b1 = merged_values.get(anchor, 0)
            anchor_b2 = b2_vals.get(anchor, 0)
            scale = anchor_b1 / anchor_b2 if anchor_b2 > 0 else 0
            for ek in extra_kws:
                merged_values[ek] = round(b2_vals.get(ek, 0) * scale)
            merged_pts.append({"date": p["date"], "values": merged_values})

        # Merge averages
        merged_avg = dict(avg1)
        anchor_avg1 = avg1.get(anchor, 0)
        anchor_avg2 = avg2.get(anchor, 0)
        avg_scale = anchor_avg1 / anchor_avg2 if anchor_avg2 > 0 else 0
        for ek in extra_kws:
            merged_avg[ek] = round(avg2.get(ek, 0) * avg_scale)

        return merged_kws, merged_pts, merged_avg

    def _fetch_batch(
        self,
        kws: list[str],
        geo: str,
    ) -> tuple[list[str], list[dict[str, Any]], dict[str, int]]:
        """Fetch a single batch of up to 5 keywords."""
        payload: dict[str, Any] = {
            "keywords": kws,
            "type": "web",
            "date_from": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
            "date_to": datetime.now().strftime("%Y-%m-%d"),
        }
        if geo.upper() == "IT":
            payload["location_code"] = _LOCATION_IT
            payload["language_code"] = "it"

        data = self._post_with_retry(payload, geo)
        if data is None:
            return [], [], {}

        task = data["tasks"][0]
        if task["status_code"] != 20000:
            raise TrendsClientError(
                f"DataForSEO status {task['status_code']}: "
                f"{task.get('status_message', 'nessun messaggio')}"
            )

        try:
            items = task["result"][0]["items"]
            graph_item = next(i for i in items if i["type"] == "google_trends_graph")
            raw_points = graph_item["data"]
            raw_averages = graph_item.get("averages", [])
        except (KeyError, IndexError, StopIteration):
            logger.warning("DataForSEO unexpected response structure for geo=%s", geo)
            return [], [], {}

        points: list[dict[str, Any]] = []
        for dp in raw_points:
            dt = datetime.fromisoformat(dp["date_from"])
            values = {kw: int(v) for kw, v in zip(kws, dp["values"], strict=False)}
            points.append({"date": dt, "values": values})

        averages = {kw: int(v) for kw, v in zip(kws, raw_averages, strict=False)}

        return list(kws), points, averages

    def _post_with_retry(self, payload: dict[str, Any], geo: str) -> dict[str, Any] | None:
        """POST con retry e backoff su errori transitori (timeout, 429, 5xx).

        Ritorna None (invece di sollevare) sugli errori non transitori o a
        retry esauriti: il chiamante li tratta come "nessun dato", stesso
        comportamento di prima per queste due categorie di fallimento.
        """
        headers = {
            "Authorization": f"Basic {self._api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(self._max_retries):
            is_last = attempt == self._max_retries - 1
            try:
                resp = httpx.post(_API_URL, headers=headers, json=[payload], timeout=self._timeout)
            except httpx.TransportError as e:
                # Timeout, connessione rifiutata, DNS: transitori, ritentabili.
                if is_last:
                    logger.warning("DataForSEO Trends errore di rete per geo=%s: %s", geo, e)
                    return None
                time.sleep(2**attempt + random.uniform(0.0, 0.5))
                continue
            except Exception:
                # Errore imprevisto e non di trasporto: non e' detto sia
                # transitorio, ci arrendiamo subito come prima di questa fix.
                logger.warning("DataForSEO Trends fetch failed for geo=%s", geo, exc_info=True)
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                if is_last:
                    logger.warning(
                        "DataForSEO Trends HTTP %s per geo=%s dopo %d tentativi",
                        resp.status_code,
                        geo,
                        self._max_retries,
                    )
                    return None
                time.sleep(2**attempt + random.uniform(0.0, 0.5))
                continue
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning("DataForSEO Trends fetch failed for geo=%s", geo, exc_info=True)
                return None
            return resp.json()
        return None
