# Tracker "Stato della ricerca in Italia" — Design spec

**Data**: 2026-04-12
**Stato**: approvato post-brainstorming, pronto per implementation plan
**Scope**: sottosistema nuovo di OsservatorioSEO, v1 free tier

## Contesto e motivazione

OsservatorioSEO oggi pubblica news quotidiane, dossier editoriali e deep analysis su item critici. Manca un tracker strutturato e quantitativo che risponda alle domande strategiche che un SEO italiano si fa ogni mattina sul rapporto **AI vs Search**.

Il riferimento ispirazionale è chatgpt-vs-google.com, che però misura *referral traffic share* aggregato da un panel di siti. OsservatorioSEO non ha un panel. Questa spec costruisce un'alternativa realistica basata su **fonti dati gratuite** che risponde a domande affini — adozione AI in Italia, erosione search tradizionale, dinamiche competitive — con un angolo editoriale unico per il mercato italiano.

## Obiettivi (e non-obiettivi)

**Obiettivi v1**:
- Dashboard live `/tracker/` aggiornato **settimanalmente** via cron
- Report editoriale mensile `/tracker/report/<YYYY-MM>/` in stile dossier pillar già esistente
- **Zero costi ricorrenti**: solo API gratuite
- 7 grafici presentati in ordine di priorità editoriale che rispondono a domande SEO operative
- Metodologia trasparente, limiti dichiarati

**Non-obiettivi**:
- Misurare referral traffic share (richiederebbe SimilarWeb / panel a pagamento)
- Replicare chatgpt-vs-google.com 1:1
- Dashboard interattivo client-side (no JavaScript framework)
- Tracking di query specifiche SEO-level (richiederebbe DataForSEO / paid tier)
- Forecasting/proiezioni lineari (rischio di comunicare certezze che non abbiamo)

## Target audience

Lettori principali (priorità descrescente):
1. **SEO consultant freelance / agenzia** italiani, che devono giustificare allocazioni budget AI vs tradizionale ai clienti
2. **In-house SEO** di media/e-commerce/finance italiani, che devono costruire roadmap 6-12 mesi
3. **SEO manager / head of SEO**, che vogliono dati condivisibili con il C-level
4. **Content strategist** e **editori** che monitorano il canale di distribuzione dei contenuti

**Non** target: principianti, curiosi generici, lettori non-SEO. Tutti i testi possono assumere conoscenza base del mercato SEO.

## Le 8 domande strategiche a cui il tracker risponde

Ogni grafico è mappato a una o più di queste domande. Se un grafico non risponde a nessuna, si taglia.

1. Sto perdendo traffico Google, è AI Overviews o altro?
2. Google sta cedendo quote davvero? A chi (Bing/DDG o AI)?
3. Il mio settore è già stato colpito o no?
4. Chi è il competitor AI emergente, quanto velocemente cresce?
5. Devo ottimizzare per citazioni LLM o è presto?
6. A che ritmo sta crescendo l'adozione AI in Italia, e di quanto è già cambiato il mercato? *(domanda di interpretazione del trend, non di forecasting)*
7. L'interesse AI si traduce in uso reale o è solo curiosità? *(deferred a v2 con Google Trends)*
8. Di questi dati di chi mi posso fidare? → metodologia trasparente

## Dataset (v1)

Due fonti, entrambe gratuite.

### 1. Cloudflare Radar API (gratis con API token)

Endpoint rilevanti:
- `GET /radar/ranking/top?location=IT&name=ai` — top N domini in categoria AI, filtro Italia
- `GET /radar/ranking/top?location=IT&name=search_engines` — top N search engines Italia
- `GET /radar/ranking/timeseries_groups?location=IT&name=<category>&dateRange=52w` — timeseries rank per categoria
- `GET /radar/ranking/domain/{domain}?location=IT&dateRange=52w` — trajectory di un singolo dominio
- `GET /radar/http/timeseries_groups/device_type?location=IT&dateRange=52w` — traffic trends
- `GET /radar/ranking/timeseries?location=IT&name=<category>` — traffic index per categoria (se disponibile)

Cosa otteniamo:
- **Rank assoluto** (integer) per dominio in categoria, filtrabile per paese
- **Delta rank** nel tempo
- **Traffic change %** per dominio vs periodo precedente
- **Timeseries 12-52 settimane** per trend
- **Categorie di destinazione** (AI, Search Engines, News, E-commerce, Finance, Entertainment, Health, Education, Gaming, Travel, Reference, Social Media…)

Cosa NON otteniamo:
- Visite assolute in numeri
- Market share % aggregato tra competitor
- Query content (non è dato SERP)
- Referrer-side data (non misura "da cosa arriva il traffico ai siti terzi")

**Rate limit**: Cloudflare Radar ha limiti generosi sul free tier. Non è un problema per run settimanali.

### 2. Cloudflare Pages Analytics (proprie di OsservatorioSEO, gratis)

Endpoint GraphQL Cloudflare (stesso account del deploy). Estraiamo:
- Top referrer source (Google, Bing, DuckDuckGo, ChatGPT, Claude, Perplexity, Direct, Other)
- Ultimi 30 giorni
- Solo valori **relativi** (%), mai assoluti

Usato **una sola volta** nel Grafico 7 come trasparenza editoriale ("ecco da dove arriva il nostro traffico, 1 data point, non rappresentativo ma trasparente").

## I 7 grafici

Ordine corrisponde a layout top-to-bottom della pagina `/tracker/`.

### Grafico 1 — "AI vs Internet in Italia, 24 mesi" (headline)

**Tipo**: line chart, doppia linea, 24 mesi  
**Risponde a**: Q1, Q6  
**Layer**: Headline, primo schermo

**Dati**:
- Linea A (verde primario): indice traffico categoria "AI" in Italia, Radar timeseries, normalizzato a 100 al mese -24
- Linea B (grigio tenue): indice traffico totale Internet in Italia, Radar timeseries, normalizzato a 100 al mese -24

**Annotazioni inline** (date precise, eventi reali):
- Rollout AI Overviews Italia
- Claude web search disponibile
- Gemini 2.0 general availability
- Altri eventi rilevanti che emergeranno

**Perché questo grafico per primo**: comunica subito se **AI in Italia sta crescendo più velocemente del resto del web o no**. Se la linea verde distacca la grigia, è adozione reale (non semplice crescita generale del traffico internet). Se vanno a braccetto, è crescita normale. Risposta concreta in un'occhiata.

### Grafico 2 — "A chi cede Google in Italia?" (composizione del mercato)

**Tipo**: stacked area chart, 12 mesi  
**Risponde a**: Q2

**Dati**: normalizzazione share relativa tra queste 3 categorie:
- Area base (verde primario): Google (`google.com`)
- Area intermedia (giallo): altri search engines aggregati (Bing + DuckDuckGo + Yahoo + Ecosia)
- Area top (arancio): AI services totali (somma dei top 10 AI domains)

Linea sottile sovrapposta: Google da solo in share percentuale, per evidenziare la curva di erosione.

**Perché questo grafico**: un SEO vuole sapere *a chi* sta perdendo traffico Google, perché l'azione è diversa. Se cede ad altri search → SEO tradizionale multi-engine. Se cede ad AI → investimento in LLM optimization.

### Grafico 3 — "Chi ha scavalcato chi" (dinamiche competitive AI)

**Tipo**: bump chart, top 10 AI Italia, 6 mesi  
**Risponde a**: Q4, Q5

**Dati**:
- 10 linee, una per ogni top-10 AI domain in Italia al mese corrente
- Asse X: settimane (6 mesi = ~26 settimane)
- Asse Y: rank (1 in alto, 10 in basso)
- Label dominio a entrambe le estremità (inizio e fine riga)
- Linee che si incrociano quando c'è overtake

**Annotazioni inline**: "Claude scavalca Perplexity — marzo 2026" e simili.

**Colori**: verde primario per top 3, giallo per 4-6, arancio per 7-10. Le linee grigie/ambra di sfondo per contesto.

**Perché questo grafico**: narrativa pura. Un SEO ci guarda e capisce il mercato competitivo senza leggere. È il grafico che genera i **titoli** dei report editoriali mensili.

### Grafico 4 — "Quale settore è già colpito" (heatmap category × mese)

**Tipo**: heatmap, 6 mesi  
**Risponde a**: Q3

**Dati**:
- Righe: categorie Radar (News, E-commerce, Finance, Entertainment, Health, Education, Gaming, Travel, Reference, Social Media) — ordine fisso + categoria "AI" in evidenza separata in alto
- Colonne: ultimi 6 mesi (colonna = 1 mese)
- Celle: traffic % change MoM per categoria in Italia

**Coloring**:
- Rosso → calo forte (<-10%)
- Arancio → calo moderato (-10% a -3%)
- Grigio → stabile (-3% a +3%)
- Verde chiaro → crescita moderata (+3% a +10%)
- Verde primario → crescita forte (>+10%)

**Ordinamento righe**: per magnitude del delta nell'ultimo mese (chi si muove di più in alto).

**Perché**: è il grafico **actionable per settore**. Un SEO di media cerca "News", un e-commerce cerca "E-commerce" e vede subito se il suo mercato sta soffrendo.

**Rischio**: Radar potrebbe non avere tutte le categorie con granularità paese-specifica affidabile. **Degrade plan**: se <5 categorie hanno dati IT affidabili, si mostra heatmap globale con nota "dati Italia non disponibili per queste categorie".

### Grafico 5 — "Biggest movers" (momentum 30 giorni)

**Tipo**: dual horizontal bar chart  
**Risponde a**: Q4 (short term)

**Dati**:
- Colonna sinistra (verde): top 5 AI services con maggiore crescita traffic % ultimi 30 giorni Italia
- Colonna destra (arancio): top 5 AI services con maggior calo
- Barre proporzionali alla magnitudo del delta
- Badge "★ MOVER OF THE MONTH" al primo classificato (positivo o negativo più estremo)

**Uso editoriale**: il mover of the month è cliccabile e porta al report mensile che lo approfondisce.

**Perché**: è l'**hook editoriale ricorrente**. Il titolo del report aprile 2026 sarà generato da questo grafico: "Claude +42%: il mover di marzo 2026 in Italia".

### Grafico 6 — "I 4 big AI — trend 6 mesi" (small multiples)

**Tipo**: small multiples 2×2 line chart  
**Risponde a**: Q4, Q5 (long term)

**Dati**:
- 4 pannelli: ChatGPT (`chat.openai.com`), Gemini (`gemini.google.com`), Claude (`claude.ai`), Perplexity (`perplexity.ai`)
- Per ciascuno: **una sola linea** che mostra il traffic index 6 mesi (normalizzato 0-100 rispetto al massimo del panel nel periodo)
- Rank **corrente** come numero grande nel corner in alto a destra del panel (es. `#3`)
- Rank **6 mesi fa** come numero piccolo grigio accanto tra parentesi (es. `(era #12)`)
- Asse Y **indipendente** per panel (ranges molto diversi)
- Titolo-frase per ogni panel, es. "Claude: da #12 a #3 in 6 mesi"

**Perché**: confronto visuale a parità di formato. Un grafico singolo con 4 serie sarebbe illeggibile per via dei range. Small multiples risolvono.

### Grafico 7 — "Da dove arriviamo noi" (trasparenza)

**Tipo**: single horizontal bar chart  
**Risponde a**: Q8 (trust)

**Dati**:
- Fonti referrer di OsservatorioSEO ultimi 30 giorni, proporzionali (%): Google, Bing, DDG, ChatGPT, Claude, Perplexity, Direct, Other
- Numeri assoluti **nascosti**, solo percentuali

**Disclaimer prominente sopra il grafico**:
> 1 sito solo, NON rappresentativo del mercato italiano. Incluso per trasparenza editoriale.

**Perché**: credibilità. Dimostra che non nascondiamo i nostri stessi numeri. Costruisce trust nei confronti del lettore SEO scettico.

## Architettura backend

### Nuovo modulo Python: `src/osservatorio_seo/tracker/`

```
src/osservatorio_seo/tracker/
├── __init__.py
├── radar_client.py       # Wrapper httpx per Cloudflare Radar API
├── pages_analytics.py    # Wrapper Cloudflare Pages Analytics GraphQL
├── models.py             # Pydantic: TrackerSnapshot, CategoryRank, DomainMovement
├── collector.py          # Pipeline: fetch + normalize + persist settimanale
├── charts.py             # Generazione SVG statici (1 funzione per chart type)
└── report.py             # Generazione report mensile via PremiumWriter
```

### Storage

`data/tracker/` directory nuova, dentro il repo:

```
data/tracker/
├── snapshots/
│   ├── 2026-W15.json       # snapshot settimanale con tutti i dati raw
│   ├── 2026-W16.json
│   └── ...
├── reports/
│   ├── 2026-04.json        # report mensile editoriale (output PremiumWriter)
│   └── ...
└── index.json               # indice snapshot + reports disponibili
```

Gli snapshot settimanali contengono **tutto il raw data** che serve per rigenerare i grafici senza nuove chiamate API. Idempotenza garantita.

### Cron weekly

GitHub Actions cron che ogni lunedì mattina (dopo il daily normale):
1. Chiama `collector.collect_week()` → fetch Radar + Pages Analytics
2. Salva snapshot in `data/tracker/snapshots/<YYYY-WW>.json`
3. Invoca `charts.render_all()` che produce gli SVG statici in memoria
4. `publisher._ssg_tracker()` renderizza la pagina `/tracker/` con gli SVG inline
5. Se è il primo lunedì del mese: invoca `report.generate_monthly(month-1)` che chiama PremiumWriter/Sonnet 4.5 con i 4 snapshot del mese precedente e produce il report editoriale
6. Commit + push + deploy

### Chart generation — SVG statico in Python

Modulo `tracker/charts.py` contiene una funzione per tipo di chart. Ogni funzione:
- Prende i dati come argomento tipizzato (pydantic model)
- Ritorna una stringa SVG completa, con viewBox impostato per essere responsive
- Usa i colori del tema OsservatorioSEO (`#00f63e` primary, `#f5a623` arancio, `#131313` background, `#919191` outline)
- Font: inherit da `font-mono` del sito (no `font-family` hardcoded nell'SVG, lascia CSS gestire)
- Niente dipendenze esterne pesanti: uso `svgwrite` oppure stringhe Jinja puri (scelta in fase di implementation)

**Template Jinja** `templates/pages/tracker.html.jinja`:
- Include gli SVG via `|safe` dopo generazione
- Layout: sezioni top-to-bottom per ogni grafico (1→7)
- Accordion `> METODOLOGIA` aperto di default in fondo
- Header con data ultimo update, prominente

### Data flow summary

```
┌─────────────────┐    ┌─────────────────┐
│ Cloudflare      │    │ Cloudflare      │
│ Radar API       │    │ Pages Analytics │
└────────┬────────┘    └────────┬────────┘
         │                      │
         ▼                      ▼
    ┌────────────────────────────────┐
    │ tracker/collector.py           │
    │  - fetch raw data              │
    │  - normalize to models         │
    │  - compute deltas              │
    └────────┬───────────────────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │ data/tracker/snapshots/        │
    │    <YYYY-WW>.json              │
    └────────┬───────────────────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │ tracker/charts.py              │
    │  - 7 chart generators → SVG    │
    └────────┬───────────────────────┘
             │
             ▼
    ┌────────────────────────────────┐
    │ publisher._ssg_tracker         │
    │  - render template + SVG inline│
    │  - write site/tracker/         │
    └────────┬───────────────────────┘
             │
             ▼
       (monthly, first Monday)
    ┌────────────────────────────────┐
    │ tracker/report.py              │
    │  - aggregate last 4 snapshots  │
    │  - invoke PremiumWriter        │
    │  - save data/tracker/reports/  │
    │  - render /tracker/report/YYYY-│
    │    MM/ page                    │
    └────────────────────────────────┘
```

## Report editoriale mensile

Struttura del report `/tracker/report/<YYYY-MM>/`, stile coerente con i dossier pillar esistenti:

- **Hero**: titolo generato dal mover of the month (es. "Claude +42% a marzo 2026: il mover del mese in Italia")
- **Executive summary**: 3-5 bullet strategici (output PremiumWriter)
- **Tutti i 7 grafici** riusati con annotazioni specifiche del mese
- **Narrative editoriale** (800-1200 parole, paragrafi brevi, voce impersonale — segue le regole `feedback_editorial_voice.md` e `feedback_tailwind_font_mono.md` in memoria)
- **Takeaways operativi** (5 bullet)
- **Outlook** (200-400 parole)
- Linka dal dashboard live come "Report aprile 2026 →"

Il report è generato via `PremiumWriter.write_tracker_report(month, snapshots)` — nuovo metodo da aggiungere alla classe esistente con prompt dedicato che segue gli stessi principi di `write_pillar`.

**Costo stimato**: ~€0.05-0.08 per report mensile (Sonnet 4.5, input più ricco del pillar standard). Totale annuo: ~€1.

## Integrazione con OsservatorioSEO esistente

- **Header nav**: aggiunto link `TRACKER` tra `DOSSIER` e `DOCS`
- **Homepage**: sezione piccola "Ultimo tracker" con link e mini-teaser dei 2 grafici headline
- **Sitemap**: `/tracker/` priority 0.9 changefreq weekly + ogni `/tracker/report/<YYYY-MM>/` priority 0.7
- **JSON-LD**: Schema `Dataset` per la pagina tracker + `Article` per ogni report mensile

## Metodologia e trasparenza (visibile nella pagina)

Sezione `> METODOLOGIA` aperta di default contiene:

1. **Fonti dati** — Cloudflare Radar + Cloudflare Pages Analytics, con link alle rispettive documentazioni
2. **Cosa misurano e cosa no** — specifico: "Cloudflare Radar misura popolarità di destinazione (quanti italiani visitano chat.openai.com), non referral traffic (quanti siti italiani ricevono visite da chat.openai.com). Queste due metriche sono correlate ma non identiche."
3. **Aggiornamento** — "Dati aggiornati settimanalmente ogni lunedì alle 08:00 Europe/Rome"
4. **Campione Cloudflare** — "Cloudflare Radar osserva ~17% del traffico internet globale. I dati sono proiezioni basate su questo campione, non misurazioni totali."
5. **Perché non vedete 'market share %'** — "Lo share di mercato richiederebbe dati di panel a pagamento (SimilarWeb, Datos.live). Questo tracker usa solo fonti gratuite e pubblica indici normalizzati 0-100 dove 100 = dominio più popolare in categoria."
6. **Limiti dichiarati** — elenco esplicito di cosa non sappiamo
7. **Suggerimenti e correzioni** — invito a contattare la redazione per segnalazioni

## Future additions (v2+, NON nel v1)

### Google Trends integration (deferred)

**Perché deferred**: `pytrends` è una library non ufficiale che fa scraping di Google Trends. Ha rischi di rate limiting, cambiamenti silenziosi del frontend Google, e affidabilità operativa variabile. Includerlo in v1 aggiungerebbe complessità operativa senza un meccanismo di graceful degradation già testato.

**Piano futuro**: quando v1 è stabile (≥4 settimane di snapshot consecutivi pubblicati senza errori), valutare aggiunta Google Trends con:
- Caching aggressivo (1 chiamata/settimana, retry con backoff)
- Fallback: se pytrends fallisce, il grafico headline Chart 1 si rende senza la seconda linea, con nota "dati Google Trends non disponibili questa settimana"
- Prevedibile uso: arricchire Grafico 1 con linea "Interesse query ChatGPT/Claude in Italia" per incrociare demand-side con adoption-side

**Grafico che si sbloccherebbe**: Grafico 1 tornerebbe dual-axis come proposto nel brainstorming originale, rispondendo alla Q7 ("l'interesse si traduce in uso reale?"). Nel frattempo, in v1, Grafico 1 usa solo dati Radar (AI index vs total internet index) che comunica una storia leggermente diversa ma ugualmente valida.

### Altre future additions candidate

- **DataForSEO SERP integration** (tier paid): "% di query commerciali IT che mostrano AI Overviews questa settimana" — richiede ~€15-20/mese ma risponde alla Q5 in modo molto specifico
- **LLM rank tracker**: per N keyword italiane tracciate, quali domini cita ChatGPT/Perplexity — richiede DataForSEO Labs API (paid)
- **Email digest mensile**: email newsletter che riassume il report mensile
- **RSS feed**: `/tracker/feed.xml` con un item per report mensile
- **API pubblica**: JSON endpoint con ultimi snapshot per sviluppatori terzi

## Rischi e mitigazioni

| Rischio | Probabilità | Mitigazione |
|---|---|---|
| Cloudflare Radar cambia schema API | Bassa | Wrapper isolato in `radar_client.py`, adapter pattern, test unitari su fixture |
| Categoria `AI` in Radar non filtra per Italia affidabilmente | Media | Degrade a globale con nota metodologica; monitoraggio qualità dati in collector |
| Heatmap categorie incomplete per IT (Grafico 4) | Media | Degrade a globale con nota; se meno di 5 categorie disponibili, si taglia il grafico e si aggiunge al future work |
| SVG generator produce markup invalid | Bassa | Test di integrità SVG in CI; validazione con lxml |
| Data snapshot corruption | Bassa | Snapshot immutabili, scritti con atomic rename; git history è il backup |
| Pages Analytics referrer data troppo pochi (sito ancora piccolo) | Alta | Accettato per v1: Grafico 7 con disclaimer esplicito "1 sito solo" |
| Rate limit Cloudflare Radar | Molto bassa | Run settimanale singolo, <30 endpoint call totali |

## Open questions

Niente di critico. Cose da decidere in fase di implementation plan:
- Libreria SVG: `svgwrite` vs stringhe Jinja pure — valutare in base a complessità chart
- Storage format snapshot: JSON flat vs JSON nested — pydantic gestirà entrambi
- Esattamente quali categorie Radar includere nella heatmap (Grafico 4) — dipende dai dati reali
- Colori esatti per gradiente heatmap — da validare sul tema del sito

## Acceptance criteria per v1

Il tracker è "done" quando:
1. Cron weekly gira con successo per 4 settimane consecutive (snapshot salvati, commit automatico)
2. Dashboard `/tracker/` è live con tutti e 7 i grafici renderizzati
3. Pagina è responsive mobile (test a 375px)
4. Sezione metodologia è completa e chiara
5. Header nav mostra `TRACKER` e il link funziona
6. Sitemap include gli URL tracker
7. Almeno 1 report mensile editoriale è pubblicato
8. Nessun dato sensibile (API token) è committato
9. Tutti i test unitari passano

## Fuori scope

- Autenticazione utente
- Personalizzazione per utente
- Alert/notifiche automatiche
- Feed RSS (in future additions)
- Export CSV/Excel
- Embedding dei grafici su altri siti
- API pubblica
- Comparazione con altri paesi (solo Italia in v1)
- Dati storici >24 mesi
