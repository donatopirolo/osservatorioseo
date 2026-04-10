"""Fetcher interface."""
from __future__ import annotations

from typing import Protocol

from osservatorio_seo.models import RawItem, Source


class Fetcher(Protocol):
    async def fetch(self, source: Source) -> list[RawItem]: ...
