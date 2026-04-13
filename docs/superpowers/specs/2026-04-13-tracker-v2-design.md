# Tracker v2 — "Stato della ricerca" (Italia + Mondo)

**Data:** 2026-04-13
**Stato:** Design approvato

## Obiettivo

Riprogettare il tracker OsservatorioSEO partendo dai dati **realmente disponibili** dall'API Cloudflare Radar (free tier). Il tracker v1 aveva 7 grafici basati su endpoint inesistenti o parametri errati — tutti i dati erano vuoti. Il v2 è costruito su endpoint testati con dati reali.

Il tracker risponde a una domanda centrale per chi fa SEO: **"Come sta cambiando il modo in cui le persone cercano informazioni, e cosa significa per il mio lavoro?"**

## Architettura generale

### Due viste: Italia e Mondo

Un toggle in alto alla pagina permette di passare tra vista Italia (`location=IT`) e vista Mondo (nessun filtro location). Ogni sezione mostra i dati per il contesto selezionato. Lo stato del toggle è persistito nel `localStorage` del browser.

### 5 sezioni

1. I 10 siti più visitati (ranking top 10, timeseries 52w)
2. Le piattaforme AI — early warning (tabella bucket, 17 domini)
3. Bot vs Umani (trend 12w)
4. Chi crawla i siti e perché (AI bots user agent + crawl purpose, 12w)
5. Quali settori sono nel mirino dell'AI (industry breakdown)

---

## Sezione 1: "I 10 siti più visitati"

### Dati

- **Endpoint:** `GET /radar/ranking/top` → top 10 attuali con categoria
- **Endpoint:** `GET /radar/ranking/timeseries_groups` → una chiamata per dominio, `dateRange=52w`
- **Limitazione:** il parametro `domains` accetta un solo dominio per chiamata (bug API multi-domain). Servono 10 chiamate per location.
- **Date range massimo:** `52w` (53 punti settimanali). I valori `1y`, `2y` non sono supportati.

### Grafico

Grafico a linee interattivo. L'asse Y è il ranking (invertito: #1 in alto, #100 in basso). L'asse X è il tempo (52 settimane). Ogni dominio è una linea con colore distinto. Cliccando sulla legenda si attiva/disattiva la linea corrispondente.

Default: tutte le linee attive. L'utente può deselezionare le CDN (gstatic, amazonaws, akadns, googleapis, googlevideo, akamaiedge) per un confronto pulito tra piattaforme utente.

### Tabella sotto il grafico

| # | Dominio | Categoria | Var. settimana |
|---|---------|-----------|----------------|

Ordinata per rank attuale. La variazione è calcolata come differenza con la settimana precedente (freccia su/giù + numero).

### Note

- chatgpt.com ha solo ~14 punti su 52w perché è entrato in top 100 di recente. I domini che non erano in top 100 non hanno punti per quel periodo — il grafico mostra solo i punti disponibili.
- Se un dominio esce/rientra dalla top 100, ci saranno gap nella linea.

---

## Sezione 2: "Le piattaforme AI — early warning"

### Dati

- **Endpoint:** `GET /radar/ranking/domain/{domain}` → rank esatto (se in top 100) + bucket
- **Bucket possibili:** 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, >200000
- Una chiamata per dominio per location: 17 domini × 2 location = 34 chiamate/settimana

### Domini monitorati

Chatbot / Assistenti AI:
- chatgpt.com (OpenAI ChatGPT)
- openai.com (OpenAI)
- claude.ai (Anthropic Claude)
- anthropic.com (Anthropic)
- deepseek.com (DeepSeek)
- gemini.google.com (Google Gemini)
- copilot.microsoft.com (Microsoft Copilot)
- meta.ai (Meta AI)
- grok.com (xAI Grok)
- character.ai (Character.AI)
- poe.com (Poe / Quora)
- mistral.ai (Mistral)

AI Search:
- perplexity.ai (Perplexity)
- brave.com (Brave Search)
- kagi.com (Kagi)

AI Tools (rilevanti per SEO):
- huggingface.co (Hugging Face)
- notion.so (Notion AI)

### Visualizzazione

Tabella con colonne: Dominio, Tipo, Rank/Bucket IT, Rank/Bucket Mondo, Variazione bucket.

La variazione bucket confronta con lo snapshot precedente. Quando un dominio passa da bucket 1000 a 500, viene evidenziato (freccia verde su). Quando un dominio entra in top 100 per la prima volta, badge "NEW".

### Accumulo storico

Ogni snapshot settimanale salva rank e bucket per tutti i 17 domini. In 6 mesi avremo un timeseries costruito internamente per tracciare l'ascesa di piattaforme come claude.ai o deepseek.com anche se Radar non fornisce timeseries per domini fuori top 100.

Quando ci saranno almeno 4 snapshot storici, aggiungere un mini-grafico sparkline nella tabella che mostra il trend del bucket.

---

## Sezione 3: "Bot vs Umani"

### Dati

- **Endpoint:** `GET /http/timeseries_groups/bot_class` con `dateRange=12w`
- Restituisce 13 punti settimanali con percentuali `human` e `bot`
- Con `location=IT` per Italia, senza per Mondo

### Grafico

Grafico a area stackata (human + bot = 100%). L'asse Y da 0% a 100%, asse X 12 settimane.

### Contesto editoriale (testo statico sotto il grafico)

Breve spiegazione: "Bot include tutti i crawler automatizzati (motori di ricerca, AI, monitoraggio). Una quota bot in crescita significa che i tuoi contenuti vengono consumati sempre più da macchine — con implicazioni su crawl budget, rendering e ottimizzazione."

### Dati attuali di riferimento

- Italia: da 13.1% bot (gen 2026) a 22.4% bot (apr 2026) — +71%
- Mondo: da 29.2% bot (gen 2026) a 35.2% bot (apr 2026) — +21%

---

## Sezione 4: "Chi crawla i siti e perché"

### Dati

**4a — Bot AI per user agent:**
- **Endpoint:** `GET /ai/bots/timeseries_groups/user_agent` con `dateRange=12w`, `aggInterval=1w`
- Con `location=IT` per Italia, senza per Mondo
- Restituisce 13 punti settimanali per ogni bot: Googlebot, GPTBot, ClaudeBot, Meta-ExternalAgent, Bingbot, Applebot, Amazonbot, Bytespider, OAI-SearchBot, ChatGPT-User (solo in IT), other

**4b — Scopo del crawling:**
- **Endpoint:** `GET /ai/bots/timeseries_groups/crawl_purpose` con `dateRange=12w`, `aggInterval=1w`
- Categorie: User Action, Training, Mixed Purpose, Search, Undeclared

### Grafici

**4a:** Grafico a linee con toggle per ogni bot (come sezione 1). Default: tutti attivi.

**4b:** Grafico a area stackata (i purpose sommano ~100%).

### Contesto editoriale

Sotto i grafici, box con insight chiave:
- In Italia, "User Action" domina (~57%) — i bot stanno rispondendo agli utenti con i tuoi contenuti
- Nel mondo, "Training" domina (~50%) — i bot stanno raccogliendo dati per addestrare modelli
- Implicazione: in Italia bloccare i bot AI potrebbe significare perdere visibilità nel nuovo canale di ricerca

---

## Sezione 5: "Quali settori sono nel mirino dell'AI"

### Dati

- **Endpoint:** `GET /ai/bots/summary/industry` con `dateRange=28d`
- Con `location=IT` per Italia, senza per Mondo
- Restituisce top 10 settori + "other"

### Grafico

Bar chart orizzontale, top 10 settori ordinati per percentuale.

### Contesto editoriale

"Se lavori nel retail, il 21% di tutto il crawling AI in Italia riguarda il tuo settore. Il Travel & Tourism emerge forte in Italia (8.8%) rispetto al dato globale — riflesso dell'importanza del turismo nell'economia italiana."

---

## Raccolta dati — Budget API

### Chiamate per run settimanale

| Endpoint | Per IT | Per Mondo | Totale |
|----------|--------|-----------|--------|
| `/ranking/top` (limit=10) | 1 | 1 | 2 |
| `/ranking/timeseries_groups` (per dominio top 10) | 10 | 10 | 20 |
| `/ranking/domain/{d}` (17 AI platforms) | 17 | 17 | 34 |
| `/http/timeseries_groups/bot_class` | 1 | 1 | 2 |
| `/ai/bots/timeseries_groups/user_agent` | 1 | 1 | 2 |
| `/ai/bots/timeseries_groups/crawl_purpose` | 1 | 1 | 2 |
| `/ai/bots/summary/industry` | 1 | 1 | 2 |
| **Totale** | **32** | **32** | **64** |

64 chiamate/settimana — ampiamente nel free tier (100.000/giorno).

---

## Modello dati — Snapshot

Ogni snapshot settimanale (`data/tracker/snapshots/YYYY-Www.json`) contiene:

```
TrackerSnapshot:
  schema_version: "2.0"
  year: int
  week: int
  generated_at: datetime

  # Sezione 1: Top 10
  top10_it: list[TopDomainEntry]       # rank, domain, categories, timeseries 52w
  top10_global: list[TopDomainEntry]

  # Sezione 2: AI platforms
  ai_platforms_it: list[AIPlatformEntry]   # domain, label, type, rank, bucket
  ai_platforms_global: list[AIPlatformEntry]

  # Sezione 3: Bot vs Human
  bot_human_it: BotHumanTimeseries     # 12w di punti {date, human_pct, bot_pct}
  bot_human_global: BotHumanTimeseries

  # Sezione 4a: AI bots per user agent
  ai_bots_ua_it: AIBotsTimeseries      # 12w, per ogni bot {date, pct}
  ai_bots_ua_global: AIBotsTimeseries

  # Sezione 4b: Crawl purpose
  crawl_purpose_it: CrawlPurposeTimeseries
  crawl_purpose_global: CrawlPurposeTimeseries

  # Sezione 5: Industry
  industry_it: list[IndustryEntry]     # {industry, pct}
  industry_global: list[IndustryEntry]

  metadata: SnapshotMetadata
```

Sub-modelli:
```
TopDomainEntry:
  rank: int
  domain: str
  categories: list[str]
  timeseries: list[TimeseriesPoint]    # {date, rank}

AIPlatformEntry:
  domain: str
  label: str                           # "OpenAI ChatGPT", "Anthropic Claude", ecc.
  type: str                            # "chatbot", "ai_search", "ai_tool"
  rank: int | None                     # solo se in top 100
  bucket: str                          # "200", "500", "1000", ..., ">200000"

BotHumanTimeseries:
  points: list[BotHumanPoint]          # {date, human_pct, bot_pct}

AIBotsTimeseries:
  agents: list[str]                    # nomi dei bot
  points: list[AIBotPoint]             # {date, values: dict[agent, pct]}

CrawlPurposeTimeseries:
  purposes: list[str]
  points: list[CrawlPurposePoint]      # {date, values: dict[purpose, pct]}

IndustryEntry:
  industry: str
  pct: float
```

---

## Frontend

### Approccio

Sito SSG (Jinja2 + Tailwind), come il resto di OsservatorioSEO. I dati del JSON snapshot vengono iniettati nel template come variabile `<script>` inline. Un file JS vanilla gestisce:

- Toggle Italia/Mondo (swap dataset, re-render grafici)
- Toggle linee nei grafici (show/hide serie)
- Tooltip su hover

### Libreria grafici

Nessuna libreria esterna. I grafici sono SVG generati da JS a partire dai dati JSON. Questo mantiene il bundle leggero e coerente con il design del sito. Se la complessità dei grafici interattivi risulta eccessiva in vanilla JS, fallback su Chart.js (51kb gzipped) come unica dipendenza.

### Layout

```
┌─────────────────────────────────────────────┐
│  TRACKER — Stato della ricerca              │
│  [🇮🇹 Italia] [🌍 Mondo]                     │
├─────────────────────────────────────────────┤
│  § 1  I 10 siti più visitati                │
│  [grafico a linee interattivo, 52w]         │
│  [tabella: rank, dominio, cat, variazione]  │
├─────────────────────────────────────────────┤
│  § 2  Le piattaforme AI — early warning     │
│  [tabella: dominio, tipo, IT, Mondo, trend] │
├─────────────────────────────────────────────┤
│  § 3  Bot vs Umani                          │
│  [grafico a area, 12w]                      │
│  [testo: contesto SEO]                      │
├─────────────────────────────────────────────┤
│  § 4  Chi crawla i siti e perché            │
│  [4a: linee per bot, 12w] [4b: area, 12w]  │
│  [testo: insight IT vs Mondo]               │
├─────────────────────────────────────────────┤
│  § 5  Settori nel mirino dell'AI            │
│  [bar chart orizzontale]                    │
│  [testo: contesto settoriale]               │
├─────────────────────────────────────────────┤
│  Metodologia + fonte dati                   │
│  Ultimo aggiornamento: YYYY-MM-DD           │
└─────────────────────────────────────────────┘
```

### Sezione Metodologia (footer)

Testo trasparente su:
- Fonte: Cloudflare Radar (dati basati su ~17% del traffico internet globale che transita su Cloudflare)
- Il ranking misura la popolarità di destinazione (quante persone visitano un dominio), non il traffico referral
- I dati sono proiezioni relative, non conteggi assoluti di visitatori
- I bucket per domini fuori top 100 indicano un range (es. "top 1000" = tra posizione 501 e 1000)
- Aggiornamento: settimanale, ogni lunedì

---

## Migrazione da v1

Il v1 aveva un modello dati `schema_version: "1.0"` con campi come `ai_index_24mo`, `bump_chart_6mo`, `big4_6mo` — tutti vuoti e basati su endpoint inesistenti. Il v2 li sostituisce completamente.

- Rinominare i modelli Pydantic esistenti o crearne di nuovi con `schema_version: "2.0"`
- Lo snapshot v1 (`2026-W16.json`) resta nel repo come storico ma non viene usato dal template v2
- Il template `tracker.html.jinja` viene riscritto
- Il file `charts.py` (SVG server-side) viene rimosso — i grafici v2 sono JS client-side
- I file `radar_client.py`, `collector.py`, `pages_analytics.py` vengono riscritti

---

## Workflow GitHub Actions

Il workflow `tracker-weekly.yml` resta invariato nella struttura (cron lunedì, via Cloudflare Worker). Gli step interni cambiano:

1. `update_tracker.py` chiama il nuovo collector con 64 endpoint
2. Salva snapshot v2
3. Rebuild SSG genera la pagina `/tracker/` con i nuovi dati
4. Commit, push, deploy

---

## Lista piattaforme AI monitorate

La lista dei 17 domini è definita in un file di configurazione (`config/tracker_platforms.yaml` o costante Python) per facilitare aggiunte future senza modificare il collector.

```yaml
platforms:
  - domain: chatgpt.com
    label: OpenAI ChatGPT
    type: chatbot
  - domain: openai.com
    label: OpenAI
    type: chatbot
  - domain: claude.ai
    label: Anthropic Claude
    type: chatbot
  - domain: anthropic.com
    label: Anthropic
    type: chatbot
  - domain: deepseek.com
    label: DeepSeek
    type: chatbot
  - domain: gemini.google.com
    label: Google Gemini
    type: chatbot
  - domain: copilot.microsoft.com
    label: Microsoft Copilot
    type: chatbot
  - domain: meta.ai
    label: Meta AI
    type: chatbot
  - domain: grok.com
    label: xAI Grok
    type: chatbot
  - domain: character.ai
    label: Character.AI
    type: chatbot
  - domain: poe.com
    label: Poe
    type: chatbot
  - domain: mistral.ai
    label: Mistral
    type: chatbot
  - domain: perplexity.ai
    label: Perplexity
    type: ai_search
  - domain: brave.com
    label: Brave Search
    type: ai_search
  - domain: kagi.com
    label: Kagi
    type: ai_search
  - domain: huggingface.co
    label: Hugging Face
    type: ai_tool
  - domain: notion.so
    label: Notion AI
    type: ai_tool
```
