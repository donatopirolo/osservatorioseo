from osservatorio_seo.slug import make_slug, make_unique_slug


def test_make_slug_basic() -> None:
    assert (
        make_slug("Google rilascia il Core Update di marzo 2026")
        == "google-rilascia-core-update-marzo-2026"
    )


def test_make_slug_accents() -> None:
    assert (
        make_slug("È arrivato il nuovo modello AI più potente")
        == "arrivato-nuovo-modello-ai-piu-potente"
    )


def test_make_slug_max_length() -> None:
    long_title = (
        "Un titolo molto molto molto molto molto molto molto molto lungo che supera il limite"
    )
    slug = make_slug(long_title, max_length=60)
    assert len(slug) <= 60
    assert not slug.endswith("-")


def test_make_slug_strips_stopwords() -> None:
    slug = make_slug("La guida di SEO per il 2026")
    assert "la-" not in slug
    assert "guida" in slug
    assert "seo" in slug
    assert "2026" in slug


def test_make_slug_empty_returns_fallback() -> None:
    assert make_slug("") == "untitled"
    assert make_slug("   ") == "untitled"


def test_make_slug_only_stopwords_returns_fallback() -> None:
    assert make_slug("la il di e in") == "untitled"


def test_make_unique_slug_suffix() -> None:
    existing = {"google-update", "google-update-2"}
    assert make_unique_slug("Google Update", existing) == "google-update-3"
