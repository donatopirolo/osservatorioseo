"""Tests for the SEC EDGAR client."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from osservatorio_seo.google_financials.edgar_client import EdgarClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_facts() -> dict:
    return json.loads((FIXTURES / "alphabet_companyfacts_sample.json").read_text())


@pytest.fixture
def client() -> EdgarClient:
    return EdgarClient()


class TestExtractMetric:
    def test_extract_revenue_q1_2023(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_metric(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_period="Q1",
        )
        assert value == 69787000000

    def test_extract_revenue_q2_2023(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_metric(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_period="Q2",
        )
        assert value == 74604000000

    def test_extract_annual_revenue_2023(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_metric(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_period="FY",
        )
        assert value == 307394000000

    def test_missing_tag_returns_none(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_metric(
            sample_facts,
            tags=["NonExistentTag"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_period="Q1",
        )
        assert value is None

    def test_missing_period_returns_none(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_metric(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2030,
            fiscal_period="Q1",
        )
        assert value is None

    def test_tag_fallback(self, client: EdgarClient, sample_facts: dict):
        """First tag misses, second tag hits."""
        value = client.extract_metric(
            sample_facts,
            tags=["FakeTag", "Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_period="Q1",
        )
        assert value == 69787000000


class TestExtractQuarterlyValue:
    def test_direct_quarterly(self, client: EdgarClient, sample_facts: dict):
        value = client.extract_quarterly_value(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_quarter=1,
        )
        assert value == 69787000000

    def test_q4_derived(self, client: EdgarClient, sample_facts: dict):
        """Q4 = FY - Q1 - Q2 - Q3."""
        value = client.extract_quarterly_value(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_quarter=4,
        )
        # FY=307394 - Q1=69787 - Q2=74604 - Q3=76693 = 86310
        assert value == 86310000000

    def test_q4_derived_capex(self, client: EdgarClient, sample_facts: dict):
        """CapEx Q4 2023 derived from FY - Q1 - Q2 - Q3."""
        value = client.extract_quarterly_value(
            sample_facts,
            tags=["PaymentsToAcquirePropertyPlantAndEquipment"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_quarter=4,
        )
        # FY=32251 - Q1=6289 - Q2=6888 - Q3=8055 = 11019
        assert value == 11019000000

    def test_q4_missing_q_returns_none(self, client: EdgarClient, sample_facts: dict):
        """If any of Q1-Q3 is missing, Q4 cannot be derived."""
        value = client.extract_quarterly_value(
            sample_facts,
            tags=["CostOfRevenue"],
            namespace="us-gaap",
            fiscal_year=2023,
            fiscal_quarter=4,
        )
        # CostOfRevenue only has Q1 and Q2, not Q3 or FY → None
        assert value is None


class TestListAvailableQuarters:
    def test_discover_quarters(self, client: EdgarClient, sample_facts: dict):
        quarters = client.list_available_quarters(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            since_year=2023,
        )
        assert (2023, 1) in quarters
        assert (2023, 2) in quarters
        assert (2023, 3) in quarters
        assert (2023, 4) in quarters  # from FY
        assert (2024, 1) in quarters

    def test_since_filter(self, client: EdgarClient, sample_facts: dict):
        quarters = client.list_available_quarters(
            sample_facts,
            tags=["Revenues"],
            namespace="us-gaap",
            since_year=2024,
        )
        assert (2023, 1) not in quarters
        assert (2024, 1) in quarters


class TestFindNewFilings:
    def test_finds_new(self, client: EdgarClient):
        index = {
            "filings": {
                "recent": {
                    "accessionNumber": ["acc-001", "acc-002", "acc-003"],
                    "form": ["10-Q", "10-K", "8-K"],
                    "filingDate": ["2024-04-25", "2024-01-30", "2024-03-15"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"],
                }
            }
        }
        known = {"acc-001"}
        new = client.find_new_filings(index, known_accessions=known)
        assert len(new) == 2
        assert new[0]["accessionNumber"] == "acc-002"

    def test_filter_by_form_type(self, client: EdgarClient):
        index = {
            "filings": {
                "recent": {
                    "accessionNumber": ["acc-001", "acc-002"],
                    "form": ["10-Q", "8-K"],
                    "filingDate": ["2024-04-25", "2024-03-15"],
                    "primaryDocument": ["doc1.htm", "doc2.htm"],
                }
            }
        }
        new = client.find_new_filings(index, known_accessions=set(), form_types=["10-Q"])
        assert len(new) == 1
        assert new[0]["form"] == "10-Q"


class TestCompanyConcept:
    def test_extract_from_concept_format(self, client: EdgarClient):
        """Test extraction from companyconcept response (flat structure)."""
        concept_data = {
            "cik": 1652044,
            "taxonomy": "goog",
            "tag": "GoogleSearchAndOtherRevenue",
            "label": "Google Search and Other Revenue",
            "units": {
                "USD": [
                    {
                        "val": 40359000000,
                        "accn": "acc-001",
                        "fy": 2023,
                        "fp": "Q1",
                        "form": "10-Q",
                        "filed": "2023-04-25",
                    },
                    {
                        "val": 42628000000,
                        "accn": "acc-002",
                        "fy": 2023,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2023-07-25",
                    },
                ]
            },
        }
        value = client.extract_metric(
            concept_data,
            tags=["GoogleSearchAndOtherRevenue"],
            namespace="goog",
            fiscal_year=2023,
            fiscal_period="Q1",
        )
        assert value == 40359000000
