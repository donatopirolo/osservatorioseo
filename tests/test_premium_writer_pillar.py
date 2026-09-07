"""Test di write_pillar e update_pillar_timeline (dossier / pillar page).

La chiamata LLM è mockata — testiamo costruzione del prompt e parsing della
risposta, non il comportamento del modello.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from osservatorio_seo.models import Item, Pillar, PillarTakeaway, Source
from osservatorio_seo.premium_writer import PremiumWriter, PremiumWriterError, _RawResult


def mk_item(item_id: str, published_at: datetime | None = None) -> Item:
    return Item(
        id=item_id,
        title_original=item_id,
        title_it=f"Titolo {item_id}",
        summary_it="Riassunto di almeno venti caratteri qui.",
        url=f"https://example.com/{item_id}",
        source=Source(
            id="s",
            name="Fonte",
            authority=9,
            type="official",
            fetcher="rss",
            feed_url="https://x.com",
        ),
        category="google_updates",
        tags=["core_update"],
        importance=5,
        published_at=published_at or datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        is_doc_change=False,
        language_original="en",
        summarizer_model="x",
        raw_hash="x",
    )


def mk_pillar(**overrides) -> Pillar:
    base = {
        "tag": "core_update",
        "slug": "core-update",
        "title_it": "Core Update: il dossier di Osservatorio SEO",
        "subtitle_it": "Sottotitolo.",
        "intro_long": "Intro congelata.",
        "context_section": "Contesto congelato.",
        "timeline_narrative": "Primo capitolo della timeline.",
        "takeaways": [PillarTakeaway(title="T1", body="Corpo takeaway congelato.")],
        "outlook": "Outlook congelato.",
        "item_refs": ["old_1", "old_2"],
        "generated_at": datetime(2026, 4, 1, tzinfo=UTC),
        "model_used": "claude-sonnet-4.5",
        "cost_eur": 0.05,
    }
    base.update(overrides)
    return Pillar(**base)


async def test_write_pillar_returns_parsed_model():
    writer = PremiumWriter(api_key="test")
    fake_response = {
        "title_it": "Core Update: il dossier di Osservatorio SEO",
        "subtitle_it": "Sottotitolo generato.",
        "intro_long": "Intro.",
        "context_section": "Contesto.",
        "timeline_narrative": "Timeline.",
        "takeaways": [{"title": f"T{i}", "body": "body"} for i in range(5)],
        "outlook": "Outlook.",
    }
    writer._call_with_fallback = AsyncMock(
        return_value=_RawResult(parsed=fake_response, model="test-model", cost_eur=0.05)
    )

    items = [mk_item("a"), mk_item("b")]
    pillar = await writer.write_pillar("core_update", items)

    assert isinstance(pillar, Pillar)
    assert pillar.tag == "core_update"
    assert pillar.slug == "core-update"
    assert len(pillar.takeaways) == 5
    assert set(pillar.item_refs) == {"a", "b"}
    assert pillar.cost_eur == 0.05


async def test_update_pillar_timeline_appends_without_touching_frozen_fields():
    """Regressione D10: l'aggiornamento deve essere append-only sulla sola
    timeline. Titolo, sottotitolo, intro, contesto, takeaway e outlook non
    devono cambiare rispetto al dossier esistente."""
    existing = mk_pillar()
    writer = PremiumWriter(api_key="test")
    writer._call_with_fallback = AsyncMock(
        return_value=_RawResult(
            parsed={"timeline_update": "Nuovo capitolo aggiunto in coda."},
            model="test-model",
            cost_eur=0.02,
        )
    )

    new_items = [mk_item("new_1")]
    updated = await writer.update_pillar_timeline(existing, new_items)

    # Campi congelati: identici all'esistente
    assert updated.title_it == existing.title_it
    assert updated.subtitle_it == existing.subtitle_it
    assert updated.intro_long == existing.intro_long
    assert updated.context_section == existing.context_section
    assert updated.takeaways == existing.takeaways
    assert updated.outlook == existing.outlook

    # Timeline: append-only, il testo vecchio resta intatto e in testa
    assert updated.timeline_narrative.startswith(existing.timeline_narrative)
    assert "Nuovo capitolo aggiunto in coda." in updated.timeline_narrative
    assert updated.timeline_narrative != existing.timeline_narrative

    # item_refs esteso, non sostituito
    assert updated.item_refs == [*existing.item_refs, "new_1"]

    # Costo cumulato, non sostituito
    assert updated.cost_eur == existing.cost_eur + 0.02


async def test_update_pillar_timeline_requires_new_items():
    writer = PremiumWriter(api_key="test")
    existing = mk_pillar()
    with pytest.raises(PremiumWriterError):
        await writer.update_pillar_timeline(existing, [])
