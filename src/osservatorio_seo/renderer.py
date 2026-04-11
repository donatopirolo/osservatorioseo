"""HTML SSG renderer built on Jinja2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


class HtmlRenderer:
    def __init__(self, templates_dir: Path) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "jinja"]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render_raw(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template file to a string."""
        template = self._env.get_template(template_name)
        return template.render(**context)

    def render_homepage(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/homepage.html.jinja", context)

    def render_snapshot(self, context: dict[str, Any]) -> str:
        return self.render_raw("pages/snapshot.html.jinja", context)
