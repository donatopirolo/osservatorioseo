#!/usr/bin/env python3
"""Weekly Google Financials update — checks for new SEC filings and generates analysis.

Usage:
    python scripts/update_google_financials.py

Environment variables:
    OPENROUTER_API_KEY     Required for AI analysis generation
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.google_financials.collector import FinancialsCollector
from osservatorio_seo.google_financials.edgar_client import EdgarClient
from osservatorio_seo.premium_writer import PremiumWriter


async def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data" / "google_financials"

    edgar = EdgarClient()
    collector = FinancialsCollector(edgar=edgar)

    api_key = os.environ.get("OPENROUTER_API_KEY")

    any_new = False

    for company in collector.enabled_companies:
        print(f"\nChecking {company.name} (CIK {company.cik})...")

        # Load state
        state = collector.load_state(data_dir, company.id)

        # Check for new filings
        try:
            new_filings = await collector.check_new_filings(company, state)
        except Exception as exc:
            print(f"  ERROR checking filings: {exc}")
            continue

        if not new_filings:
            print("  No new filings found.")
            continue

        # Separate by type
        quarterly_filings = [f for f in new_filings if f["form"] in ("10-Q", "10-K")]
        event_filings = [f for f in new_filings if f["form"] == "8-K"]

        print(f"  Found {len(quarterly_filings)} quarterly + {len(event_filings)} event filings")

        # Process quarterly filings
        for filing in quarterly_filings:
            print(f"  Processing {filing['form']} filed {filing['filingDate']}...")

            # Determine fiscal year/quarter from filing date
            # We need to fetch facts and find what quarter this filing covers
            try:
                existing_snapshots = collector.load_all_snapshots(data_dir, company.id)

                # Fetch all data and find the latest quarter not yet processed
                facts_by_source, _ = await collector._fetch_all_sources(company)
                company_facts = facts_by_source.get("companyfacts", {})

                # Find quarters from the first metric
                first_metric = next(iter(company.metrics.values()))
                available = edgar.list_available_quarters(
                    company_facts,
                    tags=first_metric.tags,
                    namespace=first_metric.namespace,
                    since_year=2021,
                )

                existing_keys = {
                    (s.fiscal_year, s.fiscal_quarter)
                    for s in existing_snapshots
                }

                new_quarters = [
                    (y, q) for y, q in available if (y, q) not in existing_keys
                ]

                for year, quarter in new_quarters:
                    print(f"    Building snapshot for Q{quarter} {year}...")
                    snapshot = await collector.collect(
                        company, year, quarter,
                        previous_snapshots=existing_snapshots,
                    )
                    target = collector.persist(snapshot, data_dir)
                    print(f"    Saved: {target}")
                    existing_snapshots.append(snapshot)

                    # Generate AI analysis
                    if api_key:
                        print(f"    Generating AI analysis...")
                        writer = PremiumWriter(api_key=api_key)
                        analysis = await writer.write_financials_analysis(
                            snapshot,
                            company.name,
                            previous_snapshots=existing_snapshots[:-1],
                        )
                        analysis_json = analysis.model_dump_json(indent=2)
                        target = collector.persist_analysis(
                            analysis_json, data_dir, company.id, year, quarter
                        )
                        print(f"    Analysis saved: {target} (cost: €{analysis.cost_eur:.4f})")
                    else:
                        print("    Skipping AI analysis (OPENROUTER_API_KEY not set)")

                    any_new = True

            except Exception as exc:
                print(f"  ERROR processing quarterly filing: {exc}")
                import traceback
                traceback.print_exc()

            # Mark filing as processed
            state.processed_accessions.add(filing["accessionNumber"])

        # Process 8-K filings (just track them for now)
        for filing in event_filings:
            state.processed_accessions.add(filing["accessionNumber"])
            print(f"  Tracked 8-K: {filing['filingDate']} (accn: {filing['accessionNumber'][:20]}...)")
            any_new = True

        # Save state
        state.last_check = datetime.now(UTC)
        collector.save_state(state, data_dir)
        print(f"  State updated. Total processed: {len(state.processed_accessions)}")

    if any_new:
        print("\nNew data found — site rebuild needed.")
    else:
        print("\nNo new data. Nothing to do.")


if __name__ == "__main__":
    asyncio.run(main())
