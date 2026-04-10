# OsservatorioSEO — Design Spec

**Data:** 2026-04-11
**Autore:** Donato + Claude (brainstorming)
**Status:** Draft — in review

---

## 1. Obiettivo

Costruire un hub pubblico di notizie quotidiane su SEO e AI, aggiornato automaticamente ogni mattina alle 07:00 (Europe/Rome), che raccoglie da fonti autorevoli, riassume in italiano via AI, e serve il tutto come:

- un **file JSON pubblico** (`feed.json`) — l'API consumabile anche da altri AI/tool
- una **pagina web statica** — con le notizie del giorno come card (top 10 + tutto categorizzato)

Il sistema deve essere **pubblico** (multi-utente), **economico** (costi operativi < €5/mese), e girare **unattended** senza manutenzione quotidiana.

### Caso d'uso principale

Un professionista SEO apre `osservatorioseo.pages.dev` (o equivalente) la mattina al caffè, legge la top-10, espande le categorie che gli interessano, e clicca sui link per approfondire le notizie rilevanti. In più, una feature distintiva — il **Doc Watcher** — lo avvisa se Google (o OpenAI/Anthropic) ha modificato silenziosamente una pagina di documentazione ufficiale rilevante per la SEO.

### Non-obiettivi (v1)

- Nessun chatbot interattivo / conversational AI (valutabile in v2)
- Nessun sistema di utenti/login/preferenze
- Nessuna newsletter email (valutabile in v2)
- Nessun supporto multilingua oltre all'italiano per i riassunti
- Nessuna monetizzazione / ads / sponsorship
- Nessuna persistenza database — solo file committati in git

---

## 2. Architettura di alto livello

```
                                                    07:00 Europe/Rome
                                                           │
                                                           ▼
                                            ┌──────────────────────────┐
                                            │  GitHub Actions Workflow │
                                            │     daily-refresh.yml    │
                                            └─────────────┬────────────┘
                                                          │
                  ┌───────────────────────────────────────┼───────────────────────────────────────┐
                  ▼                                       ▼                                       ▼
         ┌─────────────────┐                   ┌─────────────────┐                   ┌─────────────────┐
         │  Fetcher Layer  │                   │   Doc Watcher   │                   │ Sources Config  │
         │ • RSS adapter   │                   │ • fetch pagine  │                   │  (sources.yml)  │
         │ • Scraper adapt │                   │ • hash + diff   │                   └─────────────────┘
         │ • Playwright ad │                   │ • change detect │
         └────────┬────────┘                   └────────┬────────┘
                  │                                     │
                  └──────────────┬──────────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │   Normalizer + Deduplicator   │
                  └──────────────┬────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │       AI Summarizer           │
                  │  OpenRouter → Gemini Flash    │
                  │  (IT summary, category,       │
                  │   tags, importance 1-5)       │
                  └──────────────┬────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │      Ranker / Top-10          │
                  └──────────────┬────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │          Publisher            │
                  │  data/feed.json               │
                  │  data/archive/YYYY-MM-DD.json │
                  │  git commit + push            │
                  └──────────────┬────────────────┘
                                 ▼
                  ┌───────────────────────────────┐
                  │   Cloudflare Pages (CDN)      │
                  │   feed.json + index.html      │
                  └───────────────────────────────┘
```

### Approccio scelto: "Approccio A"

GitHub Actions come cron runner, codice in repo pubblico, JSON committato come artefatto versionato, Cloudflare Pages per il serving statico. Alternative valutate e scartate: Cloudflare Workers (CPU limit + Playwright non gira), Vercel Hobby (timeout 10s su serverless + clausola non-commercial).

**Motivazioni principali:**
1. Runner Ubuntu completo senza time limit → Playwright gira nativamente per fonti senza RSS
2. Git history = archivio storico gratuito e navigabile (fondamentale per Doc Watcher)
3. Zero infrastruttura da gestire
4. Evoluzione futura libera (un domani si può aggiungere un Worker che legge il JSON servito da Pages per un chatbot)

---

## 3. Componenti

Ogni componente ha un'unica responsabilità e comunica attraverso interfacce esplicite. Tutti sono testabili in isolamento.

### 3.1 Fetcher Layer (`src/osservatorio_seo/fetchers/`)

**Responsabilità:** dato un `Source` in config, produrre una lista di `RawItem`.

Tre adapter con la stessa interfaccia `Fetcher`:

- **`RSSFetcher`** — usa `feedparser`. Gestisce RSS/Atom malformati. Copre l'80%+ delle fonti.
- **`ScraperFetcher`** — fetch HTML con `httpx`, parsing con `selectolax`. Per fonti che non hanno RSS ma espongono sitemap o pagine index prevedibili. Configurabile per fonte con selettori CSS.
- **`PlaywrightFetcher`** — Chromium headless via `playwright`. Riservato alle fonti con anti-bot o JS pesante (X/Twitter, LinkedIn se fattibile).

**Interfaccia comune:**

```python
class Fetcher(Protocol):
    async def fetch(self, source: Source) -> list[RawItem]: ...
```

**Policy HTTP (Opzione 2 scelta dall'utente):**

- **NO check `robots.txt`** — scelta esplicita, vedi §10.
- **User-Agent browser-like**, rotato tra 3-5 stringhe realistiche Chrome/Firefox su Linux/macOS. Nessuna dichiarazione di bot.
- **Rate limiting:** max 3 richieste concorrenti per host, delay 1-2s tra richieste sequenziali sullo stesso host, jitter ±0.5s.
- **Timeout:** 15s per singola richiesta HTTP, 30s per singola pagina Playwright.
- **Retry:** 2 tentativi con exponential backoff per errori 5xx e timeout.

### 3.2 Doc Watcher (`src/osservatorio_seo/doc_watcher/`)

**Responsabilità:** sorvegliare un set di URL di documentazione ufficiale e rilevare modifiche.

**Config:** `config/doc_watcher.yml` — lista di pagine con `id`, `name`, `url`, `selector` CSS, `type` (html/pdf), `category`, `importance`.

**Pagine sorvegliate di default (v1):**

| ID | URL | Importanza |
|---|---|---|
| `google_spam_policies` | developers.google.com/search/docs/essentials/spam-policies | 5 |
| `google_helpful_content` | developers.google.com/search/docs/fundamentals/creating-helpful-content | 5 |
| `google_quality_rater_guidelines` | services.google.com/fh/files/misc/hsw-sqevaluatorguidelines.pdf | 5 |
| `google_ai_features_guidance` | developers.google.com/search/docs/appearance/ai-features | 4 |
| `googlebot_docs` | developers.google.com/search/docs/crawling-indexing/googlebot | 3 |
| `structured_data_docs` | developers.google.com/search/docs/appearance/structured-data | 3 |
| `google_crawlers_overview` | developers.google.com/search/docs/crawling-indexing/overview-google-crawlers | 4 |
| `openai_usage_policies` | openai.com/policies/usage-policies/ | 3 |
| `anthropic_usage_policies` | anthropic.com/legal/aup | 3 |

**Algoritmo:**

```
per ogni pagina in doc_watcher.yml:
    1. fetch raw (HTML via httpx o PDF via pdfplumber)
    2. estrai testo dal selector → html2text → normalizza whitespace e pattern rumorosi
    3. compute sha256(normalized_text)
    4. load previous hash da data/state/doc_watcher/<page_id>.hash
    5. se hash uguale → no-op
       se diverso:
         a. load testo precedente da data/state/doc_watcher/<page_id>.txt
         b. unified_diff = difflib.unified_diff(old, new, n=2)
         c. estrai righe "+" e "-" → passa al summarizer con prompt doc-change
         d. crea un DocChange item → entra nel feed del giorno
         e. sovrascrivi .hash e .txt con le nuove versioni
         f. salva copia del diff in data/state/doc_watcher/<page_id>_<date>.diff
    6. prima esecuzione: salva hash, NON emette change item
```

**Interazione con git:** i file `.hash`, `.txt` e `.diff` vengono committati a ogni run — `git log -- data/state/doc_watcher/<page_id>.txt` fornisce la storia completa versionata di quella pagina. Il campo `doc_change.diff_url` nel JSON punta al commit GitHub corrispondente.

**Edge cases gestiti:**
- **Whitespace e date dinamiche** → normalizzati via regex configurabili per pagina (`noise_patterns`).
- **Similarity threshold** → ignora cambiamenti < 0.3% del testo totale (configurabile).
- **Fetch fallito** → skip, state non toccato, entry in `failed_sources`.
- **PDF Quality Rater Guidelines (~170 pagine)** → se il diff supera 50k caratteri, viene troncato prima del passaggio all'AI con nota "diff troncato, vedi commit per full".

### 3.3 Normalizer + Deduplicator (`src/osservatorio_seo/normalizer.py`)

**Responsabilità:** dato `list[RawItem]` proveniente da fetcher eterogenei, produrre `list[NormalizedItem]` pulita e deduplicata.

**Operazioni:**
- Normalizza URL (rimuove query string di tracking `utm_*`, `fbclid`, ecc., trailing slash, protocol)
- Normalizza titoli (strip whitespace, decodifica entities HTML, rimuove emoji ridondanti)
- Deduplica per:
  1. URL canonicalizzato (match esatto)
  2. Title similarity > 0.85 (fuzzywuzzy o rapidfuzz) — tiene l'item con authority più alta
- Filtra item con `published_at` più vecchio di 48 ore (configurabile)
- Filtra item troppo corti (< 100 char di content)

### 3.4 AI Summarizer (`src/osservatorio_seo/summarizer.py`)

**Responsabilità:** arricchire ogni `NormalizedItem` con campi generati dall'AI.

**Provider:** OpenRouter (`https://openrouter.ai/api/v1/chat/completions`).

**Modello default:** `google/gemini-2.0-flash` — miglior rapporto costo/qualità per riassunti brevi.

**Fallback chain:** `gemini-2.0-flash` → `anthropic/claude-haiku-4.5` → `openai/gpt-5-mini` → skip con badge "riassunto non disponibile".

**Due prompt distinti:**

1. **Prompt summarizer** (per item regolari): produce `title_it`, `summary_it` (2-4 frasi asciutte in italiano), `category`, `tags` (1-4, snake_case, inglese), `importance` (1-5). Il prompt vieta esplicitamente tono hype/marketing.

2. **Prompt doc-change** (per item del Doc Watcher): analizza il diff unificato, produce un `summary_it` che spiega **concretamente** cosa è cambiato e perché importa a un SEO. `title_it` inizia con "⚠️".

**Output format:** JSON strutturato garantito via `response_format: {type: "json_object"}`, validato post-risposta con Pydantic. In caso di JSON malformato: 1 retry, poi fallback model.

**Stima costi giornalieri:**

| Modello | Prezzo | Costo/giorno (40 item, ~3k tok input, 200 tok output) |
|---|---|---|
| `google/gemini-2.0-flash` | $0.075 in / $0.30 out | **~€0.02-0.05** |
| `anthropic/claude-haiku-4.5` (fallback) | $1.00 in / $5.00 out | ~€0.15-0.30 |
| `openai/gpt-5-mini` (fallback 2) | $0.25 in / $2.00 out | ~€0.08-0.15 |

Il costo totale giornaliero viene calcolato dal codice e salvato in `stats.ai_cost_eur` del `feed.json` per trasparenza e monitoring.

### 3.5 Ranker (`src/osservatorio_seo/ranker.py`)

**Responsabilità:** ordinare gli item e marcare i top-10 del giorno.

**Scoring (funzione pura, zero side-effect):**

```
score = (
    importance * 10               # peso principale (1-5 → 10-50)
    + source.authority             # bonus autorità fonte (1-10)
    + freshness_bonus              # 5 se published < 6h, 2 se < 24h, 0 altrimenti
    + doc_change_bonus             # +20 se is_doc_change
    + category_bonus               # +5 se google_updates, +3 se ai_models
)
```

Il top-10 è semplicemente il `sorted(items, key=score, reverse=True)[:10]`. Gli item rimanenti vengono raggruppati per `category` mantenendo l'ordine di score decrescente.

### 3.6 Publisher (`src/osservatorio_seo/publisher.py`)

**Responsabilità:** serializzare il risultato finale su disco e committare.

**File scritti:**

- `data/feed.json` — feed corrente (sovrascritto ogni run)
- `data/archive/YYYY-MM-DD.json` — snapshot del giorno (idempotente)
- `data/state/doc_watcher/<page_id>.hash` — hash correnti
- `data/state/doc_watcher/<page_id>.txt` — testo corrente
- `data/state/doc_watcher/<page_id>_<date>.diff` — diff del giorno (solo se cambiato)

**Commit atomico:**
1. Costruisce il JSON in memoria, valida contro lo schema
2. Scrive tutti i file
3. `git add data/`
4. Se ci sono cambiamenti: commit con messaggio `chore(feed): refresh YYYY-MM-DD`
5. Push; se fallisce, rollback locale

---

## 4. Schema dati

### 4.1 `feed.json` (output pubblico)

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-04-11T05:00:12Z",
  "generated_at_local": "2026-04-11T07:00:12+02:00",
  "timezone": "Europe/Rome",
  "run_id": "2026-04-11-0700",
  "stats": {
    "sources_checked": 47,
    "sources_failed": 2,
    "items_collected": 63,
    "items_after_dedup": 41,
    "doc_changes_detected": 1,
    "ai_cost_eur": 0.037
  },
  "top10": ["item_2026-04-11_001", "..."],
  "categories": {
    "google_updates": ["item_2026-04-11_001"],
    "google_docs_change": ["item_2026-04-11_002"],
    "ai_models": ["..."],
    "ai_overviews_llm_seo": ["..."],
    "technical_seo": ["..."],
    "content_eeat": ["..."],
    "tools_platforms": ["..."],
    "industry_news": ["..."]
  },
  "items": [
    {
      "id": "item_2026-04-11_001",
      "title_original": "March 2026 Core Update finished rolling out",
      "title_it": "Il Core Update di marzo 2026 ha completato il rollout",
      "summary_it": "Google ha confermato oggi il completamento del core update iniziato il 18 marzo. Il rollout è durato 24 giorni — più lungo della media. Analisti segnalano forti scossoni nei settori YMYL e health.",
      "url": "https://developers.google.com/search/blog/2026/04/march-core-update-done",
      "source": {
        "id": "google_search_central",
        "name": "Google Search Central Blog",
        "authority": 10,
        "type": "official"
      },
      "category": "google_updates",
      "tags": ["core_update", "ranking", "ymyl"],
      "importance": 5,
      "published_at": "2026-04-11T03:42:00Z",
      "fetched_at": "2026-04-11T05:00:03Z",
      "is_doc_change": false,
      "language_original": "en",
      "summarizer_model": "google/gemini-2.0-flash",
      "raw_hash": "sha256:a3f9..."
    },
    {
      "id": "item_2026-04-11_002",
      "title_it": "⚠️ Google ha aggiornato la pagina Spam Policies",
      "summary_it": "Aggiunta una nuova sezione \"scaled content abuse\" che chiarisce come Google tratta i contenuti generati in massa con AI. Rimossa la frase ambigua sul 'low-value AI content' di marzo.",
      "url": "https://developers.google.com/search/docs/essentials/spam-policies",
      "source": {
        "id": "doc_watcher",
        "name": "OsservatorioSEO Doc Watcher",
        "authority": 10,
        "type": "doc_change"
      },
      "category": "google_docs_change",
      "tags": ["spam_policies", "ai_content"],
      "importance": 5,
      "is_doc_change": true,
      "doc_change": {
        "page_id": "google_spam_policies",
        "previous_hash": "sha256:b71c...",
        "current_hash": "sha256:e4d2...",
        "diff_url": "https://github.com/<user>/osservatorioseo/commit/<sha>#diff-abc",
        "lines_added": 14,
        "lines_removed": 3
      }
    }
  ],
  "doc_watcher_status": [
    {"page_id": "google_spam_policies", "last_checked": "2026-04-11T05:00:08Z", "changed": true},
    {"page_id": "google_helpful_content", "last_checked": "2026-04-11T05:00:09Z", "changed": false}
  ],
  "failed_sources": [
    {"id": "linkedin_john_mueller", "error": "playwright_timeout", "last_success": "2026-04-10T05:00:04Z"}
  ]
}
```

**Scelte di design:**

- `top10` è una lista di ID (lookup nel frontend) → zero duplicazione dati
- `categories` è una mappa categoria→IDs → rendering veloce per sezione
- `items` è la sorgente di verità → un solo posto dove modificare un campo
- `title_original` sempre presente → trasparenza totale
- `failed_sources` esplicito → nessun errore nascosto
- `stats.ai_cost_eur` → monitoring costi dal JSON stesso

### 4.2 Categorie (v1)

| ID | Nome | Contenuto |
|---|---|---|
| `google_updates` | Google Updates | core updates, spam updates, annunci SearchLiaison |
| `google_docs_change` | Google Docs Change | output del Doc Watcher |
| `ai_models` | AI Models | release OpenAI/Anthropic/Google/Meta/Mistral |
| `ai_overviews_llm_seo` | AI Overviews & LLM SEO | AI Overviews, GEO, llms.txt, citazioni in LLM |
| `technical_seo` | Technical SEO | crawling, indexing, schema, Core Web Vitals |
| `content_eeat` | Content & E-E-A-T | helpful content, authorship, quality |
| `tools_platforms` | Tools & Platforms | annunci tool vendor (Ahrefs, Semrush, Sistrix…) |
| `industry_news` | Industry News | antitrust, regulatory, industry shifts |

### 4.3 `sources.yml` (schema)

```yaml
sources:
  - id: google_search_central
    name: "Google Search Central Blog"
    authority: 10
    type: official
    category_hint: google_updates
    fetcher: rss
    feed_url: https://developers.google.com/search/blog/rss
    enabled: true

  - id: search_engine_roundtable
    name: "Search Engine Roundtable"
    authority: 9
    type: media
    fetcher: rss
    feed_url: https://www.seroundtable.com/feed.xml
    enabled: true

  - id: searchliaison_x
    name: "Danny Sullivan (SearchLiaison) on X"
    authority: 10
    type: social
    fetcher: playwright
    target_url: https://x.com/searchliaison
    selectors:
      post: "article[data-testid='tweet']"
      text: "div[data-testid='tweetText']"
    enabled: true
```

**Lista completa fonti v1** (sarà finalizzata nel plan):

- **Primary/ufficiali:** Google Search Status Dashboard, Google Search Central Blog, Google Search Central X, OpenAI Blog, Anthropic News, Google DeepMind Blog, Microsoft Bing Blogs, ai.google
- **Media di settore:** Search Engine Land, Search Engine Journal, Search Engine Roundtable, Marie Haynes, SEOFOMO
- **Trackers SERP:** SEMrush Sensor, MozCast, AWR Sensor
- **Googlers diretti:** John Mueller (LinkedIn/Bluesky), Gary Illyes (LinkedIn), Search Off the Record podcast, SearchLiaison X
- **Tool vendor:** Ahrefs Blog, Semrush Blog, Sistrix Blog, Moz Blog
- **Voci indipendenti:** Kevin Indig (Growth Memo), Lily Ray, Glenn Gabe, Cyrus Shepard, iPullRank
- **AI labs:** Meta AI Blog, Mistral AI, xAI, Perplexity, Hugging Face (solo major releases)
- **Web/platform:** web.dev, Chrome Developers Blog, Schema.org news

---

## 5. Frontend

Pagina HTML statica, zero framework, zero build step.

**File:** `site/index.html`, `site/styles.css`, `site/app.js` (~300 righe totali).

**Comportamento:**
- `fetch('/data/feed.json')` al load
- Render del header con data, ora, stats
- Render della sezione "TOP 10" come card verticali
- Render delle categorie collassabili (native `<details>`)
- Filtro per tag via querystring `?tag=core_update`
- Search client-side su titolo + summary

**Stile:**
- System font stack, niente webfonts
- Dark mode via `@media (prefers-color-scheme: dark)`
- Mobile-first, padding generoso
- Meta SEO completo (`<title>`, `og:*`, canonical, `lang="it"`)

**Deploy:** Cloudflare Pages collegato al repo, output directory `site/`. Per rendere `data/feed.json` accessibile al frontend con path relativo, il workflow `daily-refresh.yml` include uno step finale che copia `data/feed.json` (e gli archivi N+1 più recenti) in `site/data/` **prima del commit**. Il frontend fetcha da `/data/feed.json` path relativo → zero CORS, zero configurazione cross-origin, zero dipendenza da URL raw GitHub.

---

## 6. Error handling & resilience

Un sistema che gira unattended DEVE essere resiliente. Ogni livello di fallimento ha una strategia esplicita.

| Livello | Cosa può rompersi | Strategia |
|---|---|---|
| Singola fonte | RSS 404, HTML cambia, Playwright timeout | try/except per fonte, log in `failed_sources`, continua |
| Singola pagina Doc Watcher | fetch fallisce | skip, state non toccato, log |
| Singolo item AI | OpenRouter timeout, JSON malformato | 1 retry → fallback model → skip con badge |
| Tutto OpenRouter down | 3 modelli falliti | feed pubblicato senza `summary_it`, badge "non disponibile" |
| Normalizer crash | bug nel codice | workflow **fails**, no commit, issue GitHub automatica |
| Publisher crash | I/O error | commit atomico, rollback su push failure |

**Meccanismi concreti:**

1. **Circuit breaker per fonte** — dopo 7 giorni consecutivi di fallimento, la fonte viene marcata `enabled: false` via PR automatica del bot, richiede review umana.

2. **Daily issue on failure** — se il workflow termina con errore, `actions/github-script` apre un'issue con titolo `[osservatorioseo] Workflow failed YYYY-MM-DD` e link al run. Arriva email a chi watcha il repo → **questo è il sistema di alerting**.

3. **Timeout espliciti** — singola richiesta HTTP 15s, singola pagina Playwright 30s, singolo fetcher totale 90s, workflow totale 10 min (GitHub Actions lo killa).

4. **Idempotenza** — il workflow può essere rieseguito manualmente lo stesso giorno senza conseguenze: Doc Watcher non emette falsi change, feed sovrascritto, archivio stesso nome file.

5. **Graceful degradation** — se il run fallisce del tutto, il `feed.json` precedente resta servito. Il sito non va mai "vuoto", nel peggiore dei casi è di un giorno fa con banner "ultimo aggiornamento: ieri".

6. **Canary settimanale** — workflow separato `smoke-real-sources.yml` che esegue una volta a settimana un fetch di 3-5 fonti reali (senza AI, senza commit) per rilevare early se un parser si è rotto per cambio HTML upstream.

---

## 7. Testing

**Filosofia:** test per l'essenziale, non per coverage massimo.

| Tipo | Cosa | Come |
|---|---|---|
| Unit | Normalizer, Ranker, Doc Watcher diff, Deduplicator | pytest + fixture in `tests/fixtures/` |
| Fetcher integration | Parser RSS/HTML | fixture file salvati da fonti reali, no network |
| Summarizer contract | Schema JSON AI | mock OpenRouter + Pydantic validation |
| E2E smoke | Pipeline intera da fixture a feed.json | CLI su `sources.test.yml` con 3 fonti locali |
| Doc Watcher regression | Diff riproducibile | fixture con 2 versioni di una pagina |

**Non testati:** API esterne reali (OpenRouter live, siti upstream), frontend (~300 righe, ispezione visiva), comportamenti di rete reali (coperti dal logging in produzione).

**CI:** `.github/workflows/ci.yml` — `ruff check`, `ruff format --check`, `pytest`. Gira su ogni push/PR. <30s totali.

---

## 8. Stack tecnologico

| Pezzo | Scelta | Motivo |
|---|---|---|
| Linguaggio | Python 3.12 | ecosistema scraping maturo, `feedparser` gold standard |
| RSS | `feedparser` | gestisce feed malformati real-world |
| HTTP | `httpx` (async) | parallelizzazione nativa |
| HTML | `selectolax` + `beautifulsoup4` | selectolax 10x più veloce per scraping semplice |
| Playwright | `playwright` (Chromium headless) | unica via realistica per X/LinkedIn |
| Diff | `difflib` + `html2text` | stdlib, leggeri |
| PDF | `pdfplumber` | per Quality Rater Guidelines |
| AI | OpenRouter (Gemini 2.0 Flash default) | best price/quality per riassunti |
| Config | YAML | human-readable, review-friendly |
| Frontend | HTML + vanilla JS + CSS | zero dipendenze, zero build |
| Test | `pytest` | standard |
| Lint/format | `ruff` | unico tool velocissimo |
| CI/CD | GitHub Actions | già incluso nell'approccio |
| Data validation | `pydantic` v2 | validazione schema AI e config |

**NO Docker** — GitHub Actions fornisce runner Ubuntu fresco a ogni run, Docker aggiungerebbe overhead senza valore. Ripensabile se in futuro si migra a un VPS.

---

## 9. Struttura repo

```
osservatorioseo/
├── .github/
│   └── workflows/
│       ├── daily-refresh.yml       # cron 07:00 Europe/Rome
│       ├── ci.yml                   # test + lint su PR
│       └── smoke-real-sources.yml  # canary settimanale
├── src/
│   └── osservatorio_seo/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py                # dataclass/Pydantic models
│       ├── fetchers/
│       │   ├── base.py
│       │   ├── rss.py
│       │   ├── scraper.py
│       │   └── playwright.py
│       ├── doc_watcher/
│       │   ├── watcher.py
│       │   └── state.py
│       ├── normalizer.py
│       ├── summarizer.py
│       ├── ranker.py
│       ├── publisher.py
│       └── cli.py                   # python -m osservatorio_seo refresh
├── data/
│   ├── feed.json
│   ├── archive/
│   │   └── YYYY-MM-DD.json
│   └── state/
│       └── doc_watcher/
│           ├── <page_id>.hash
│           ├── <page_id>.txt
│           └── <page_id>_<date>.diff
├── config/
│   ├── sources.yml
│   └── doc_watcher.yml
├── site/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/
│   ├── test_fetchers.py
│   ├── test_normalizer.py
│   ├── test_ranker.py
│   ├── test_doc_watcher.py
│   └── fixtures/
├── pyproject.toml
├── README.md
└── .env.example
```

---

## 10. Compliance, etica, policy HTTP

**Scelta esplicita dell'utente (Opzione 2):** il sistema **non rispetta `robots.txt`**, si presenta con User-Agent browser-like realistico (rotazione 3-5 stringhe), e usa rate limiting conservativo (max 3 concorrenti per host, 1-2s sequenziali con jitter).

**Rischi accettati:**

- Possibile ban IP del pool GitHub Actions da parte di fonti aggressive
- Possibile challenge Cloudflare Bot Fight Mode → fallback Playwright se disponibile, altrimenti fonte marcata failed
- Esposizione legale grigia in giurisdizioni UE/US — mitigata dal fatto che il progetto è pubblico, cita sempre le fonti, linka sempre all'originale, non ripubblica testo integrale

**Mitigazioni volontarie:**

- Mai pubblicare il testo integrale degli articoli — solo titolo originale + riassunto originale (scritto dall'AI) + link
- Ogni card linka chiaramente alla fonte → il progetto **manda** traffico, non lo ruba
- Rate limiting rispettoso del carico (≠ rispetto dei segnali)
- Se una fonte richiede esplicitamente rimozione, si rimuove entro 24h (policy documentata nel README)

**Su LinkedIn/X specificamente:** se lo scraping con credenziali è problematico, ci si limita a estrarre metadati pubblici (titolo/link del post) senza il contenuto — la card mostra "post di X, clicca per leggere" e manda l'utente sulla piattaforma originale.

---

## 11. Workflow GitHub Actions (riferimento)

`daily-refresh.yml`:

- Trigger: `schedule: "0 5 * * *"` e `"0 6 * * *"` (doppio cron per DST Europe/Rome) + `workflow_dispatch`
- Step `Check local time`: salta se non sono le 07:00 locali
- Setup Python 3.12 con cache pip
- Install deps + Playwright Chromium
- `python -m osservatorio_seo refresh` con `OPENROUTER_API_KEY` da secrets
- Commit e push di `data/` se ci sono cambiamenti
- `actions/github-script` apre issue se fallisce

`ci.yml`: lint + test su PR e push su main.

`smoke-real-sources.yml`: canary settimanale che prova 3-5 fonti reali.

---

## 12. Costi operativi

| Voce | Costo/mese |
|---|---|
| GitHub Actions (repo pubblico) | **€0** — illimitato |
| GitHub Pages / Cloudflare Pages | **€0** |
| OpenRouter (Gemini 2.0 Flash) | **~€1-3** (~€0.02-0.10/giorno × 30) |
| Dominio custom (opzionale) | €10-15/anno |
| **Totale** | **~€1-3/mese** |

---

## 13. Roadmap post-v1 (non in scope ora)

- Chatbot interattivo (il JSON consumato al volo da un Worker + UI chat)
- Newsletter email giornaliera (SendGrid/Resend free tier)
- Dashboard analytics (quali notizie cliccate di più)
- Multilingua (EN summary in parallelo all'IT)
- RSS output del feed stesso (meta, eh?)
- Notifiche Telegram/Slack su doc changes
- Espansione Doc Watcher a documentazione Bing, Perplexity, Meta AI
- API autenticata per tool di terze parti
- Migrazione a VPS + Docker se i costi o la portabilità lo richiederanno

---

## 14. Criteri di successo (v1)

Il progetto è considerato completato con successo quando:

1. Il workflow GitHub Actions gira ogni mattina alle 07:00 senza intervento manuale per 7 giorni consecutivi
2. Il `feed.json` contiene ≥ 20 item al giorno, di cui ≥ 5 nella top-10
3. Almeno un rilevamento reale del Doc Watcher è stato generato (anche solo di test)
4. Il frontend è accessibile pubblicamente via HTTPS
5. Il costo mensile reale è ≤ €5
6. Errore/issue automatica su failure funziona end-to-end (testato forzando un errore)
7. Almeno una persona oltre l'autore ha consultato il sito e riferito utilità

---

## Appendice A — Dipendenze Python principali

```toml
[project]
name = "osservatorio-seo"
requires-python = ">=3.12"
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
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
]
```
