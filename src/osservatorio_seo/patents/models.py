"""Modelli della sezione Brevetti.

Due livelli, tenuti separati di proposito:

- :class:`PatentDoc` e' cio' che dice il documento brevettuale (dati
  bibliografici, abstract, rivendicazioni) cosi' come lo pubblica Google
  Patents. Nessuna interpretazione.
- :class:`PatentAnalysis` e' la lettura editoriale generata dal modello,
  divisa in "cosa rivendica" / "lettura SEO" / "cosa non dimostra": un
  brevetto descrive opzioni implementative, non l'algoritmo in produzione,
  e la pagina deve rendere visibile la differenza.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Filoni tematici: lista chiusa, cosi' l'indice /brevetti/ si puo' raggruppare
# e il modello non inventa una categoria nuova a ogni brevetto.
THEMES: dict[str, str] = {
    "selezione_fonti_ai": "Risposte AI in Search: sintesi e scelta delle fonti",
    "grounding_citazioni": "Grounding, attribuzione e citazioni",
    "ricerca_conversazionale": "Ricerca conversazionale e contesto",
    "ricerca_tematica": "Organizzazione dei risultati per temi",
    "pagine_generate_ai": "Pagine di destinazione generate dall'AI",
    "passaggi_snippet": "Passaggi, risposte dirette e snippet",
    "entita_knowledge_graph": "Entità e Knowledge Graph",
    "ranking_link": "Link e ranking",
    "segnali_utente": "Segnali di comportamento degli utenti",
    "qualita_fiducia": "Qualità e fiducia dei siti",
    "spam": "Spam e manipolazione del ranking",
    "duplicati_canonical": "Contenuti duplicati e canonicalizzazione",
    "freshness_storico": "Freschezza e dati storici",
    "query_comprensione": "Comprensione e riscrittura delle query",
    "local": "Ricerca locale",
    "altro": "Altro",
}

Theme = Literal[
    "selezione_fonti_ai",
    "grounding_citazioni",
    "ricerca_conversazionale",
    "ricerca_tematica",
    "pagine_generate_ai",
    "passaggi_snippet",
    "entita_knowledge_graph",
    "ranking_link",
    "segnali_utente",
    "qualita_fiducia",
    "spam",
    "duplicati_canonical",
    "freshness_storico",
    "query_comprensione",
    "local",
    "altro",
]


class FamilyMember(BaseModel):
    """Altra pubblicazione collegata per priorita' (continuation, divisional, ...)."""

    model_config = ConfigDict(extra="forbid")

    number: str
    relation: str | None = None  # "Continuation", "Division", ... come su Google Patents
    direction: Literal["parent", "child", "priority"]
    title: str | None = None


class PatentDoc(BaseModel):
    """Dati del documento brevettuale, estratti da Google Patents."""

    model_config = ConfigDict(extra="forbid")

    number: str  # es. "US11769017B1"
    title: str
    abstract: str
    claims: list[str] = Field(default_factory=list)
    independent_claims: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)  # titolari originali
    inventors: list[str] = Field(default_factory=list)
    priority_date: date | None = None
    filing_date: date | None = None
    publication_date: date | None = None
    status: str | None = None  # "Active", "Expired - Fee Related", ...
    cpc_codes: list[str] = Field(default_factory=list)  # solo i codici foglia
    # Pubblicazioni della stessa catena di priorita' (continuation comprese):
    # serve a dire "continuation di X" invece di contarla come prova a se'.
    family: list[FamilyMember] = Field(default_factory=list)
    cited_by_count: int = 0
    # Descrizione integrale: va al modello ma NON viene salvata nel JSON (fino a
    # 150 KB per brevetto in git, e il sito non ripubblica testi integrali).
    description: str = Field(default="", exclude=True)

    @property
    def is_grant(self) -> bool:
        """True per un brevetto concesso (B1/B2), False per una domanda (A1)."""
        return self.number[-2:-1] == "B"

    @property
    def url(self) -> str:
        return f"https://patents.google.com/patent/{self.number}/en"


class KeyTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str  # termine come compare nel brevetto, es. "selection rate"
    explanation: str


class PatentAnalysis(BaseModel):
    """Lettura editoriale del brevetto, in italiano."""

    model_config = ConfigDict(extra="forbid")

    title_it: str  # oggetto del brevetto in italiano, breve
    summary: str  # 2-3 frasi
    theme: Theme
    seo_relevance: int = Field(ge=1, le=5)
    scope: str  # dove si applica: Search web, Ads, Workspace, ...
    what_it_claims: str  # cosa coprono le rivendicazioni
    seo_reading: str  # interpretazione plausibile, al condizionale
    limits: list[str] = Field(default_factory=list, max_length=6)  # cosa NON dimostra
    implications: list[str] = Field(default_factory=list, max_length=6)
    key_terms: list[KeyTerm] = Field(default_factory=list, max_length=8)


class Patent(BaseModel):
    """Scheda pubblicata: documento + analisi + metadati di generazione."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    doc: PatentDoc
    analysis: PatentAnalysis
    origin: Literal["seed", "discovery"]
    generated_at: datetime
    model_used: str
    cost_eur: float = 0.0

    @property
    def slug(self) -> str:
        return self.doc.number.lower()
