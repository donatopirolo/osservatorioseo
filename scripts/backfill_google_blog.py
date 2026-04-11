#!/usr/bin/env python3
"""Backfill: recupera i post storici di Google Search Central Blog dal 2026.

Scrape della index page ``developers.google.com/search/blog``, estrazione
URL 2026, fetch delle singole pagine, summarize con Gemini 2.0 Flash, merge
negli archive JSON di Osservatorio SEO.

Date di pubblicazione REALI estratte dal testo del post (formato
'Weekday, Month DD, YYYY'). Usato per ``published_at`` + ``fetched_at``.

Uso (richiede OPENROUTER_API_KEY in env):
    .venv/bin/python scripts/backfill_google_blog.py [YEAR]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
from selectolax.parser import HTMLParser

from osservatorio_seo.config import load_settings
from osservatorio_seo.models import (
    Feed,
    FeedStats,
    Item,
    RawItem,
    Source,
)
from osservatorio_seo.ranker import Ranker
from osservatorio_seo.sources import override_importance
from osservatorio_seo.summarizer import Summarizer
from osservatorio_seo.tags import normalize_tags

INDEX_URL = "https://developers.google.com/search/blog"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

SOURCE = Source(
    id="google_search_central_blog",
    name="Google Search Central Blog",
    authority=10,
    type="official",
    fetcher="rss",
    feed_url="https://developers.google.com/search/blog/feed.xml",
    category_hint="google_updates",
    enabled=True,
)

MONTHS_EN = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}

ROME = ZoneInfo("Europe/Rome")


def fetch_index(client: httpx.Client, year: int) -> list[str]:
    """Ritorna tutte le URL del blog Google SC per ``year``."""
    resp = client.get(INDEX_URL, headers={"User-Agent": UA}, follow_redirects=True)
    resp.raise_for_status()
    pattern = rf'href="(/search/blog/{year}/\d{{2}}/[\w-]+)"'
    urls = re.findall(pattern, resp.text)
    # Deduplicate keeping order
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(f"https://developers.google.com{u}")
    return out


def clean_title(raw: str) -> str:
    # Remove '&nbsp;' entity and ' | Google Search Central Blog | Google for Developers' suffix
    t = raw.replace("&nbsp;", " ").replace("\xa0", " ")
    parts = re.split(r"\s*\|\s*", t)
    return parts[0].strip()


def fetch_post(client: httpx.Client, url: str) -> RawItem | None:
    """Fetch un post del blog e ritorna un RawItem (o None se parsing fallisce)."""
    resp = client.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=20)
    if resp.status_code != 200:
        return None
    tree = HTMLParser(resp.text)

    og_title = tree.css_first('meta[property="og:title"]')
    title = clean_title(og_title.attributes.get("content", "") if og_title else "")
    if not title:
        return None

    article = tree.css_first("article") or tree.css_first("main")
    if not article:
        return None
    text = article.text()

    # Parse date: "Weekday, Month DD, YYYY" (prima occorrenza dopo il titolo)
    date_match = re.search(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),\s+(\d{4})",
        text,
    )
    if not date_match:
        return None
    month_name, day_str, year_str = date_match.groups()
    published_local = datetime(
        int(year_str),
        MONTHS_EN[month_name],
        int(day_str),
        7,
        0,
        tzinfo=ROME,
    )
    published_utc = published_local.astimezone(UTC)

    # Body: testo dopo la data, tagliato a "Was this helpful" / "Send feedback"
    idx = text.find(date_match.group(0))
    body = text[idx + len(date_match.group(0)) :] if idx >= 0 else text
    for cut in ("Was this helpful?", "Send feedback", "Send a comment"):
        if cut in body:
            body = body.split(cut)[0]
    body = " ".join(body.split())[:4000]
    if len(body) < 50:
        return None

    return RawItem(
        title=title,
        url=url,
        source_id=SOURCE.id,
        published_at=published_utc,
        content=body,
        language_original="en",
    )


async def summarize_all(
    raw_items: list[RawItem], summarizer: Summarizer
) -> list[tuple[RawItem, Item | None, float]]:
    """Ritorna (raw, item, cost) per ogni raw. item=None se summarize fallisce."""
    results: list[tuple[RawItem, Item | None, float]] = []
    for idx, raw in enumerate(raw_items, start=1):
        print(f"  [{idx}/{len(raw_items)}] Summarizing: {raw.title[:70]}…")
        try:
            summary = await summarizer.summarize_item(raw, SOURCE)
        except Exception as e:
            print(f"    FAILED: {e}")
            results.append((raw, None, 0.0))
            continue
        day_str = raw.published_at.astimezone(ROME).strftime("%Y-%m-%d")
        short_id = hashlib.sha256(raw.url.encode()).hexdigest()[:6].upper()
        normalized_tags = normalize_tags(summary.tags)
        item = Item(
            id=f"item_{day_str}_gsc_{short_id}",
            title_original=raw.title,
            title_it=summary.title_it,
            summary_it=summary.summary_it,
            url=raw.url,
            source=SOURCE,
            category=summary.category,
            tags=normalized_tags,
            importance=override_importance(SOURCE.id, summary.importance, normalized_tags),
            published_at=raw.published_at,
            fetched_at=raw.published_at,  # coincide con la data reale
            is_doc_change=False,
            language_original=raw.language_original,
            summarizer_model=summary.model_used,
            raw_hash="sha256:" + hashlib.sha256(raw.content.encode()).hexdigest()[:16],
        )
        results.append((raw, item, summary.cost_eur))
    return results


def build_feed_for_day(
    day_iso: str,
    new_items: list[Item],
    archive_dir: Path,
    total_cost: float,
) -> Feed:
    """Crea un Feed per ``day_iso`` mergiando con l'archivio esistente se c'è."""
    existing_file = archive_dir / f"{day_iso}.json"
    existing_items: list[Item] = []
    if existing_file.exists():
        try:
            data = json.loads(existing_file.read_text(encoding="utf-8"))
            existing_feed = Feed.model_validate(data)
            existing_items = existing_feed.items
        except Exception as e:
            print(f"    ⚠️ existing archive parse error: {e}, overwriting")

    # Dedup: evita di reinserire un item già presente (per URL)
    existing_urls = {i.url for i in existing_items}
    fresh_new = [i for i in new_items if i.url not in existing_urls]
    merged_items = existing_items + fresh_new

    ranker = Ranker()
    ranked = ranker.rank(merged_items)

    # generated_at = 07:00 Europe/Rome del giorno stesso (backfill "cron-like")
    y, m, d = day_iso.split("-")
    gen_local = datetime(int(y), int(m), int(d), 7, 0, tzinfo=ROME)
    gen_utc = gen_local.astimezone(UTC)

    stats = FeedStats(
        sources_checked=1
        if not existing_items
        else max(1, len({i.source.id for i in merged_items})),
        sources_failed=0,
        items_collected=len(merged_items),
        items_after_dedup=len(merged_items),
        doc_changes_detected=0,
        ai_cost_eur=round(total_cost, 5),
    )

    return Feed(
        schema_version="1.0",
        generated_at=gen_utc,
        generated_at_local=gen_local,
        timezone="Europe/Rome",
        run_id=f"{day_iso}-0700",
        stats=stats,
        top10=ranked.top10,
        categories=ranked.categories,
        items=merged_items,
        doc_watcher_status=[],
        failed_sources=[],
    )


async def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    archive_dir = data_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    print(f"Backfill Google Search Central Blog year={year}")

    settings = load_settings()
    summarizer = Summarizer(
        api_key=settings.openrouter_api_key,
        primary_model=settings.summarizer_model,
        fallback_models=settings.fallback_models,
    )

    # Step 1: extract URLs
    with httpx.Client() as client:
        print(f"\n[1/4] Fetching index page {INDEX_URL}…")
        urls = fetch_index(client, year)
        print(f"      found {len(urls)} URLs for {year}")

        # Step 2: filter URLs already present in any archive
        existing_urls: set[str] = set()
        for arc in archive_dir.glob("20*.json"):
            try:
                data = json.loads(arc.read_text(encoding="utf-8"))
                for item in data.get("items", []):
                    existing_urls.add(item.get("url", ""))
            except Exception:
                continue

        new_urls = [u for u in urls if u not in existing_urls]
        print(f"      {len(new_urls)} new URLs (not already in archive)")
        if not new_urls:
            print("Nothing to backfill. Exiting.")
            return

        # Step 3: fetch each post
        print("\n[2/4] Fetching posts…")
        raw_items: list[RawItem] = []
        for i, u in enumerate(new_urls, start=1):
            print(f"  [{i}/{len(new_urls)}] {u}")
            raw = fetch_post(client, u)
            if raw is None:
                print("    parse failed, skipping")
                continue
            print(f"    title: {raw.title[:80]}")
            print(f"    published: {raw.published_at.isoformat()}")
            raw_items.append(raw)

    if not raw_items:
        print("No raw items parsed. Exiting.")
        return

    # Step 4: summarize
    print("\n[3/4] Summarizing with AI…")
    results = await summarize_all(raw_items, summarizer)
    total_cost = sum(cost for _, _, cost in results)
    successful = [item for _, item, _ in results if item is not None]
    print(f"      {len(successful)}/{len(results)} summarized, total cost €{total_cost:.4f}")

    if not successful:
        print("No items summarized successfully. Exiting.")
        return

    # Step 5: group by day and merge into archive JSONs
    print("\n[4/4] Writing to archive…")
    by_day: dict[str, list[Item]] = defaultdict(list)
    for item in successful:
        day_iso = item.published_at.astimezone(ROME).strftime("%Y-%m-%d")
        by_day[day_iso].append(item)

    for day_iso, day_items in sorted(by_day.items()):
        print(f"  {day_iso}: merging {len(day_items)} item(s)")
        cost_for_day = sum(c for _, it, c in results if it is not None and it in day_items)
        feed = build_feed_for_day(day_iso, day_items, archive_dir, cost_for_day)
        (archive_dir / f"{day_iso}.json").write_text(
            feed.model_dump_json(indent=2), encoding="utf-8"
        )
        print(f"    wrote {archive_dir / f'{day_iso}.json'} ({len(feed.items)} items total)")

    print("\nDone. Run `.venv/bin/python scripts/rebuild_seo_html.py` to regenerate HTML.")


if __name__ == "__main__":
    asyncio.run(main())
