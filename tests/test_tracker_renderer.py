"""Smoke test that the tracker template renders with minimal context."""

from pathlib import Path

from osservatorio_seo.renderer import HtmlRenderer


def test_tracker_template_renders_smoke():
    templates_dir = Path(__file__).resolve().parent.parent / "templates"
    renderer = HtmlRenderer(templates_dir)
    ctx = {
        "page_title": "Tracker — Osservatorio SEO",
        "page_description": "Stato della ricerca in Italia",
        "canonical_url": "https://osservatorioseo.pages.dev/tracker/",
        "active_nav": "tracker",
        "noindex": True,
        "og_type": "website",
        "page_headline": "Stato della ricerca in Italia — Settimana 15, 2026",
        "updated_label": "14 aprile 2026",
        "updated_iso": "2026-04-14T08:00:00+00:00",
        "next_update_label": "21 aprile 2026",
        "dataset_name": "Tracker Osservatorio SEO",
        "dataset_description": "Dati settimanali sull'adozione di AI e Search Engines in Italia",
        "dataset_url": "https://osservatorioseo.pages.dev/tracker/",
        "chart_1_svg": "<svg></svg>",
        "chart_1_caption": "Caption 1",
        "chart_2_svg": "<svg></svg>",
        "chart_2_caption": "Caption 2",
        "chart_3_svg": "<svg></svg>",
        "chart_3_caption": "Caption 3",
        "chart_4_svg": "<svg></svg>",
        "chart_4_caption": "Caption 4",
        "chart_5_svg": "<svg></svg>",
        "chart_5_caption": "Caption 5",
        "chart_6_svg": "<svg></svg>",
        "chart_6_caption": "Caption 6",
        "chart_7_svg": "<svg></svg>",
        "latest_monthly_report_path": None,
        "breadcrumbs": [
            {"name": "Home", "url": "https://osservatorioseo.pages.dev/"},
            {"name": "Tracker", "url": "https://osservatorioseo.pages.dev/tracker/"},
        ],
    }
    html = renderer.render_tracker(ctx)
    assert "Stato della ricerca in Italia" in html
    assert "METODOLOGIA" in html
    assert "Cloudflare Radar" in html
    assert "<svg></svg>" in html
