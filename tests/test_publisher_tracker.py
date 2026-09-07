"""Test delle pagine tracker generate da Publisher (D11)."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from osservatorio_seo.publisher import Publisher


def _write_snapshot(
    data_dir: Path, year: int, week: int, generated_at: datetime, **overrides
) -> None:
    snapshots_dir = data_dir / "tracker" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    base = {
        "schema_version": "3.0",
        "year": year,
        "week": week,
        "generated_at": generated_at.isoformat(),
        "top10_it": [{"rank": 1, "domain": "google.com", "categories": []}],
        "top10_global": [{"rank": 1, "domain": "google.com", "categories": []}],
        "ai_platforms_it": [
            {
                "domain": "chatgpt.com",
                "label": "ChatGPT",
                "type": "chatbot",
                "rank": 5,
                "bucket": "100",
            }
        ],
        "ai_platforms_global": [
            {
                "domain": "chatgpt.com",
                "label": "ChatGPT",
                "type": "chatbot",
                "rank": 50,
                "bucket": "100",
            }
        ],
        "trends_it": {
            "keywords": ["ChatGPT", "Claude"],
            "points": [{"date": generated_at.isoformat(), "values": {"ChatGPT": 80, "Claude": 20}}],
            "averages": {"ChatGPT": 75, "Claude": 18},
        },
        "trends_global": {
            "keywords": ["ChatGPT", "Claude"],
            "points": [{"date": generated_at.isoformat(), "values": {"ChatGPT": 90, "Claude": 30}}],
            "averages": {"ChatGPT": 85, "Claude": 28},
        },
        "bot_human_it": {"points": []},
        "bot_human_global": {"points": []},
        "ai_bots_ua_it": {"agents": [], "points": []},
        "ai_bots_ua_global": {"agents": [], "points": []},
        "crawl_purpose_it": {"purposes": [], "points": []},
        "crawl_purpose_global": {"purposes": [], "points": []},
        "industry_it": [],
        "industry_global": [],
        "device_type_it": {"points": []},
        "device_type_global": {"points": []},
        "os_it": [],
        "os_global": [],
        "metadata": {"radar_calls": 0, "warnings": []},
    }
    base.update(overrides)
    filename = f"{year}-W{week:02d}.json"
    (snapshots_dir / filename).write_text(json.dumps(base), encoding="utf-8")


def test_ssg_tracker_writes_latest_and_monthly_permalinks(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    _write_snapshot(data_dir, 2026, 14, datetime(2026, 4, 6, tzinfo=UTC))
    _write_snapshot(data_dir, 2026, 15, datetime(2026, 4, 13, tzinfo=UTC))
    _write_snapshot(data_dir, 2026, 18, datetime(2026, 5, 4, tzinfo=UTC))

    pub = Publisher(data_dir=data_dir, archive_dir=data_dir / "archive")
    pub._ssg_tracker(
        renderer=_renderer(),
        site_dir=site_dir,
        allow_indexing=True,
    )

    # /tracker/ mostra l'ultimo snapshot in assoluto (maggio)
    latest_html = (site_dir / "tracker" / "index.html").read_text()
    assert "Settimana 18, 2026" in latest_html

    # Permalink mensili (D11): un URL per ogni mese con almeno uno snapshot
    april_html = (site_dir / "tracker" / "2026-04" / "index.html").read_text()
    may_html = (site_dir / "tracker" / "2026-05" / "index.html").read_text()
    # Aprile ha 2 snapshot (W14, W15): il mensile mostra l'ultimo del mese (W15)
    assert "Settimana 15, 2026" in april_html
    assert "Settimana 18, 2026" in may_html

    # Canonical distinti, non tutti sullo stesso /tracker/
    assert 'href="https://www.osservatorioseo.com/tracker/2026-04/"' in april_html
    assert 'href="https://www.osservatorioseo.com/tracker/2026-05/"' in may_html


def test_ssg_tracker_writes_csv_alongside_html(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    _write_snapshot(data_dir, 2026, 14, datetime(2026, 4, 6, tzinfo=UTC))

    pub = Publisher(data_dir=data_dir, archive_dir=data_dir / "archive")
    pub._ssg_tracker(renderer=_renderer(), site_dir=site_dir, allow_indexing=True)

    csv_path = site_dir / "tracker" / "data.csv"
    assert csv_path.exists()
    rows = list(csv.reader(csv_path.open()))
    assert rows[0] == ["scope", "section", "key", "value"]
    assert any(r[1] == "ai_platform_rank" and r[2] == "ChatGPT" for r in rows)


def test_ssg_tracker_renders_real_trends_numbers_in_html(tmp_path: Path) -> None:
    """Regressione D11: i numeri di Google Trends devono comparire
    nell'HTML servito (tabella server-side), non solo dentro il canvas JS."""
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    _write_snapshot(data_dir, 2026, 14, datetime(2026, 4, 6, tzinfo=UTC))

    pub = Publisher(data_dir=data_dir, archive_dir=data_dir / "archive")
    pub._ssg_tracker(renderer=_renderer(), site_dir=site_dir, allow_indexing=True)

    html = (site_dir / "tracker" / "index.html").read_text()
    assert "<table" in html
    assert ">80<" in html  # valore IT di ChatGPT
    assert ">90<" in html  # valore Mondo di ChatGPT


def test_ssg_tracker_includes_jsonld_dataset(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    _write_snapshot(data_dir, 2026, 14, datetime(2026, 4, 6, tzinfo=UTC))

    pub = Publisher(data_dir=data_dir, archive_dir=data_dir / "archive")
    pub._ssg_tracker(renderer=_renderer(), site_dir=site_dir, allow_indexing=True)

    html = (site_dir / "tracker" / "index.html").read_text()
    assert '"@type": "Dataset"' in html


def _renderer():
    from osservatorio_seo.renderer import HtmlRenderer

    return HtmlRenderer(templates_dir=Path("templates"))


def test_sitemap_includes_monthly_tracker_permalinks(tmp_path: Path) -> None:
    """Regressione D11: i permalink mensili del tracker non erano mai stati
    aggiunti alla sitemap (non esistevano)."""
    from datetime import UTC as _UTC

    from osservatorio_seo.models import Feed, FeedStats, Item, Source

    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    _write_snapshot(data_dir, 2026, 14, datetime(2026, 4, 6, tzinfo=UTC))

    item = Item(
        id="a",
        title_original="a",
        title_it="a",
        summary_it="s",
        url="https://example.com/a",
        source=Source(
            id="s", name="S", authority=5, type="official", fetcher="rss", feed_url="https://x.com"
        ),
        category="google_updates",
        tags=[],
        importance=3,
        published_at=datetime.now(_UTC),
        fetched_at=datetime.now(_UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )
    feed = Feed(
        generated_at=datetime.now(_UTC),
        generated_at_local=datetime.now(_UTC),
        timezone="Europe/Rome",
        run_id="2026-04-11-0700",
        stats=FeedStats(
            sources_checked=1,
            sources_failed=0,
            items_collected=1,
            items_after_dedup=1,
            doc_changes_detected=0,
            ai_cost_eur=0.0,
        ),
        top10=["a"],
        categories={"google_updates": ["a"]},
        items=[item],
        doc_watcher_status=[],
        failed_sources=[],
    )

    pub = Publisher(
        data_dir=data_dir, archive_dir=data_dir / "archive", site_data_dir=site_dir / "data"
    )
    pub.publish_ssg(
        feed, [], [], templates_dir=Path("templates"), site_dir=site_dir, allow_indexing=True
    )

    sitemap = (site_dir / "sitemap.xml").read_text()
    assert "/tracker/2026-04/" in sitemap
