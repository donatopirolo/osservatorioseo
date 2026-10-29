import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from osservatorio_seo.patents.google_patents import parse_patent_page
from osservatorio_seo.patents.models import FamilyMember, Patent, PatentAnalysis, PatentDoc
from osservatorio_seo.patents.writer import PatentAnalysisError, validate_analysis
from osservatorio_seo.publisher import Publisher
from tests.test_publisher import mk_feed_on

FIXTURE = Path(__file__).parent / "fixtures" / "google_patents_sample.html"


def test_parse_patent_page_extracts_bibliographic_data() -> None:
    doc = parse_patent_page("US11769017B1", FIXTURE.read_text(encoding="utf-8"))
    assert doc.title == "Generative summaries for search results"
    assert doc.assignees == ["Google LLC"]
    assert doc.inventors == ["Matthew K. Gray", "John Blitzer"]
    assert doc.priority_date == date(2022, 12, 30)
    assert doc.filing_date == date(2023, 3, 20)
    assert doc.publication_date == date(2023, 9, 26)
    assert doc.status == "Active"
    assert doc.abstract.startswith("At least selectively utilizing")
    # Solo i codici CPC completi, non i nodi dell'albero (G, G06F).
    assert doc.cpc_codes == ["G06F40/56", "G06F16/3329"]
    assert doc.cited_by_count == 2
    assert doc.description.startswith("BACKGROUND")
    assert doc.is_grant


def test_parse_patent_page_separates_independent_claims() -> None:
    doc = parse_patent_page("US11769017B1", FIXTURE.read_text(encoding="utf-8"))
    assert len(doc.claims) == 3
    assert [c.split(".")[0] for c in doc.independent_claims] == ["1", "3"]
    assert "selection rate" in doc.independent_claims[0]


def test_parse_patent_page_family_keeps_relation_and_skips_self() -> None:
    doc = parse_patent_page("US11769017B1", FIXTURE.read_text(encoding="utf-8"))
    by_number = {f.number: f for f in doc.family}
    assert "US11769017B1" not in by_number
    # La continuation compare sia in childApps sia in priorityApps: deve
    # restare una sola voce, con la relazione presa da childApps.
    assert by_number["US11900068B1"].relation == "Continuation"
    assert by_number["US11900068B1"].direction == "child"
    assert by_number["US20250005303A1"].direction == "priority"
    assert len(doc.family) == 2


def _analysis_payload(**overrides) -> dict:
    payload = {
        "title_it": "Selezione delle fonti per le sintesi generative",
        "summary": "Il brevetto descrive come scegliere i documenti da passare a un LLM.",
        "theme": "selezione_fonti_ai",
        "seo_relevance": 5,
        "scope": "Google Search, risposte generative",
        "what_it_claims": " ".join(["rivendica"] * 200),
        "seo_reading": " ".join(["potrebbe"] * 200),
        "limits": ["Non dimostra che il metodo sia in produzione."],
        "implications": ["Cura la verificabilita' dei passaggi."],
        "key_terms": [{"term": "selection rate", "explanation": "Tasso di selezione."}],
    }
    payload.update(overrides)
    return payload


def test_validate_analysis_accepts_complete_output() -> None:
    analysis = validate_analysis(_analysis_payload())
    assert analysis.theme == "selezione_fonti_ai"


@pytest.mark.parametrize(
    "overrides",
    [
        {"theme": "filone_inventato"},
        {"seo_relevance": 7},
        {"what_it_claims": "troppo corto"},
        {"seo_reading": "troppo corto"},
        {"limits": []},
    ],
)
def test_validate_analysis_rejects_incomplete_output(overrides: dict) -> None:
    with pytest.raises(PatentAnalysisError):
        validate_analysis(_analysis_payload(**overrides))


def _mk_patent(number: str, family: list[FamilyMember] | None = None) -> Patent:
    return Patent(
        doc=PatentDoc(
            number=number,
            title="Generative summaries for search results",
            abstract="Abstract.",
            claims=["1. A method."],
            independent_claims=["1. A method."],
            assignees=["Google LLC"],
            publication_date=date(2023, 9, 26),
            family=family or [],
        ),
        analysis=PatentAnalysis.model_validate(_analysis_payload()),
        origin="seed",
        generated_at=datetime(2026, 10, 29, 9, 0, tzinfo=UTC),
        model_used="anthropic/claude-sonnet-4.5",
    )


def _publish(tmp_path: Path, patents: list[Patent]) -> Path:
    data_dir = tmp_path / "data"
    site_dir = tmp_path / "site"
    (data_dir / "patents").mkdir(parents=True)
    for p in patents:
        (data_dir / "patents" / f"{p.doc.number}.json").write_text(p.model_dump_json())
    pub = Publisher(
        data_dir=data_dir, archive_dir=data_dir / "archive", site_data_dir=site_dir / "data"
    )
    feed = mk_feed_on(datetime(2026, 10, 29, 7, 0, tzinfo=UTC), [])
    pub.publish_ssg(feed, [], [], templates_dir=Path("templates"), site_dir=site_dir)
    return site_dir


def test_ssg_patents_renders_index_detail_and_sitemap(tmp_path: Path) -> None:
    original = _mk_patent(
        "US11769017B1",
        family=[FamilyMember(number="US20250005303A1", direction="priority")],
    )
    continuation = _mk_patent("US20250005303A1")
    site_dir = _publish(tmp_path, [original, continuation])

    index = (site_dir / "brevetti" / "index.html").read_text()
    assert 'href="/brevetti/us11769017b1/"' in index
    assert "DOMANDA" in index  # la A1 e' segnalata come domanda

    detail = (site_dir / "brevetti" / "us11769017b1" / "index.html").read_text()
    assert "COSA NON DIMOSTRA" in detail
    assert 'href="/brevetti/us20250005303a1/"' in detail
    assert "https://patents.google.com/patent/US11769017B1/en" in detail
    jsonld = [
        json.loads(m)
        for m in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', detail, flags=re.S
        )
    ]
    assert any(b.get("articleSection") == "Brevetti" for b in jsonld)

    # La continuation vede l'originale anche se la sua pagina non lo elenca.
    cont = (site_dir / "brevetti" / "us20250005303a1" / "index.html").read_text()
    assert 'href="/brevetti/us11769017b1/"' in cont

    sitemap = (site_dir / "sitemap.xml").read_text()
    assert "/brevetti/us11769017b1/" in sitemap
    assert "/brevetti/</loc>" in sitemap


def test_ssg_patents_removes_orphan_pages(tmp_path: Path) -> None:
    site_dir = tmp_path / "site"
    orphan = site_dir / "brevetti" / "us0000000b1"
    orphan.mkdir(parents=True)
    (orphan / "index.html").write_text("vecchia")
    _publish(tmp_path, [_mk_patent("US11769017B1")])
    assert not orphan.exists()


def test_check_doc_rejects_half_parsed_page() -> None:
    """Regressione: dall'HTML renderizzato da Chrome si estraevano solo titolo e
    rivendicazioni, e il modello scriveva schede senza abstract e senza date."""
    from osservatorio_seo.patents.writer import check_doc

    doc = PatentDoc(number="US1B1", title="T", abstract="", claims=["1. A method."])
    with pytest.raises(PatentAnalysisError, match="abstract"):
        check_doc(doc)
    check_doc(parse_patent_page("US11769017B1", FIXTURE.read_text(encoding="utf-8")))


def test_full_description_is_not_saved_to_json() -> None:
    doc = parse_patent_page("US11769017B1", FIXTURE.read_text(encoding="utf-8"))
    assert doc.description
    assert "description" not in json.loads(doc.model_dump_json())


def test_validate_analysis_trims_long_lists() -> None:
    terms = [{"term": f"t{i}", "explanation": "x"} for i in range(12)]
    analysis = validate_analysis(_analysis_payload(key_terms=terms, limits=["a"] * 9))
    assert len(analysis.key_terms) == 8
    assert len(analysis.limits) == 6
