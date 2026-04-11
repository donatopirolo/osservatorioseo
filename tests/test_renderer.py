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
