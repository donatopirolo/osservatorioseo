"""Prompt e validazione per la sezione Brevetti.

Due chiamate distinte:

- :func:`classify` decide se un brevetto trovato dalla ricerca automatica
  riguarda la SEO (titolo + abstract + CPC, prompt corto);
- :func:`analyze` scrive la scheda sul testo del brevetto (abstract,
  rivendicazioni indipendenti, inizio della descrizione).

La pubblicazione e' automatica, senza revisione umana: per questo
:func:`analyze` valida l'output e rifiuta schede troppo corte, con un
filone fuori lista o senza la sezione "cosa non dimostra".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import ValidationError

from osservatorio_seo.patents.models import THEMES, Patent, PatentAnalysis, PatentDoc
from osservatorio_seo.premium_writer import PremiumWriter

THEMES_BLOCK = "\n".join(f'- "{k}": {v}' for k, v in THEMES.items())

CLASSIFY_PROMPT = """Sei un SEO tecnico senior. Devi decidere se un brevetto (o una \
domanda di brevetto) puo' interessare chi fa SEO: ranking dei risultati organici, \
selezione e citazione delle fonti nelle risposte AI di Google Search, comprensione \
delle query, segnali di qualita'/fiducia, spam, link, comportamento degli utenti nella \
SERP, passaggi e risposte dirette, entita' e Knowledge Graph, ricerca locale, \
contenuti duplicati e canonicalizzazione, interfacce dei risultati di ricerca.

NON sono rilevanti: pubblicita' (Ads) senza effetti sull'organico, hardware, \
assistenti vocali o chatbot non legati alla ricerca web, addestramento di modelli in \
generale, Workspace/Cloud senza un parallelo diretto con la ricerca web.

Rispondi SOLO con un JSON valido:
{{"seo_relevance": <intero 1-5>, "theme": "<uno dei filoni sotto>", \
"reason": "<una frase in italiano>"}}

seo_relevance: 5 = tocca direttamente ranking o fonti delle risposte AI in Search; \
4 = rilevante con un passaggio di ragionamento; 3 = tangente; 1-2 = non SEO.

Filoni ammessi:
{themes}

--- BREVETTO ---
Numero: {number}
Titolo: {title}
Titolare: {assignees}
Codici CPC: {cpc}
Abstract: {abstract}
"""

ANALYZE_PROMPT = """Sei un SEO tecnico senior italiano e scrivi la scheda di un brevetto \
per Osservatorio SEO. Il lettore e' un professionista SEO: non spiegargli cos'e' un \
brevetto, spiegagli cosa dice QUESTO brevetto e quanto peso dargli.

PRINCIPIO GUIDA: un brevetto descrive cosa un'azienda vuole proteggere, non cosa \
gira in produzione. Tieni sempre separati quattro livelli:
1. cosa coprono le rivendicazioni: e' l'unica parte protetta (fatto, verificabile);
2. cosa contempla la descrizione: forme di realizzazione possibili, esempi, segnali \
elencati come opzioni ("in some implementations"). Non sono protette e non sono \
per forza in uso: scrivi "la descrizione contempla", mai "Google usa";
3. cosa potrebbe significare per la SEO (interpretazione, sempre al condizionale);
4. cosa il brevetto NON dimostra.

Hai il documento COMPLETO: tutte le rivendicazioni e tutta la descrizione. Usalo. \
I dettagli che contano per la SEO (segnali, misure, criteri di selezione, esempi) \
spesso stanno nella descrizione e non nell'abstract: cercali e citali in modo \
specifico (nome del segnale, numero del blocco o della figura, rivendicazione N).

REGOLE:
- Scrivi in italiano, tono asciutto, niente hype ("rivoluzione", "svelato", \
"segreto", "Google usa X per..."). Mai affermare che Google applica il brevetto in \
Search se non lo dice il testo.
- Usa SOLO il testo che ti do sotto. Non citare notizie, studi, dichiarazioni di \
Google o altri brevetti che non compaiono qui: se non lo sai dal testo, non scriverlo.
- I termini tecnici del brevetto lasciali in inglese tra virgolette la prima volta \
(es. "selection rate"), con la spiegazione in italiano.
- Se e' una domanda (numero che finisce per A1/A2) ricorda che non e' (ancora) un \
brevetto concesso. Se fa parte di una famiglia con continuation, dillo nei limiti: \
non e' una prova indipendente.
- Se l'ambito non e' la ricerca web (es. documenti in cloud, Ads, assistente), \
dichiaralo in "scope" e nei limiti.
- Zero markdown, zero elenchi dentro i campi di testo: prosa, paragrafi separati \
da \\n\\n.

Rispondi SOLO con un JSON valido, senza testo prima o dopo:
{{
  "title_it": "Oggetto del brevetto in italiano, 3-8 parole, es. 'Selezione delle \
fonti per le sintesi generative'",
  "summary": "2-3 frasi: che problema affronta e come, in parole semplici.",
  "theme": "uno dei filoni ammessi sotto",
  "seo_relevance": <intero 1-5, quanto conta per chi fa SEO>,
  "scope": "Dove si applica secondo il testo, 2-6 parole (es. 'Google Search, \
risposte generative', 'Documenti in cloud storage, non Search web')",
  "what_it_claims": "250-450 parole. Prima le rivendicazioni indipendenti (passaggi \
del metodo, dati in ingresso, segnali), poi le dipendenti che aggiungono dettagli \
rilevanti per la SEO, citandone il numero. Fedele al testo.",
  "seo_reading": "250-450 parole. Parti da cosa contempla la descrizione (segnali, \
misure, esempi, citando dove compaiono), poi cosa potrebbe voler dire per la SEO, al \
condizionale, distinguendo cio' che e' plausibile da cio' che sarebbe una forzatura.",
  "limits": ["2-4 frasi, ognuna una cosa che il brevetto NON dimostra o un limite \
di lettura"],
  "implications": ["2-4 indicazioni operative prudenti che restano valide anche se il \
brevetto non fosse mai applicato. NON suggerire tattiche che hanno senso solo se il \
brevetto e' in uso (es. 'aumenta i clic perche' potrebbero contare')"],
  "key_terms": [{{"term": "termine come nel brevetto", "explanation": "spiegazione \
in italiano, 1 frase"}}]
}}

Filoni ammessi:
{themes}

--- BREVETTO ---
Numero: {number} ({kind})
Titolo originale: {title}
Titolare: {assignees}
Data di priorita': {priority_date} · Pubblicazione: {publication_date} · Stato: {status}
Famiglia: {family}

Abstract:
{abstract}

Rivendicazioni (tutte, {claims_count}):
{claims}

Descrizione (integrale):
{description}
"""

# Soglie minime della scheda: sotto queste, la generazione e' fallita in modo
# silenzioso (testo troncato, modello che ha ignorato il formato) e la scheda
# non va pubblicata. Volutamente piu' basse dei target del prompt.
MIN_CLAIMS_WORDS = 180
MIN_READING_WORDS = 180


class PatentAnalysisError(Exception):
    pass


@dataclass
class Classification:
    seo_relevance: int
    theme: str
    reason: str
    cost_eur: float


def _family_line(doc: PatentDoc) -> str:
    if not doc.family:
        return "nessuna pubblicazione collegata"
    parts = []
    for f in doc.family[:8]:
        label = f.relation or ("genitore" if f.direction == "parent" else "stessa priorita'")
        parts.append(f"{f.number} ({label})")
    return ", ".join(parts)


async def classify(
    writer: PremiumWriter, number: str, title: str, abstract: str, assignees: str, cpc: str
) -> Classification:
    prompt = CLASSIFY_PROMPT.format(
        themes=THEMES_BLOCK,
        number=number,
        title=title,
        assignees=assignees or "—",
        cpc=cpc or "—",
        abstract=abstract[:2500] or "—",
    )
    parsed, _model, cost = await writer.complete_json(prompt)
    theme = parsed.get("theme")
    return Classification(
        seo_relevance=int(parsed.get("seo_relevance", 0)),
        theme=theme if theme in THEMES else "altro",
        reason=str(parsed.get("reason", "")),
        cost_eur=cost,
    )


def validate_analysis(parsed: dict) -> PatentAnalysis:
    # Con il documento completo il modello tende a dare piu' voci del previsto:
    # meglio tenere le prime che scartare una scheda buona per un elenco lungo.
    parsed = dict(parsed)
    for field in ("limits", "implications", "key_terms"):
        limit = PatentAnalysis.model_fields[field].metadata[0].max_length
        if isinstance(parsed.get(field), list):
            parsed[field] = parsed[field][:limit]
    try:
        analysis = PatentAnalysis.model_validate(parsed)
    except ValidationError as e:
        fields = ", ".join(".".join(str(p) for p in err["loc"]) for err in e.errors())
        raise PatentAnalysisError(f"schema non valido ({fields})") from e
    if len(analysis.what_it_claims.split()) < MIN_CLAIMS_WORDS:
        raise PatentAnalysisError("'what_it_claims' troppo corto")
    if len(analysis.seo_reading.split()) < MIN_READING_WORDS:
        raise PatentAnalysisError("'seo_reading' troppo corto")
    if not analysis.limits:
        raise PatentAnalysisError("manca la sezione 'limits'")
    return analysis


def check_doc(doc: PatentDoc) -> None:
    """Rifiuta un documento estratto a meta' (pagina cambiata, HTML renderizzato).

    Senza abstract o date il modello scrive comunque una scheda plausibile ma
    basata sulle sole rivendicazioni, e puo' dichiarare cose false (es.
    "nessuna pubblicazione collegata"): meglio non pubblicarla.
    """
    missing = [
        name
        for name, ok in (
            ("rivendicazioni", bool(doc.claims)),
            ("abstract", bool(doc.abstract)),
            ("data di pubblicazione", doc.publication_date is not None),
            ("titolare", bool(doc.assignees)),
        )
        if not ok
    ]
    if missing:
        raise PatentAnalysisError(f"{doc.number}: dati mancanti ({', '.join(missing)})")


async def analyze(
    writer: PremiumWriter, doc: PatentDoc, origin: Literal["seed", "discovery"]
) -> Patent:
    check_doc(doc)
    prompt = ANALYZE_PROMPT.format(
        themes=THEMES_BLOCK,
        number=doc.number,
        kind="brevetto concesso" if doc.is_grant else "domanda di brevetto",
        title=doc.title,
        assignees=", ".join(doc.assignees) or "—",
        priority_date=doc.priority_date or "—",
        publication_date=doc.publication_date or "—",
        status=doc.status or "—",
        family=_family_line(doc),
        abstract=doc.abstract,
        claims_count=len(doc.claims),
        claims="\n\n".join(doc.claims),
        description=doc.description or "(non disponibile)",
    )
    parsed, model, cost = await writer.complete_json(prompt)
    try:
        analysis = validate_analysis(parsed)
    except PatentAnalysisError as e:
        snippet = json.dumps(parsed, ensure_ascii=False)[:300]
        raise PatentAnalysisError(f"{doc.number}: {e} — output: {snippet}") from e
    return Patent(
        doc=doc,
        analysis=analysis,
        origin=origin,
        generated_at=datetime.now(UTC),
        model_used=model,
        cost_eur=cost,
    )
