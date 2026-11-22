---
slug: ai-overviews
title: "AI Overview di Google: cosa sono, come funzionano e cosa cambiano per i siti"
page_title: "AI Overview di Google: cosa sono, come funzionano, impatto sulla SEO"
description: "Cosa sono gli AI Overview, come scelgono le fonti, quanti clic tolgono ai siti e come comparire o escludersi. Con numeri, cronologia e modifiche alla documentazione di Google, aggiornati di continuo."
tags: [ai_overviews, google_ai_overview, sge]
reviewed: 2026-11-22
min_importance: 4
review_importance: 5
doc_watcher: [google_ai_features_guidance, google_help_ai_overviews]
patents: [US11769017B1, US20250005303A1, US12639300B2, US20250156456A1, US20260211889A1, US20240289395A1, US20260154578A1, US20260212135A1, US12530398B2]
patent_themes: [selezione_fonti_ai, grounding_citazioni]
patent_min_relevance: 4
---

## In breve

Gli **AI Overview** sono i riepiloghi generati dall'intelligenza artificiale che Google mostra in cima ad alcune pagine dei risultati, sopra i link organici. Rispondono direttamente alla domanda e citano alcune pagine web come fonti. In Italia sono attivi da fine marzo 2025.

Per chi ha un sito contano per tre motivi:

- compaiono ormai in gran parte delle ricerche;
- quando compaiono, i clic verso i risultati organici calano;
- essere citati tra le fonti è diventato una forma di visibilità a sé.

Google sostiene che per comparire non serva niente oltre alla buona SEO di sempre. I dati indipendenti dicono che il traffico organico, sulle query con un AI Overview, scende.

[[numeri]]

## Cosa sono gli AI Overview

Un AI Overview è un blocco di testo generato da un modello linguistico di Google (della famiglia Gemini) a partire dai risultati di ricerca. Riassume la risposta e affianca link alle pagine da cui ha preso le informazioni.

Sono l'evoluzione della **Search Generative Experience (SGE)**, il prototipo che Google ha aperto in Search Labs a maggio 2023. A maggio 2024 SGE è diventata AI Overviews ed è uscita negli Stati Uniti. Da lì si è estesa a oltre 200 paesi, Italia compresa (fine marzo 2025). In Francia è arrivata solo il 22 luglio 2026, e quel lancio tardivo ha permesso di misurarne l'effetto sul traffico prima e dopo.

Non vanno confusi con:

- **AI Mode:** una modalità di ricerca separata, conversazionale, che l'utente apre di proposito;
- **i featured snippet:** un estratto copiato da una sola pagina, non un testo generato.

Le differenze sono nella tabella più sotto.

## Come funzionano e come scelgono le fonti

Secondo la [guida di Google per chi ha un sito](https://developers.google.com/search/docs/appearance/ai-features?hl=it), gli AI Overview compaiono solo quando i sistemi di Google ritengono che aggiungano qualcosa ai risultati classici. Per questo su molte ricerche non compaiono.

Per costruire la risposta Google può usare una tecnica chiamata **query fan-out**. Lancia in parallelo più ricerche collegate (sui sottotemi della domanda e su fonti diverse), poi sceglie le pagine che sostengono ciascun punto. Per questo un AI Overview cita spesso pagine che non sono tra i primi dieci risultati per la query originale. Basta che rispondano bene a una delle sottodomande.

Alcuni punti fermi:

- **Requisito tecnico:** per essere citata, una pagina deve essere indicizzata e idonea a comparire in Google con uno snippet. Non ci sono altri requisiti tecnici.
- **Il modello cambia spesso:**
  - Gemini 3.5 Flash-Lite da luglio 2026;
  - risposte in stile AI Mode con Gemini 3.7 Flash da agosto 2026;
  - da novembre 2026 [Gemini 4 Hydrogen](https://www.searchenginejournal.com/google-gemini-4-hydrogen-default-ai-mode/597096) per le risposte più complesse.

  Ogni cambio di modello può cambiare quali fonti vengono scelte.
- **Le regole antispam valgono anche qui.** A maggio 2026 Google ha [esteso esplicitamente le norme antispam](https://www.seroundtable.com/google-spam-policies-apply-ai-responses-41331.html) alle risposte AI. Sempre a maggio ha [eliminato il ritardo](https://www.seroundtable.com/google-ai-overview-lag-gone-41368.html) per cui una pagina deindicizzata o penalizzata restava citata negli AI Overview per alcuni giorni.
- **AI Overview e AI Mode possono usare modelli e tecniche diversi:** a parità di domanda, fonti e risposte possono non coincidere.

## Le differenze con AI Mode, featured snippet, Gemini e ChatGPT

| | Cos'è | Quando compare | Fonti |
|---|---|---|---|
| **AI Overview** | Riepilogo generato in cima ai risultati di Google | Da solo, sulle query dove Google lo ritiene utile | Link a più pagine, scelte anche con il fan-out |
| **AI Mode** | Ricerca conversazionale dentro Google, con domande successive | Quando l'utente la apre | Più link, risposte più lunghe; modelli e fonti possono differire dagli AI Overview |
| **Featured snippet** | Estratto copiato da una sola pagina | Su query con risposta breve | Una sola pagina, citata per esteso |
| **Gemini** | L'assistente AI di Google, app e web | Fuori dai risultati di ricerca | Può usare la ricerca, ma non è una pagina di risultati |
| **ChatGPT Search** | La ricerca web dentro ChatGPT | Dentro ChatGPT | Indice e fonti proprie, non quelle di Google |

Per un sito la differenza pratica è dove si gioca la visibilità. Negli AI Overview e in AI Mode si compete per essere citati da Google. In Gemini e ChatGPT valgono regole e crawler diversi: se ne parla nella guida alla SEO per l'AI.

## Quando compaiono: quanto spesso, su quali ricerche, in Italia

La frequenza è cresciuta in fretta:

- circa il 13–20% delle ricerche a metà 2025;
- il [43–48% a luglio 2026](https://www.seroundtable.com/half-google-searches-ai-overviews-41780.html);
- [oltre l'80% a ottobre 2026](https://www.seroundtable.com/over-80-of-google-searches-have-ai-overviews-42372.html), secondo i dati di Semrush, SE Ranking e seoClarity.

All'inizio comparivano soprattutto sulle ricerche informative. Oggi coprono anche:

- **le ricerche di brand:** [83% secondo Ahrefs](https://ahrefs.com/blog/ai-overviews-on-branded-searches), spesso con fonti come Wikipedia, YouTube e LinkedIn al posto del sito ufficiale;
- **le ricerche commerciali;**
- **le ricerche locali:** in [oltre 15 mercati superano già il local pack](https://www.searchenginejournal.com/ai-overviews-now-answer-most-local-searches-how-to-get-your-business-cited/580757), e [secondo Semrush](https://www.semrush.com/blog/ai-overviews-are-taking-over-the-map-pack) consigliano spesso attività diverse da quelle della mappa.

**In Italia** il quadro è simile. Il 22 novembre 2026 abbiamo letto 221 pagine di risultati di Google Italia per ricerche informative sui temi della SEO: **211 avevano un AI Overview**. Il metodo è in fondo alla pagina.

## Quanto traffico tolgono: cosa dicono gli studi

Qui le posizioni di Google e i dati indipendenti non coincidono, ed è giusto metterle una accanto all'altra.

**Cosa dice Google:**
- chi clicca da una pagina con AI Overview è un visitatore «di qualità più alta» e resta di più sul sito, secondo la guida per i siti;
- le funzioni AI portano «miliardi di clic» a settimana verso il web, secondo dichiarazioni dei dirigenti riportate nel [report di agosto 2026](https://www.seroundtable.com/august-2026-google-webmaster-report-41804.html).

Google però non pubblica dati sui clic che arrivano dagli AI Overview.

**Cosa dicono le misure indipendenti:**
- **−38% di clic organici** sulle query che attivano un AI Overview, senza un aumento della soddisfazione degli utenti ([esperimento sul campo, aprile 2026](https://www.searchenginejournal.com/ai-overviews-cut-organic-clicks-38-field-study-finds/573145)).
- **−23,1% di CTR** per i domini più esposti dopo il lancio in Francia, con un calo medio del 3,4% in nove giorni su 963 domini ([Ahrefs, settembre 2026](https://ahrefs.com/blog/ai-overviews-france-impact)). Anche l'[analisi di Glenn Gabe](https://www.gsqi.com/marketing-blog/google-ai-overviews-roll-out-in-france-impact) sui dati di Search Console mostra cali netti per alcuni siti e non per altri.
- **Il 68% delle ricerche non genera clic**, e solo il 27,6% dei clic arriva a siti esterni a Google ([SparkToro e Similarweb](https://www.seroundtable.com/google-zero-click-searches-fall-41475.html)).
- **Gli editori:** Ziff Davis riporta un −37% di traffico organico da Google in un trimestre e impressioni dalle funzioni AI dieci volte superiori ai clic ([novembre 2026](https://www.searchenginejournal.com/ziff-davis-organic-google-referrals-decline/596279)). Reddit attribuisce agli AI Overview e ad AI Mode un calo di oltre un milione di visite a settimana ([ottobre 2026](https://www.searchenginejournal.com/reddit-to-test-login-only-mode-as-google-search-traffic-drops/595270)).

L'effetto non è uguale per tutti. Pesa di più sulle query informative con una risposta breve, e meno su quelle dove serve approfondire, confrontare o comprare. Un sito che vive di definizioni e risposte veloci è il più esposto.

## Come comparire tra le fonti

La [guida di Google](https://developers.google.com/search/docs/appearance/ai-features?hl=it) è netta: **non esistono requisiti aggiuntivi né ottimizzazioni speciali** per gli AI Overview. Non servono file per l'AI come `llms.txt`, né markup o dati strutturati particolari. Valgono le basi della SEO:

- lasciare la scansione aperta in `robots.txt` e nella configurazione di CDN e hosting;
- rendere le pagine raggiungibili con link interni;
- offrire una buona esperienza di pagina;
- mettere il contenuto importante in forma di testo, accompagnato da immagini e video di qualità dove servono;
- tenere i dati strutturati coerenti con il testo visibile;
- tenere aggiornati Merchant Center e Profilo dell'attività, se ci sono.

Dal funzionamento del sistema e dagli studi si ricava qualcosa di più concreto:

1. **Rispondere alle sottodomande, non solo alla domanda principale.** Con il fan-out Google cerca pagine che coprano bene ciascun aspetto. Una pagina che risponde in modo chiaro a una domanda precisa, con un titolo che la contiene, ha più occasioni di essere scelta di una pagina generica.
2. **Mettere in evidenza fatti verificabili:** numeri con fonte e data, definizioni nette, passaggi ordinati, tabelle. Sono i pezzi che un riepilogo può riprendere e attribuire.
3. **Curare la presenza fuori dal sito**, sapendo che conta: per le ricerche di brand gli AI Overview citano spesso Wikipedia, YouTube e LinkedIn. Ma non va comprata. Google ha detto che l'[acquisto o la manipolazione di menzioni](https://www.seroundtable.com/google-inauthentic-mentions-ai-41401.html) per influenzare le risposte AI va trattato come l'acquisto di link.
4. **Tenere aggiornate le pagine** sui temi che cambiano. Il modello e i criteri di scelta cambiano spesso: una pagina ferma da un anno perde terreno.
5. **Segnalare le «fonti preferite».** Da maggio 2026 gli utenti possono indicare le [fonti preferite](https://www.seroundtable.com/google-ai-preferred-sources-41394.html), e Google le mostra negli AI Overview e in AI Mode. Per un sito editoriale vale la pena chiedere ai lettori di aggiungerlo.

## Come misurarli in Search Console e con altri strumenti

- **Search Console, rapporto Prestazioni:** le apparizioni negli AI Overview sono incluse nel traffico «Web». Il rapporto non le separa dal resto, quindi clic e impressioni da AI Overview e da risultati classici sono mescolati.
- **Report sulle prestazioni delle funzioni AI:** dal 1° settembre 2026 sono [disponibili per tutti i siti](https://www.searchenginejournal.com/google-search-console-ai-reports-rolled-out-worldwide/587836). Mostrano le impressioni negli AI Overview e in AI Mode. Google ha detto che non darà dati sui clic specifici delle risposte AI.
- **Quando si conta un'impressione:** solo quando il link al sito è visibile nel riepilogo, come ha precisato John Mueller di Google a giugno 2026.
- **La posizione media è meno affidabile.** Google tratta l'AI Overview come [un blocco unico](https://www.searchenginejournal.com/search-console-uses-block-flattening-for-aios-forget-position-focus-on-outcomes/589582) («block flattening»), quindi tutte le fonti citate prendono la posizione del blocco. Meglio guardare clic, conversioni e andamento delle singole query.
- **Un controllo pratico:** confrontare il CTR delle query più importanti prima e dopo la comparsa di un AI Overview. Se le impressioni crescono e i clic no, la causa è probabilmente quella.
- **Strumenti esterni** come Semrush e SE Ranking tracciano quali keyword attivano un AI Overview e quali domini vengono citati. Google Analytics serve a capire se il traffico rimasto converte meglio, come sostiene Google.

## Come escludere il proprio sito, e quando conviene

Gli strumenti sono quelli degli snippet:

- `nosnippet` (meta tag o intestazione HTTP) esclude la pagina dagli snippet e dagli AI Overview;
- `data-nosnippet` esclude solo alcune parti della pagina;
- `max-snippet` limita la lunghezza del testo riutilizzabile;
- `noindex` toglie la pagina da Google del tutto.

Il blocco di **Google-Extended** in `robots.txt` non toglie le pagine dagli AI Overview. Riguarda l'uso dei contenuti per addestrare e fare grounding in altri sistemi di Google, come le app Gemini. Bloccare Googlebot invece toglie il sito dalla ricerca intera.

A giugno 2026 Google ha introdotto in Search Console [controlli specifici](https://www.seroundtable.com/google-search-generative-ai-control-explained-41569.html) per escludere i contenuti dalle funzioni di IA generativa della ricerca. Sono attivi dal 17 giugno 2026 per i siti nel Regno Unito, dopo un obbligo dell'autorità britannica. Altrove la disponibilità va verificata nella propria proprietà Search Console.

**Quando conviene escludersi?** Raramente. Uscire dagli AI Overview non riporta i clic persi. Fa sparire il sito da un blocco che occupa la parte alta della pagina, e può costare anche la presenza nei [caroselli Top Stories](https://www.searchenginejournal.com/ai-opt-out-may-cost-publishers-a-top-stories-spot/584016), che Google sta integrando negli AI Overview. Ha senso per contenuti a pagamento o molto specifici, il cui valore sta nel testo integrale. Usa `data-nosnippet` sulle parti da proteggere, invece di escludere tutta la pagina.

## Affidabilità, errori e responsabilità

Google stessa avverte che le risposte AI possono contenere errori. I casi più seri hanno avuto conseguenze legali:

- a maggio 2026 un musicista canadese ha [fatto causa a Google](https://www.searchenginejournal.com/google-sued-over-false-ai-overview-about-musician/573944) per un AI Overview che lo descriveva falsamente come molestatore;
- a giugno 2026 un [tribunale di Monaco](https://www.searchenginejournal.com/a-german-court-made-google-liable-for-what-its-ai-says-about-you/579295) ha stabilito che gli AI Overview sono contenuti prodotti da Google, non semplici risultati, e che Google ne risponde;
- sul fronte degli editori, a ottobre 2026 è stata [respinta la causa di Penske Media](https://www.seroundtable.com/video-10-02-2026-42210.html) sull'uso dei contenuti negli AI Overview.

Per un brand le conseguenze pratiche sono due:

- controllare periodicamente cosa dicono gli AI Overview sulle ricerche con il proprio nome;
- sapere che le fonti citate, anche di terzi, influenzano quello che gli utenti leggono prima di arrivare al sito.

Gli errori si segnalano con il feedback sotto ogni AI Overview. Per le affermazioni false su una persona, in Europa c'è anche la strada legale aperta dalla sentenza tedesca.

## Annunci negli AI Overview

Google ha iniziato a mostrare annunci negli AI Overview e sta testando formati pubblicitari anche in AI Mode, per esempio nel settore sanitario negli Stati Uniti. Per chi fa SEO significa che la parte alta della pagina si affolla ancora di più: annunci, riepilogo AI, caroselli. I risultati organici scendono. Le novità sugli annunci sono nella cronologia qui sotto.

## Cronologia: tutte le novità con le date

Le novità più importanti degli ultimi mesi, dalle notizie che seguiamo ogni giorno. L'elenco si aggiorna da solo e ogni voce porta alla notizia con la fonte originale.

[[cronologia]]

## Cosa dice la documentazione di Google

Le pagine ufficiali di Google sugli AI Overview cambiano spesso, e a volte senza annunci. Le rileggiamo ogni giorno e registriamo ogni modifica, con il prima e il dopo.

[[documentazione]]

## Brevetti collegati

Alcuni brevetti di Google descrivono tecniche vicine a quelle degli AI Overview: riepiloghi generativi dei risultati, sottoquery multiple, citazioni delle fonti, controllo della fattualità. Un brevetto non prova che una tecnica sia in uso, ma aiuta a capire in che direzione lavora Google. L'elenco si allarga da solo quando analizziamo un nuovo brevetto Google su questi temi.

[[brevetti]]

## Domande frequenti

### Cosa vuol dire AI Overview?

È il riepilogo generato dall'intelligenza artificiale che Google mostra in cima ad alcune ricerche, con i link alle pagine da cui ha preso le informazioni.

### AI Overview è Gemini?

Gli AI Overview usano modelli della famiglia Gemini, ma non sono l'app Gemini. Sono una funzione della ricerca Google, che compare da sola nei risultati. L'app Gemini è un assistente separato.

### Che differenza c'è tra AI Overview e AI Mode?

L'AI Overview compare da solo in cima ai risultati classici. AI Mode è una modalità di ricerca conversazionale che l'utente apre di proposito, con risposte più lunghe e domande successive. Possono usare modelli diversi e citare fonti diverse.

### Da quando ci sono gli AI Overview in Italia?

Da fine marzo 2025. Negli Stati Uniti sono attivi da maggio 2024, dopo un anno di prova come Search Generative Experience.

### Perché un AI Overview non compare sempre?

Google lo mostra solo quando i suoi sistemi ritengono che aggiunga qualcosa ai risultati classici. Su molte ricerche, soprattutto di navigazione o molto semplici, non compare.

### Serve il file llms.txt o un markup speciale per comparire?

No. Google dice esplicitamente che non servono file per l'AI, markup particolari o dati strutturati speciali. Valgono le stesse regole della SEO: pagina indicizzata, idonea allo snippet, contenuto utile.

### Gli AI Overview riducono il traffico dei siti?

Sulle query dove compaiono, gli studi indipendenti misurano cali dei clic organici tra il 23% e il 38%. Google sostiene che i clic rimasti siano di qualità più alta, ma non pubblica dati sui clic dagli AI Overview.

### Come si esclude un sito dagli AI Overview?

Con `nosnippet` o `max-snippet` sulle pagine, o `data-nosnippet` su parti di esse. Bloccare Google-Extended non basta. Nel Regno Unito ci sono anche controlli dedicati in Search Console.

### Quanto è affidabile un AI Overview?

Può sbagliare, e Google stessa lo segnala. Ci sono stati casi di affermazioni false su persone finiti in tribunale. Le informazioni importanti vanno verificate nelle fonti citate.

## Fonti e metodo

Questa guida è curata dalla redazione di Osservatorio SEO a partire da tre fonti:

- **La documentazione ufficiale di Google**, che il nostro Doc Watcher rilegge ogni giorno. Le modifiche sono registrate nella sezione [Modifiche](/modifiche/).
- **Le notizie raccolte ogni giorno** da blog e testate della SEO internazionale. Ogni dato della guida ha un link alla fonte originale.
- **Una misura nostra delle SERP italiane:** il 22 novembre 2026 abbiamo raccolto le prime dieci posizioni di Google Italia (desktop, lingua italiana) per 221 ricerche informative sui temi della SEO, scelte tra quelle con più ricerche mensili. Per ciascuna abbiamo registrato se compariva un AI Overview: succedeva in 211 casi.

La parte di guida viene riletta quando arrivano novità importanti sul tema. La cronologia, i documenti ufficiali e i brevetti si aggiornano da soli.
