#!/usr/bin/env python3
"""Weekly tracker update — fetches Radar + Google Trends data, saves snapshot.

Usage:
    python scripts/update_tracker.py

Environment variables:
    CLOUDFLARE_RADAR_TOKEN     Required, token with Account Analytics Read
    CLOUDFLARE_API_TOKEN       Fallback if CLOUDFLARE_RADAR_TOKEN not set
    DATAFORSEO_API_KEY         Base64-encoded DataForSEO credentials (optional)
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.radar_client import RadarClient
from osservatorio_seo.tracker.trends_client import TrendsClient


async def main() -> None:
    token = os.environ.get("CLOUDFLARE_RADAR_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise SystemExit("CLOUDFLARE_RADAR_TOKEN (or CLOUDFLARE_API_TOKEN) not set")

    repo_root = Path(__file__).resolve().parent.parent
    radar = RadarClient(api_token=token)

    dataforseo_key = os.environ.get("DATAFORSEO_API_KEY")
    trends = TrendsClient(api_key=dataforseo_key) if dataforseo_key else None
    collector = TrackerCollector(radar=radar, trends_client=trends)

    today = date.today()
    year, week, _ = today.isocalendar()
    print(f"Collecting tracker v2 data for {year}-W{week:02d}...")
    snapshot = await collector.collect(year=year, week=week)

    tracker_dir = repo_root / "data" / "tracker"
    target = TrackerCollector.persist(snapshot, base_dir=tracker_dir)
    print(f"  saved {target}")
    print(f"  radar calls: {snapshot.metadata.radar_calls}")
    if snapshot.metadata.warnings:
        print("  warnings:")
        for w in snapshot.metadata.warnings:
            print(f"    - {w}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
