# Tracker v3 — Intelligence Report settimanale

**Data:** 2026-04-13
**Sostituisce:** tracker-v2-design.md (layout a 5 sezioni con toggle IT/Mondo)

## Principio

Il tracker non è un dashboard di grafici. È un **report di intelligence strategica** che risponde a 10 domande che un SEO professionista si pone. Ogni sezione ha: domanda, grafico, risposta, nota metodologica. Italia e Mondo sono sempre **affiancati**, mai nascosti dietro un toggle.

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
│  4 KPI cards                                    │
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

Un numero grande con contesto. Cambia ogni settimana scegliendo il dato più significativo.

Logica di scelta (in ordine di priorità):
1. Se una piattaforma AI entra nella top 100 per la prima volta → quello è il dato
2. Se una piattaforma cambia fascia (es. da top 1.000 a top 500) → segnalare
3. Se il crawling User Action cambia di più di 5 punti percentuali → segnalare
4. Fallback: posizione attuale di chatgpt.com in Italia

Esempio: **"chatgpt.com è tra i 10 siti più popolari in Italia"**
Sotto: "4 mesi fa era oltre la posizione 90. È l'unica piattaforma AI nella top 100."

## 4 KPI Cards

Sempre visibili, aggiornate ogni settimana:

| KPI | Esempio | Dato |
|-----|---------|------|
| Posizione chatgpt.com in Italia | #9 ↑ | `top10_it` → cercare chatgpt.com |
| Crawling AI per gli utenti (IT) | 57% | Ultimo punto `crawl_purpose_it` → User Action |
| Traffico bot in Italia | 20% | Ultimo punto `bot_human_it` → bot_pct |
| Bot AI più attivo in Italia | ChatGPT-User | Primo agente in `ai_bots_ua_it` per valore |

Ogni card mostra: valore, freccia trend (vs settimana precedente), label.

---

## Le 10 sezioni

### Sezione 1: "ChatGPT sta diventando uno strumento quotidiano per gli italiani?"

**Grafico:** Linea singola — posizione di chatgpt.com in Italia nel tempo (52 settimane).
- Asse X: tempo (settimane)
- Asse Y: posizione (invertito: #1 in alto)
- Colore: verde primario (#00f63e)
- Annotazione: posizione attuale in grande a destra della linea

**Risposta (testo sotto il grafico):**
"chatgpt.com è salito dalla posizione {rank_inizio} alla posizione #{rank_attuale} in Italia in {N} mesi. È l'unica piattaforma di intelligenza artificiale nella top 100 italiana. Questo conferma che milioni di italiani utilizzano ChatGPT quotidianamente per cercare informazioni — un canale che affianca la ricerca tradizionale su Google."

**Nota metodologica (collapsible):**
"Questo grafico mostra la popolarità del dominio chatgpt.com misurata da Cloudflare Radar attraverso il traffico internet che transita dalla sua rete (circa il 17% del traffico globale). Non misura le visite dirette al sito, ma la frequenza con cui il dominio viene richiesto dagli utenti italiani. È un indicatore affidabile di tendenza, non un conteggio assoluto."

**Dati necessari:** `top10_it` → trovare chatgpt.com → campo `timeseries`.

---

### Sezione 2: "Quali piattaforme AI stanno emergendo?"

**Grafico:** Tabella interattiva con le 17 piattaforme monitorate.

Colonne:
| Piattaforma | Tipo | Posizione Italia | Posizione Mondo | Segnale |
|-------------|------|-----------------|-----------------|---------|
| chatgpt.com | Chatbot | #9 (top 200) | #10 (top 200) | Stabile |
| openai.com | Chatbot | tra i primi 500 | tra i primi 500 | — |
| claude.ai | Chatbot | tra i primi 1.000 | tra i primi 1.000 | — |

Regole di visualizzazione:
- Se il dominio è in top 100: mostrare la posizione esatta con "#"
- Se è fuori top 100: mostrare "tra i primi X"
- Se è >200.000: mostrare "oltre 200.000"
- Colonna "Segnale": icona/colore per variazione vs settimana precedente. Verde ↑ se migliora, rosso ↓ se peggiora, grigio — se stabile
- Colonna "Gap": se la posizione mondiale è migliore di quella italiana, evidenziare (indica che potrebbe arrivare in Italia)

Ordinamento: per fascia di posizione (i più popolari in alto).

**Risposta:**
"Oggi solo chatgpt.com è nella top 100 in Italia e nel mondo. Le piattaforme da tenere d'occhio sono quelle che migliorano posizione a livello globale prima che in Italia — storicamente i mercati anglofoni anticipano i trend italiani di qualche mese. Se una piattaforma come Perplexity o Claude sale nel ranking mondiale, è probabile che farà lo stesso in Italia."

**Nota metodologica (collapsible):**
"Per i domini fuori dalla top 100, Cloudflare Radar fornisce solo una fascia approssimativa (es. 'tra i primi 500' significa una posizione tra 201 e 500). Non è possibile sapere la posizione esatta. I dati vengono raccolti settimanalmente: accumulando le fasce nel tempo, si può osservare se un dominio sta salendo o scendendo."

**Dati necessari:** `ai_platforms_it`, `ai_platforms_global`. Quando ci saranno almeno 4 snapshot storici, aggiungere una sparkline nella colonna Segnale.

---

### Sezione 3: "Cosa fanno i bot AI con i contenuti dei siti italiani?"

**Grafico:** Area stackata (12 settimane) — scopo del crawling AI in Italia.
- Asse X: settimane
- Asse Y: percentuale (0-100%)
- Colori:
  - Per gli utenti (User Action): verde #00f63e
  - Addestramento modelli (Training): rosso #e24c4c
  - Scopo misto (Mixed): arancione #f5a623
  - Ricerca (Search): blu #4ca6e2
  - Non dichiarato: grigio #919191

**Legenda:** Sempre visibile sotto il grafico, con spiegazione di ogni voce:
- **Per gli utenti** — Un utente ha fatto una domanda all'AI, che ha recuperato la tua pagina per rispondere in tempo reale
- **Addestramento modelli** — Il bot raccoglie contenuti per addestrare o aggiornare i modelli AI (GPT, Claude, Llama ecc.)
- **Scopo misto** — Il bot dichiara di servire sia gli utenti che l'addestramento
- **Ricerca** — Il bot costruisce un indice per la funzione search dell'AI (es. ChatGPT Search)

**Risposta:**
"In Italia, il {user_action_pct}% del crawling AI serve a rispondere agli utenti in tempo reale. Solo il {training_pct}% è per l'addestramento dei modelli. Questo significa che i bot AI non stanno principalmente 'rubando' i contenuti dei siti italiani — li stanno distribuendo ai propri utenti. Se il tuo contenuto è di qualità, l'AI lo sta già mostrando a chi cerca informazioni."

**Dati necessari:** `crawl_purpose_it`.

---

### Sezione 4: "Quali aziende AI scansionano di più i siti italiani?"

**Grafico:** Linee multiple (12 settimane), ciascuna rappresenta un bot AI. Legenda cliccabile per mostrare/nascondere le singole linee.
- Asse X: settimane
- Asse Y: percentuale del crawling AI
- Una linea per ogni bot (ChatGPT-User, Googlebot, ClaudeBot, GPTBot, Meta-ExternalAgent, Bytespider, Bingbot, ecc.)

**Legenda esplicativa (sempre visibile):**

| Bot | Azienda | Scopo |
|-----|---------|-------|
| ChatGPT-User | OpenAI | Recupera pagine per rispondere agli utenti di ChatGPT |
| GPTBot | OpenAI | Raccoglie contenuti per addestrare i modelli GPT |
| OAI-SearchBot | OpenAI | Costruisce l'indice di ChatGPT Search |
| ClaudeBot | Anthropic | Raccoglie contenuti per Claude |
| Googlebot | Google | Indicizza per Google Search (anche training Gemini) |
| Meta-ExternalAgent | Meta | Raccoglie contenuti per Meta AI / Llama |
| Bytespider | ByteDance | Raccoglie contenuti per TikTok AI |
| Bingbot | Microsoft | Indicizza per Bing (alimenta anche ChatGPT) |

**Risposta:**
"Il bot più attivo sui siti italiani è {top_agent} ({top_agent_pct}%), gestito da {top_agent_company}. {interpretation}."

Logica di interpretazione:
- Se ChatGPT-User è primo: "Questo conferma che OpenAI sta attivamente utilizzando i contenuti italiani per rispondere ai propri utenti."
- Se GPTBot cresce: "OpenAI sta intensificando la raccolta di contenuti italiani per l'addestramento — i prossimi modelli GPT potrebbero essere significativamente migliori in italiano."
- Se ClaudeBot cresce: "Anthropic sta investendo nel crawling di siti italiani — possibile segnale di espansione di Claude nel mercato italiano."

**Dati necessari:** `ai_bots_ua_it`.

---

### Sezione 5: "L'Italia è in anticipo o in ritardo rispetto al mondo?"

**Grafico:** Barre orizzontali affiancate — Italia (verde) vs Mondo (grigio) per ogni metrica chiave.

Metriche visualizzate:
1. Posizione chatgpt.com → IT #9 vs Mondo #10
2. Traffico bot (% del totale) → IT 20% vs Mondo 35%
3. Crawling per gli utenti (% AI bot) → IT 57% vs Mondo 2%
4. Crawling per addestramento (% AI bot) → IT 13% vs Mondo 50%
5. ClaudeBot (% AI bot) → IT 4.5% vs Mondo 11.9%
6. GPTBot (% AI bot) → IT 3.2% vs Mondo 9.8%

Per ogni riga: etichetta, barra IT (verde), barra Mondo (grigio), indicazione "Italia avanti" / "Italia indietro" / "In linea".

**Risposta:**
"L'Italia è in linea con il mondo sull'adozione di ChatGPT (#9 vs #10), ma ha un profilo di crawling molto diverso. Il crawling AI in Italia è dominato dalle richieste degli utenti ({user_action_it}%), mentre nel mondo domina l'addestramento dei modelli ({training_global}%). ClaudeBot e GPTBot sono meno attivi in Italia che nel mondo — se iniziano a crescere, è il segnale che le AI company stanno investendo nel mercato italiano."

**Perché conta per la SEO:**
"I mercati anglofoni anticipano i trend italiani. Se un bot o una piattaforma cresce nel dato mondiale ma è ancora piccolo in Italia, è probabile che arrivi nei prossimi mesi. Monitorare il gap aiuta a prepararsi prima dei competitor."

**Dati necessari:** Ultimo punto di `bot_human_it`, `bot_human_global`, `crawl_purpose_it`, `crawl_purpose_global`, `ai_bots_ua_it`, `ai_bots_ua_global`, posizione chatgpt.com da `top10_it` e `top10_global`.

---

### Sezione 6: "Quale piattaforma AI potrebbe esplodere prossimamente in Italia?"

**Grafico:** Tabella semplificata — solo le piattaforme dove il dato mondiale è significativamente migliore di quello italiano.

| Piattaforma | Italia | Mondo | Gap | Segnale |
|-------------|--------|-------|-----|---------|
| perplexity.ai | tra i primi 1.000 | tra i primi 1.000 | Nessuno | ⚪ Da monitorare |
| claude.ai | tra i primi 1.000 | tra i primi 1.000 | Nessuno | ⚪ Da monitorare |

Quando il dato mondiale migliora (es. Perplexity passa a "tra i primi 500" nel mondo ma resta "tra i primi 1.000" in Italia), la riga diventa evidenziata con un segnale giallo/arancione: "🟡 In crescita nel mondo".

**Risposta:**
"Al momento nessuna piattaforma AI mostra un gap significativo tra mondo e Italia — l'adozione procede in parallelo. Quando una piattaforma inizierà a salire nel ranking mondiale prima che in Italia, la segnaleremo qui come 'in arrivo'."

(Questa sezione diventa molto più interessante col tempo, quando si accumulano dati storici.)

**Dati necessari:** `ai_platforms_it`, `ai_platforms_global`, confronto snapshot precedente.

---

### Sezione 7: "Il tuo settore è nel mirino dell'AI?"

**Grafico:** Barre orizzontali — top 10 settori per volume di crawling AI. Italia (verde) e Mondo (grigio) affiancati per ogni settore.

**Risposta:**
"Il settore più scansionato dall'AI in Italia è {top_industry_it} ({top_industry_pct_it}%). A livello mondiale è {top_industry_global} ({top_industry_pct_global}%). Se lavori in uno di questi settori, l'AI sta già consumando massivamente i contenuti dei tuoi competitor — e probabilmente anche i tuoi."

**Legenda / nota:**
"I settori sono classificati da Cloudflare in base al dominio del sito scansionato. 'Retail' include ecommerce, 'Leisure, Travel & Tourism' include siti di viaggio e ospitalità. La percentuale indica quanta parte del crawling AI totale riguarda quel settore."

**Dati necessari:** `industry_it`, `industry_global`.

---

### Sezione 8: "OpenAI sta raccogliendo massivamente contenuti italiani per il training?"

**Grafico:** Linea singola — percentuale di GPTBot (il crawler di training di OpenAI) nel tempo in Italia, con linea tratteggiata per il dato mondiale come riferimento.

**Risposta (dinamica):**
- Se GPTBot è stabile: "GPTBot rappresenta il {gptbot_pct}% del crawling AI in Italia — relativamente basso rispetto al mondo ({gptbot_global_pct}%). OpenAI non sta intensificando la raccolta di contenuti italiani per il training. Il focus resta sul servire gli utenti via ChatGPT-User."
- Se GPTBot cresce: "GPTBot è in crescita in Italia (dal {old}% al {new}%). OpenAI sta raccogliendo più contenuti italiani per l'addestramento dei modelli. Questo suggerisce che i prossimi modelli GPT avranno una competenza migliore sulla lingua e il mercato italiano."

**Dati necessari:** `ai_bots_ua_it` → estrarre serie GPTBot, `ai_bots_ua_global` → serie GPTBot.

---

### Sezione 9: "Google sta perdendo centralità come crawler?"

**Grafico:** Linea singola — percentuale di Googlebot tra i bot AI nel tempo (12 settimane), Italia e Mondo affiancati.

**Risposta:**
"Googlebot rappresenta il {googlebot_it_pct}% del crawling AI in Italia e il {googlebot_global_pct}% nel mondo. Il trend globale mostra un calo (dal {g_start}% al {g_end}% in 12 settimane) — non perché Google crawla meno, ma perché gli altri bot crescono di più. Per chi fa SEO, questo significa che il crawl budget del tuo sito è condiviso tra sempre più bot: ottimizzarlo non è più solo una questione Google."

**Dati necessari:** `ai_bots_ua_it` → serie Googlebot, `ai_bots_ua_global` → serie Googlebot.

---

### Sezione 10: "La pressione dei bot AI sui siti italiani sta crescendo?"

**Grafico:** Area chart — percentuale di traffico bot vs umano nel tempo (12 settimane). Italia e Mondo affiancati (due grafici piccoli).
- Area arancione: bot
- Area grigia chiara: umani
- Annotazione: percentuale attuale di bot

**Risposta:**
"Il {bot_pct_it}% del traffico verso i siti italiani su Cloudflare è generato da bot (era {bot_pct_it_start}% {N} settimane fa). A livello mondiale la percentuale è {bot_pct_global}%. Il trend è in crescita. Per chi fa SEO, questo significa che le metriche di analytics (frequenza di rimbalzo, tempo sulla pagina, conversioni) sono sempre meno affidabili se non si filtra il traffico automatizzato."

**Dati necessari:** `bot_human_it`, `bot_human_global`.

---

## Sezione Trasparenza

Titolo: **"Cosa misurano questi dati — e cosa no"**

Testo fisso, sempre presente:

**Risposte affidabili:**
- "ChatGPT sta diventando più popolare in Italia?" — Sì, il trend è chiaro e inequivocabile
- "Quali bot AI sono più attivi sui siti italiani?" — Sì, la distribuzione è un dato solido
- "Il crawling AI è in crescita?" — Sì, il trend bot vs umani lo conferma
- "ChatGPT recupera contenuti per rispondere ai propri utenti?" — Sì, ChatGPT-User è specifico per questo scopo

**Da interpretare con cautela:**
- "ChatGPT è il 9° sito più visitato in Italia?" — Non esattamente: è il 9° dominio più popolare nel traffico che transita da Cloudflare, che copre circa il 17% dell'internet globale. È un indicatore di tendenza, non un conteggio assoluto
- "Il 57% del crawling AI è per gli utenti?" — Probabilmente sì, ma dipende dalla classificazione di Cloudflare che si basa sulle dichiarazioni degli operatori dei bot

**Non rispondibile con questi dati:**
- "Quanti utenti italiani usano ChatGPT?" — Il dato DNS indica popolarità, non conteggi di utenti
- "Il mio sito appare nelle risposte di ChatGPT?" — Cloudflare Radar non ha dati per singolo sito
- "L'AI sta togliendo traffico a Google?" — google.com è stabilmente al primo posto; ChatGPT si aggiunge, non sostituisce (per ora)

## Sezione Metodologia

**Fonte:** Cloudflare Radar (radar.cloudflare.com)
**Campione:** Circa il 17% del traffico internet globale che transita dalla rete Cloudflare
**Aggiornamento:** Settimanale, ogni lunedì
**Piattaforme monitorate:** 17 domini AI (chatbot, motori di ricerca AI, strumenti AI)
**Limiti:**
- I dati rappresentano il traffico attraverso Cloudflare, non il traffico internet totale
- La classificazione "bot vs umano" usa algoritmi euristici con possibili falsi positivi
- Per i domini fuori dalla top 100, la posizione è approssimativa (fasce di 200, 500, 1.000 ecc.)
- Il confronto Italia vs Mondo risente delle differenze nella copertura Cloudflare per paese

---

## Dati raccolti (invariati rispetto a v2)

Il modello dati `TrackerSnapshot` resta identico a v2. Le 64 chiamate API settimanali (32 IT + 32 globale) non cambiano. Cambia solo come i dati vengono presentati nel template.

## Cosa cambia rispetto a v2

| Aspetto | v2 | v3 |
|---------|-----|-----|
| Struttura | 5 sezioni per tipo di dato | 10 sezioni per domanda strategica |
| IT vs Mondo | Toggle (una vista alla volta) | Affiancati dove serve il confronto |
| Top 10 generico | Mostrava CDN e infrastruttura | Eliminato — focus solo sulle piattaforme AI |
| Interpretazione | Assente | Testo dinamico sotto ogni grafico |
| Trasparenza | Metodologia minima | Sezione dedicata: cosa misuriamo, cosa no |
| Linguaggio | Tecnico (bucket, DNS) | Accessibile (fascia, popolarità, scansione) |
| Hero | Assente | Dato della settimana con contesto |
| KPI | Assenti | 4 card sempre visibili |
