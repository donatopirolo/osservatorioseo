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
    # "ai" intenzionalmente NON incluso: in italiano è dative ma in contesto
    # tech è l'acronimo Artificial Intelligence → semanticamente rilevante
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

    raw = slugify(title, lowercase=True, separator="-")
    if not raw:
        return _FALLBACK

    parts = [p for p in raw.split("-") if p and p not in _IT_STOPWORDS]
    if not parts:
        return _FALLBACK

    slug = "-".join(parts)

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
