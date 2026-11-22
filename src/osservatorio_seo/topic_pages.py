"""Pagine sui temi: guida fissa scritta a mano + parti dinamiche dall'archivio.

Una pagina sul tema sostituisce il dossier generato dall'AI per lo stesso slug
(``/dossier/<slug>/``, stesso URL). È composta da:

- ``content/temi/<slug>.md``: front matter YAML + guida in Markdown. È la parte
  fissa: la scrive e la rivede una persona, nessun job la rigenera.
- ``content/temi/<slug>.numbers.yml`` (facoltativo): i numeri chiave, ognuno
  con fonte, link e data, mostrati in tabella.
- blocchi dinamici, ricalcolati a ogni run senza chiamate AI, inseriti dove la
  guida contiene un segnaposto su una riga da solo:
  ``[[numeri]]``, ``[[cronologia]]``, ``[[documentazione]]``, ``[[brevetti]]``.

``review_needed`` confronta la data di revisione della guida con le notizie
importanti e le modifiche alla documentazione arrivate dopo: serve all'allarme
che chiede di rileggere la guida prima che invecchi.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import markdown
import yaml

CONTENT_DIR = Path("content") / "temi"
REVIEW_FILE = "review.json"
PLACEHOLDER_RE = re.compile(r"<p>\[\[(numeri|cronologia|documentazione|brevetti)\]\]</p>")
FAQ_HEADING = "Domande frequenti"

# Riepiloghi e report periodici: utili come notizie, non come eventi della
# cronologia di un tema (parlano di dieci cose insieme).
DIGEST_RE = re.compile(r"^(riepilogo|riassunto|recap|report|il report|rapporto)\b", re.IGNORECASE)


@dataclass
class TopicNumber:
    valore: str
    descrizione: str
    fonte: str
    url: str
    data: str  # YYYY-MM o YYYY-MM-DD
    gruppo: str = ""


@dataclass
class Topic:
    slug: str
    title: str
    page_title: str
    description: str
    tags: list[str]
    reviewed: date
    body_md: str
    doc_watcher: list[str] = field(default_factory=list)
    patents: list[str] = field(default_factory=list)
    min_importance: int = 4
    review_importance: int = 5
    numbers: list[TopicNumber] = field(default_factory=list)
    author: str = "Redazione Osservatorio SEO"


def _split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError("pagina sul tema senza front matter YAML")
    _, fm, body = text.split("---", 2)
    data = yaml.safe_load(fm) or {}
    if not isinstance(data, dict):
        raise ValueError("front matter non valido")
    return data, body.lstrip("\n")


def load_topic(path: Path) -> Topic:
    data, body = _split_front_matter(path.read_text(encoding="utf-8"))
    for key in ("slug", "title", "page_title", "description", "tags", "reviewed"):
        if not data.get(key):
            raise ValueError(f"{path.name}: manca '{key}' nel front matter")
    reviewed = data["reviewed"]
    if isinstance(reviewed, str):
        reviewed = date.fromisoformat(reviewed)
    numbers: list[TopicNumber] = []
    numbers_path = path.with_name(f"{data['slug']}.numbers.yml")
    if numbers_path.exists():
        raw = yaml.safe_load(numbers_path.read_text(encoding="utf-8")) or []
        numbers = [TopicNumber(**{k: str(v) for k, v in n.items()}) for n in raw]
    return Topic(
        slug=data["slug"],
        title=data["title"],
        page_title=data["page_title"],
        description=data["description"],
        tags=[str(t) for t in data["tags"]],
        reviewed=reviewed,
        body_md=body,
        doc_watcher=[str(x) for x in data.get("doc_watcher") or []],
        patents=[str(x) for x in data.get("patents") or []],
        min_importance=int(data.get("min_importance", 4)),
        review_importance=int(data.get("review_importance", 5)),
        numbers=numbers,
        author=data.get("author") or "Redazione Osservatorio SEO",
    )


def load_topics(content_dir: Path) -> dict[str, Topic]:
    """slug -> Topic per ogni ``*.md`` in ``content_dir``."""
    if not content_dir.exists():
        return {}
    topics: dict[str, Topic] = {}
    for path in sorted(content_dir.glob("*.md")):
        topic = load_topic(path)
        topics[topic.slug] = topic
    return topics


def render_body(body_md: str) -> tuple[str, list[dict[str, str]]]:
    """Markdown -> HTML con id sui titoli; ritorna anche l'indice degli H2."""
    md = markdown.Markdown(extensions=["tables", "toc", "attr_list", "sane_lists"])
    html = md.convert(body_md)
    toc = [
        {"id": t["id"], "name": t["name"]}
        for t in md.toc_tokens  # type: ignore[attr-defined]
        if t["level"] == 2
    ]
    return html, toc


def extract_faq(body_md: str) -> list[dict[str, str]]:
    """Domande (###) e risposte della sezione '## Domande frequenti', in testo semplice."""
    m = re.search(rf"^## {FAQ_HEADING}\s*$(.*?)(?=^## |\Z)", body_md, re.M | re.S)
    if not m:
        return []
    faq = []
    for q, a in re.findall(r"^### (.+?)\s*$(.*?)(?=^### |\Z)", m.group(1), re.M | re.S):
        answer = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a)  # link -> testo
        answer = re.sub(r"[*_`]", "", answer)
        answer = " ".join(answer.split())
        if answer:
            faq.append({"question": q.strip(), "answer": answer})
    return faq


def timeline(topic: Topic, item_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Eventi del tema, per mese (più recenti prima).

    Solo notizie con un tag del tema, importanza >= ``min_importance`` e che
    non siano riepiloghi periodici.
    """
    tags = set(topic.tags)
    events = [
        meta
        for meta in item_index.values()
        if tags & set(meta.get("tags") or [])
        and (meta.get("importance") or 0) >= topic.min_importance
        and not DIGEST_RE.match(meta.get("title") or "")
    ]
    events.sort(key=lambda m: m["date"], reverse=True)
    months: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        months.setdefault(ev["date"][:7], []).append(ev)
    return [{"month": k, "events": v} for k, v in months.items()]


def review_needed(
    topic: Topic,
    item_index: dict[str, dict[str, Any]],
    doc_changes: list[Any],
) -> dict[str, Any] | None:
    """Cosa è arrivato dopo l'ultima revisione della guida, o None se niente."""
    since = topic.reviewed.isoformat()
    tags = set(topic.tags)
    news = sorted(
        (
            {"date": m["date"], "title": m["title"], "path": m["site_path"]}
            for m in item_index.values()
            if m["date"] > since
            and tags & set(m.get("tags") or [])
            and (m.get("importance") or 0) >= topic.review_importance
        ),
        key=lambda x: x["date"],
    )
    docs = sorted(
        (
            {"date": r.day, "title": r.page_name, "path": r.path}
            for r in doc_changes
            if r.page_id in topic.doc_watcher and r.day > since
        ),
        key=lambda x: x["date"],
    )
    if not news and not docs:
        return None
    return {"slug": topic.slug, "reviewed": since, "news": news, "doc_changes": docs}


def split_dynamic(html: str) -> list[tuple[str, str]]:
    """Divide l'HTML della guida in pezzi ('html', testo) e ('block', nome)."""
    parts: list[tuple[str, str]] = []
    pos = 0
    for m in PLACEHOLDER_RE.finditer(html):
        parts.append(("html", html[pos : m.start()]))
        parts.append(("block", m.group(1)))
        pos = m.end()
    parts.append(("html", html[pos:]))
    return [p for p in parts if p[1].strip()]


def word_count(body_md: str) -> int:
    return len(re.sub(r"[#*_`|>\-\[\]()]", " ", body_md).split())
