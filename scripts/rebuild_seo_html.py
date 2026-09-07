#!/usr/bin/env python3
"""Rigenera tutti gli HTML SSG a partire dai JSON in ``data/archive/*.json``
e dal feed corrente ``data/feed.json``.

Usage:
    .venv/bin/python scripts/rebuild_seo_html.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.config import load_doc_watcher, load_sources
from osservatorio_seo.models import Feed
from osservatorio_seo.publisher import Publisher


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    site_dir = repo_root / "site"
    archive_dir = data_dir / "archive"
    templates_dir = repo_root / "templates"

    sources = load_sources(repo_root / "config" / "sources.yml")
    doc_pages = load_doc_watcher(repo_root / "config" / "doc_watcher.yml")

    pub = Publisher(
        data_dir=data_dir,
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )

    # Pulizia totale prima di rigenerare: senza questo, le pagine che un run
    # precedente ha scritto ma che il run corrente non riscrive piu' (slug
    # cambiato, importance abbassata, doppio run dello stesso giorno)
    # restano per sempre in site/archivio come pagine orfane indicizzabili.
    shutil.rmtree(site_dir / "archivio", ignore_errors=True)

    # Rebuild lineare: per ogni giorno d'archivio scriviamo SOLO le sue
    # pagine permanenti (snapshot + articoli). Homepage, hub, sitemap,
    # tracker e dossier dipendono dallo stato completo, non dal singolo
    # giorno: prima venivano ricalcolati una volta per ogni file d'archivio
    # (decine di rigenerazioni identiche e sprecate), ora una volta sola alla
    # fine, con il feed piu' recente — publish_global e' comunque idempotente
    # rispetto all'archivio completo.
    latest_feed: Feed | None = None
    for json_path in sorted(archive_dir.glob("20*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            feed = Feed.model_validate(data)
        except Exception as exc:
            print(f"SKIP {json_path.name}: {exc}")
            continue
        print(f"Rendering day {json_path.stem}…")
        pub.publish_day(feed, templates_dir=templates_dir, site_dir=site_dir, allow_indexing=True)
        latest_feed = feed

    current_feed_path = data_dir / "feed.json"
    if current_feed_path.exists():
        data = json.loads(current_feed_path.read_text(encoding="utf-8"))
        latest_feed = Feed.model_validate(data)
        print(f"Rendering current feed ({latest_feed.run_id})…")
        pub.publish_day(
            latest_feed, templates_dir=templates_dir, site_dir=site_dir, allow_indexing=True
        )

    if latest_feed is not None:
        print("Rendering global state (homepage, hub, sitemap, tracker, dossier)…")
        pub.publish_global(
            latest_feed,
            sources,
            doc_pages,
            templates_dir=templates_dir,
            site_dir=site_dir,
            allow_indexing=True,
        )

    print("Done.")


if __name__ == "__main__":
    main()
