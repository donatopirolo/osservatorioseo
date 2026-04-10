"""Doc Watcher: rileva modifiche a pagine di documentazione ufficiale."""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import html2text
from selectolax.parser import HTMLParser

from osservatorio_seo.config import DocWatcherPage
from osservatorio_seo.doc_watcher.state import StateStore
from osservatorio_seo.http_client import HttpClient

MAX_DIFF_CHARS = 50_000


@dataclass(frozen=True)
class DocChangeResult:
    page_id: str
    changed: bool
    previous_hash: str | None
    current_hash: str
    diff: str
    lines_added: int
    lines_removed: int
    checked_at: datetime
    new_text: str


class DocWatcher:
    def __init__(
        self,
        http: HttpClient,
        state: StateStore,
        similarity_threshold: float = 0.003,
    ) -> None:
        self._http = http
        self._state = state
        self._similarity_threshold = similarity_threshold
        self._h2t = html2text.HTML2Text()
        self._h2t.ignore_links = True
        self._h2t.ignore_images = True
        self._h2t.body_width = 0

    async def check(self, page: DocWatcherPage) -> DocChangeResult:
        now = datetime.now(UTC)
        if page.type == "pdf":
            raw_text = await self._fetch_pdf(page.url)
        else:
            raw_text = await self._fetch_html(page.url, page.selector)

        new_text = self._normalize(raw_text, page.noise_patterns)
        current_hash = "sha256:" + hashlib.sha256(new_text.encode("utf-8")).hexdigest()
        previous_hash = self._state.load_hash(page.id)
        previous_text = self._state.load_text(page.id)

        if previous_hash is None:
            self._state.save(page.id, current_hash, new_text)
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=None,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        if previous_hash == current_hash:
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=previous_hash,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        if not self._is_significant_change(previous_text or "", new_text):
            self._state.save(page.id, current_hash, new_text)
            return DocChangeResult(
                page_id=page.id,
                changed=False,
                previous_hash=previous_hash,
                current_hash=current_hash,
                diff="",
                lines_added=0,
                lines_removed=0,
                checked_at=now,
                new_text=new_text,
            )

        diff_lines = list(
            difflib.unified_diff(
                (previous_text or "").splitlines(),
                new_text.splitlines(),
                fromfile="prev",
                tofile="curr",
                n=2,
                lineterm="",
            )
        )
        diff = "\n".join(diff_lines)
        if len(diff) > MAX_DIFF_CHARS:
            diff = diff[:MAX_DIFF_CHARS] + "\n... [diff truncated]"
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

        date_str = now.strftime("%Y-%m-%d")
        self._state.save_diff(page.id, date_str, diff)
        self._state.save(page.id, current_hash, new_text)

        return DocChangeResult(
            page_id=page.id,
            changed=True,
            previous_hash=previous_hash,
            current_hash=current_hash,
            diff=diff,
            lines_added=added,
            lines_removed=removed,
            checked_at=now,
            new_text=new_text,
        )

    async def _fetch_html(self, url: str, selector: str | None) -> str:
        resp = await self._http.get(url)
        tree = HTMLParser(resp.text)
        root = tree.css_first(selector) if selector else tree.body
        html_frag = root.html if root else resp.text
        return self._h2t.handle(html_frag or "")

    async def _fetch_pdf(self, url: str) -> str:
        import io

        import pdfplumber

        resp = await self._http.get(url)
        buf = io.BytesIO(resp.content)
        with pdfplumber.open(buf) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)

    def _normalize(self, text: str, noise_patterns: list[str]) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        for pattern in noise_patterns:
            text = re.sub(pattern, "", text, flags=re.MULTILINE)
        return text.strip()

    def _is_significant_change(self, old: str, new: str) -> bool:
        if not old:
            return True
        ratio = difflib.SequenceMatcher(None, old, new).ratio()
        return (1.0 - ratio) >= self._similarity_threshold
