from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from osservatorio_seo import topic_pages as tp

REPO = Path(__file__).resolve().parent.parent

GUIDE = """---
slug: prova
title: "Prova: cos'è"
page_title: "Prova"
description: "Descrizione"
tags: [tag_a, tag_b]
reviewed: 2026-11-01
doc_watcher: [doc_1]
patents: [US1]
---

## In breve

Testo con [link](https://example.com).

[[numeri]]

## Cronologia

[[cronologia]]

## Domande frequenti

### Prima domanda?

Risposta con **grassetto** e [link](/x/).

### Seconda domanda?

Altra risposta.

## Fonti
"""


def _write(tmp_path: Path, numbers: str | None = None) -> Path:
    d = tmp_path / "temi"
    d.mkdir()
    (d / "prova.md").write_text(GUIDE, encoding="utf-8")
    if numbers:
        (d / "prova.numbers.yml").write_text(numbers, encoding="utf-8")
    return d


def test_load_topic_and_numbers(tmp_path):
    d = _write(
        tmp_path,
        "- valore: '50%'\n  descrizione: d\n  fonte: f\n  url: https://x\n  data: 2026-10\n",
    )
    topics = tp.load_topics(d)
    t = topics["prova"]
    assert t.tags == ["tag_a", "tag_b"]
    assert t.reviewed == date(2026, 11, 1)
    assert t.numbers[0].valore == "50%"
    assert t.numbers[0].data == "2026-10"


def test_missing_front_matter_key(tmp_path):
    d = tmp_path / "temi"
    d.mkdir()
    (d / "x.md").write_text("---\nslug: x\n---\ntesto", encoding="utf-8")
    with pytest.raises(ValueError, match="title"):
        tp.load_topics(d)


def test_render_body_toc_and_placeholders():
    _, body = tp._split_front_matter(GUIDE)
    html, toc = tp.render_body(body)
    assert [t["name"] for t in toc] == ["In breve", "Cronologia", "Domande frequenti", "Fonti"]
    parts = tp.split_dynamic(html)
    assert ("block", "numeri") in parts
    assert ("block", "cronologia") in parts
    assert not any("[[" in v for k, v in parts if k == "html")


def test_extract_faq_plain_text():
    _, body = tp._split_front_matter(GUIDE)
    faq = tp.extract_faq(body)
    assert faq == [
        {"question": "Prima domanda?", "answer": "Risposta con grassetto e link."},
        {"question": "Seconda domanda?", "answer": "Altra risposta."},
    ]


def _idx():
    return {
        "1": {
            "date": "2026-11-10",
            "title": "Notizia forte",
            "tags": ["tag_a"],
            "importance": 5,
            "site_path": "/a/",
            "source": "S",
        },
        "2": {
            "date": "2026-10-02",
            "title": "Notizia media",
            "tags": ["tag_b"],
            "importance": 4,
            "site_path": "/b/",
            "source": "S",
        },
        "3": {
            "date": "2026-10-03",
            "title": "Notizia debole",
            "tags": ["tag_a"],
            "importance": 3,
            "site_path": "/c/",
            "source": "S",
        },
        "4": {
            "date": "2026-10-04",
            "title": "Riepilogo settimanale",
            "tags": ["tag_a"],
            "importance": 5,
            "site_path": "/d/",
            "source": "S",
        },
        "5": {
            "date": "2026-10-05",
            "title": "Altro tema",
            "tags": ["zzz"],
            "importance": 5,
            "site_path": "/e/",
            "source": "S",
        },
    }


def test_timeline_filters_and_groups(tmp_path):
    t = tp.load_topics(_write(tmp_path))["prova"]
    months = tp.timeline(t, _idx())
    assert [m["month"] for m in months] == ["2026-11", "2026-10"]
    titles = [e["title"] for m in months for e in m["events"]]
    assert titles == ["Notizia forte", "Notizia media"]


@dataclass
class _Change:
    page_id: str
    day: str
    page_name: str = "Doc"

    @property
    def path(self) -> str:
        return f"/modifiche/{self.page_id}/{self.day}/"


def test_review_needed(tmp_path):
    t = tp.load_topics(_write(tmp_path))["prova"]
    changes = [
        _Change("doc_1", "2026-11-05"),
        _Change("doc_1", "2026-10-01"),
        _Change("x", "2026-11-09"),
    ]
    rv = tp.review_needed(t, _idx(), changes)
    assert rv["reviewed"] == "2026-11-01"
    assert [n["title"] for n in rv["news"]] == ["Notizia forte"]
    assert [c["date"] for c in rv["doc_changes"]] == ["2026-11-05"]


def test_review_not_needed(tmp_path):
    t = tp.load_topics(_write(tmp_path))["prova"]
    assert tp.review_needed(t, {}, []) is None


def test_real_content_is_valid():
    """Le guide vere in content/temi/ si caricano e non lasciano segnaposti."""
    topics = tp.load_topics(REPO / tp.CONTENT_DIR)
    assert "ai-overviews" in topics
    for t in topics.values():
        html, toc = tp.render_body(t.body_md)
        assert toc
        assert not any("[[" in v for k, v in tp.split_dynamic(html) if k == "html")
        assert tp.extract_faq(t.body_md)
        for n in t.numbers:
            assert n.valore and n.fonte and n.url and n.data
