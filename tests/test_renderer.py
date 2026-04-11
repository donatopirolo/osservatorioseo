from pathlib import Path

from osservatorio_seo.renderer import HtmlRenderer


def test_renderer_smoke_layout() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    html = renderer.render_raw(
        "layout.html.jinja",
        {
            "page_title": "Test page",
            "page_description": "desc",
            "canonical_url": "https://example.com/",
            "active_nav": "today",
            "noindex": True,
            "content": "<p>hello</p>",
        },
    )
    assert "<!DOCTYPE html>" in html
    assert "<title>Test page" in html
    assert '<meta name="description" content="desc"' in html
    assert '<link rel="canonical" href="https://example.com/"' in html
    assert '<meta name="robots" content="noindex, nofollow"' in html
    assert "<p>hello</p>" in html
    assert 'href="/"' in html
    assert 'href="/archivio/"' in html
    assert 'href="/docs/"' in html


def test_renderer_no_noindex_when_false() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    html = renderer.render_raw(
        "layout.html.jinja",
        {
            "page_title": "Public",
            "page_description": "d",
            "canonical_url": "https://example.com/",
            "active_nav": "today",
            "noindex": False,
            "content": "<p>ok</p>",
        },
    )
    assert "noindex" not in html


def test_render_homepage_includes_top10_and_categories() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    html = renderer.render_homepage(
        {
            "page_title": "Home",
            "page_description": "Daily SEO/AI news",
            "canonical_url": "https://osservatorioseo.pages.dev/",
            "active_nav": "today",
            "noindex": True,
            "meta_line": "SYSTEM STATUS: OPTIMAL",
            "top10_cards": ["<article class='card'>FakeTop</article>"],
            "categories": [
                {
                    "label": "Google Updates",
                    "icon": "history",
                    "path": "/categoria/google-updates/",
                    "cards": ["<article class='card'>FakeCat</article>"],
                }
            ],
            "failed_sources": [],
            "breadcrumbs": [{"name": "Home", "url": "https://osservatorioseo.pages.dev/"}],
        }
    )
    assert "TOP 10 DEL GIORNO" in html
    assert "FakeTop" in html
    assert "Google Updates" in html
    assert "FakeCat" in html
    assert 'id="archive-results"' in html


def test_render_snapshot_has_date_in_titles() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    html = renderer.render_snapshot(
        {
            "page_title": "Snapshot",
            "page_description": "d",
            "canonical_url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/",
            "active_nav": "archive",
            "noindex": True,
            "meta_line": "SNAPSHOT 2026-04-11",
            "top10_title": "> TOP 10 DEL GIORNO 11 04 2026",
            "categories_title": "> TUTTE PER CATEGORIA 11 04 2026",
            "top10_cards": [],
            "categories": [],
            "failed_sources": [],
            "breadcrumbs": [],
        }
    )
    assert "TOP 10 DEL GIORNO 11 04 2026" in html
    assert "TUTTE PER CATEGORIA 11 04 2026" in html
    assert "SNAPSHOT 2026-04-11" in html


def test_render_article_has_jsonld_and_breadcrumb() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    item = {
        "id": "item_2026-04-11_001",
        "title_it": "Google rilascia il core update",
        "summary_it": "Google ha annunciato oggi il rilascio.",
        "url": "https://example.com/a",
        "source": {"name": "SEJ"},
        "tags": ["core_update"],
        "published_at": "2026-04-11T07:00:00+00:00",
        "summarizer_model": "google/gemini-2.0-flash-001",
    }
    html = renderer.render_article(
        {
            "page_title": "Google rilascia il core update — Osservatorio SEO",
            "page_description": "Google ha annunciato oggi il rilascio.",
            "canonical_url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/google-rilascia-core-update/",
            "active_nav": "archive",
            "noindex": True,
            "og_type": "article",
            "item": item,
            "stars": "★★★★★",
            "absolute_date": "sabato 11 aprile 2026",
            "day_label": "sabato 11 aprile 2026",
            "day_path": "/archivio/2026/04/11/",
            "category_path": "/categoria/google-updates/",
            "category_label": "Google Updates",
            "published_iso": "2026-04-11T07:00:00+00:00",
            "article_url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/google-rilascia-core-update/",
            "breadcrumbs": [
                {
                    "name": "Home",
                    "url": "https://osservatorioseo.pages.dev/",
                    "site_path": "/",
                },
                {
                    "name": "Archivio",
                    "url": "https://osservatorioseo.pages.dev/archivio/",
                    "site_path": "/archivio/",
                },
                {
                    "name": "2026",
                    "url": "https://osservatorioseo.pages.dev/archivio/2026/",
                    "site_path": "/archivio/2026/",
                },
                {
                    "name": "11 aprile",
                    "url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/",
                    "site_path": "/archivio/2026/04/11/",
                },
                {
                    "name": "Google rilascia il core update",
                    "url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/google-rilascia-core-update/",
                    "site_path": "",
                },
            ],
        }
    )
    assert "<h1" in html
    assert "Google rilascia il core update" in html
    assert '"@type": "NewsArticle"' in html
    assert '"@type": "BreadcrumbList"' in html
    assert "LEGGI L&#39;ORIGINALE" in html or "LEGGI L'ORIGINALE" in html
    assert "/categoria/google-updates/" in html
    assert "/tag/core-update/" in html


def test_all_hub_templates_render() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    base_ctx = {
        "page_title": "Hub",
        "page_description": "d",
        "canonical_url": "https://example.com/",
        "active_nav": "archive",
        "noindex": True,
        "breadcrumbs": [],
        "meta_line": "X",
    }
    assert "ARCHIVE_INDEX" in renderer.render_archive_index({**base_ctx, "years": []})
    assert "2026" in renderer.render_year_hub({**base_ctx, "year": 2026, "months": []})
    assert "Aprile" in renderer.render_month_hub(
        {
            **base_ctx,
            "year": 2026,
            "year_path": "/archivio/2026/",
            "month_label": "Aprile",
            "days": [],
        }
    )
    assert "sabato 11 aprile 2026" in renderer.render_day_hub(
        {
            **base_ctx,
            "year": 2026,
            "year_path": "/archivio/2026/",
            "month_label": "Aprile",
            "month_path": "/archivio/2026/04/",
            "day": 11,
            "day_label": "sabato 11 aprile 2026",
            "teaser_cards": [],
            "snapshot_path": "/archivio/2026/04/11/",
        }
    )
    assert "Google Updates" in renderer.render_category_hub(
        {**base_ctx, "category_label": "Google Updates", "teaser_cards": []}
    )
    assert "#core_update" in renderer.render_tag_hub(
        {**base_ctx, "tag_label": "core_update", "teaser_cards": []}
    )


def test_render_docs_and_about() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    base_ctx = {
        "page_title": "Docs",
        "page_description": "d",
        "canonical_url": "https://example.com/docs/",
        "active_nav": "docs",
        "noindex": True,
        "breadcrumbs": [],
    }
    docs_html = renderer.render_docs(
        {
            **base_ctx,
            "sources": [],
            "sources_by_type": {"UFFICIALE": []},
            "doc_watcher_pages": [],
        }
    )
    assert "DOCS" in docs_html
    assert "UFFICIALE" in docs_html

    about_html = renderer.render_about(
        {**base_ctx, "page_title": "Chi siamo", "source_count": 21}
    )
    assert "Chi siamo" in about_html
    assert "donatopirolo" in about_html
