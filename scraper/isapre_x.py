"""Placeholder scraper for isapre_x site."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from scraper.base import ScraperBase


class Scraper(ScraperBase):
    site_id = "isapre-x"

    def login_via_context(self, page, username: str, password: str) -> None:
        # TODO: Implement Playwright actions: fill username/password, submit, wait for dashboard.
        raise NotImplementedError("Implement login flow for isapre-x.")

    def discover_documents(self, page, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        # TODO: Navigate ASPX menus, capture PDF links and metadata.
        raise NotImplementedError("Implement document discovery for isapre-x.")

    def extract(self, pdf_path: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: Parse PDF and produce normalized JSON.
        raise NotImplementedError("Implement PDF extraction for isapre-x.")
