#!/usr/bin/env python3
"""Weekly tracker update — fetches Radar + Pages Analytics, saves snapshot, rebuilds SSG.

Usage:
    .venv/bin/python scripts/update_tracker.py [--monthly-report]

Flags:
    --monthly-report  Also generate the monthly editorial report for the
                      previous calendar month (should be set when running
                      on the first Monday of a month).

Environment variables:
    CLOUDFLARE_API_TOKEN       Required, token with Radar + Analytics read
    CLOUDFLARE_ACCOUNT_ID      Required for Pages Analytics
    CLOUDFLARE_ZONE_ID         Required for Pages Analytics
    OPENROUTER_API_KEY         Required if --monthly-report is set
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.premium_writer import PremiumWriter
from osservatorio_seo.tracker.collector import TrackerCollector
from osservatorio_seo.tracker.models import TrackerSnapshot
from osservatorio_seo.tracker.pages_analytics import PagesAnalyticsClient
from osservatorio_seo.tracker.radar_client import RadarClient


def _iso_year_week(d: date) -> tuple[int, int]:
    year, week, _ = d.isocalendar()
    return year, week


async def run_weekly_collection(repo_root: Path) -> Path:
    """Fetch snapshot, persist, return path."""
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not token:
        raise SystemExit("CLOUDFLARE_API_TOKEN not set")

    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    pages_client = None
    if acct and zone:
        pages_client = PagesAnalyticsClient(api_token=token, account_id=acct, zone_id=zone)

    radar = RadarClient(api_token=token)
    collector = TrackerCollector(
        radar=radar,
        pages_analytics=pages_client,
        location="IT",
    )

    today = date.today()
    year, week = _iso_year_week(today)
    print(f"Collecting tracker data for {year}-W{week:02d}...")
    snapshot = await collector.collect(year=year, week=week)

    tracker_dir = repo_root / "data" / "tracker"
    target = TrackerCollector.persist(snapshot, base_dir=tracker_dir)
    print(f"  saved {target}")
    if snapshot.metadata.warnings:
        print("  warnings:")
        for w in snapshot.metadata.warnings:
            print(f"    - {w}")
    return target


async def run_monthly_report(repo_root: Path) -> Path | None:
    """Generate the monthly report for the PREVIOUS calendar month."""
    if os.environ.get("OPENROUTER_API_KEY") is None:
        raise SystemExit("OPENROUTER_API_KEY not set, cannot generate monthly report")

    today = date.today()
    if today.month == 1:
        prev_year, prev_month = today.year - 1, 12
    else:
        prev_year, prev_month = today.year, today.month - 1

    snapshots_dir = repo_root / "data" / "tracker" / "snapshots"
    if not snapshots_dir.exists():
        print("No snapshots yet, skipping monthly report")
        return None

    relevant: list[TrackerSnapshot] = []
    for p in sorted(snapshots_dir.glob("*-W*.json")):
        try:
            snap = TrackerSnapshot.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  skipping {p.name}: {e}")
            continue
        if snap.generated_at.month == prev_month and snap.generated_at.year == prev_year:
            relevant.append(snap)

    if not relevant:
        print(f"No snapshots for {prev_year}-{prev_month:02d}, skipping monthly report")
        return None

    print(
        f"Generating monthly report for {prev_year}-{prev_month:02d} from {len(relevant)} snapshots..."
    )

    writer = PremiumWriter(api_key=os.environ["OPENROUTER_API_KEY"])
    report = await writer.write_tracker_report(
        year=prev_year,
        month=prev_month,
        snapshots=relevant,
    )

    reports_dir = repo_root / "data" / "tracker" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    target = reports_dir / f"{prev_year}-{prev_month:02d}.json"
    target.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"  saved {target} (cost EUR{report.cost_eur:.4f}, model {report.model_used})")
    return target


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--monthly-report", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    await run_weekly_collection(repo_root)
    if args.monthly_report:
        await run_monthly_report(repo_root)

    print("\nDone. Run `.venv/bin/python scripts/rebuild_seo_html.py` to regenerate HTML.")


if __name__ == "__main__":
    asyncio.run(main())
