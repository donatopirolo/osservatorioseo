"""Google Financials SEO Analyzer: quarterly SEC EDGAR data → SEO implications.

Fetches Alphabet (and future companies) financial data from SEC EDGAR XBRL API,
analyses metrics relevant to SEO (Search revenue, TAC, YouTube, Cloud, CapEx),
and generates AI-powered editorial analysis of SEO implications.

Architecture is multi-company ready: CIK is parametric, metrics are configurable
per company via ``config/google_financials.yaml``.
"""
