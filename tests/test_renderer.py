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
