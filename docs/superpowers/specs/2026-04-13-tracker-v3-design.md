# Tracker v3 — Intelligence Report settimanale

**Data:** 2026-04-13
**Sostituisce:** tracker-v2-design.md

## Principio

Il tracker è un **report di intelligence strategica** che risponde a 9 domande che un SEO professionista si pone. Ogni sezione ha: la domanda, il perché la monitoriamo (la teoria), il grafico, la risposta (il come leggere il dato), la nota metodologica. Italia e Mondo sono sempre **affiancati**, mai nascosti dietro un toggle. Tutte le domande e le risposte sono **universali** — non legate a un player specifico. Se domani Claude supera ChatGPT, il tracker si adatta automaticamente.

## Linguaggio

- Mai usare termini tecnici non SEO ("bucket", "resolver", "DNS query")
- "Fascia top 1.000" invece di "bucket 1000"
- "Popolarità del dominio" invece di "ranking DNS"
- "Scansione" o "crawling" (termine noto ai SEO) invece di "fetch"
- Numeri sempre contestualizzati: non "#9" da solo, ma "#9 tra tutti i siti in Italia"

## Struttura della pagina

```
┌─────────────────────────────────────────────────┐
│  HEADER: titolo + data aggiornamento            │
├─────────────────────────────────────────────────┤
│  HERO: il dato della settimana (numero grande)  │
├─────────────────────────────────────────────────┤
│  4 KPI cards (dinamiche, non legate a un player)│
├─────────────────────────────────────────────────┤
│  10 SEZIONI (una per domanda)                   │
├─────────────────────────────────────────────────┤
│  TRASPARENZA: cosa misurano questi dati         │
├─────────────────────────────────────────────────┤
│  METODOLOGIA: fonte, campione, limiti           │
└─────────────────────────────────────────────────┘
```

---

## Hero

Un numero grande con contesto. Dinamico — mostra automaticamente il dato più rilevante della settimana.

Logica di scelta (in ordine di priorità):
1. Se una piattaforma AI entra nella top 100 per la prima volta → quello è il dato
2. Se una piattaforma cambia fascia (es. da "tra i primi 1.000" a "tra i primi 500") → segnalare
3. Se il crawling "per gli utenti" cambia di più di 5 punti percentuali → segnalare
4. Fallback: posizione della piattaforma AI più popolare in Italia (qualunque essa sia)

Il hero non nomina mai un player in modo hardcodato nel codice. La logica cerca la piattaforma AI con il rank migliore in `ai_platforms_it` e costruisce il testo dinamicamente.

## 4 KPI Cards

Tutte dinamiche — cercano automaticamente il primo/migliore valore nei dati:

| KPI | Come si calcola | Esempio |
|-----|-----------------|---------|
| AI più popolare in Italia | Piattaforma con rank migliore in `ai_platforms_it` | chatgpt.com #9 ↑ |
| Crawling AI per gli utenti | Ultimo punto `crawl_purpose_it` → valore "User Action" | 57% |
| Traffico bot in Italia | Ultimo punto `bot_human_it` → `bot_pct` | 20% ↑ |
| Bot AI più attivo | Agente con valore più alto nell'ultimo punto di `ai_bots_ua_it` | ChatGPT-User |

Ogni card: valore, freccia trend (vs settimana precedente se disponibile), label.

---

## Le 9 sezioni

---

### Sezione 1: "Quali AI usano gli italiani?"

**Perché lo monitoriamo:**
Per fare SEO nell'era dell'AI, serve sapere dove vanno gli utenti. Per 25 anni la risposta è stata "Google". Se gli utenti si spostano verso piattaforme AI per cercare informazioni, un SEO deve saperlo per studiare come apparire su quelle piattaforme. Inoltre, confrontando Italia e Mondo si possono anticipare i trend: i mercati anglofoni adottano prima, l'Italia segue di qualche mese.

**Grafico A:** Linee nel tempo — posizione delle piattaforme AI che sono (o sono state) nella top 100 in Italia. 52 settimane. Se oggi solo una piattaforma è in top 100, ci sarà una sola linea. Quando altre entrano, le linee si aggiungono automaticamente.
- Asse X: tempo
- Asse Y: posizione (invertito: #1 in alto)
- Una linea per ogni piattaforma AI presente in top 100 (colore distinto)
- Annotazione: posizione attuale a destra di ogni linea

**Grafico B (sotto):** Tabella completa delle 17 piattaforme monitorate.

| Piattaforma | Tipo | Italia | Mondo | Gap | Segnale |
|-------------|------|--------|-------|-----|---------|

Regole di visualizzazione:
- Top 100: posizione esatta con "#" (es. "#9")
- Fuori top 100: "tra i primi 500", "tra i primi 1.000", ecc.
- Oltre 200.000: "oltre 200.000"
- Colonna Gap: se il Mondo è migliore dell'Italia → evidenziato come "🟡 In crescita nel mondo" (segnale anticipatore)
- Colonna Segnale: freccia verde/rossa/grigia vs settimana precedente
- Ordinamento: per fascia di posizione (i più popolari in alto)

**Come leggere questo dato:**
"La tabella mostra la popolarità di ogni piattaforma AI in Italia e nel mondo. Quando una piattaforma migliora posizione a livello mondiale prima che in Italia, è un segnale anticipatore: storicamente i mercati anglofoni anticipano i trend italiani. Oggi {top_ai_domain} è la piattaforma AI più popolare in Italia (posizione #{top_ai_rank}). Le piattaforme da tenere d'occhio sono quelle che mostrano un gap tra mondo e Italia — indicano cosa potrebbe arrivare nei prossimi mesi."

**Nota metodologica (collapsible):**
"La posizione è basata sulla popolarità del dominio misurata da Cloudflare Radar (circa il 17% del traffico internet globale). Non misura le visite dirette, ma la frequenza con cui il dominio viene richiesto. Per i domini fuori dalla top 100, la posizione è una fascia approssimativa. I dati vengono raccolti ogni settimana — nel tempo si costruisce lo storico per osservare le tendenze."

**Dati necessari:** `ai_platforms_it`, `ai_platforms_global`, `top10_it` (per timeseries delle AI in top 100).

---

### Sezione 2: "Cosa fanno i bot AI con i tuoi contenuti?"

**Perché lo monitoriamo:**
Questa è la domanda più importante per un SEO. Sapere CHE i bot AI scansionano i siti non basta — serve sapere PERCHÉ. La differenza è strategica: se scansionano per servire gli utenti, il tuo contenuto viene distribuito (è un'opportunità). Se scansionano per addestrare i modelli, il tuo contenuto viene assorbito nel training (e poi il modello risponde senza citarti). La risposta cambia completamente la strategia: nel primo caso vuoi essere crawlabile, nel secondo potresti voler proteggere il contenuto.

**Grafico:** Due grafici a area stackata affiancati — Italia e Mondo (12 settimane).
- Asse X: settimane
- Asse Y: percentuale (0-100%)
- Colori:
  - **Per gli utenti** (User Action): verde #00f63e
  - **Addestramento modelli** (Training): rosso #e24c4c
  - **Scopo misto** (Mixed Purpose): arancione #f5a623
  - **Ricerca** (Search): blu #4ca6e2
  - **Non dichiarato** (Undeclared): grigio #919191

**Legenda esplicativa (sempre visibile):**
- **Per gli utenti** — Un utente ha fatto una domanda all'AI, che ha recuperato la tua pagina per rispondere in tempo reale. È il nuovo "traffico organico": il tuo contenuto viene servito, ma l'utente potrebbe non arrivare mai sul tuo sito.
- **Addestramento modelli** — Il bot raccoglie contenuti per addestrare o aggiornare i modelli AI. Il tuo contenuto di oggi influenza le risposte AI di domani.
- **Scopo misto** — Il bot dichiara di servire sia gli utenti che l'addestramento. Non è possibile separare le due funzioni.
- **Ricerca** — Il bot costruisce un indice per la funzione search dell'AI (es. ChatGPT Search, Perplexity). Simile a come Googlebot indicizza per Google.
- **Non dichiarato** — L'operatore del bot non ha dichiarato lo scopo.

**Come leggere questo dato:**
"In Italia, il {user_action_it}% del crawling AI serve a rispondere agli utenti in tempo reale. Nel mondo, solo il {user_action_global}%. Questa differenza è significativa: indica che i siti italiani sono già attivamente utilizzati dall'AI come fonte di risposte. Se la quota 'addestramento modelli' inizia a crescere, significa che le AI company stanno investendo nel training di modelli migliori per la lingua italiana — il contenuto che pubblichi oggi sarà nel modello di domani."

**Dati necessari:** `crawl_purpose_it`, `crawl_purpose_global`.

---

### Sezione 3: "Quali aziende AI scansionano di più i siti italiani?"

**Perché lo monitoriamo:**
Ogni azienda AI ha un bot diverso con uno scopo diverso. Sapere chi scansiona i siti italiani e quanto aiuta a capire quale azienda sta investendo di più nel mercato italiano e per quale motivo. Se il bot di OpenAI domina, il focus è su ChatGPT. Se il bot di Anthropic cresce, Claude sta arrivando. Se Meta sale, il contenuto finisce nei modelli Llama che alimentano prodotti usati da miliardi di persone. Ogni crescita è un segnale strategico.

**Grafico:** Due grafici a linee affiancati — Italia e Mondo (12 settimane). Legenda cliccabile per mostrare/nascondere le singole linee.
- Asse X: settimane
- Asse Y: percentuale del crawling AI totale
- Una linea per ogni bot

**Tabella di riferimento (sempre visibile sotto i grafici):**

| Bot | Azienda | Cosa fa con i tuoi contenuti |
|-----|---------|------------------------------|
| ChatGPT-User | OpenAI | Li mostra agli utenti che fanno domande a ChatGPT |
| GPTBot | OpenAI | Li usa per addestrare i prossimi modelli GPT |
| OAI-SearchBot | OpenAI | Li indicizza per la funzione Search di ChatGPT |
| ClaudeBot | Anthropic | Li usa per addestrare Claude e potenzialmente per web search |
| Googlebot | Google | Li indicizza per Google Search e per addestrare Gemini |
| Meta-ExternalAgent | Meta | Li usa per addestrare Meta AI e i modelli Llama |
| Bytespider | ByteDance | Li usa per addestrare i modelli AI di TikTok |
| Bingbot | Microsoft | Li indicizza per Bing (che alimenta anche i risultati di ChatGPT) |
| Applebot | Apple | Li indicizza per Siri e Apple Intelligence |
| Amazonbot | Amazon | Li usa per Alexa e i servizi AI di Amazon |

**Come leggere questo dato:**
"Il bot più attivo sui siti italiani è {top_agent} ({top_agent_pct}%), gestito da {top_agent_company}. A livello mondiale il bot più attivo è {top_agent_global} ({top_agent_global_pct}%). La differenza tra Italia e Mondo indica dove ogni azienda sta concentrando i propri sforzi. Se un bot cresce rapidamente in Italia, quell'azienda sta investendo nel mercato italiano — e probabilmente lancerà o migliorerà il proprio servizio per gli utenti italiani."

**Dati necessari:** `ai_bots_ua_it`, `ai_bots_ua_global`.

---

### Sezione 4: "L'Italia è in anticipo o in ritardo rispetto al mondo?"

**Perché lo monitoriamo:**
I mercati anglofoni (USA, UK) tendono ad adottare le nuove tecnologie prima dell'Italia. Confrontando i dati italiani con quelli mondiali si possono anticipare i trend: se qualcosa sta crescendo nel dato mondiale ma è ancora piccolo in Italia, è probabile che arrivi nei prossimi mesi. Chi lo vede prima ha un vantaggio competitivo. Questo è il "radar" che permette di prepararsi prima dei competitor.

**Grafico:** Barre orizzontali — Italia (verde) vs Mondo (grigio) per ogni metrica chiave.

Metriche (calcolate dinamicamente):
1. AI più popolare: posizione IT vs Mondo
2. Traffico bot (% del totale): IT vs Mondo
3. Crawling per gli utenti (% AI bot): IT vs Mondo
4. Crawling per addestramento (% AI bot): IT vs Mondo
5. Secondo bot AI per attività: % IT vs % Mondo
6. Terzo bot AI per attività: % IT vs % Mondo

Per ogni riga: barra IT, barra Mondo, etichetta "Italia avanti" / "Italia indietro" / "In linea" (calcolata: avanti se IT > Mondo di almeno 20% relativo, indietro se < 20%, altrimenti in linea).

**Come leggere questo dato:**
"Le barre verdi (Italia) e grigie (Mondo) mostrano dove l'Italia è allineata al resto del mondo e dove diverge. Le metriche dove l'Italia è 'indietro' sono quelle che probabilmente cresceranno nei prossimi mesi per allinearsi al dato mondiale. Le metriche dove l'Italia è 'avanti' indicano trend che il resto del mondo potrebbe seguire. Ogni divergenza è un segnale da monitorare."

**Dati necessari:** Ultimo punto di `bot_human_it`, `bot_human_global`, `crawl_purpose_it`, `crawl_purpose_global`, `ai_bots_ua_it`, `ai_bots_ua_global`, posizione AI top da `ai_platforms_it` e `ai_platforms_global`.

---

### Sezione 5: "Chi sta raccogliendo contenuti italiani per l'addestramento?"

**Perché lo monitoriamo:**
I modelli AI vengono addestrati su enormi quantità di testo. Se i bot di training (GPTBot, ClaudeBot, Meta-ExternalAgent) aumentano la scansione dei siti italiani, significa che le AI company stanno preparando modelli migliori per la lingua italiana. Il contenuto che pubblichi oggi finirà nel training di domani — e influenzerà le risposte che l'AI darà ai tuoi potenziali clienti. Monitorare chi raccoglie e quanto aiuta a capire quale modello sarà più competente in italiano nel prossimo futuro.

**Grafico:** Linee multiple (12 settimane) — solo i bot di training, Italia con linee continue, Mondo con linee tratteggiate.

Bot di training da mostrare:
- GPTBot (OpenAI) — addestra GPT
- ClaudeBot (Anthropic) — addestra Claude
- Meta-ExternalAgent (Meta) — addestra Llama
- Bytespider (ByteDance) — addestra modelli TikTok

**Come leggere questo dato:**
"Questo grafico mostra specificamente i bot che raccolgono contenuti per addestrare i modelli AI. Se uno di questi bot cresce improvvisamente in Italia, significa che quell'azienda sta investendo nel dataset italiano — e il prossimo aggiornamento del loro modello sarà significativamente migliore in italiano. Oggi GPTBot rappresenta il {gptbot_it}% in Italia vs {gptbot_global}% nel mondo. {interpretation}."

Logica di interpretazione dinamica:
- Se tutti stabili: "Nessuna variazione significativa — la fase di raccolta per il mercato italiano procede al ritmo attuale."
- Se uno cresce > 2pp: "{bot_name} è in crescita in Italia (+{delta}pp). {company} sta intensificando la raccolta di contenuti italiani — possibile segnale di un miglioramento del modello per la lingua italiana nei prossimi mesi."
- Se IT < Mondo per un bot: "{bot_name} è meno attivo in Italia ({it}%) che nel mondo ({global}%). Se inizia a crescere, {company} sta estendendo al mercato italiano l'investimento già fatto a livello globale."

**Dati necessari:** `ai_bots_ua_it`, `ai_bots_ua_global` — filtrare solo GPTBot, ClaudeBot, Meta-ExternalAgent, Bytespider.

---

### Sezione 6: "Come sta cambiando l'equilibrio tra i crawler?"

**Perché lo monitoriamo:**
Per 20 anni il crawl budget è stato una questione legata quasi esclusivamente a Googlebot. Oggi i siti vengono scansionati da decine di bot diversi — ognuno con regole e scopi diversi. Se Googlebot perde quota relativa non è perché Google crawla meno, ma perché gli altri crescono. Questo cambia il modo in cui un SEO gestisce il proprio sito: il robots.txt, il crawl budget, la velocità del server, la struttura dei link interni — tutto deve tenere conto di crawler multipli.

**Grafico:** Due grafici a area stackata affiancati — Italia e Mondo (12 settimane). Ogni area è un bot. Mostra come le quote relative cambiano nel tempo.

**Come leggere questo dato:**
"L'equilibrio tra i crawler sta cambiando. Googlebot rappresenta il {googlebot_it}% del crawling AI in Italia (era {googlebot_it_start}% {N} settimane fa). Se la quota di Googlebot cala, non significa che Google scansiona meno — significa che gli altri bot crescono più rapidamente. Per un SEO, questo ha implicazioni pratiche: il server deve gestire più richieste automatizzate, il robots.txt deve considerare più user-agent, e le strategie di indicizzazione non possono più focalizzarsi solo su Google."

**Dati necessari:** `ai_bots_ua_it`, `ai_bots_ua_global`.

---

### Sezione 7: "Il tuo settore è nel mirino dell'AI?"

**Perché lo monitoriamo:**
I bot AI non scansionano tutti i settori allo stesso modo. Se lavori nel retail, nel turismo o nel software, il volume di scansione AI sul tuo settore è molto più alto della media. Sapere quanto il tuo settore è esposto aiuta a capire l'urgenza: se il 21% di tutto il crawling AI riguarda il retail, un ecommerce manager deve avere una strategia AI. Se il tuo settore è poco scansionato, hai più tempo per prepararti.

**Grafico:** Barre orizzontali affiancate — Italia (verde) e Mondo (grigio). Top 10 settori, ordinati per volume in Italia. "Altro" escluso.

**Come leggere questo dato:**
"Il settore più scansionato dall'AI in Italia è {top_industry_it} ({top_pct_it}%). A livello mondiale è {top_industry_global} ({top_pct_global}%). Se il tuo settore è in questa lista, l'AI sta già utilizzando massivamente i contenuti dei tuoi competitor. I settori dove l'Italia ha una percentuale più alta del mondo (es. Travel & Tourism) riflettono le specificità dell'economia italiana."

**Nota:** "I settori sono classificati da Cloudflare in base al dominio del sito scansionato. La percentuale indica quanta parte del crawling AI totale riguarda quel settore."

**Dati necessari:** `industry_it`, `industry_global`.

---

### Sezione 8: "La pressione dei bot AI sui siti italiani sta crescendo?"

**Perché lo monitoriamo:**
Se la quota di traffico automatizzato cresce, cambia tutto per un SEO: le metriche di analytics diventano meno affidabili (bounce rate, tempo sulla pagina, conversioni includono traffico non umano), il server deve gestire più richieste, e il crawl budget diventa una risorsa contesa. Sapere quanto traffico bot ricevono i siti italiani — e se il trend è in crescita — aiuta a dimensionare il problema e a decidere quando agire.

**Grafico:** Due grafici a area affiancati — Italia e Mondo (12 settimane).
- Area arancione: traffico bot
- Area grigia chiara: traffico umano
- Annotazione: percentuale attuale di bot a destra

**Come leggere questo dato:**
"Il {bot_pct_it}% del traffico verso i siti italiani è generato da bot (era il {bot_pct_it_start}% {N} settimane fa). A livello mondiale la percentuale è {bot_pct_global}%. Il gap tra Italia e Mondo ({delta}pp) suggerisce che la pressione bot sui siti italiani potrebbe ancora crescere per avvicinarsi al dato globale. Per chi fa SEO: se non filtri il traffico bot nelle tue analytics, stai prendendo decisioni basate su dati che includono fino a un quinto di visite non umane."

**Dati necessari:** `bot_human_it`, `bot_human_global`.

---

### Sezione 9: "Come navigano gli italiani?"

**Perché lo monitoriamo:**
Il dispositivo con cui gli utenti navigano determina l'esperienza da ottimizzare. Se il mobile cala in Italia, il desktop torna rilevante per Core Web Vitals, layout e conversioni. Se Android domina, le feature PWA e Chrome-specific funzionano su una fetta più ampia del pubblico. Il trend conta più del dato assoluto — un cambiamento di 5 punti percentuali in pochi mesi può spostare le priorità di ottimizzazione. Il confronto con il mondo rivela se l'Italia ha abitudini diverse che richiedono strategie specifiche.

**Grafico A:** Due grafici a area affiancati — Italia e Mondo (12 settimane).
- Area verde: mobile
- Area grigia: desktop
- Annotazione: percentuali attuali a destra

**Grafico B (sotto):** Barre orizzontali affiancate IT vs Mondo per sistema operativo (top 5).
- Android, Windows, iOS, macOS, Linux
- Verde per Italia, grigio per Mondo

**Come leggere questo dato:**
"L'Italia è storicamente un mercato più mobile del mondo ({mobile_it}% mobile vs {mobile_global}% globale). Il sistema operativo più diffuso in Italia è Android ({android_it}%), che offre pieno supporto a PWA, notifiche push e feature Chrome. iOS è al {ios_it}%, inferiore alla media mondiale. Se il trend mobile è in calo, potrebbe indicare un ritorno al desktop per attività più complesse — o un effetto stagionale. Per un SEO: se il tuo pubblico è italiano, quasi 4 utenti su 10 navigano da Android, e l'esperienza mobile resta prioritaria."

**Nota metodologica (collapsible):**
"Il dato device type e sistema operativo è basato sulle richieste HTTP che transitano dalla rete Cloudflare. Lo user-agent può essere manipolato, ma su scala aggregata è un indicatore affidabile delle tendenze. Il dato 'altro' (smart TV, console, e-reader) è trascurabile (<0.1%)."

**Dati necessari:** Nuovi endpoint da aggiungere al collector:
- `GET /http/timeseries_groups/device_type` con `dateRange=12w` (IT e globale)
- `GET /http/summary/os` con `dateRange=28d` (IT e globale)

**Nuovi campi nel modello TrackerSnapshot:**
```
device_type_it: DeviceTypeTimeseries     # {points: [{date, mobile_pct, desktop_pct}]}
device_type_global: DeviceTypeTimeseries
os_it: list[OSEntry]                     # [{os: "Android", pct: 38.5}, ...]
os_global: list[OSEntry]
```

**Nuove chiamate API:** +4 (2 device_type + 2 os) → totale da 64 a 68 chiamate/settimana.

---

## Sezione 10: "Cosa misurano questi dati — e cosa no"

**Perché questa sezione:**
Un osservatorio credibile dichiara i limiti dei propri dati. Troppi tool SEO presentano numeri senza spiegare cosa significano. OsservatorioSEO fa il contrario: ogni dato è accompagnato dal suo contesto. Questa sezione è fissa e visibile a tutti.

**Risposte affidabili (il trend è chiaro):**
- "Le piattaforme AI stanno diventando più popolari in Italia?" — Sì, il trend è inequivocabile
- "Quali bot AI sono più attivi sui siti italiani?" — Sì, la distribuzione per user-agent è un dato solido
- "Il crawling AI è in crescita?" — Sì, il trend bot vs umani lo conferma
- "I bot AI recuperano contenuti per rispondere ai propri utenti?" — Sì, il tipo "per gli utenti" (User Action) è specifico per questo scopo

**Da interpretare con cautela (il dato è reale ma il contesto conta):**
- "Questa piattaforma AI è il N° sito più visitato in Italia?" — Non esattamente: è il N° dominio più popolare nel traffico che transita da Cloudflare (circa il 17% dell'internet globale). La classifica include anche domini infrastrutturali (CDN, API) che non sono siti visitati dagli utenti. È un indicatore affidabile di tendenza, non una classifica di visite
- "Il X% del crawling AI è per gli utenti?" — Probabilmente sì, ma la classificazione si basa sulle dichiarazioni degli operatori dei bot e sull'analisi di Cloudflare

**Non rispondibile con questi dati (serve un altro strumento):**
- "Quanti utenti italiani usano una specifica AI?" — Il dato indica popolarità relativa, non conteggi di utenti
- "Il mio sito appare nelle risposte dell'AI?" — Cloudflare Radar monitora il traffico aggregato, non i singoli siti
- "L'AI sta togliendo traffico a Google?" — google.com è stabilmente al primo posto; le piattaforme AI si aggiungono, non sostituiscono (per ora)
- "Quale contenuto viene citato dall'AI?" — Serve un tool specifico di monitoraggio AI (come analisi delle citazioni nelle risposte)

## Sezione Metodologia

**Fonte:** Cloudflare Radar (radar.cloudflare.com)
**Campione:** Circa il 17% del traffico internet globale che transita dalla rete Cloudflare
**Aggiornamento:** Settimanale, ogni lunedì
**Piattaforme monitorate:** 17 domini AI (chatbot, motori di ricerca AI, strumenti AI)
**Limiti:**
- I dati rappresentano il traffico attraverso Cloudflare, non il traffico internet totale
- La classificazione "bot vs umano" usa algoritmi euristici con possibili errori di classificazione
- Per i domini fuori dalla top 100, la posizione è approssimativa (fasce: primi 200, 500, 1.000, ecc.)
- Il confronto Italia vs Mondo risente delle differenze nella copertura Cloudflare per paese
- Le percentuali di crawling AI sono relative al totale del crawling AI, non al traffico totale del sito

---

## Dati raccolti (invariati rispetto a v2)

Il modello dati `TrackerSnapshot` viene esteso con 4 nuovi campi (device_type e os per IT e globale). Le chiamate API salgono da 64 a 68 settimanali (+2 device_type + 2 os). Il resto cambia solo nella presentazione: template Jinja + JS.

## Cosa cambia rispetto a v2

| Aspetto | v2 | v3 |
|---------|-----|-----|
| Struttura | 5 sezioni per tipo di dato | 10 sezioni per domanda strategica |
| IT vs Mondo | Toggle (una vista alla volta) | Affiancati dove serve il confronto |
| Top 10 generico | Mostrava CDN e infrastruttura | Eliminato — focus solo sulle piattaforme AI |
| Perché monitoriamo | Assente | Ogni sezione spiega la teoria e il perché |
| Come leggere | Assente | Testo dinamico sotto ogni grafico |
| Trasparenza | Metodologia minima | Sezione dedicata: cosa misuriamo, con che limiti |
| Linguaggio | Tecnico (bucket, DNS) | Accessibile (fascia, popolarità, scansione) |
| Hero | Assente | Dato della settimana dinamico |
| KPI | Assenti | 4 card dinamiche |
| Universalità | Hardcodato su ChatGPT | Dinamico — si adatta a qualunque AI emerga |
