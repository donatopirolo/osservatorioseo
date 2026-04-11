"""CLI entrypoint."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from osservatorio_seo.config import load_settings
from osservatorio_seo.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="osservatorio-seo")
    sub = parser.add_subparsers(dest="command", required=True)

    refresh = sub.add_parser("refresh", help="Run the daily pipeline")
    refresh.add_argument("--sources", type=Path, default=Path("config/sources.yml"))
    refresh.add_argument("--doc-watcher", type=Path, default=Path("config/doc_watcher.yml"))
    refresh.add_argument("--site-data", type=Path, default=Path("site/data"))

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command == "refresh":
        settings = load_settings()
        pipeline = Pipeline(
            settings=settings,
            sources_path=args.sources,
            doc_watcher_path=args.doc_watcher,
            site_data_dir=args.site_data,
        )
        feed = asyncio.run(pipeline.run())
        print(f"OK — {len(feed.items)} items, top10={len(feed.top10)}, cost={feed.stats.ai_cost_eur}€")
        sys.exit(0)
