#!/usr/bin/env python3
"""One-shot backfill — fetches all Alphabet financials from SEC EDGAR since 2021.

Usage:
    python scripts/backfill_google_financials.py [--dry-run] [--since YEAR]

Options:
    --dry-run    Fetch and display data without generating AI analysis
    --since      Start year for backfill (default: 2021)

Environment variables:
    OPENROUTER_API_KEY     Required for AI analysis generation (unless --dry-run)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.google_financials.collector import FinancialsCollector
from osservatorio_seo.google_financials.edgar_client import EdgarClient
from osservatorio_seo.premium_writer import PremiumWriter


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Google Financials data")
    parser.add_argument("--dry-run", action="store_true", help="Skip AI analysis")
    parser.add_argument("--since", type=int, default=2021, help="Start year")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data" / "google_financials"

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not args.dry_run and not api_key:
        print("WARNING: OPENROUTER_API_KEY not set. Skipping AI analysis.")
        args.dry_run = True

    edgar = EdgarClient()
    collector = FinancialsCollector(edgar=edgar)

    for company in collector.enabled_companies:
        print(f"\n{'=' * 60}")
        print(f"Backfilling {company.name} (CIK {company.cik}) since {args.since}")
        print(f"{'=' * 60}")

        print("\nFetching all available data from SEC EDGAR...")
        snapshots = await collector.collect_all_available(company, since_year=args.since)

        if not snapshots:
            print("  No data found.")
            continue

        print(f"\nFound {len(snapshots)} quarters:")
        total_cost = 0.0

        for snapshot in snapshots:
            q_label = f"Q{snapshot.fiscal_quarter} {snapshot.fiscal_year}"
            n_metrics = len(snapshot.metrics)
            warnings = snapshot.metadata.warnings

            # Persist snapshot
            target = collector.persist(snapshot, data_dir)
            print(f"\n  [{q_label}] {n_metrics} metrics → {target}")

            # Show key metrics
            for mid in (
                "total_revenue",
                "google_search_revenue",
                "traffic_acquisition_costs",
                "capital_expenditures",
            ):
                m = snapshot.metrics.get(mid)
                if m:
                    yoy = f" (YoY {m.yoy_change_pct:+.1f}%)" if m.yoy_change_pct is not None else ""
                    print(f"    {m.label}: ${m.value_usd_millions:,.1f}M{yoy}")

            if snapshot.tac_as_pct_of_search_revenue is not None:
                print(f"    TAC/Search: {snapshot.tac_as_pct_of_search_revenue:.1f}%")

            if warnings:
                for w in warnings:
                    print(f"    ⚠ {w}")

            # Generate AI analysis
            if not args.dry_run:
                # Skip if analysis already exists (resumability)
                analysis_file = (
                    data_dir
                    / company.id
                    / "analyses"
                    / f"{snapshot.fiscal_year}-Q{snapshot.fiscal_quarter}.json"
                )
                if analysis_file.exists():
                    print(f"    Analysis already exists, skipping: {analysis_file}")
                    continue

                print("    Generating AI analysis...")
                try:
                    writer = PremiumWriter(api_key=api_key)
                    idx = snapshots.index(snapshot)
                    previous = snapshots[:idx]
                    analysis = await writer.write_financials_analysis(
                        snapshot,
                        company.name,
                        previous_snapshots=previous,
                    )
                    analysis_json = analysis.model_dump_json(indent=2)
                    analysis_target = collector.persist_analysis(
                        analysis_json,
                        data_dir,
                        company.id,
                        snapshot.fiscal_year,
                        snapshot.fiscal_quarter,
                    )
                    print(f"    Analysis: {analysis_target} (€{analysis.cost_eur:.4f})")
                    total_cost += analysis.cost_eur

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(2)
                except Exception as exc:
                    print(f"    ERROR generating analysis: {exc}")
                    # Continue with next quarter — the script is resumable
                    # and a future run will retry just the missing analyses.

        print(f"\n{'=' * 60}")
        print(f"Backfill complete: {len(snapshots)} quarters")
        if not args.dry_run:
            print(f"Total AI cost: €{total_cost:.4f}")
        print(f"Data saved to: {data_dir / company.id}/")


if __name__ == "__main__":
    asyncio.run(main())
