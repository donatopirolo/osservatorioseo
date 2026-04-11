# OsservatorioSEO

Hub giornaliero di notizie **SEO e AI** da fonti autorevoli. Ogni mattina alle 07:00 (Europe/Rome) un workflow GitHub Actions recupera notizie da blog ufficiali (Google, OpenAI, Anthropic), testate di settore (Search Engine Land, Journal, Roundtable), e voci indipendenti. L'AI (via OpenRouter → Gemini 2.0 Flash) le riassume in italiano, e il **Doc Watcher** segnala quando Google aggiorna silenziosamente una pagina di documentazione critica.

L'output è un `feed.json` pubblico consumabile anche da altri tool AI, e una pagina web statica servita da Cloudflare Pages.

## Feature principali

- 🔄 **Aggiornamento automatico** ogni mattina alle 07:00 Europe/Rome
- 🌐 **Fonti multi-tipo**: RSS, HTML scraping, Playwright per anti-bot
- 🇮🇹 **Riassunti in italiano** tono asciutto, no hype
- ⚠️ **Doc Watcher**: rileva modifiche a pagine Google (Spam Policies, Helpful Content, QRG PDF, ecc.)
- 📊 **Top 10 del giorno** + tutto categorizzato (8 categorie)
- 💰 **Costo < €3/mese** grazie a GitHub Actions gratis + Gemini 2.0 Flash economico
- 📁 **Zero database**: tutto è committato in git, archivio storico versionato gratis
- 🔁 **Resiliente**: graceful degradation, issue automatiche su failure, canary settimanale

## Architettura

```
GitHub Actions (cron 07:00) → Python pipeline → feed.json → Cloudflare Pages
```

Pipeline:
1. **Fetcher** — RSS/Scraper/Playwright paralleli, User-Agent browser-like, rate limit per host
2. **Doc Watcher** — fetch pagine, hash+diff, rileva cambiamenti significativi
3. **Normalizer** — canonicalizza URL, dedup per URL + fuzzy title
4. **Summarizer** — OpenRouter con fallback chain (Gemini Flash → Claude Haiku → GPT-5 Mini)
5. **Ranker** — scoring per top-10 e raggruppamento categorie
6. **Publisher** — scrive `data/feed.json`, archivio giornaliero, commit+push

## Quick start locale

```bash
git clone https://github.com/<your-user>/osservatorioseo.git
cd osservatorioseo
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install --with-deps chromium

cp .env.example .env
# modifica .env con la tua API key OpenRouter

export $(cat .env | xargs)
python -m osservatorio_seo refresh
```

## Deploy

### 1. GitHub
- Fork/clona il repo
- Aggiungi secret `OPENROUTER_API_KEY` in Settings → Secrets and variables → Actions
- Il workflow `daily-refresh.yml` partirà automaticamente alle 07:00 Rome

### 2. Cloudflare Pages
- Vai su Cloudflare Pages → Create a project → Connect to GitHub
- Build output directory: `site/`
- Build command: (vuoto)
- Deploy

## Testing

```bash
pytest -v
ruff check .
ruff format --check .
```

## Configurazione

- `config/sources.yml` — lista fonti (aggiungi/rimuovi/disabilita)
- `config/doc_watcher.yml` — pagine sorvegliate

## Struttura progetto

```
osservatorioseo/
├── src/osservatorio_seo/   # codice Python
├── config/                 # YAML config
├── data/                   # feed.json + archive + state (committato dal bot)
├── site/                   # frontend statico
├── tests/                  # pytest suite
└── .github/workflows/      # CI/CD
```

## Roadmap

- [ ] Chatbot interattivo che legge il feed al volo
- [ ] Newsletter email giornaliera
- [ ] Notifiche Telegram/Slack sui doc changes
- [ ] Espansione Doc Watcher a Bing, Perplexity, Meta AI
- [ ] RSS output del feed stesso

## Contenuti e policy

OsservatorioSEO pubblica solo **titolo + nostro riassunto + link alla fonte**. Nessun testo integrale, massima attribuzione, traffico mandato indietro alle fonti. Se sei titolare di una fonte e vuoi essere rimosso, apri un'issue — rispondiamo entro 24h.

## License

MIT — vedi `LICENSE`.
