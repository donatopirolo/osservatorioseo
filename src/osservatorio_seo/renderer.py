"""HTML SSG renderer built on Jinja2."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from osservatorio_seo.seo import SITE_URL


class HtmlRenderer:
    def __init__(self, templates_dir: Path, static_dir: Path | None = None) -> None:
        self._static_dir = static_dir
        self._asset_versions: dict[str, str] = {}
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "jinja"]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._env.globals["site_url"] = SITE_URL
        self._env.globals["asset_url"] = self.asset_url

    def asset_url(self, path: str) -> str:
        """URL di un asset statico con la versione del contenuto, es. ``/tailwind.css?v=3f9a1c0b2d``.

        Senza versione il browser (e la cache di Cloudflare) servono il CSS
        vecchio per ore dopo un deploy, e le pagine nuove appaiono rotte.
        Il file va gia' compilato quando si genera l'HTML: nei workflow il
        build di Tailwind gira prima del rendering.
        """
        if self._static_dir is None:
            return path
        if path not in self._asset_versions:
            file = self._static_dir / path.lstrip("/")
            if not file.is_file():
                return path
            digest = hashlib.sha256(file.read_bytes()).hexdigest()[:10]
            self._asset_versions[path] = f"{path}?v={digest}"
        return self._asset_versions[path]

    def render_raw(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template file to a string."""
        template = self._env.get_template(template_name)
        return template.render(**context)

    def render_homepage(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/homepage.html.jinja", context)

    def render_snapshot(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/snapshot.html.jinja", context)

    def render_article(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/article.html.jinja", context)

    def render_archive_index(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/archive_index.html.jinja", context)

    def render_year_hub(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/year_hub.html.jinja", context)

    def render_month_hub(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/month_hub.html.jinja", context)

    def render_category_hub(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/category_hub.html.jinja", context)

    def render_tag_hub(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/tag_hub.html.jinja", context)

    def render_docs(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/docs.html.jinja", context)

    def render_about(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/about.html.jinja", context)

    def render_sitemap(self, context: dict[str, Any]) -> str:
        return self.render_raw("sitemap.xml.jinja", context)

    def render_feed_xml(self, context: dict[str, Any]) -> str:
        return self.render_raw("feed.xml.jinja", context)

    def render_robots_txt(self, context: dict[str, Any]) -> str:
        return self.render_raw("robots.txt.jinja", context)

    def render_top_week(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/top_week.html.jinja", context)

    def render_sitemap_news(self, context: dict[str, Any]) -> str:
        return self.render_raw("sitemap_news.xml.jinja", context)

    def render_dossier(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/dossier.html.jinja", context)

    def render_dossier_index(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/dossier_index.html.jinja", context)

    def render_patents_index(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/patents_index.html.jinja", context)

    def render_patent(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/patent.html.jinja", context)

    def render_tracker(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/tracker.html.jinja", context)
