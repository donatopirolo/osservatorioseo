# SEO SSG Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trasformare OsservatorioSEO da client-side rendered a **Static Site Generator** SEO-ready. La pipeline Python pre-renderizza tutte le pagine come HTML statici con URL parlanti (`/archivio/2026/04/11/<slug>/`), meta tag OpenGraph completi, JSON-LD NewsArticle schema, sitemap.xml, feed RSS. Il JavaScript diventa hydration-only (search, toggle cross-archive, card collapse) letto dal DOM già popolato. Mantiene `noindex` attivo finché l'utente decide di aprire al pubblico — al quel punto basterà una riga.

**Architecture:** Publisher Python invoca un nuovo modulo `renderer.py` (Jinja2) che produce HTML statici dentro `site/`. I template vivono in `templates/` con layout condiviso, partials per card, e pagine specifiche per ogni tipo di URL. Il frontend JS legge gli `<article class="card">` già presenti nel DOM usando i `data-search-blob` già generati server-side. URL scheme a la WordPress: `/archivio/YYYY/MM/DD/` per snapshot, `/archivio/YYYY/MM/DD/<slug>/` per articoli, `/categoria/<cat>/`, `/tag/<tag>/`.

**Tech Stack:** Jinja2 (BSD), python-slugify (MIT), pytest (esistente). Zero nuove dipendenze runtime. Hosting invariato (Cloudflare Pages).

**Prerequisiti:**
- Python 3.12 già in `.venv/` dal progetto esistente
- Repo `donatopirolo/osservatorioseo` esistente con feed corrente committato
- Accesso a GitHub Actions + Cloudflare Pages già configurato

**Vincoli:**
- **Articoli singoli solo per `importance >= 4`** (per stare sotto 20k file Cloudflare free per ~6 anni)
- `noindex` resta attivo ma in una variabile template facilmente toggleabile
- Mantiene backward compat: vecchi URL `?date=X` fanno redirect client-side al nuovo schema
- Il `feed.json` resta pubblico come API per agent AI
- **Feed filter a 24h** già applicato in un commit standalone precedente (`max_age_hours=24`). Ogni daily snapshot è un set disgiunto → zero duplicate content cross-day. Il SSG è sviluppato su questa base.
- **Nuova pagina `/top-settimana/`** aggregata rolling su 7 giorni (Task 16b) ri-ranka i top10 di ciascun archivio recente, deduplica per URL, applica lo scoring settimanale.

**Riferimento spec:** questa conversazione (turni "Ragiona come un esperto SEO" + "Il mio piano da esperto").

---

## File Structure

### Nuovi file

```
pyproject.toml                             # aggiunta jinja2 + python-slugify (modifica)
src/osservatorio_seo/slug.py               # slug generator IT-aware
src/osservatorio_seo/renderer.py           # HtmlRenderer class (Jinja2)
src/osservatorio_seo/seo.py                # SEO helpers (canonical_url, article_urls)
templates/layout.html.jinja                # shell HTML comune (head, header, footer)
templates/partials/_head_meta.html.jinja   # meta tags condivisi
templates/partials/_header.html.jinja      # top nav + search bar
templates/partials/_footer.html.jinja      # footer con author credit
templates/partials/_card_top10.html.jinja  # card Top 10 numerata
templates/partials/_card_category.html.jinja  # card categoria
templates/partials/_card_article_teaser.html.jinja  # card compatta per hub
templates/partials/_jsonld_newsarticle.html.jinja  # JSON-LD NewsArticle
templates/partials/_jsonld_breadcrumb.html.jinja   # JSON-LD BreadcrumbList
templates/pages/homepage.html.jinja        # /
templates/pages/snapshot.html.jinja        # /archivio/YYYY/MM/DD/
templates/pages/article.html.jinja         # /archivio/YYYY/MM/DD/<slug>/
templates/pages/archive_index.html.jinja   # /archivio/
templates/pages/year_hub.html.jinja        # /archivio/YYYY/
templates/pages/month_hub.html.jinja       # /archivio/YYYY/MM/
templates/pages/category_hub.html.jinja    # /categoria/<cat>/
templates/pages/tag_hub.html.jinja         # /tag/<tag>/
templates/pages/docs.html.jinja            # /docs/
templates/pages/about.html.jinja           # /about/
templates/pages/top_week.html.jinja        # /top-settimana/ (TOP 10 rolling 7d)
tests/test_slug.py                         # unit test slug
tests/test_renderer.py                     # unit test renderer
tests/test_seo.py                          # unit test SEO helpers
scripts/rebuild_seo_html.py                # rebuild storico da data/archive/*.json
```

### File modificati

```
src/osservatorio_seo/publisher.py          # chiama renderer per ogni URL da generare
src/osservatorio_seo/pipeline.py           # passa sources/doc_pages a publisher
tests/test_publisher.py                    # copre SSG output
site/app.js                                # hydration-only (rimuove render*, tiene setup*)
site/archive.js                            # adatta all'URL scheme nuovo (se serve)
site/docs.js                               # reso inerte (docs è statico ora)
site/index.html                            # rimosso (sarà generato da Jinja2)
site/archive.html                          # rimosso (generato)
site/docs.html                             # rimosso (generato)
```

---

## Fasi

1. **Foundation** (T1-T3): dipendenze, slug module, renderer scaffold
2. **Templates base** (T4-T6): layout + partials + homepage
3. **Template pagine hub + article** (T7-T10): snapshot, hub anno/mese/giorno/categoria/tag, article
4. **Template docs + about** (T11-T12)
5. **SEO assets** (T13-T15): sitemap.xml, feed.xml, robots.txt
6. **Publisher integration** (T16-T16b): SSG triggering durante la pipeline + pagina TOP WEEK
7. **Frontend hydration** (T17-T18): app.js rewrite, date refresh, redirect compat
8. **Historical rebuild** (T19): script per rigenerare tutto lo storico
9. **Test + Deploy** (T20-T21): Playwright + verifica live

---

## Task 1: Dipendenze

**Files:**
- Modify: `pyproject.toml`
- Verify: `.venv/bin/pip install -e ".[dev]"`

- [ ] **Step 1: Aggiungi jinja2 e python-slugify a `pyproject.toml`**

Edita la lista `dependencies` di `pyproject.toml` per aggiungere queste due righe:

```toml
    "jinja2>=3.1",
    "python-slugify>=8.0",
```

Il blocco completo `dependencies` diventa:

```toml
dependencies = [
    "feedparser>=6.0",
    "httpx>=0.27",
    "selectolax>=0.3",
    "beautifulsoup4>=4.12",
    "playwright>=1.45",
    "html2text>=2024.2",
    "pdfplumber>=0.11",
    "pydantic>=2.7",
    "pyyaml>=6.0",
    "rapidfuzz>=3.9",
    "python-dateutil>=2.9",
    "jinja2>=3.1",
    "python-slugify>=8.0",
]
```

- [ ] **Step 2: Install**

```bash
.venv/bin/pip install -e ".[dev]" 2>&1 | tail -5
```

Expected: `Successfully installed …` con `jinja2` e `python-slugify` nell'elenco, oppure `Requirement already satisfied`.

- [ ] **Step 3: Verify import**

```bash
.venv/bin/python -c "import jinja2; from slugify import slugify; print(jinja2.__version__, slugify('Ciao Mondo!'))"
```

Expected: stampa versione jinja2 e `ciao-mondo`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore(deps): add jinja2 and python-slugify for SSG"
```

---

## Task 2: Slug Module

**Files:**
- Create: `src/osservatorio_seo/slug.py`
- Create: `tests/test_slug.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_slug.py
from osservatorio_seo.slug import make_slug


def test_make_slug_basic() -> None:
    assert make_slug("Google rilascia il Core Update di marzo 2026") == "google-rilascia-core-update-marzo-2026"


def test_make_slug_accents() -> None:
    assert make_slug("È arrivato il nuovo modello AI più potente") == "arrivato-nuovo-modello-ai-piu-potente"


def test_make_slug_max_length() -> None:
    long_title = "Un titolo molto molto molto molto molto molto molto molto lungo che supera il limite"
    slug = make_slug(long_title, max_length=60)
    assert len(slug) <= 60
    assert not slug.endswith("-")


def test_make_slug_strips_stopwords() -> None:
    # Italian stopwords should be removed
    slug = make_slug("La guida di SEO per il 2026")
    # "la", "di", "per", "il" removed
    assert "la-" not in slug
    assert "guida" in slug
    assert "seo" in slug
    assert "2026" in slug


def test_make_slug_empty_returns_fallback() -> None:
    assert make_slug("") == "untitled"
    assert make_slug("   ") == "untitled"


def test_make_slug_only_stopwords_returns_fallback() -> None:
    assert make_slug("la il di e in") == "untitled"


def test_make_slug_unique_suffix() -> None:
    from osservatorio_seo.slug import make_unique_slug
    existing = {"google-update", "google-update-2"}
    assert make_unique_slug("Google Update", existing) == "google-update-3"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_slug.py -v
```

Expected: FAIL con `ImportError: cannot import name 'make_slug' from 'osservatorio_seo.slug'`.

- [ ] **Step 3: Create `src/osservatorio_seo/slug.py`**

```python
"""SEO slug generator IT-aware."""

from __future__ import annotations

from slugify import slugify

# Stopwords italiane più comuni da rimuovere dagli slug
_IT_STOPWORDS = {
    "il",
    "lo",
    "la",
    "i",
    "gli",
    "le",
    "un",
    "uno",
    "una",
    "di",
    "a",
    "da",
    "in",
    "con",
    "su",
    "per",
    "tra",
    "fra",
    "del",
    "dello",
    "della",
    "dei",
    "degli",
    "delle",
    "al",
    "allo",
    "alla",
    "ai",
    "agli",
    "alle",
    "dal",
    "dallo",
    "dalla",
    "dai",
    "dagli",
    "dalle",
    "nel",
    "nello",
    "nella",
    "nei",
    "negli",
    "nelle",
    "e",
    "ed",
    "o",
    "ma",
    "se",
    "che",
    "non",
    "è",
}

_FALLBACK = "untitled"


def make_slug(title: str, max_length: int = 60) -> str:
    """Genera uno slug SEO-friendly dal titolo italiano.

    - Rimuove accenti, punteggiatura, caratteri non-ASCII
    - Lowercase
    - Tronca a ``max_length`` (senza trattini pendenti)
    - Rimuove stopwords italiane comuni
    - Ritorna "untitled" se il titolo è vuoto o solo stopwords
    """
    if not title or not title.strip():
        return _FALLBACK

    # Prima passata: slugify grezzo
    raw = slugify(title, lowercase=True, separator="-")
    if not raw:
        return _FALLBACK

    # Rimuovi stopwords
    parts = [p for p in raw.split("-") if p and p not in _IT_STOPWORDS]
    if not parts:
        return _FALLBACK

    slug = "-".join(parts)

    # Tronca a max_length senza lasciare trattino pendente
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit("-", 1)[0]

    return slug or _FALLBACK


def make_unique_slug(title: str, existing: set[str], max_length: int = 60) -> str:
    """Come make_slug ma aggiunge un suffisso numerico se collide con ``existing``."""
    base = make_slug(title, max_length=max_length)
    if base not in existing:
        return base
    n = 2
    while True:
        candidate = f"{base}-{n}"
        if candidate not in existing:
            return candidate
        n += 1
```

- [ ] **Step 4: Run test**

```bash
.venv/bin/pytest tests/test_slug.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Ruff check**

```bash
.venv/bin/ruff check src/osservatorio_seo/slug.py tests/test_slug.py
.venv/bin/ruff format src/osservatorio_seo/slug.py tests/test_slug.py
```

Expected: All checks passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/slug.py tests/test_slug.py
git commit -m "feat(slug): IT-aware SEO slug generator with stopwords and uniqueness"
```

---

## Task 3: SEO URL helpers

**Files:**
- Create: `src/osservatorio_seo/seo.py`
- Create: `tests/test_seo.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seo.py
from datetime import UTC, datetime

from osservatorio_seo.models import Item, Source
from osservatorio_seo.seo import (
    article_path,
    category_path,
    day_path,
    month_path,
    tag_path,
    year_path,
)


def mk_item(item_id: str = "item_2026-04-11_001", title_it: str = "Google rilascia il Core Update") -> Item:
    return Item(
        id=item_id,
        title_original="Google releases the Core Update",
        title_it=title_it,
        summary_it="s",
        url="https://example.com/a",
        source=Source(
            id="src",
            name="Src",
            authority=9,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category="google_updates",
        tags=["core_update"],
        importance=5,
        published_at=datetime(2026, 4, 11, 7, 0, tzinfo=UTC),
        fetched_at=datetime(2026, 4, 11, 7, 0, tzinfo=UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def test_year_path() -> None:
    assert year_path(2026) == "/archivio/2026/"


def test_month_path() -> None:
    assert month_path(2026, 4) == "/archivio/2026/04/"


def test_day_path() -> None:
    assert day_path(2026, 4, 11) == "/archivio/2026/04/11/"


def test_article_path() -> None:
    item = mk_item()
    path = article_path(item, date_str="2026-04-11", slug="google-rilascia-core-update")
    assert path == "/archivio/2026/04/11/google-rilascia-core-update/"


def test_category_path() -> None:
    assert category_path("google_updates") == "/categoria/google-updates/"


def test_tag_path() -> None:
    assert tag_path("core_update") == "/tag/core-update/"
    assert tag_path("ai_overviews") == "/tag/ai-overviews/"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_seo.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `src/osservatorio_seo/seo.py`**

```python
"""SEO URL / path helpers."""

from __future__ import annotations

from osservatorio_seo.models import Item

SITE_URL = "https://osservatorioseo.pages.dev"


def year_path(year: int) -> str:
    return f"/archivio/{year:04d}/"


def month_path(year: int, month: int) -> str:
    return f"/archivio/{year:04d}/{month:02d}/"


def day_path(year: int, month: int, day: int) -> str:
    return f"/archivio/{year:04d}/{month:02d}/{day:02d}/"


def article_path(item: Item, date_str: str, slug: str) -> str:
    """``date_str`` is ``YYYY-MM-DD`` (the publish day of the feed, not the item)."""
    y, m, d = date_str.split("-")
    return f"/archivio/{y}/{m}/{d}/{slug}/"


def category_path(category: str) -> str:
    # ``google_updates`` → ``google-updates``
    return f"/categoria/{category.replace('_', '-')}/"


def tag_path(tag: str) -> str:
    return f"/tag/{tag.replace('_', '-')}/"


def canonical(path: str) -> str:
    """Build full canonical URL from a site-relative path."""
    if path.startswith("/"):
        return SITE_URL + path
    return SITE_URL + "/" + path
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_seo.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
.venv/bin/ruff format src/osservatorio_seo/seo.py tests/test_seo.py
git add src/osservatorio_seo/seo.py tests/test_seo.py
git commit -m "feat(seo): URL path helpers for SSG archive scheme"
```

---

## Task 4: Renderer foundation + base layout template

**Files:**
- Create: `src/osservatorio_seo/renderer.py`
- Create: `templates/layout.html.jinja`
- Create: `templates/partials/_head_meta.html.jinja`
- Create: `templates/partials/_header.html.jinja`
- Create: `templates/partials/_footer.html.jinja`
- Create: `tests/test_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_renderer.py
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
    # Nav presente con link parlanti
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
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Create `src/osservatorio_seo/renderer.py`**

```python
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
```

- [ ] **Step 4: Create `templates/partials/_head_meta.html.jinja`**

```html
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
{% if noindex %}
<meta name="robots" content="noindex, nofollow" />
<meta name="googlebot" content="noindex, nofollow" />
{% endif %}
<title>{{ page_title }}</title>
<meta name="description" content="{{ page_description }}" />
<link rel="canonical" href="{{ canonical_url }}" />
<meta property="og:title" content="{{ page_title }}" />
<meta property="og:description" content="{{ page_description }}" />
<meta property="og:type" content="{{ og_type | default('website') }}" />
<meta property="og:url" content="{{ canonical_url }}" />
<meta property="og:site_name" content="Osservatorio SEO" />
<meta name="twitter:card" content="summary_large_image" />
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;700&display=swap" rel="stylesheet" />
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
<script id="tailwind-config">
  tailwind.config = {
    darkMode: "class",
    theme: {
      extend: {
        colors: {
          "on-surface": "#e2e2e2",
          "primary-container": "#00f63e",
          "surface-container-lowest": "#0e0e0e",
          "surface-container-low": "#1b1b1b",
          "surface-container": "#1f1f1f",
          "outline": "#919191",
          "outline-variant": "#474747",
          "surface": "#131313",
          "background": "#131313",
          "on-surface-variant": "#c6c6c6",
          "primary": "#ffffff",
          "error": "#ffb4ab"
        },
        borderRadius: { DEFAULT: "0px", lg: "0px", xl: "0px", full: "9999px" },
        fontFamily: {
          headline: ["Space Grotesk"],
          body: ["Space Grotesk"],
          label: ["Space Grotesk"]
        }
      }
    }
  };
</script>
<link rel="stylesheet" href="/styles.css" />
```

- [ ] **Step 5: Create `templates/partials/_header.html.jinja`**

```html
<header class="fixed top-0 left-0 w-full z-50 flex flex-col lg:flex-row lg:justify-between lg:items-center gap-3 lg:gap-0 px-4 sm:px-6 py-3 sm:py-4 bg-[#131313] border-b border-[#919191] border-dashed font-['Space_Grotesk'] tracking-[0.02em] uppercase text-sm">
  <div class="flex items-center justify-between gap-4 flex-wrap">
    <a href="/" class="text-lg sm:text-xl font-bold text-white before:content-['>_'] tracking-tighter terminal-glow">OSSERVATORIO_SEO</a>
    <nav class="flex gap-4 sm:gap-6 items-center text-xs sm:text-sm">
      {% set active = active_nav | default('') %}
      <a class="{% if active == 'today' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/">TODAY</a>
      <a class="{% if active == 'archive' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/archivio/">ARCHIVIO</a>
      <a class="{% if active == 'docs' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/docs/">DOCS</a>
    </nav>
  </div>
  <div class="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
    <input
      type="search"
      id="search"
      placeholder="SEARCH_DB..."
      class="bg-surface-container-lowest border border-outline-variant text-white text-xs px-3 py-2 focus:outline-none focus:border-primary-container w-full sm:w-56 uppercase placeholder:text-outline" />
    <label class="flex items-center gap-2 cursor-pointer group">
      <input type="checkbox" id="search-archive-toggle" class="cursor-pointer" />
      <span class="text-[10px] text-outline group-hover:text-primary-container transition-colors">CROSS_ARCHIVE // LAST 7 DAYS</span>
    </label>
  </div>
</header>
```

- [ ] **Step 6: Create `templates/partials/_footer.html.jinja`**

```html
<footer class="w-full py-8 px-6 flex flex-col md:flex-row justify-between items-center gap-4 bg-[#0e0e0e] border-t border-[#474747] border-dashed mt-auto font-['Space_Grotesk'] text-[10px] tracking-widest uppercase">
  <div class="text-[#919191]">
    (C) 2026 OSSERVATORIO_SEO // AUTORE:
    <a class="text-primary-container hover:underline" href="https://donatopirolo.dev" target="_blank" rel="noopener">donatopirolo.dev</a>
  </div>
  <div class="flex gap-6">
    <a class="text-[#919191] hover:text-[#00f63e] transition-opacity duration-200" href="/data/feed.json">FEED.JSON</a>
    <a class="text-[#919191] hover:text-[#00f63e] transition-opacity duration-200" href="/feed.xml">RSS</a>
    <a class="text-[#919191] hover:text-[#00f63e] transition-opacity duration-200" href="https://github.com/donatopirolo/osservatorioseo" target="_blank" rel="noopener">GITHUB.SYS</a>
  </div>
  <div class="text-primary-container font-mono animate-pulse">SYSTEM_UPTIME: 99.998%</div>
</footer>
```

- [ ] **Step 7: Create `templates/layout.html.jinja`**

```html
<!DOCTYPE html>
<html class="dark" lang="it">
<head>
{% include "partials/_head_meta.html.jinja" %}
{% block extra_head %}{% endblock %}
</head>
<body class="min-h-screen flex flex-col selection:bg-primary-container selection:text-surface">
{% include "partials/_header.html.jinja" %}

<main class="flex-grow pt-44 sm:pt-36 lg:pt-24 pb-12 px-4 sm:px-6 max-w-7xl mx-auto w-full">
{{ content | safe }}
</main>

{% include "partials/_footer.html.jinja" %}

<div class="fixed inset-0 pointer-events-none z-40 bg-[radial-gradient(circle_at_50%_0%,rgba(0,246,62,0.05)_0%,transparent_50%)]"></div>

<script src="/app.js"></script>
{% block extra_scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 8: Run test**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 2 passed.

- [ ] **Step 9: Ruff**

```bash
.venv/bin/ruff check src/osservatorio_seo/renderer.py tests/test_renderer.py
.venv/bin/ruff format src/osservatorio_seo/renderer.py tests/test_renderer.py
```

- [ ] **Step 10: Commit**

```bash
git add src/osservatorio_seo/renderer.py templates/layout.html.jinja templates/partials/ tests/test_renderer.py
git commit -m "feat(renderer): Jinja2 scaffold with layout template and shared partials"
```

---

## Task 5: Card partials

**Files:**
- Create: `templates/partials/_card_top10.html.jinja`
- Create: `templates/partials/_card_category.html.jinja`
- Create: `templates/partials/_card_article_teaser.html.jinja`

- [ ] **Step 1: Create `_card_top10.html.jinja`**

```html
{# Context: item (dict), order (int), search_blob (str), short_id (str), relative_date (str), absolute_date (str), stars (str), tags (list), article_url (str) #}
<article class="card bg-surface p-4 sm:p-6 flex flex-col md:flex-row md:items-start md:justify-between group hover:bg-surface-container transition-colors"
  data-item-id="{{ item.id }}"
  data-tags="{{ tags | join(',') }}"
  data-search-blob="{{ search_blob }}">
  <div class="flex items-start gap-4 flex-grow min-w-0">
    <span class="text-primary-container font-bold text-lg shrink-0">{{ "%02d" | format(order) }}.</span>
    <div class="max-w-3xl min-w-0 flex-1">
      <h3 class="text-base sm:text-xl font-medium group-hover:text-primary-container transition-colors">
        <a href="{{ article_url }}" class="hover:underline">{{ item.title_it }}</a>
      </h3>
      <p class="text-[10px] sm:text-[11px] text-outline mt-1 mb-2 uppercase font-mono break-words">
        {{ item.source.name }} · <span class="text-[#f5a623] whitespace-nowrap">{{ stars }}</span> · <time class="whitespace-nowrap" datetime="{{ item.published_at }}" title="{{ absolute_date }}">{{ relative_date }}</time> <span class="whitespace-nowrap">// ID: {{ short_id }}</span>
      </p>
      <div class="card-body">
        <p class="text-sm text-on-surface-variant font-mono leading-relaxed">{{ item.summary_it }}</p>
        {% if tags %}
        <div class="mt-2">
          {% for t in tags %}
          <a href="/tag/{{ t | replace('_', '-') }}/" class="inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 mr-1 mt-2 border border-outline-variant text-outline hover:text-primary-container hover:border-primary-container font-mono">{{ t }}</a>
          {% endfor %}
        </div>
        {% endif %}
      </div>
    </div>
  </div>
  <div class="card-body mt-4 md:mt-0 md:ml-6 shrink-0">
    <a class="inline-block text-xs border border-outline px-3 py-1 hover:border-primary-container hover:text-primary-container transition-all uppercase tracking-wider" href="{{ article_url }}">READ_LOG</a>
  </div>
</article>
```

- [ ] **Step 2: Create `_card_category.html.jinja`**

```html
{# Context: item, search_blob, short_id, relative_date, absolute_date, stars, tags, article_url #}
{% set border_class = "border-l-2 border-primary-container bg-surface-container-low" if (item.importance >= 5 or item.is_doc_change) else "border-l-2 border-outline-variant bg-surface-container-lowest" %}
<article class="card {{ border_class }} p-4 sm:p-6 flex flex-col md:flex-row md:justify-between md:items-start group hover:bg-surface-container transition-colors"
  data-item-id="{{ item.id }}"
  data-tags="{{ tags | join(',') }}"
  data-search-blob="{{ search_blob }}">
  <div class="max-w-4xl min-w-0 flex-1">
    <h4 class="text-base sm:text-lg font-bold mb-1 group-hover:text-primary-container transition-colors">
      <a href="{{ article_url }}" class="hover:underline">{{ item.title_it }}</a>
    </h4>
    <p class="text-[10px] sm:text-[11px] text-outline mb-2 font-mono uppercase break-words">
      {{ item.source.name }} · <span class="text-[#f5a623] whitespace-nowrap">{{ stars }}</span> · <time class="whitespace-nowrap" datetime="{{ item.published_at }}" title="{{ absolute_date }}">{{ relative_date }}</time> <span class="whitespace-nowrap">// ID: {{ short_id }}</span>
    </p>
    <div class="card-body">
      <p class="text-sm text-on-surface-variant font-mono">{{ item.summary_it }}</p>
      {% if tags %}
      <div class="mt-2">
        {% for t in tags %}
        <a href="/tag/{{ t | replace('_', '-') }}/" class="inline-block text-[10px] uppercase tracking-wider px-2 py-0.5 mr-1 mt-2 border border-outline-variant text-outline hover:text-primary-container hover:border-primary-container font-mono">{{ t }}</a>
        {% endfor %}
      </div>
      {% endif %}
    </div>
  </div>
  <a class="card-body text-outline text-xs font-mono mt-4 md:mt-0 md:ml-6 shrink-0 hover:text-primary-container transition-colors uppercase tracking-wider" href="{{ article_url }}">LOG_OPEN →</a>
</article>
```

- [ ] **Step 3: Create `_card_article_teaser.html.jinja`**

Card compatta per listing di hub pages (categoria, tag, mese, anno). Nessun summary inline, solo titolo + meta + link.

```html
{# Context: item, short_id, relative_date, article_url, stars #}
<article class="card flex items-start gap-3 p-3 sm:p-4 border-l-2 border-outline-variant bg-surface-container-lowest hover:bg-surface-container transition-colors">
  <div class="flex-1 min-w-0">
    <h4 class="text-sm sm:text-base font-medium">
      <a href="{{ article_url }}" class="text-white hover:text-primary-container transition-colors">{{ item.title_it }}</a>
    </h4>
    <p class="text-[10px] text-outline mt-1 uppercase font-mono break-words">
      {{ item.source.name }} · <span class="text-[#f5a623] whitespace-nowrap">{{ stars }}</span> · <time class="whitespace-nowrap" datetime="{{ item.published_at }}">{{ relative_date }}</time> <span class="whitespace-nowrap">// ID: {{ short_id }}</span>
    </p>
  </div>
</article>
```

- [ ] **Step 4: Smoke test**

```bash
.venv/bin/python <<'PY'
from pathlib import Path
from osservatorio_seo.renderer import HtmlRenderer
r = HtmlRenderer(Path("templates"))
html = r.render_raw("partials/_card_top10.html.jinja", {
  "item": {"id": "x", "title_it": "Test", "summary_it": "sum", "source": {"name": "Src"}, "importance": 5, "is_doc_change": False, "published_at": "2026-04-11T07:00:00+00:00"},
  "order": 1,
  "search_blob": "test src",
  "short_id": "ABCD",
  "relative_date": "2 ore fa",
  "absolute_date": "sabato 11 aprile 2026, 09:00",
  "stars": "★★★★★",
  "tags": ["core_update"],
  "article_url": "/archivio/2026/04/11/test/",
})
assert "/archivio/2026/04/11/test/" in html
assert "core_update" in html
assert "Test" in html
print("OK")
PY
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add templates/partials/_card_top10.html.jinja templates/partials/_card_category.html.jinja templates/partials/_card_article_teaser.html.jinja
git commit -m "feat(templates): top10, category, and teaser card partials"
```

---

## Task 6: JSON-LD partials + homepage template + render_homepage method

**Files:**
- Create: `templates/partials/_jsonld_newsarticle.html.jinja`
- Create: `templates/partials/_jsonld_breadcrumb.html.jinja`
- Create: `templates/pages/homepage.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py` (add `render_homepage`)
- Modify: `tests/test_renderer.py` (add homepage test)

- [ ] **Step 1: Create `_jsonld_newsarticle.html.jinja`**

```html
{# Context: item, article_url (absolute), published_iso, category_label #}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": {{ item.title_it | tojson }},
  "description": {{ item.summary_it | tojson }},
  "datePublished": "{{ published_iso }}",
  "dateModified": "{{ published_iso }}",
  "author": {
    "@type": "Organization",
    "name": "Osservatorio SEO",
    "url": "https://osservatorioseo.pages.dev/"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Osservatorio SEO",
    "url": "https://osservatorioseo.pages.dev/"
  },
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "{{ article_url }}"
  },
  "articleSection": {{ category_label | tojson }},
  "inLanguage": "it-IT",
  "isBasedOn": {{ item.url | tojson }}
}
</script>
```

- [ ] **Step 2: Create `_jsonld_breadcrumb.html.jinja`**

```html
{# Context: breadcrumbs (list of {name, url}) #}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {% for crumb in breadcrumbs %}
    {
      "@type": "ListItem",
      "position": {{ loop.index }},
      "name": {{ crumb.name | tojson }},
      "item": "{{ crumb.url }}"
    }{% if not loop.last %},{% endif %}
    {% endfor %}
  ]
}
</script>
```

- [ ] **Step 3: Create `templates/pages/homepage.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content_wrapper %}{% endblock %}
```

Visto che usiamo `{{ content | safe }}` nel layout, in realtà la homepage genera il content in Python e passa la stringa. Però per hub pages + articolo è più comodo estendere il layout con block. Rivedo: cambio layout per usare blocks.

**Fix layout** — edita `templates/layout.html.jinja` per supportare sia `{{ content | safe }}` che un block:

Sostituisci:
```html
<main class="flex-grow pt-44 sm:pt-36 lg:pt-24 pb-12 px-4 sm:px-6 max-w-7xl mx-auto w-full">
{{ content | safe }}
</main>
```

con:

```html
<main class="{{ main_class | default('flex-grow pt-44 sm:pt-36 lg:pt-24 pb-12 px-4 sm:px-6 max-w-7xl mx-auto w-full') }}">
{% block content %}
{{ content | default('') | safe }}
{% endblock %}
</main>
```

Così è possibile estendere `layout.html.jinja` con `{% block content %}`.

- [ ] **Step 4: Reemplace `homepage.html.jinja` con block content pieno**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<section class="mb-10">
  <pre class="hidden md:block text-primary-container font-mono text-[8px] lg:text-[9px] leading-[1] mb-4 overflow-hidden terminal-glow">
 ██████╗ ███████╗███████╗███████╗██████╗ ██╗   ██╗ █████╗ ████████╗ ██████╗ ██████╗ ██╗ ██████╗    ███████╗███████╗ ██████╗
██╔═══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██║   ██║██╔══██╗╚══██╔══╝██╔═══██╗██╔══██╗██║██╔═══██╗   ██╔════╝██╔════╝██╔═══██╗
██║   ██║███████╗███████╗█████╗  ██████╔╝██║   ██║███████║   ██║   ██║   ██║██████╔╝██║██║   ██║   ███████╗█████╗  ██║   ██║
██║   ██║╚════██║╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══██║   ██║   ██║   ██║██╔══██╗██║██║   ██║   ╚════██║██╔══╝  ██║   ██║
╚██████╔╝███████║███████║███████╗██║  ██║ ╚████╔╝ ██║  ██║   ██║   ╚██████╔╝██║  ██║██║╚██████╔╝██╗███████║███████╗╚██████╔╝
 ╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝╚══════╝╚══════╝ ╚═════╝
  </pre>
  <div class="md:hidden text-primary-container font-bold text-2xl tracking-tight uppercase terminal-glow mb-4">OSSERVATORIO SEO</div>
  <div class="flex items-center gap-2 text-outline">
    <span class="text-primary-container">●</span>
    <span class="text-[10px] tracking-widest uppercase break-words" id="meta">{{ meta_line }}</span>
  </div>
</section>

<section class="mb-16" id="top10-section">
  <div class="flex items-center gap-4 mb-8">
    <h2 class="text-2xl font-bold tracking-tight uppercase" id="top10-title">&gt; TOP 10 DEL GIORNO</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <div id="top10" class="grid grid-cols-1 gap-px bg-outline-variant border border-outline-variant">
  {% for card in top10_cards %}
  {{ card | safe }}
  {% endfor %}
  </div>
</section>

<section class="mb-12" id="categories-section">
  <div class="flex items-center gap-4 mb-12">
    <h2 class="text-2xl font-bold tracking-tight uppercase" id="categories-title">&gt; TUTTE PER CATEGORIA</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <div id="categories" class="flex flex-col gap-16">
  {% for cat in categories %}
    <section class="flex flex-col gap-6">
      <div class="flex items-center justify-between border-b border-primary-container pb-2">
        <h3 class="text-primary-container font-bold uppercase tracking-widest text-sm">
          [ <a href="{{ cat.path }}" class="hover:underline">{{ cat.label }}</a> ]
        </h3>
        <span class="material-symbols-outlined text-primary-container text-sm">{{ cat.icon }}</span>
      </div>
      <div class="flex flex-col gap-4">
      {% for card in cat.cards %}
      {{ card | safe }}
      {% endfor %}
      </div>
    </section>
  {% endfor %}
  </div>
</section>

{% if failed_sources %}
<section class="mb-12" id="failed">
  <div class="flex items-center gap-4 mb-6">
    <h2 class="text-lg font-bold tracking-tight uppercase text-error">&gt; FONTI CON ERRORI</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <ul id="failed-list" class="flex flex-col gap-2 font-mono text-xs text-on-surface-variant">
  {% for fs in failed_sources %}
  <li class="border-l-2 border-error px-3 py-2 bg-surface-container-lowest">
    <span class="text-error uppercase">[ERR]</span>
    <code class="text-white">{{ fs.id }}</code>:
    <span class="text-on-surface-variant">{{ fs.error }}</span>
  </li>
  {% endfor %}
  </ul>
</section>
{% endif %}

<section class="mb-12" id="archive-results" hidden>
  <div class="flex items-center gap-4 mb-6">
    <h2 class="text-2xl font-bold tracking-tight uppercase">&gt; RISULTATI DALL'ARCHIVIO</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-4" id="archive-results-meta"></p>
  <div id="archive-results-list" class="flex flex-col gap-10"></div>
</section>
{% endblock %}
```

- [ ] **Step 5: Add `render_homepage` method to renderer**

Edit `src/osservatorio_seo/renderer.py`, aggiungendo il metodo:

```python
def render_homepage(self, context: dict) -> str:
    return self.render_raw("pages/homepage.html.jinja", context)
```

- [ ] **Step 6: Add smoke test for homepage rendering**

Append to `tests/test_renderer.py`:

```python
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
```

- [ ] **Step 7: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add templates/partials/_jsonld_newsarticle.html.jinja templates/partials/_jsonld_breadcrumb.html.jinja templates/pages/homepage.html.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py templates/layout.html.jinja
git commit -m "feat(renderer): homepage template with JSON-LD breadcrumb + render_homepage"
```

---

## Task 7: Snapshot template + render_snapshot

**Files:**
- Create: `templates/pages/snapshot.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Create `templates/pages/snapshot.html.jinja`**

Uguale alla homepage ma con banner in meta line + titolo section con data:

```html
{% extends "pages/homepage.html.jinja" %}

{# Il layout è identico alla homepage tranne due dettagli gestiti dal context:
   - ``meta_line`` già contiene il banner SNAPSHOT YYYY-MM-DD // …
   - I titoli sezione top10-title e categories-title sono passati in context
     come ``top10_title`` e ``categories_title``. Poiché homepage.html.jinja
     attualmente hardcoda "> TOP 10 DEL GIORNO", il metodo renderer
     ``render_snapshot`` passerà valori diversi via contesto + override block. #}
```

Questo approccio è fragile. Alternativa pulita: **entrambi** usano la stessa template ma il context passa `top10_title` e `categories_title` come variabili. Aggiorno `homepage.html.jinja`:

- [ ] **Step 2: Aggiorna `homepage.html.jinja`**

Sostituisci le due h2 hardcoded:

```html
<h2 class="text-2xl font-bold tracking-tight uppercase" id="top10-title">&gt; TOP 10 DEL GIORNO</h2>
```

con:

```html
<h2 class="text-2xl font-bold tracking-tight uppercase" id="top10-title">{{ top10_title | default("> TOP 10 DEL GIORNO") }}</h2>
```

E stessa cosa per `categories-title`:

```html
<h2 class="text-2xl font-bold tracking-tight uppercase" id="categories-title">{{ categories_title | default("> TUTTE PER CATEGORIA") }}</h2>
```

- [ ] **Step 3: Definisci `snapshot.html.jinja` come alias**

```html
{% extends "pages/homepage.html.jinja" %}
```

Aggiungi un `extra_head` block con banner JSON-LD tipo `WebPage` che riferisce allo snapshot del giorno (opzionale, posso aggiungerlo in un Task successivo).

Per ora snapshot è semplicemente homepage con context diverso.

- [ ] **Step 4: Aggiungi `render_snapshot` al renderer**

```python
def render_snapshot(self, context: dict) -> str:
    return self.render_raw("pages/snapshot.html.jinja", context)
```

- [ ] **Step 5: Aggiungi test**

```python
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
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/pages/snapshot.html.jinja templates/pages/homepage.html.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): snapshot template reuses homepage with dynamic section titles"
```

---

## Task 8: Article single page template + render_article

**Files:**
- Create: `templates/pages/article.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Create `templates/pages/article.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_newsarticle.html.jinja" %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6 flex items-center gap-2 flex-wrap">
  {% for crumb in breadcrumbs %}
    {% if not loop.last %}
    <a href="{{ crumb.site_path }}" class="hover:text-primary-container">{{ crumb.name }}</a>
    <span class="text-outline-variant">/</span>
    {% else %}
    <span class="text-primary-container">{{ crumb.name }}</span>
    {% endif %}
  {% endfor %}
</nav>

<article class="max-w-3xl mx-auto">
  <header class="mb-8">
    <p class="text-[10px] text-outline uppercase font-mono mb-2">
      <a href="{{ category_path }}" class="text-primary-container hover:underline">{{ category_label }}</a>
      · <span class="text-[#f5a623]">{{ stars }}</span>
      · <time datetime="{{ item.published_at }}">{{ absolute_date }}</time>
    </p>
    <h1 class="text-3xl sm:text-4xl font-bold tracking-tight mb-4">{{ item.title_it }}</h1>
    <p class="text-sm text-outline font-mono uppercase">Fonte: <a class="text-primary-container hover:underline" href="{{ item.url }}" target="_blank" rel="noopener">{{ item.source.name }}</a></p>
  </header>

  <section class="prose prose-invert mb-8">
    <p class="text-lg leading-relaxed text-on-surface">{{ item.summary_it }}</p>
  </section>

  {% if item.tags %}
  <section class="mb-8">
    <h2 class="text-sm text-outline uppercase font-mono mb-3">&gt; TAGS</h2>
    <div class="flex flex-wrap gap-2">
      {% for t in item.tags %}
      <a href="/tag/{{ t | replace('_', '-') }}/" class="text-xs uppercase tracking-wider px-3 py-1 border border-outline-variant text-outline hover:text-primary-container hover:border-primary-container font-mono">#{{ t }}</a>
      {% endfor %}
    </div>
  </section>
  {% endif %}

  <section class="mb-8 p-6 bg-surface-container-low border-l-2 border-primary-container">
    <p class="text-sm text-on-surface-variant font-mono leading-relaxed">
      Questo è un <strong class="text-white">riassunto generato da AI</strong> a partire dall'articolo originale pubblicato su
      <a class="text-primary-container hover:underline" href="{{ item.url }}" target="_blank" rel="noopener">{{ item.source.name }}</a>.
      Il riassunto è creato da <code class="text-primary-container">{{ item.summarizer_model }}</code>.
      Per il testo completo e l'attribuzione, consulta la fonte originale.
    </p>
    <a class="inline-block mt-4 text-xs border border-outline px-3 py-1 hover:border-primary-container hover:text-primary-container transition-all uppercase tracking-wider" href="{{ item.url }}" target="_blank" rel="noopener">LEGGI L'ORIGINALE →</a>
  </section>

  <section class="mb-8">
    <h2 class="text-sm text-outline uppercase font-mono mb-3">&gt; ALTRI DAL GIORNO</h2>
    <p class="text-xs text-outline font-mono uppercase">
      <a href="{{ day_path }}" class="text-primary-container hover:underline">Vedi tutti gli articoli del {{ day_label }}</a>
    </p>
  </section>
</article>
{% endblock %}
```

- [ ] **Step 2: Add `render_article` to renderer**

```python
def render_article(self, context: dict) -> str:
    return self.render_raw("pages/article.html.jinja", context)
```

- [ ] **Step 3: Add test**

```python
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
                {"name": "Home", "url": "https://osservatorioseo.pages.dev/", "site_path": "/"},
                {"name": "Archivio", "url": "https://osservatorioseo.pages.dev/archivio/", "site_path": "/archivio/"},
                {"name": "2026", "url": "https://osservatorioseo.pages.dev/archivio/2026/", "site_path": "/archivio/2026/"},
                {"name": "11 aprile", "url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/", "site_path": "/archivio/2026/04/11/"},
                {"name": "Google rilascia il core update", "url": "https://osservatorioseo.pages.dev/archivio/2026/04/11/google-rilascia-core-update/", "site_path": ""},
            ],
        }
    )
    assert '<h1' in html
    assert "Google rilascia il core update" in html
    assert '"@type": "NewsArticle"' in html
    assert '"@type": "BreadcrumbList"' in html
    assert "LEGGI L'ORIGINALE" in html
    assert "/categoria/google-updates/" in html
    assert "/tag/core-update/" in html
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add templates/pages/article.html.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): article template with JSON-LD NewsArticle + breadcrumb"
```

---

## Task 9: Hub templates (archive, year, month, day, category, tag)

**Files:**
- Create: `templates/pages/archive_index.html.jinja`
- Create: `templates/pages/year_hub.html.jinja`
- Create: `templates/pages/month_hub.html.jinja`
- Create: `templates/pages/day_hub.html.jinja`
- Create: `templates/pages/category_hub.html.jinja`
- Create: `templates/pages/tag_hub.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py`

- [ ] **Step 1: Create `archive_index.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; ARCHIVE_INDEX</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">{{ meta_line }}</p>

  <ul class="flex flex-col gap-2">
  {% for year_entry in years %}
    <li>
      <a class="group flex items-center justify-between px-4 py-3 border border-outline-variant bg-surface-container-low hover:border-primary-container hover:bg-surface-container transition-colors" href="{{ year_entry.path }}">
        <div class="flex items-center gap-4">
          <span class="text-primary-container font-bold font-mono text-sm">{{ "%04d" | format(year_entry.year) }}</span>
          <span class="font-mono text-sm text-white">{{ year_entry.count }} LOG FILES</span>
        </div>
        <span class="text-xs text-outline uppercase tracking-widest group-hover:text-primary-container transition-colors">OPEN_YEAR →</span>
      </a>
    </li>
  {% endfor %}
  </ul>
</section>
{% endblock %}
```

- [ ] **Step 2: Create `year_hub.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <a href="/archivio/" class="hover:text-primary-container">ARCHIVIO</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">{{ year }}</span>
</nav>

<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; ARCHIVIO {{ year }}</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>

  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
  {% for month_entry in months %}
    <a href="{{ month_entry.path }}" class="px-4 py-3 border border-outline-variant bg-surface-container-low hover:border-primary-container hover:bg-surface-container transition-colors">
      <div class="font-mono text-sm text-white uppercase">{{ month_entry.label }}</div>
      <div class="text-[10px] text-outline uppercase font-mono">{{ month_entry.count }} giorni</div>
    </a>
  {% endfor %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 3: Create `month_hub.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <a href="/archivio/" class="hover:text-primary-container">ARCHIVIO</a>
  <span class="text-outline-variant"> / </span>
  <a href="{{ year_path }}" class="hover:text-primary-container">{{ year }}</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">{{ month_label }}</span>
</nav>

<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; {{ month_label }} {{ year }}</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>

  <ul class="flex flex-col gap-2">
  {% for day_entry in days %}
    <li>
      <a class="group flex items-center justify-between px-4 py-3 border border-outline-variant bg-surface-container-low hover:border-primary-container hover:bg-surface-container transition-colors" href="{{ day_entry.path }}">
        <div class="flex items-center gap-4">
          <span class="text-primary-container font-bold font-mono text-sm">{{ day_entry.date }}</span>
          <span class="font-mono text-xs text-outline uppercase hidden md:inline">{{ day_entry.label }}</span>
        </div>
        <span class="text-xs text-outline uppercase tracking-widest group-hover:text-primary-container transition-colors">{{ day_entry.count }} LOGS →</span>
      </a>
    </li>
  {% endfor %}
  </ul>
</section>
{% endblock %}
```

- [ ] **Step 4: Create `day_hub.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <a href="/archivio/" class="hover:text-primary-container">ARCHIVIO</a>
  <span class="text-outline-variant"> / </span>
  <a href="{{ year_path }}" class="hover:text-primary-container">{{ year }}</a>
  <span class="text-outline-variant"> / </span>
  <a href="{{ month_path }}" class="hover:text-primary-container">{{ month_label }}</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">{{ day }}</span>
</nav>

<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; {{ day_label }}</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">{{ meta_line }}</p>

  <div class="flex flex-col gap-2">
  {% for card in teaser_cards %}
  {{ card | safe }}
  {% endfor %}
  </div>

  <div class="mt-8 text-[10px] text-outline uppercase font-mono">
    Vedi anche:
    <a class="text-primary-container hover:underline" href="{{ snapshot_path }}">vista completa di questo giorno</a>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 5: Create `category_hub.html.jinja` e `tag_hub.html.jinja`**

Entrambi sono quasi identici; listing di card teaser.

```html
{# templates/pages/category_hub.html.jinja #}
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-outline">CATEGORIA</span>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">{{ category_label }}</span>
</nav>

<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; {{ category_label }}</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">{{ meta_line }}</p>

  <div class="flex flex-col gap-2">
  {% for card in teaser_cards %}
  {{ card | safe }}
  {% endfor %}
  </div>
</section>
{% endblock %}
```

```html
{# templates/pages/tag_hub.html.jinja — identica salvo label #}
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="text-[10px] text-outline uppercase font-mono mb-6">
  <a href="/" class="hover:text-primary-container">HOME</a>
  <span class="text-outline-variant"> / </span>
  <span class="text-outline">TAG</span>
  <span class="text-outline-variant"> / </span>
  <span class="text-primary-container">#{{ tag_label }}</span>
</nav>

<section class="mb-12">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; #{{ tag_label }}</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">{{ meta_line }}</p>

  <div class="flex flex-col gap-2">
  {% for card in teaser_cards %}
  {{ card | safe }}
  {% endfor %}
  </div>
</section>
{% endblock %}
```

- [ ] **Step 6: Add render methods**

```python
def render_archive_index(self, context: dict) -> str:
    return self.render_raw("pages/archive_index.html.jinja", context)

def render_year_hub(self, context: dict) -> str:
    return self.render_raw("pages/year_hub.html.jinja", context)

def render_month_hub(self, context: dict) -> str:
    return self.render_raw("pages/month_hub.html.jinja", context)

def render_day_hub(self, context: dict) -> str:
    return self.render_raw("pages/day_hub.html.jinja", context)

def render_category_hub(self, context: dict) -> str:
    return self.render_raw("pages/category_hub.html.jinja", context)

def render_tag_hub(self, context: dict) -> str:
    return self.render_raw("pages/tag_hub.html.jinja", context)
```

- [ ] **Step 7: Smoke test**

Append a single smoke test in `tests/test_renderer.py`:

```python
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
```

- [ ] **Step 8: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 6 passed.

- [ ] **Step 9: Commit**

```bash
git add templates/pages/archive_index.html.jinja templates/pages/year_hub.html.jinja templates/pages/month_hub.html.jinja templates/pages/day_hub.html.jinja templates/pages/category_hub.html.jinja templates/pages/tag_hub.html.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): archive/year/month/day/category/tag hub templates"
```

---

## Task 10: Docs + About templates

**Files:**
- Create: `templates/pages/docs.html.jinja`
- Create: `templates/pages/about.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py`

- [ ] **Step 1: Create `templates/pages/docs.html.jinja`**

Per brevità di plan: copia il contenuto di `site/docs.html` (tutta la sezione `<main>` con `> DOCS // COME FUNZIONA`, `> LE PAGINE`, `> RANKING & CATEGORIE`, `> STACK TECNICO`) dentro un block `{% block content %}`, e sostituisci le sezioni dinamiche per fonti + doc watcher con loop Jinja2 sulle liste `sources` e `doc_watcher_pages` passate in context (invece del fetch JS). Struttura:

```html
{% extends "layout.html.jinja" %}

{% block content %}
<section class="mb-16">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; DOCS // COME FUNZIONA</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <div class="space-y-6 font-mono text-sm text-on-surface-variant leading-relaxed">
    <!-- ...stesso testo della versione JS ma statico... -->
  </div>
</section>

<!-- ... LE PAGINE ... (identico alla versione JS ma statico) -->

<section class="mb-16">
  <div class="flex items-center gap-4 mb-8">
    <h2 class="text-2xl font-bold tracking-tight uppercase">&gt; FONTI MONITORATE</h2>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">{{ sources | length }} FONTI ATTIVE</p>
  {% for type_label, type_sources in sources_by_type.items() %}
  <div class="mb-6">
    <h3 class="text-primary-container font-bold uppercase tracking-widest text-xs mb-3 pb-1 border-b border-outline-variant">[ {{ type_label }} // {{ type_sources | length }} ]</h3>
    <div class="flex flex-col gap-1">
    {% for s in type_sources %}
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-2 px-4 py-2 border border-outline-variant bg-surface-container-lowest font-mono text-xs">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-[#f5a623]">{{ '★' * s.authority }}</span>
        <span class="text-white">{{ s.name }}</span>
        <span class="text-outline text-[10px] uppercase">{{ s.id }}</span>
      </div>
      <div class="flex items-center gap-3 text-[10px] uppercase">
        <span>{{ s.fetcher }}</span>
        <a href="{{ s.url }}" target="_blank" rel="noopener" class="text-outline hover:text-primary-container">{{ s.hostname }} →</a>
      </div>
    </div>
    {% endfor %}
    </div>
  </div>
  {% endfor %}
</section>

<!-- DOC WATCHER section, static loop on doc_watcher_pages -->

<section class="mb-16">
  <h2 class="text-2xl font-bold tracking-tight uppercase mb-8">&gt; RANKING &amp; CATEGORIE</h2>
  <!-- static content -->
</section>

<section class="mb-16">
  <h2 class="text-2xl font-bold tracking-tight uppercase mb-8">&gt; STACK TECNICO</h2>
  <!-- static content -->
</section>
{% endblock %}
```

**Nota**: il template concreto deve includere tutto il testo narrativo attualmente in `site/docs.html` — copia-incolla + adatta i blocchi dinamici a loop Jinja. Per il plan, fidarsi che il file sarà ~300 righe perché il contenuto narrativo è già pronto.

- [ ] **Step 2: Create `templates/pages/about.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block content %}
<article class="max-w-3xl mx-auto">
  <h1 class="text-3xl sm:text-4xl font-bold mb-6">Chi siamo</h1>

  <p class="font-mono text-sm text-on-surface-variant mb-4">
    <strong class="text-white">Osservatorio SEO</strong> è un hub giornaliero di notizie SEO e AI che riassume in italiano articoli da fonti autorevoli internazionali. Il sito è costruito da <a class="text-primary-container hover:underline" href="https://donatopirolo.dev" target="_blank" rel="noopener">Donato Pirolo</a>, consulente SEO e sviluppatore.
  </p>

  <h2 class="text-xl font-bold mt-8 mb-3">Come sono generati i contenuti</h2>
  <p class="font-mono text-sm text-on-surface-variant mb-4">
    Ogni mattina alle 07:00 Europe/Rome, una pipeline Python scarica gli ultimi articoli da {{ source_count }} fonti (blog ufficiali Google/OpenAI/Anthropic, media come Search Engine Land/Journal/Roundtable, voci indipendenti come Kevin Indig e Glenn Gabe). Per ogni articolo, un modello AI (<code class="text-primary-container">google/gemini-2.0-flash-001</code>) genera un riassunto in italiano, una categoria, tag, e un punteggio di importanza 1-5.
  </p>

  <h2 class="text-xl font-bold mt-8 mb-3">Trasparenza AI</h2>
  <p class="font-mono text-sm text-on-surface-variant mb-4">
    I riassunti sono <strong class="text-white">generati da AI, non rivisti editorialmente</strong>. Ogni articolo linka sempre alla fonte originale e il modello usato è dichiarato in ogni pagina. I riassunti possono contenere imprecisioni — per decisioni operative, consulta sempre la fonte originale.
  </p>

  <h2 class="text-xl font-bold mt-8 mb-3">Policy contenuti</h2>
  <p class="font-mono text-sm text-on-surface-variant mb-4">
    Pubblichiamo solo <strong class="text-white">titoli nostri + riassunti nostri + link alle fonti</strong>. Nessun testo integrale viene riprodotto. Se sei titolare di una fonte e vuoi essere rimosso, apri una issue su <a class="text-primary-container hover:underline" href="https://github.com/donatopirolo/osservatorioseo" target="_blank" rel="noopener">GitHub</a> — rispondiamo entro 24h.
  </p>

  <h2 class="text-xl font-bold mt-8 mb-3">Stack tecnico</h2>
  <p class="font-mono text-sm text-on-surface-variant mb-4">
    Open source, zero server, zero database. Python 3.12 + GitHub Actions + Cloudflare Pages. Codice su <a class="text-primary-container hover:underline" href="https://github.com/donatopirolo/osservatorioseo" target="_blank" rel="noopener">github.com/donatopirolo/osservatorioseo</a>.
  </p>
</article>
{% endblock %}
```

- [ ] **Step 3: Add render methods**

```python
def render_docs(self, context: dict) -> str:
    return self.render_raw("pages/docs.html.jinja", context)

def render_about(self, context: dict) -> str:
    return self.render_raw("pages/about.html.jinja", context)
```

- [ ] **Step 4: Smoke test**

```python
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

    about_html = renderer.render_about({**base_ctx, "page_title": "Chi siamo", "source_count": 21})
    assert "Chi siamo" in about_html
    assert "donatopirolo" in about_html
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add templates/pages/docs.html.jinja templates/pages/about.html.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): docs and about page templates"
```

---

## Task 11: Sitemap.xml + feed.xml + robots.txt generators

**Files:**
- Create: `templates/sitemap.xml.jinja`
- Create: `templates/feed.xml.jinja`
- Create: `templates/robots.txt.jinja`
- Modify: `src/osservatorio_seo/renderer.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Create `templates/sitemap.xml.jinja`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{% for url in urls %}
  <url>
    <loc>{{ url.loc }}</loc>
    {% if url.lastmod %}<lastmod>{{ url.lastmod }}</lastmod>{% endif %}
    <changefreq>{{ url.changefreq | default('daily') }}</changefreq>
    <priority>{{ url.priority | default('0.5') }}</priority>
  </url>
{% endfor %}
</urlset>
```

- [ ] **Step 2: Create `templates/feed.xml.jinja` (Atom)**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Osservatorio SEO</title>
  <subtitle>News giornaliere SEO e AI — riassunti in italiano</subtitle>
  <link href="{{ site_url }}/feed.xml" rel="self" />
  <link href="{{ site_url }}/" />
  <id>{{ site_url }}/</id>
  <updated>{{ updated }}</updated>
  <author>
    <name>Osservatorio SEO</name>
    <uri>{{ site_url }}/</uri>
  </author>
  {% for entry in entries %}
  <entry>
    <title>{{ entry.title }}</title>
    <link href="{{ entry.url }}" />
    <id>{{ entry.url }}</id>
    <updated>{{ entry.updated }}</updated>
    <published>{{ entry.published }}</published>
    <summary type="html">{{ entry.summary }}</summary>
    {% for tag in entry.tags %}
    <category term="{{ tag }}" />
    {% endfor %}
  </entry>
  {% endfor %}
</feed>
```

- [ ] **Step 3: Create `templates/robots.txt.jinja`**

```txt
User-agent: *
{% if allow_indexing %}Allow: /
{% else %}Disallow: /
{% endif %}

Sitemap: {{ site_url }}/sitemap.xml
```

- [ ] **Step 4: Add render methods**

```python
def render_sitemap(self, context: dict) -> str:
    return self.render_raw("sitemap.xml.jinja", context)

def render_feed_xml(self, context: dict) -> str:
    return self.render_raw("feed.xml.jinja", context)

def render_robots_txt(self, context: dict) -> str:
    return self.render_raw("robots.txt.jinja", context)
```

- [ ] **Step 5: Test**

```python
def test_render_sitemap_robots_feed() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    sitemap = renderer.render_sitemap(
        {
            "urls": [
                {"loc": "https://x.com/", "lastmod": "2026-04-11", "priority": "1.0"},
                {"loc": "https://x.com/archivio/", "lastmod": "2026-04-11", "priority": "0.8"},
            ]
        }
    )
    assert "<loc>https://x.com/</loc>" in sitemap
    assert "<lastmod>2026-04-11</lastmod>" in sitemap

    robots_noindex = renderer.render_robots_txt({"allow_indexing": False, "site_url": "https://x.com"})
    assert "Disallow: /" in robots_noindex
    assert "Sitemap: https://x.com/sitemap.xml" in robots_noindex

    robots_allow = renderer.render_robots_txt({"allow_indexing": True, "site_url": "https://x.com"})
    assert "Allow: /" in robots_allow

    feed = renderer.render_feed_xml(
        {
            "site_url": "https://x.com",
            "updated": "2026-04-11T07:00:00Z",
            "entries": [
                {
                    "title": "Test",
                    "url": "https://x.com/a/",
                    "updated": "2026-04-11T07:00:00Z",
                    "published": "2026-04-11T07:00:00Z",
                    "summary": "summary",
                    "tags": ["seo"],
                }
            ],
        }
    )
    assert "<title>Test</title>" in feed
    assert '<category term="seo"' in feed
```

- [ ] **Step 6: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py -v
```

Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/sitemap.xml.jinja templates/feed.xml.jinja templates/robots.txt.jinja src/osservatorio_seo/renderer.py tests/test_renderer.py
git commit -m "feat(renderer): sitemap.xml, feed.xml (Atom) and robots.txt templates"
```

---

## Task 12: Publisher integration — basic SSG output (homepage + snapshot + archive index)

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Modify: `src/osservatorio_seo/pipeline.py`
- Modify: `tests/test_publisher.py`

- [ ] **Step 1: Add `publish_ssg()` method to `Publisher`**

Edit `src/osservatorio_seo/publisher.py`, aggiungendo import in cima:

```python
from osservatorio_seo.renderer import HtmlRenderer
from osservatorio_seo.seo import (
    canonical,
    day_path as make_day_path,
    month_path as make_month_path,
    year_path as make_year_path,
    category_path as make_category_path,
    tag_path as make_tag_path,
)
from osservatorio_seo.slug import make_unique_slug
```

E aggiungi il metodo alla classe:

```python
def publish_ssg(
    self,
    feed: Feed,
    sources: list[Source],
    doc_pages: list[DocWatcherPage],
    templates_dir: Path,
    site_dir: Path,
    *,
    allow_indexing: bool = False,
) -> None:
    """Genera tutti gli HTML SSG per ``feed``.

    ``site_dir`` è la root di output (solitamente ``site/``). Questo metodo
    NON tocca ``data/`` (che è già stato popolato da ``publish()``).
    Genera:
      - index.html (feed del giorno)
      - archivio/YYYY/MM/DD/index.html (snapshot)
      - archivio/YYYY/MM/DD/<slug>/index.html (articolo, solo importance>=4)
      - archivio/index.html, archivio/YYYY/index.html, archivio/YYYY/MM/index.html
      - categoria/<cat>/index.html, tag/<tag>/index.html
      - docs/index.html, about/index.html
      - sitemap.xml, feed.xml, robots.txt
    """
    renderer = HtmlRenderer(templates_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    # Placeholder chiamate — riempite da step successivi
    self._ssg_homepage(renderer, feed, site_dir, allow_indexing)
```

E il helper privato:

```python
def _ssg_homepage(
    self,
    renderer: HtmlRenderer,
    feed: Feed,
    site_dir: Path,
    allow_indexing: bool,
) -> None:
    """Render homepage and write site_dir/index.html."""
    context = self._build_homepage_context(feed, allow_indexing)
    html = renderer.render_homepage(context)
    (site_dir / "index.html").write_text(html, encoding="utf-8")

def _build_homepage_context(self, feed: Feed, allow_indexing: bool) -> dict:
    # Stub minimale per il primo step — il rendering di top10/categories
    # card è implementato in Task 13
    return {
        "page_title": "Osservatorio SEO — News giornaliere SEO e AI",
        "page_description": (
            "Hub giornaliero di notizie SEO e AI aggiornato alle 07:00. "
            "Raccoglie fonti autorevoli, riassume in italiano, rileva modifiche "
            "alle policy Google."
        ),
        "canonical_url": canonical("/"),
        "active_nav": "today",
        "noindex": not allow_indexing,
        "meta_line": "SYSTEM STATUS: OPTIMAL",
        "top10_cards": [],
        "categories": [],
        "failed_sources": [],
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
        ],
    }
```

- [ ] **Step 2: Call `publish_ssg` from pipeline**

Edit `src/osservatorio_seo/pipeline.py`, alla fine di `run()`:

```python
publisher.publish(feed)
publisher.publish_config_snapshot(sources, doc_pages)
publisher.publish_ssg(
    feed,
    sources,
    doc_pages,
    templates_dir=Path("templates"),
    site_dir=Path("site"),
    allow_indexing=False,
)
return feed
```

- [ ] **Step 3: Test**

Edit `tests/test_publisher.py`, aggiungi:

```python
def test_publish_ssg_writes_homepage(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    templates_dir = Path("templates")
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    pub.publish_ssg(feed, [], [], templates_dir=templates_dir, site_dir=site_dir)
    index_html = site_dir / "index.html"
    assert index_html.exists()
    content = index_html.read_text()
    assert "OSSERVATORIO_SEO" in content
    assert 'id="top10"' in content
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_publisher.py -v
```

Expected: 6 passed (5 esistenti + 1 nuovo).

- [ ] **Step 5: Commit**

```bash
git add src/osservatorio_seo/publisher.py src/osservatorio_seo/pipeline.py tests/test_publisher.py
git commit -m "feat(publisher): scaffold publish_ssg with homepage rendering"
```

---

## Task 13: Publisher — top10 + categories card rendering

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Modify: `tests/test_publisher.py`

- [ ] **Step 1: Extract card context builder**

Edit `publisher.py`, aggiungi helper per costruire context card:

```python
def _stars(importance: int) -> str:
    return "★" * importance + "☆" * (5 - importance)

def _short_id(item: Item) -> str:
    import re as _re
    src = item.raw_hash or item.id or ""
    m = _re.sub(r"[^a-zA-Z0-9]", "", src)
    return (m[-4:] or "0000").upper()

def _build_search_blob(item: Item) -> str:
    import re as _re
    parts = [
        item.title_it or "",
        item.title_original or "",
        item.summary_it or "",
        " ".join(item.tags or []),
        item.source.name if item.source else "",
        item.source.id if item.source else "",
        item.category or "",
        item.url or "",
    ]
    blob = " ".join(parts)
    return _re.sub(r"[_\-/]+", " ", blob).lower()
```

- [ ] **Step 2: Build card contexts using renderer partials**

Aggiorna `_build_homepage_context` in publisher.py:

```python
from datetime import UTC, datetime

from osservatorio_seo.renderer import HtmlRenderer


_CATEGORY_LABELS = {
    "google_updates": "Google Updates",
    "google_docs_change": "Google Docs Change ⚠️",
    "ai_models": "AI Models",
    "ai_overviews_llm_seo": "AI Overviews & LLM SEO",
    "technical_seo": "Technical SEO",
    "content_eeat": "Content & E-E-A-T",
    "tools_platforms": "Tools & Platforms",
    "industry_news": "Industry News",
}

_CATEGORY_ICONS = {
    "google_updates": "history",
    "google_docs_change": "warning",
    "ai_models": "smart_toy",
    "ai_overviews_llm_seo": "auto_awesome",
    "technical_seo": "build",
    "content_eeat": "article",
    "tools_platforms": "settings",
    "industry_news": "public",
}


def _relative_date(published: datetime) -> str:
    """Format date in Italian relative form ('2 ore fa', 'ieri', '3 giorni fa')."""
    now = datetime.now(UTC)
    diff = now - published
    secs = diff.total_seconds()
    if secs < 60:
        return "adesso"
    if secs < 3600:
        return f"{int(secs // 60)} min fa"
    if secs < 86400:
        return f"{int(secs // 3600)} h fa"
    days = int(secs // 86400)
    if days < 2:
        return "ieri"
    if days < 7:
        return f"{days} giorni fa"
    return published.strftime("%-d %b %Y")


def _absolute_date(published: datetime) -> str:
    # Italian locale is not always installed, we use a simple format
    return published.strftime("%A %-d %B %Y, %H:%M")
```

Poi in `_build_homepage_context`, aggiungi generazione top10 + categories con articoli slug:

```python
def _build_homepage_context(
    self,
    feed: Feed,
    allow_indexing: bool,
    item_slugs: dict[str, str],
    renderer: HtmlRenderer,
    day_iso: str,
) -> dict:
    items_by_id = {i.id: i for i in feed.items}

    def build_card_ctx(item: Item) -> dict:
        article_url = "/archivio/{}/{}/{}/{}/".format(
            *day_iso.split("-"), item_slugs.get(item.id, "untitled")
        ) if item.importance >= 4 else item.url  # fallback to external if no internal page
        return {
            "item": item.model_dump(mode="json"),
            "search_blob": _build_search_blob(item),
            "short_id": _short_id(item),
            "relative_date": _relative_date(item.published_at),
            "absolute_date": _absolute_date(item.published_at),
            "stars": _stars(item.importance),
            "tags": item.tags,
            "article_url": article_url,
        }

    top10_cards = []
    for idx, item_id in enumerate(feed.top10, start=1):
        item = items_by_id.get(item_id)
        if not item:
            continue
        ctx = {**build_card_ctx(item), "order": idx}
        top10_cards.append(renderer.render_raw("partials/_card_top10.html.jinja", ctx))

    categories = []
    for cat_id, ids in feed.categories.items():
        cards = []
        for item_id in ids:
            item = items_by_id.get(item_id)
            if not item:
                continue
            ctx = build_card_ctx(item)
            cards.append(renderer.render_raw("partials/_card_category.html.jinja", ctx))
        if cards:
            categories.append({
                "label": _CATEGORY_LABELS.get(cat_id, cat_id),
                "icon": _CATEGORY_ICONS.get(cat_id, "folder"),
                "path": make_category_path(cat_id),
                "cards": cards,
            })

    meta_line = (
        f"SYSTEM STATUS: OPTIMAL // LAST REFRESH "
        f"{feed.generated_at_local.strftime('%A %d %B %Y, %H:%M')} // "
        f"{feed.stats.sources_checked} SOURCES // {feed.stats.items_after_dedup} LOGS // "
        f"{feed.stats.doc_changes_detected} DOC CHANGES // €{feed.stats.ai_cost_eur:.3f} AI COST"
    )

    return {
        "page_title": "Osservatorio SEO — News giornaliere SEO e AI",
        "page_description": "Hub giornaliero di notizie SEO e AI.",
        "canonical_url": canonical("/"),
        "active_nav": "today",
        "noindex": not allow_indexing,
        "meta_line": meta_line,
        "top10_cards": top10_cards,
        "categories": categories,
        "failed_sources": [fs.model_dump() for fs in feed.failed_sources],
        "breadcrumbs": [{"name": "Home", "url": canonical("/")}],
    }
```

- [ ] **Step 3: Generate slugs for all items in `publish_ssg`**

Before calling `_ssg_homepage`, build a slug map:

```python
def publish_ssg(self, feed, sources, doc_pages, templates_dir, site_dir, *, allow_indexing=False) -> None:
    renderer = HtmlRenderer(templates_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    existing_slugs: set[str] = set()
    item_slugs: dict[str, str] = {}
    for item in feed.items:
        if item.importance < 4:
            continue
        slug = make_unique_slug(item.title_it, existing_slugs)
        existing_slugs.add(slug)
        item_slugs[item.id] = slug

    self._ssg_homepage(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

E aggiorna `_ssg_homepage`:

```python
def _ssg_homepage(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    context = self._build_homepage_context(feed, allow_indexing, item_slugs, renderer, day_iso)
    html = renderer.render_homepage(context)
    (site_dir / "index.html").write_text(html, encoding="utf-8")
```

- [ ] **Step 4: Update test to match**

In `tests/test_publisher.py` il test `test_publish_ssg_writes_homepage` ora deve passare `sources=[]` e `doc_pages=[]` (già fa). L'output deve contenere la card del top10.

Aggiungi assertion:

```python
    assert "01." in content  # top10 numbered card
    assert mk_feed().items[0].title_it in content
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/pytest tests/test_publisher.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): render top10 and categories cards into homepage SSG"
```

---

## Task 14: Publisher — snapshot + day hub + article pages

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Modify: `tests/test_publisher.py`

- [ ] **Step 1: Add snapshot + day_hub + article generation to `publish_ssg`**

In `publish_ssg`, dopo `_ssg_homepage`:

```python
    # Snapshot: identico alla homepage ma con titoli "del giorno X"
    self._ssg_snapshot(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)

    # Day hub: listing compatto (teaser) per day_iso
    self._ssg_day_hub(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)

    # Single article pages per importance >= 4
    self._ssg_articles(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

E i 3 metodi helper:

```python
def _ssg_snapshot(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    ctx = self._build_homepage_context(feed, allow_indexing, item_slugs, renderer, day_iso)
    y, m, d = day_iso.split("-")
    day_int = int(d)
    month_int = int(m)
    year_int = int(y)
    ctx = {
        **ctx,
        "page_title": f"Snapshot {day_iso} — Osservatorio SEO",
        "canonical_url": canonical(f"/archivio/{y}/{m}/{d}/"),
        "active_nav": "archive",
        "meta_line": f"SNAPSHOT {day_iso} // " + ctx["meta_line"],
        "top10_title": f"> TOP 10 DEL GIORNO {d} {m} {y}",
        "categories_title": f"> TUTTE PER CATEGORIA {d} {m} {y}",
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Archivio", "url": canonical("/archivio/")},
            {"name": str(year_int), "url": canonical(f"/archivio/{y}/")},
            {"name": f"{month_int:02d}", "url": canonical(f"/archivio/{y}/{m}/")},
            {"name": day_iso, "url": canonical(f"/archivio/{y}/{m}/{d}/")},
        ],
    }
    html = renderer.render_snapshot(ctx)
    target_dir = site_dir / "archivio" / y / m / d
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text(html, encoding="utf-8")

def _ssg_day_hub(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    y, m, d = day_iso.split("-")
    teaser_cards = []
    for item in feed.items:
        article_url = f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/" if item.importance >= 4 else item.url
        tctx = {
            "item": item.model_dump(mode="json"),
            "short_id": _short_id(item),
            "relative_date": _relative_date(item.published_at),
            "absolute_date": _absolute_date(item.published_at),
            "stars": _stars(item.importance),
            "article_url": article_url,
        }
        teaser_cards.append(renderer.render_raw("partials/_card_article_teaser.html.jinja", tctx))

    day_label = feed.generated_at_local.strftime("%A %d %B %Y")
    ctx = {
        "page_title": f"Archivio {day_iso} — Osservatorio SEO",
        "page_description": f"Tutte le notizie SEO e AI del {day_label}",
        "canonical_url": canonical(f"/archivio/{y}/{m}/{d}/hub/"),
        "active_nav": "archive",
        "noindex": not allow_indexing,
        "meta_line": f"{len(feed.items)} ARTICOLI",
        "year": int(y),
        "year_path": f"/archivio/{y}/",
        "month_label": feed.generated_at_local.strftime("%B"),
        "month_path": f"/archivio/{y}/{m}/",
        "day": int(d),
        "day_label": day_label,
        "teaser_cards": teaser_cards,
        "snapshot_path": f"/archivio/{y}/{m}/{d}/",
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Archivio", "url": canonical("/archivio/")},
            {"name": y, "url": canonical(f"/archivio/{y}/")},
            {"name": m, "url": canonical(f"/archivio/{y}/{m}/")},
            {"name": d, "url": canonical(f"/archivio/{y}/{m}/{d}/hub/")},
        ],
    }
    html = renderer.render_day_hub(ctx)
    target_dir = site_dir / "archivio" / y / m / d / "hub"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text(html, encoding="utf-8")

def _ssg_articles(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    y, m, d = day_iso.split("-")
    for item in feed.items:
        if item.importance < 4:
            continue
        slug = item_slugs[item.id]
        article_url = canonical(f"/archivio/{y}/{m}/{d}/{slug}/")
        ctx = {
            "page_title": f"{item.title_it} — Osservatorio SEO",
            "page_description": item.summary_it[:155],
            "canonical_url": article_url,
            "active_nav": "archive",
            "noindex": not allow_indexing,
            "og_type": "article",
            "item": item.model_dump(mode="json"),
            "stars": _stars(item.importance),
            "absolute_date": _absolute_date(item.published_at),
            "day_label": feed.generated_at_local.strftime("%A %d %B %Y"),
            "day_path": f"/archivio/{y}/{m}/{d}/",
            "category_path": make_category_path(item.category),
            "category_label": _CATEGORY_LABELS.get(item.category, item.category),
            "published_iso": item.published_at.isoformat(),
            "article_url": article_url,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/"), "site_path": "/"},
                {"name": "Archivio", "url": canonical("/archivio/"), "site_path": "/archivio/"},
                {"name": y, "url": canonical(f"/archivio/{y}/"), "site_path": f"/archivio/{y}/"},
                {"name": m, "url": canonical(f"/archivio/{y}/{m}/"), "site_path": f"/archivio/{y}/{m}/"},
                {"name": d, "url": canonical(f"/archivio/{y}/{m}/{d}/"), "site_path": f"/archivio/{y}/{m}/{d}/"},
                {"name": item.title_it, "url": article_url, "site_path": ""},
            ],
        }
        html = renderer.render_article(ctx)
        target_dir = site_dir / "archivio" / y / m / d / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(html, encoding="utf-8")
```

- [ ] **Step 2: Update test to cover new outputs**

Append to `tests/test_publisher.py`:

```python
def test_publish_ssg_writes_snapshot_and_day_hub_and_articles(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    snapshot = site_dir / "archivio" / y / m / d / "index.html"
    assert snapshot.exists()
    assert f"TOP 10 DEL GIORNO {d} {m} {y}" in snapshot.read_text()

    day_hub = site_dir / "archivio" / y / m / d / "hub" / "index.html"
    assert day_hub.exists()

    # mk_feed() ha 1 item con importance=3, quindi NO articolo
    articles = list((site_dir / "archivio" / y / m / d).rglob("index.html"))
    assert len(articles) == 2  # snapshot + day_hub, niente articolo (importance<4)


def test_publish_ssg_writes_article_for_high_importance(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    feed = mk_feed()
    # bump importance to 5 to trigger article page
    feed.items[0].importance = 5
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)

    day_iso = feed.generated_at_local.strftime("%Y-%m-%d")
    y, m, d = day_iso.split("-")
    # Ogni articolo ha un slug; ce n'è 1
    articles = [
        p for p in (site_dir / "archivio" / y / m / d).iterdir()
        if p.is_dir() and p.name != "hub"
    ]
    assert len(articles) == 1
    article_html = (articles[0] / "index.html").read_text()
    assert '"@type": "NewsArticle"' in article_html
    assert '"@type": "BreadcrumbList"' in article_html
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/test_publisher.py -v
```

Expected: 8 passed.

- [ ] **Step 4: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): SSG output for snapshot, day hub, and article pages (importance>=4)"
```

---

## Task 15: Publisher — archive/year/month hubs + category/tag hubs

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Modify: `tests/test_publisher.py`

- [ ] **Step 1: Add archive index, year, month hubs that iterate over `data/archive/*.json`**

Aggiungi al publisher:

```python
def _ssg_archive_hubs(self, renderer, site_dir, allow_indexing):
    """Genera archivio/index.html, archivio/YYYY/, archivio/YYYY/MM/ leggendo
    l'elenco dei file in ``self._archive_dir``."""
    import json

    # Scanna i file dated
    dated_files = sorted(
        (p for p in self._archive_dir.glob("20*.json")),
        key=lambda p: p.stem,
        reverse=True,
    )
    if not dated_files:
        return

    # Raggruppa per anno → mese → giorno
    from collections import defaultdict
    by_year: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for p in dated_files:
        y, m, d = p.stem.split("-")
        by_year[int(y)][int(m)].append(d)

    # Archive index
    years_ctx = [
        {"year": y, "path": f"/archivio/{y:04d}/", "count": sum(len(v) for v in months.values())}
        for y, months in sorted(by_year.items(), reverse=True)
    ]
    idx_ctx = {
        "page_title": "Archivio — Osservatorio SEO",
        "page_description": "Tutte le giornate archiviate di Osservatorio SEO",
        "canonical_url": canonical("/archivio/"),
        "active_nav": "archive",
        "noindex": not allow_indexing,
        "meta_line": f"{len(dated_files)} LOG FILES",
        "years": years_ctx,
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Archivio", "url": canonical("/archivio/")},
        ],
    }
    (site_dir / "archivio").mkdir(parents=True, exist_ok=True)
    (site_dir / "archivio" / "index.html").write_text(
        renderer.render_archive_index(idx_ctx), encoding="utf-8"
    )

    MONTH_LABELS = {
        1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile", 5: "Maggio", 6: "Giugno",
        7: "Luglio", 8: "Agosto", 9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
    }

    # Year hubs
    for year, months in by_year.items():
        y_ctx = {
            "page_title": f"Archivio {year} — Osservatorio SEO",
            "page_description": f"Archivio di tutte le notizie del {year}",
            "canonical_url": canonical(f"/archivio/{year:04d}/"),
            "active_nav": "archive",
            "noindex": not allow_indexing,
            "year": year,
            "months": [
                {
                    "label": MONTH_LABELS[m],
                    "path": f"/archivio/{year:04d}/{m:02d}/",
                    "count": len(days),
                }
                for m, days in sorted(months.items(), reverse=True)
            ],
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": "Archivio", "url": canonical("/archivio/")},
                {"name": str(year), "url": canonical(f"/archivio/{year:04d}/")},
            ],
        }
        y_dir = site_dir / "archivio" / f"{year:04d}"
        y_dir.mkdir(parents=True, exist_ok=True)
        (y_dir / "index.html").write_text(renderer.render_year_hub(y_ctx), encoding="utf-8")

        # Month hubs
        for month, days in months.items():
            m_ctx = {
                "page_title": f"Archivio {MONTH_LABELS[month]} {year} — Osservatorio SEO",
                "page_description": f"Notizie SEO e AI di {MONTH_LABELS[month]} {year}",
                "canonical_url": canonical(f"/archivio/{year:04d}/{month:02d}/"),
                "active_nav": "archive",
                "noindex": not allow_indexing,
                "year": year,
                "year_path": f"/archivio/{year:04d}/",
                "month_label": MONTH_LABELS[month],
                "days": [
                    {
                        "date": f"{year:04d}-{month:02d}-{day}",
                        "path": f"/archivio/{year:04d}/{month:02d}/{day}/",
                        "label": f"{int(day)} {MONTH_LABELS[month]}",
                        "count": "?",  # known solo se leggiamo il JSON
                    }
                    for day in sorted(days, reverse=True)
                ],
                "breadcrumbs": [
                    {"name": "Home", "url": canonical("/")},
                    {"name": "Archivio", "url": canonical("/archivio/")},
                    {"name": str(year), "url": canonical(f"/archivio/{year:04d}/")},
                    {"name": MONTH_LABELS[month], "url": canonical(f"/archivio/{year:04d}/{month:02d}/")},
                ],
            }
            m_dir = y_dir / f"{month:02d}"
            m_dir.mkdir(parents=True, exist_ok=True)
            (m_dir / "index.html").write_text(renderer.render_month_hub(m_ctx), encoding="utf-8")


def _ssg_category_tag_hubs(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    """Genera /categoria/<cat>/index.html e /tag/<tag>/index.html per il feed
    corrente."""
    from collections import defaultdict

    y, m, d = day_iso.split("-")
    items_by_cat: dict[str, list[Item]] = defaultdict(list)
    items_by_tag: dict[str, list[Item]] = defaultdict(list)
    for item in feed.items:
        items_by_cat[item.category].append(item)
        for tag in item.tags:
            items_by_tag[tag].append(item)

    def build_teaser(item: Item) -> str:
        article_url = (
            f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/"
            if item.importance >= 4
            else item.url
        )
        return renderer.render_raw(
            "partials/_card_article_teaser.html.jinja",
            {
                "item": item.model_dump(mode="json"),
                "short_id": _short_id(item),
                "relative_date": _relative_date(item.published_at),
                "absolute_date": _absolute_date(item.published_at),
                "stars": _stars(item.importance),
                "article_url": article_url,
            },
        )

    for cat_id, items in items_by_cat.items():
        cards = [build_teaser(i) for i in items]
        ctx = {
            "page_title": f"{_CATEGORY_LABELS.get(cat_id, cat_id)} — Osservatorio SEO",
            "page_description": f"Notizie SEO e AI della categoria {cat_id}",
            "canonical_url": canonical(make_category_path(cat_id)),
            "active_nav": "today",
            "noindex": not allow_indexing,
            "category_label": _CATEGORY_LABELS.get(cat_id, cat_id),
            "meta_line": f"{len(items)} ARTICOLI IN CATEGORIA",
            "teaser_cards": cards,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": _CATEGORY_LABELS.get(cat_id, cat_id), "url": canonical(make_category_path(cat_id))},
            ],
        }
        target_dir = site_dir / "categoria" / cat_id.replace("_", "-")
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(renderer.render_category_hub(ctx), encoding="utf-8")

    # Tag hubs — solo tag con >= 2 articoli (evita rumore)
    for tag, items in items_by_tag.items():
        if len(items) < 2:
            continue
        cards = [build_teaser(i) for i in items]
        ctx = {
            "page_title": f"#{tag} — Osservatorio SEO",
            "page_description": f"Articoli taggati {tag}",
            "canonical_url": canonical(make_tag_path(tag)),
            "active_nav": "today",
            "noindex": not allow_indexing,
            "tag_label": tag,
            "meta_line": f"{len(items)} ARTICOLI",
            "teaser_cards": cards,
            "breadcrumbs": [
                {"name": "Home", "url": canonical("/")},
                {"name": f"#{tag}", "url": canonical(make_tag_path(tag))},
            ],
        }
        target_dir = site_dir / "tag" / tag.replace("_", "-")
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "index.html").write_text(renderer.render_tag_hub(ctx), encoding="utf-8")
```

Invoca i due metodi alla fine di `publish_ssg`:

```python
    self._ssg_archive_hubs(renderer, site_dir, allow_indexing)
    self._ssg_category_tag_hubs(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

- [ ] **Step 2: Test**

```python
def test_publish_ssg_writes_archive_hubs(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    archive_dir = tmp_path / "data" / "archive"
    archive_dir.mkdir(parents=True)
    # Pre-seed con 2 file
    (archive_dir / "2026-04-10.json").write_text("{}")
    (archive_dir / "2026-04-11.json").write_text("{}")

    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)

    assert (site_dir / "archivio" / "index.html").exists()
    assert (site_dir / "archivio" / "2026" / "index.html").exists()
    assert (site_dir / "archivio" / "2026" / "04" / "index.html").exists()


def test_publish_ssg_writes_category_hub(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)
    cat_html = site_dir / "categoria" / "google-updates" / "index.html"
    assert cat_html.exists()
    assert "Google Updates" in cat_html.read_text()
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/test_publisher.py -v
```

Expected: 10 passed.

- [ ] **Step 4: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): SSG archive/year/month + category/tag hub pages"
```

---

## Task 16: Publisher — docs + about + sitemap + feed.xml + robots.txt

**Files:**
- Modify: `src/osservatorio_seo/publisher.py`
- Modify: `tests/test_publisher.py`

- [ ] **Step 1: Add docs/about/seo-assets helpers**

In `publisher.py`:

```python
def _ssg_docs_and_about(self, renderer, sources, doc_pages, site_dir, allow_indexing):
    from collections import defaultdict
    from urllib.parse import urlparse

    def hostname(url: str) -> str:
        try:
            return urlparse(url).hostname or url
        except Exception:
            return url

    TYPE_LABELS = {
        "official": "UFFICIALE",
        "media": "MEDIA",
        "independent": "INDIPENDENTE",
        "tool_vendor": "TOOL VENDOR",
        "social": "SOCIAL",
    }

    enriched = []
    for s in sources:
        enriched.append({
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "authority": s.authority,
            "fetcher": s.fetcher,
            "url": s.feed_url or s.target_url or "",
            "hostname": hostname(s.feed_url or s.target_url or ""),
        })
    by_type: dict[str, list] = defaultdict(list)
    for s in sorted(enriched, key=lambda x: -x["authority"]):
        by_type[TYPE_LABELS.get(s["type"], s["type"].upper())].append(s)

    docs_ctx = {
        "page_title": "Docs — Osservatorio SEO",
        "page_description": "Come funziona Osservatorio SEO: fonti, pipeline, stack.",
        "canonical_url": canonical("/docs/"),
        "active_nav": "docs",
        "noindex": not allow_indexing,
        "sources": enriched,
        "sources_by_type": dict(by_type),
        "doc_watcher_pages": [
            {
                "id": p.id,
                "name": p.name,
                "url": p.url,
                "type": p.type,
                "importance": p.importance,
                "hostname": hostname(p.url),
            }
            for p in sorted(doc_pages, key=lambda p: -p.importance)
        ],
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Docs", "url": canonical("/docs/")},
        ],
    }
    (site_dir / "docs").mkdir(parents=True, exist_ok=True)
    (site_dir / "docs" / "index.html").write_text(renderer.render_docs(docs_ctx), encoding="utf-8")

    about_ctx = {
        "page_title": "Chi siamo — Osservatorio SEO",
        "page_description": "Chi c'è dietro Osservatorio SEO",
        "canonical_url": canonical("/about/"),
        "active_nav": "",
        "noindex": not allow_indexing,
        "source_count": len(sources),
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Chi siamo", "url": canonical("/about/")},
        ],
    }
    (site_dir / "about").mkdir(parents=True, exist_ok=True)
    (site_dir / "about" / "index.html").write_text(renderer.render_about(about_ctx), encoding="utf-8")


def _ssg_seo_assets(self, renderer, feed, site_dir, allow_indexing, item_slugs, day_iso):
    """Genera sitemap.xml, feed.xml (Atom), robots.txt."""
    y, m, d = day_iso.split("-")
    today = day_iso

    urls: list[dict] = [
        {"loc": canonical("/"), "lastmod": today, "priority": "1.0", "changefreq": "daily"},
        {"loc": canonical("/archivio/"), "lastmod": today, "priority": "0.7", "changefreq": "daily"},
        {"loc": canonical("/docs/"), "lastmod": today, "priority": "0.3", "changefreq": "monthly"},
        {"loc": canonical("/about/"), "lastmod": today, "priority": "0.3", "changefreq": "monthly"},
    ]
    # Category + tag urls
    categories_seen = {i.category for i in feed.items}
    for cat in categories_seen:
        urls.append({"loc": canonical(make_category_path(cat)), "lastmod": today, "priority": "0.6"})
    tags_seen = set()
    for item in feed.items:
        for t in item.tags:
            tags_seen.add(t)
    for t in tags_seen:
        urls.append({"loc": canonical(make_tag_path(t)), "lastmod": today, "priority": "0.4"})

    # Snapshot corrente + articoli importance>=4
    urls.append({"loc": canonical(f"/archivio/{y}/{m}/{d}/"), "lastmod": today, "priority": "0.8"})
    for item in feed.items:
        if item.importance < 4:
            continue
        slug = item_slugs.get(item.id, "untitled")
        urls.append({
            "loc": canonical(f"/archivio/{y}/{m}/{d}/{slug}/"),
            "lastmod": today,
            "priority": "0.7",
        })

    (site_dir / "sitemap.xml").write_text(
        renderer.render_sitemap({"urls": urls}), encoding="utf-8"
    )

    # Atom feed
    entries = [
        {
            "title": item.title_it,
            "url": canonical(
                f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/"
                if item.importance >= 4
                else item.url
            ),
            "updated": item.fetched_at.isoformat(),
            "published": item.published_at.isoformat(),
            "summary": item.summary_it,
            "tags": list(item.tags or []),
        }
        for item in feed.items[:50]
    ]
    (site_dir / "feed.xml").write_text(
        renderer.render_feed_xml({
            "site_url": "https://osservatorioseo.pages.dev",
            "updated": feed.generated_at.isoformat(),
            "entries": entries,
        }),
        encoding="utf-8",
    )

    (site_dir / "robots.txt").write_text(
        renderer.render_robots_txt({
            "allow_indexing": allow_indexing,
            "site_url": "https://osservatorioseo.pages.dev",
        }),
        encoding="utf-8",
    )
```

Invoca entrambi alla fine di `publish_ssg`:

```python
    self._ssg_docs_and_about(renderer, sources, doc_pages, site_dir, allow_indexing)
    self._ssg_seo_assets(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

- [ ] **Step 2: Test**

```python
def test_publish_ssg_writes_docs_about_sitemap_feed_robots(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=tmp_path / "data" / "archive",
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)
    assert (site_dir / "docs" / "index.html").exists()
    assert (site_dir / "about" / "index.html").exists()
    sitemap = site_dir / "sitemap.xml"
    assert sitemap.exists()
    assert "<loc>" in sitemap.read_text()
    feed_xml = site_dir / "feed.xml"
    assert feed_xml.exists()
    assert "<feed xmlns" in feed_xml.read_text()
    robots = site_dir / "robots.txt"
    assert robots.exists()
    # Con allow_indexing=False (default), robots deve bloccare
    assert "Disallow: /" in robots.read_text()
    assert "Sitemap:" in robots.read_text()
```

- [ ] **Step 3: Run tests**

```bash
.venv/bin/pytest tests/test_publisher.py -v
```

Expected: 11 passed.

- [ ] **Step 4: Commit**

```bash
git add src/osservatorio_seo/publisher.py tests/test_publisher.py
git commit -m "feat(publisher): docs, about, sitemap.xml, feed.xml (Atom), robots.txt"
```

---

## Task 16b: TOP WEEK page (rolling 7-day top 10)

**Files:**
- Create: `templates/pages/top_week.html.jinja`
- Modify: `src/osservatorio_seo/renderer.py` (add `render_top_week`)
- Modify: `src/osservatorio_seo/publisher.py` (add `_ssg_top_week` helper invoked from `publish_ssg`)
- Modify: `templates/partials/_header.html.jinja` (add `TOP WEEK` nav link)
- Modify: `tests/test_renderer.py`
- Modify: `tests/test_publisher.py`

**Rationale:** Con il nuovo filtro 24h la homepage mostra solo articoli del giorno. La pagina `/top-settimana/` aggrega gli ultimi 7 archivi giornalieri per produrre un "Best of the week" che viene aggiornato ogni run. È una landing page di richiamo SEO (topical authority) + utente (chi non visita ogni giorno vede comunque il meglio della settimana).

**Algoritmo:**
1. Leggi gli ultimi 7 file `data/archive/YYYY-MM-DD.json` (esclude il feed corrente se già presente come archive)
2. Unisci tutti gli items
3. Dedup per URL (stesso URL in più giorni tiene la prima apparizione)
4. Applica `Ranker.rank()` standard su items combinati
5. Prendi i top 10
6. Render in una pagina identica alla homepage top10, ma con `h1 = "> TOP 10 DELLA SETTIMANA"` e meta `"rolling 7 days"`

- [ ] **Step 1: Create `templates/pages/top_week.html.jinja`**

```html
{% extends "layout.html.jinja" %}

{% block extra_head %}
{% include "partials/_jsonld_breadcrumb.html.jinja" %}
{% endblock %}

{% block content %}
<section class="mb-10">
  <div class="md:hidden text-primary-container font-bold text-2xl tracking-tight uppercase terminal-glow mb-4">TOP SETTIMANA</div>
  <div class="flex items-center gap-2 text-outline">
    <span class="text-primary-container">●</span>
    <span class="text-[10px] tracking-widest uppercase break-words">{{ meta_line }}</span>
  </div>
</section>

<section class="mb-16" id="top10-section">
  <div class="flex items-center gap-4 mb-8">
    <h1 class="text-2xl font-bold tracking-tight uppercase">&gt; TOP 10 DELLA SETTIMANA</h1>
    <div class="flex-grow h-px bg-outline-variant border-dashed border-t"></div>
  </div>
  <p class="text-[10px] text-outline uppercase font-mono mb-6">ROLLING WINDOW // ULTIMI 7 GIORNI // RANKED BY IMPORTANCE + AUTHORITY</p>
  <div id="top10" class="grid grid-cols-1 gap-px bg-outline-variant border border-outline-variant">
  {% for card in top10_cards %}
  {{ card | safe }}
  {% endfor %}
  </div>
</section>

<section class="mb-12">
  <p class="text-xs text-outline font-mono uppercase">
    Vedi anche:
    <a href="/" class="text-primary-container hover:underline">oggi</a> ·
    <a href="/archivio/" class="text-primary-container hover:underline">archivio completo</a>
  </p>
</section>
{% endblock %}
```

- [ ] **Step 2: Add `render_top_week` to renderer**

Edit `src/osservatorio_seo/renderer.py`, aggiungi il metodo:

```python
def render_top_week(self, context: dict) -> str:
    return self.render_raw("pages/top_week.html.jinja", context)
```

- [ ] **Step 3: Add TOP WEEK nav link to header partial**

Edit `templates/partials/_header.html.jinja`, sostituisci il blocco `<nav>` con:

```html
<nav class="flex gap-4 sm:gap-6 items-center text-xs sm:text-sm">
  {% set active = active_nav | default('') %}
  <a class="{% if active == 'today' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/">TODAY</a>
  <a class="{% if active == 'top-week' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/top-settimana/">TOP_WEEK</a>
  <a class="{% if active == 'archive' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/archivio/">ARCHIVIO</a>
  <a class="{% if active == 'docs' %}text-[#00f63e] font-bold border-b-2 border-[#00f63e] pb-1{% else %}text-[#919191] hover:text-white transition-colors duration-150{% endif %}" href="/docs/">DOCS</a>
</nav>
```

- [ ] **Step 4: Add `_ssg_top_week` method to Publisher**

In `src/osservatorio_seo/publisher.py`, aggiungi il metodo che legge archivi recenti, dedup, rank, render:

```python
def _ssg_top_week(
    self,
    renderer: HtmlRenderer,
    current_feed: Feed,
    site_dir: Path,
    allow_indexing: bool,
    item_slugs: dict[str, str],
    day_iso: str,
) -> None:
    """Render /top-settimana/ = top 10 dei migliori articoli degli ultimi 7
    giorni, rolling window. Legge l'archivio per unire ~7 giorni di feed,
    dedup per URL, ri-ranka con Ranker standard, prende top10.

    ``item_slugs`` e ``day_iso`` si riferiscono al feed corrente: servono
    solo per generare i link agli articoli di oggi.
    """
    import json
    from datetime import UTC, datetime, timedelta

    from osservatorio_seo.ranker import Ranker

    # Raccogli ~7 giorni di feed (oggi incluso tramite current_feed, il
    # resto letto dai file archive)
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)
    combined_items: list[Item] = []
    seen_urls: set[str] = set()

    # Items del feed corrente (più freschi, priorità su dedup)
    for item in current_feed.items:
        if item.url not in seen_urls:
            combined_items.append(item)
            seen_urls.add(item.url)

    # Items da archivio (esclude il file del giorno corrente che coincide
    # con current_feed)
    archive_files = sorted(
        [
            p
            for p in self._archive_dir.glob("20*.json")
            if p.stem != day_iso
        ],
        reverse=True,
    )
    for path in archive_files[:7]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            feed = Feed.model_validate(data)
        except Exception:
            continue
        if feed.generated_at < seven_days_ago:
            continue
        for item in feed.items:
            if item.url in seen_urls:
                continue
            combined_items.append(item)
            seen_urls.add(item.url)

    if not combined_items:
        return

    # Ranka con Ranker standard
    ranker = Ranker()
    ranked = ranker.rank(combined_items)
    items_by_id = {i.id: i for i in combined_items}

    # Costruisci context card per i top10
    top10_cards = []
    for idx, item_id in enumerate(ranked.top10, start=1):
        item = items_by_id.get(item_id)
        if not item:
            continue

        # URL articolo: se importance>=4 E proviene dal feed corrente → link
        # alla pagina SSG di oggi; altrimenti fallback al URL originale
        is_today = item in current_feed.items
        if is_today and item.importance >= 4:
            y, m, d = day_iso.split("-")
            article_url = f"/archivio/{y}/{m}/{d}/{item_slugs.get(item.id, 'untitled')}/"
        else:
            article_url = item.url

        card_ctx = {
            "item": item.model_dump(mode="json"),
            "search_blob": _build_search_blob(item),
            "short_id": _short_id(item),
            "relative_date": _relative_date(item.published_at),
            "absolute_date": _absolute_date(item.published_at),
            "stars": _stars(item.importance),
            "tags": item.tags,
            "article_url": article_url,
            "order": idx,
        }
        top10_cards.append(
            renderer.render_raw("partials/_card_top10.html.jinja", card_ctx)
        )

    meta_line = (
        f"SYSTEM STATUS: OPTIMAL // ROLLING 7D // "
        f"{len(combined_items)} ARTICOLI ANALIZZATI // TOP 10"
    )

    ctx = {
        "page_title": "Top della Settimana — Osservatorio SEO",
        "page_description": (
            "Le 10 notizie SEO e AI più rilevanti degli ultimi 7 giorni, "
            "aggiornate ogni mattina."
        ),
        "canonical_url": canonical("/top-settimana/"),
        "active_nav": "top-week",
        "noindex": not allow_indexing,
        "meta_line": meta_line,
        "top10_cards": top10_cards,
        "breadcrumbs": [
            {"name": "Home", "url": canonical("/")},
            {"name": "Top Settimana", "url": canonical("/top-settimana/")},
        ],
    }
    html = renderer.render_top_week(ctx)
    target_dir = site_dir / "top-settimana"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "index.html").write_text(html, encoding="utf-8")
```

- [ ] **Step 5: Call `_ssg_top_week` from `publish_ssg`**

In `publish_ssg`, dopo `_ssg_seo_assets(...)`:

```python
    self._ssg_top_week(renderer, feed, site_dir, allow_indexing, item_slugs, day_iso)
```

- [ ] **Step 6: Test renderer**

Append to `tests/test_renderer.py`:

```python
def test_render_top_week() -> None:
    renderer = HtmlRenderer(templates_dir=Path("templates"))
    html = renderer.render_top_week(
        {
            "page_title": "Top Settimana",
            "page_description": "d",
            "canonical_url": "https://osservatorioseo.pages.dev/top-settimana/",
            "active_nav": "top-week",
            "noindex": True,
            "meta_line": "ROLLING 7D // 100 ARTICOLI",
            "top10_cards": ["<article class='card'>Week1</article>"],
            "breadcrumbs": [{"name": "Home", "url": "/"}],
        }
    )
    assert "TOP 10 DELLA SETTIMANA" in html
    assert "Week1" in html
    assert "ROLLING 7D" in html
```

- [ ] **Step 7: Test publisher**

Append to `tests/test_publisher.py`:

```python
def test_publish_ssg_writes_top_week(tmp_path: Path) -> None:
    import json as _json

    site_dir = tmp_path / "site"
    archive_dir = tmp_path / "data" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    # Seed archive con 2 giorni di feed finti (stessa struttura di mk_feed)
    for d in ("2026-04-09", "2026-04-10"):
        feed = mk_feed()
        feed.run_id = f"{d}-0700"
        feed.generated_at = datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), 5, 0, tzinfo=UTC)
        feed.generated_at_local = feed.generated_at
        (archive_dir / f"{d}.json").write_text(
            feed.model_dump_json(indent=2), encoding="utf-8"
        )

    pub = Publisher(
        data_dir=tmp_path / "data",
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )
    pub.publish_ssg(mk_feed(), [], [], templates_dir=Path("templates"), site_dir=site_dir)

    top_week = site_dir / "top-settimana" / "index.html"
    assert top_week.exists()
    content = top_week.read_text()
    assert "TOP 10 DELLA SETTIMANA" in content
```

- [ ] **Step 8: Run tests**

```bash
.venv/bin/pytest tests/test_renderer.py tests/test_publisher.py -v
```

Expected: tutti verdi (publisher +1, renderer +1).

- [ ] **Step 9: Commit**

```bash
git add templates/pages/top_week.html.jinja templates/partials/_header.html.jinja src/osservatorio_seo/renderer.py src/osservatorio_seo/publisher.py tests/test_renderer.py tests/test_publisher.py
git commit -m "feat(ssg): /top-settimana/ page with rolling 7-day top 10"
```

---

## Task 17: Frontend app.js — hydration-only rewrite

**Files:**
- Modify: `site/app.js`
- Delete: `site/archive.js` (logica spostata nelle pagine SSG)
- Delete: `site/docs.js` (idem)
- Delete: `site/index.html`, `site/archive.html`, `site/docs.html` (generati da Jinja)

- [ ] **Step 1: Rewrite `site/app.js` as hydration-only**

```javascript
// Hydration-only. Il markup è già pre-renderizzato server-side. Qui attiviamo
// SOLO: search filter locale, toggle cross-archive, card collapse mobile,
// redirect compat ?date=YYYY-MM-DD → /archivio/YYYY/MM/DD/, e refresh client-
// side delle date relative (es "2 ore fa" → "8 ore fa") ricalcolate dal
// datetime attribute all'atto del load.

const ARCHIVE_SEARCH_DAYS = 7;
let archiveItemsCache = null;

(function init() {
  redirectLegacyDateParam();
  refreshRelativeDates();
  setupSearch();
  setupCardCollapse();
  preloadArchiveIfQueryParam();
})();

function redirectLegacyDateParam() {
  const params = new URLSearchParams(window.location.search);
  const date = params.get("date");
  if (!date) return;
  const m = date.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return;
  window.location.replace(`/archivio/${m[1]}/${m[2]}/${m[3]}/`);
}

function refreshRelativeDates() {
  document.querySelectorAll(".card time[datetime]").forEach((el) => {
    const iso = el.getAttribute("datetime");
    if (!iso) return;
    el.textContent = formatRelative(iso);
  });
}

function formatRelative(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diff = now - d;
  const min = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (diff < 0) return d.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
  if (min < 1) return "adesso";
  if (min < 60) return `${min} min fa`;
  if (h < 24) return `${h} h fa`;
  if (days < 2) return "ieri";
  if (days < 7) return `${days} giorni fa`;
  return d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });
}

function setupSearch() {
  const input = document.getElementById("search");
  const toggle = document.getElementById("search-archive-toggle");
  if (!input) return;

  const runSearch = async () => {
    const raw = input.value.trim().toLowerCase();
    const q = raw.replace(/[_\-/]+/g, " ");

    document.querySelectorAll("#top10-section .card, #categories-section .card").forEach((card) => {
      const blob = card.dataset.searchBlob || "";
      card.style.display = !q || blob.includes(q) ? "" : "none";
    });

    if (toggle && toggle.checked && q) {
      await showArchiveResults(q);
    } else {
      hideArchiveResults();
    }
  };

  input.addEventListener("input", runSearch);
  if (toggle) toggle.addEventListener("change", runSearch);
}

async function showArchiveResults(query) {
  const section = document.getElementById("archive-results");
  const meta = document.getElementById("archive-results-meta");
  const list = document.getElementById("archive-results-list");
  if (!section) return;
  section.hidden = false;
  meta.textContent = "Caricamento archivio…";

  try {
    if (archiveItemsCache === null) {
      archiveItemsCache = await loadArchiveItems(ARCHIVE_SEARCH_DAYS);
    }
  } catch (e) {
    meta.textContent = "Errore caricamento archivio: " + e.message;
    list.innerHTML = "";
    return;
  }

  const matches = archiveItemsCache.filter((entry) => buildSearchBlob(entry.item).includes(query));
  if (matches.length === 0) {
    meta.textContent = `Nessun risultato negli ultimi ${ARCHIVE_SEARCH_DAYS} giorni.`;
    list.innerHTML = "";
    return;
  }
  meta.textContent = `${matches.length} RESULTS IN LAST ${ARCHIVE_SEARCH_DAYS} DAYS`;
  // Raggruppa per data e genera HTML leggero (no ri-rendering card server-side)
  const byDate = {};
  for (const { date, item } of matches) {
    (byDate[date] = byDate[date] || []).push(item);
  }
  list.innerHTML = Object.entries(byDate)
    .sort(([a], [b]) => (a < b ? 1 : -1))
    .map(([date, items]) => {
      const cards = items.map((i) => renderArchiveSearchResult(i, date)).join("");
      return `<div class="flex flex-col gap-4">
        <div class="flex items-center justify-between border-b border-outline-variant pb-2">
          <h3 class="text-outline font-bold uppercase tracking-widest text-xs">[ ARCHIVE // ${escape(date)} ]</h3>
          <span class="text-outline text-[10px] font-mono">${items.length} HITS</span>
        </div>
        <div class="flex flex-col gap-4">${cards}</div>
      </div>`;
    })
    .join("");
}

function renderArchiveSearchResult(item, date) {
  const [y, m, d] = date.split("-");
  const slug = item.__slug || "untitled";
  const path = item.importance >= 4 ? `/archivio/${y}/${m}/${d}/${slug}/` : item.url;
  const stars = "★".repeat(item.importance) + "☆".repeat(5 - item.importance);
  return `<a href="${escape(path)}" class="block p-4 border-l-2 border-outline-variant bg-surface-container-lowest hover:bg-surface-container transition-colors">
    <h4 class="text-sm font-bold text-white hover:text-primary-container">${escape(item.title_it)}</h4>
    <p class="text-[10px] text-outline mt-1 font-mono uppercase">${escape(item.source.name)} · <span class="text-[#f5a623]">${stars}</span></p>
  </a>`;
}

function hideArchiveResults() {
  const section = document.getElementById("archive-results");
  if (!section) return;
  section.hidden = true;
  const list = document.getElementById("archive-results-list");
  if (list) list.innerHTML = "";
}

async function loadArchiveItems(days) {
  const idxResp = await fetch("/data/archive/index.json", { cache: "no-cache" });
  if (!idxResp.ok) throw new Error("index.json HTTP " + idxResp.status);
  const entries = await idxResp.json();
  const slice = entries.slice(0, days);

  const feeds = await Promise.all(
    slice.map(async (e) => {
      try {
        const r = await fetch(`/data/archive/${encodeURIComponent(e.file)}`, { cache: "no-cache" });
        if (!r.ok) return null;
        return { date: e.date, feed: await r.json() };
      } catch {
        return null;
      }
    }),
  );

  const items = [];
  for (const f of feeds) {
    if (!f || !f.feed || !Array.isArray(f.feed.items)) continue;
    for (const item of f.feed.items) {
      items.push({ date: f.date, item });
    }
  }
  return items;
}

function buildSearchBlob(item) {
  const parts = [
    item.title_it || "",
    item.title_original || "",
    item.summary_it || "",
    (item.tags || []).join(" "),
    item.source?.name || "",
    item.source?.id || "",
    item.category || "",
    item.url || "",
  ];
  return parts.join(" ").replace(/[_\-/]+/g, " ").toLowerCase();
}

function setupCardCollapse() {
  const mobileMql = window.matchMedia("(max-width: 767px)");
  document.addEventListener("click", (e) => {
    if (!mobileMql.matches) return;
    if (e.target.closest("a")) return;
    const card = e.target.closest(".card");
    if (!card) return;
    card.classList.toggle("expanded");
  });
}

function preloadArchiveIfQueryParam() {
  const params = new URLSearchParams(window.location.search);
  const q = params.get("q");
  const cross = params.get("cross");
  if (!q) return;
  const input = document.getElementById("search");
  if (!input) return;
  input.value = q;
  if (cross) {
    const toggle = document.getElementById("search-archive-toggle");
    if (toggle) toggle.checked = true;
  }
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.focus();
}

function escape(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
```

- [ ] **Step 2: Remove archive.js and docs.js**

```bash
rm site/archive.js site/docs.js site/nav-search.js
```

- [ ] **Step 3: Remove old static HTML files that will be regenerated by publisher**

```bash
rm site/index.html site/archive.html site/docs.html
```

**WARNING**: questi file saranno **rigenerati** al prossimo `publish_ssg`. Non committare il delete da solo — prima esegui la pipeline (vedi Task 19) o aggiorna `.gitignore` per ignorare `site/*.html` generati.

Per sicurezza, non fare il delete ora. Lo script `rebuild_seo_html.py` (Task 18) rigenererà tutto. Oppure, per questo step, **sposta** i file in `site/_legacy/` e committa:

```bash
mkdir -p site/_legacy
git mv site/index.html site/_legacy/index.html
git mv site/archive.html site/_legacy/archive.html
git mv site/docs.html site/_legacy/docs.html
git rm site/archive.js site/docs.js site/nav-search.js
```

- [ ] **Step 4: Verify ruff/eslint on app.js non applicabile (JS non ha linting in questo repo)**

Skip — JS non è nella pipeline lint.

- [ ] **Step 5: Commit**

```bash
git add site/app.js site/_legacy/
git commit -m "feat(frontend): hydration-only app.js + legacy HTML parked"
```

---

## Task 18: Rebuild historical HTML script

**Files:**
- Create: `scripts/rebuild_seo_html.py`

- [ ] **Step 1: Create `scripts/rebuild_seo_html.py`**

```python
#!/usr/bin/env python3
"""Rigenera tutti gli HTML SSG a partire dai JSON già presenti in
``data/archive/*.json``.

Usage:
    .venv/bin/python scripts/rebuild_seo_html.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from osservatorio_seo.config import load_doc_watcher, load_sources
from osservatorio_seo.models import Feed
from osservatorio_seo.publisher import Publisher


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    site_dir = repo_root / "site"
    archive_dir = data_dir / "archive"
    templates_dir = repo_root / "templates"

    sources = load_sources(repo_root / "config" / "sources.yml")
    doc_pages = load_doc_watcher(repo_root / "config" / "doc_watcher.yml")

    pub = Publisher(
        data_dir=data_dir,
        archive_dir=archive_dir,
        site_data_dir=site_dir / "data",
    )

    # Scorri ogni JSON archivio e rigenera SSG
    for json_path in sorted(archive_dir.glob("20*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        feed = Feed.model_validate(data)
        print(f"Rendering {json_path.stem}…")
        pub.publish_ssg(
            feed,
            sources,
            doc_pages,
            templates_dir=templates_dir,
            site_dir=site_dir,
            allow_indexing=False,
        )

    # Esegui un ultimo render per feed corrente
    current_feed_path = data_dir / "feed.json"
    if current_feed_path.exists():
        data = json.loads(current_feed_path.read_text(encoding="utf-8"))
        feed = Feed.model_validate(data)
        print(f"Rendering current feed ({feed.run_id})…")
        pub.publish_ssg(
            feed,
            sources,
            doc_pages,
            templates_dir=templates_dir,
            site_dir=site_dir,
            allow_indexing=False,
        )

    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable and run**

```bash
chmod +x scripts/rebuild_seo_html.py
.venv/bin/python scripts/rebuild_seo_html.py
```

Expected: stampa "Rendering 2026-04-11…" e "Rendering current feed…" e "Done."

- [ ] **Step 3: Verify output**

```bash
ls site/index.html site/archivio/index.html site/sitemap.xml site/robots.txt site/feed.xml site/docs/index.html site/about/index.html 2>&1
```

Tutti devono esistere.

- [ ] **Step 4: Commit**

```bash
git add scripts/rebuild_seo_html.py site/
git commit -m "feat(ssg): rebuild historical HTML script + initial SSG output"
```

---

## Task 19: End-to-end Playwright test suite (local)

**Files:**
- No new files; test con http.server locale + Playwright

- [ ] **Step 1: Run http.server + Playwright comprehensive test**

```bash
.venv/bin/python -m http.server -d site 8099 >/tmp/httpd.log 2>&1 &
SRV=$!
sleep 1
.venv/bin/python <<'PY' 2>&1
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        urls_to_check = [
            "http://localhost:8099/",
            "http://localhost:8099/top-settimana/",
            "http://localhost:8099/archivio/",
            "http://localhost:8099/archivio/2026/",
            "http://localhost:8099/archivio/2026/04/",
            "http://localhost:8099/archivio/2026/04/11/",
            "http://localhost:8099/categoria/google-updates/",
            "http://localhost:8099/docs/",
            "http://localhost:8099/about/",
            "http://localhost:8099/sitemap.xml",
            "http://localhost:8099/feed.xml",
            "http://localhost:8099/robots.txt",
        ]
        for url in urls_to_check:
            errors.clear()
            resp = await page.goto(url, wait_until="networkidle")
            status = resp.status if resp else "?"
            print(f"{status} {url}")
            if errors:
                print(f"   ERRORS: {errors}")

        # Specific checks on homepage
        await page.goto("http://localhost:8099/")
        h1_count = await page.locator("h1").count()
        cards = await page.locator(".card").count()
        search_works = await page.locator("#search").count()
        print(f"\nHomepage: h1={h1_count}, cards={cards}, search={search_works}")

        # Legacy redirect ?date=
        await page.goto("http://localhost:8099/?date=2026-04-11", wait_until="networkidle")
        await asyncio.sleep(0.3)
        final_url = page.url
        print(f"\n?date=2026-04-11 redirected to: {final_url}")
        assert "/archivio/2026/04/11/" in final_url

        await browser.close()

asyncio.run(main())
PY
kill $SRV 2>/dev/null
wait 2>/dev/null
```

Expected: ogni URL restituisce 200, nessun errore JS, homepage ha h1 e cards, legacy ?date= redirecta.

- [ ] **Step 2: Commit (nessuna modifica, solo verifica)**

Se tutto verde, procedi. Altrimenti fix issue e re-run.

---

## Task 20: Full suite + pipeline smoke + ruff + deploy verification

**Files:**
- No new files

- [ ] **Step 1: Full pytest**

```bash
.venv/bin/pytest -v
```

Expected: tutto verde, include i nuovi test di `test_slug.py`, `test_seo.py`, `test_renderer.py`, `test_publisher.py`.

- [ ] **Step 2: Ruff check + format**

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Expected: all clean.

- [ ] **Step 3: Run local pipeline**

```bash
TZ=Europe/Rome .venv/bin/python -m osservatorio_seo refresh 2>&1 | tail -5
```

Expected: `OK — N items, top10=10, cost=0.00X€`. Al termine, `site/` contiene tutti gli HTML generati.

- [ ] **Step 4: Verify generated structure**

```bash
find site/ -name "index.html" | head -30
ls site/sitemap.xml site/feed.xml site/robots.txt
```

Expected:
```
site/index.html
site/about/index.html
site/archivio/index.html
site/archivio/2026/index.html
site/archivio/2026/04/index.html
site/archivio/2026/04/11/index.html
site/archivio/2026/04/11/hub/index.html
site/archivio/2026/04/11/<slug>/index.html  (per articoli importance>=4)
site/categoria/<cat>/index.html  (multipli)
site/tag/<tag>/index.html  (multipli, >= 2 items)
site/docs/index.html
```

- [ ] **Step 5: Git commit del nuovo SSG output**

```bash
git add site/ data/
git commit -m "chore(ssg): initial full SSG rebuild from current feed"
```

- [ ] **Step 6: Push**

```bash
git push origin main
```

- [ ] **Step 7: Trigger workflow e watch**

```bash
gh workflow run daily-refresh.yml --repo donatopirolo/osservatorioseo
gh run watch $(gh run list --repo donatopirolo/osservatorioseo --workflow daily-refresh.yml --limit 1 --json databaseId --jq '.[0].databaseId') --repo donatopirolo/osservatorioseo --exit-status
```

Expected: workflow verde, inclusi tutti gli step incluso "Deploy to Cloudflare Pages".

- [ ] **Step 8: Verifica live**

```bash
for url in \
  "https://osservatorioseo.pages.dev/" \
  "https://osservatorioseo.pages.dev/top-settimana/" \
  "https://osservatorioseo.pages.dev/archivio/" \
  "https://osservatorioseo.pages.dev/archivio/2026/" \
  "https://osservatorioseo.pages.dev/archivio/2026/04/11/" \
  "https://osservatorioseo.pages.dev/categoria/google-updates/" \
  "https://osservatorioseo.pages.dev/docs/" \
  "https://osservatorioseo.pages.dev/about/" \
  "https://osservatorioseo.pages.dev/sitemap.xml" \
  "https://osservatorioseo.pages.dev/feed.xml" \
  "https://osservatorioseo.pages.dev/robots.txt"; do
  code=$(curl -sL -o /dev/null -w "%{http_code}" "$url")
  echo "$code $url"
done
```

Expected: tutte 200.

- [ ] **Step 9: Valida JSON-LD con strumento esterno (manuale)**

Apri https://validator.schema.org/#url=https://osservatorioseo.pages.dev/archivio/2026/04/11/<slug>/ e verifica zero errori.

- [ ] **Step 10: Lighthouse audit**

Esegui da Chrome DevTools → Lighthouse → Performance + SEO. Target: Performance 95+, SEO 100, LCP < 200ms.

- [ ] **Step 11: Commit eventuali fix residui + tag release**

```bash
git tag v2.0-ssg
git push origin v2.0-ssg
```

---

## Criteri di accettazione finale

Il redesign SSG è "done" quando:

1. ✅ Tutti i test Python passano (`pytest -v`)
2. ✅ Ruff check + format check puliti
3. ✅ `python -m osservatorio_seo refresh` genera gli HTML senza errori
4. ✅ Tutti i 11 URL listati nello Step 8 ritornano 200 in produzione
5. ✅ `curl https://osservatorioseo.pages.dev/archivio/2026/04/11/<slug>/` contiene `"@type": "NewsArticle"` nel body
6. ✅ `curl https://osservatorioseo.pages.dev/robots.txt` contiene `Disallow: /` (mantiene noindex finché l'utente decide di aprire)
7. ✅ Legacy `?date=YYYY-MM-DD` fa redirect JS a `/archivio/YYYY/MM/DD/`
8. ✅ Mobile responsive: cards collassabili + header visibile (Playwright test)
9. ✅ Search: filter locale funziona, cross-archive toggle funziona
10. ✅ Cloudflare Pages deployment verde dal workflow GitHub Actions
11. ✅ Lighthouse SEO score: 100
12. ✅ JSON-LD NewsArticle valido su almeno un articolo importance=5
13. ✅ Costo AI run invariato (€0.005 ± 0.001)
14. ✅ Costo monetario ricorrente: 0 €/mese
15. ✅ `/top-settimana/` ritorna 200 e mostra 10 articoli ranked dai 7 giorni precedenti con link corretti agli articoli di oggi
