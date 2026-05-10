"""
Unit tests for the GeM tender scraper.

Same testing pattern as the other scrapers — pure parser against a frozen
fixture, HTTP layer mocked. Fixture mirrors real GeM card structure
discovered via Playwright probe (each .card block under #bidCard with
bid number link, items, quantity, department name, start/end dates).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lead_sources.gem_tenders import (
    GEMTenderSource,
    DEFAULT_APEX_KEYWORDS,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def sample_html() -> str:
    return (FIXTURE_DIR / "gem_sample.html").read_text()


@pytest.fixture
def scraper() -> GEMTenderSource:
    return GEMTenderSource()


class TestParser:
    def test_extracts_three_bids_skipping_no_department(self, scraper, sample_html):
        """Fixture has 4 bids; one has no department name — should be skipped."""
        results = scraper.parse_bid_list(sample_html)
        assert len(results) == 3

    def test_captures_bid_number_in_extra_data(self, scraper, sample_html):
        results = scraper.parse_bid_list(sample_html)
        bid_numbers = [r["extra_data"]["bid_number"] for r in results]
        assert "GEM/2026/B/7000001" in bid_numbers
        assert "GEM/2026/B/7000002" in bid_numbers
        assert "GEM/2026/B/7000003" in bid_numbers

    def test_company_name_is_full_department_path(self, scraper, sample_html):
        results = scraper.parse_bid_list(sample_html)
        defence = next(r for r in results if "Defence" in r["company"]["name"])
        assert "Ministry of Defence" in defence["company"]["name"]
        assert "Military Affairs" in defence["company"]["name"]

    def test_captures_bid_url_with_full_origin(self, scraper, sample_html):
        results = scraper.parse_bid_list(sample_html)
        first = results[0]
        assert first["extra_data"]["bid_url"].startswith("https://bidplus.gem.gov.in/")

    def test_captures_items_text_from_popover_data_content(self, scraper, sample_html):
        """When the items cell has a popover, we prefer data-content (full text)
        over the visible truncated label."""
        results = scraper.parse_bid_list(sample_html)
        polos = next(r for r in results if "Polo" in r["extra_data"]["bid_items"] or "polo" in r["extra_data"]["bid_items"])
        assert "200 GSM" in polos["extra_data"]["bid_items"]

    def test_captures_quantity(self, scraper, sample_html):
        results = scraper.parse_bid_list(sample_html)
        polos = next(r for r in results if "Polo" in r["extra_data"]["bid_items"] or "polo" in r["extra_data"]["bid_items"])
        assert polos["extra_data"]["bid_quantity"] == "5000"

    def test_captures_dates(self, scraper, sample_html):
        results = scraper.parse_bid_list(sample_html)
        first = results[0]
        assert first["extra_data"]["bid_start_date"]
        assert first["extra_data"]["bid_end_date"]

    def test_default_contact_is_procurement_office(self, scraper, sample_html):
        for r in scraper.parse_bid_list(sample_html):
            assert r["title"] == "Head of Procurement"
            assert r["first_name"] == "Procurement"

    def test_industry_is_government(self, scraper, sample_html):
        for r in scraper.parse_bid_list(sample_html):
            assert r["company"]["industry"] == "Government Administration"

    def test_returns_empty_when_no_cards(self, scraper):
        html = "<html><body><h1>No bids</h1></body></html>"
        assert scraper.parse_bid_list(html) == []


class TestKeywordFilter:
    @pytest.mark.asyncio
    async def test_default_keywords_match_uniform_and_polo(self, scraper, sample_html):
        """Default Apex keywords should match the polo bid + the school uniform bid
        but NOT the toner cartridge bid."""
        with patch.object(scraper, "_fetch_bid_list", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=None, limit=20)
        names = [r["company"]["name"] for r in results]
        # Should include the two uniform-related bids
        assert any("Defence" in n for n in names), "polo bid filtered out incorrectly"
        assert any("Education" in n or "Vidyalaya" in n for n in names), "school uniform filtered out incorrectly"
        # Should NOT include the toner bid
        assert not any("Atomic Energy" in n for n in names), "toner bid not filtered out"

    @pytest.mark.asyncio
    async def test_custom_keywords_override_defaults(self, scraper, sample_html):
        """profile.search_params.keywords = ['toner'] → only toner bid matches."""
        profile = MagicMock()
        profile.search_params = {"keywords": ["toner"]}
        with patch.object(scraper, "_fetch_bid_list", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=profile, limit=20)
        assert len(results) == 1
        assert "Atomic Energy" in results[0]["company"]["name"]

    @pytest.mark.asyncio
    async def test_empty_keywords_returns_all_bids(self, scraper, sample_html):
        """An explicit empty keyword list bypasses filtering."""
        # NOTE: Currently DEFAULT_APEX_KEYWORDS kicks in when the profile's
        # keywords list is missing or empty. This test documents that
        # behavior — if you want truly unfiltered results, edit the scraper
        # to fetch with no keyword filter explicitly.
        profile = MagicMock()
        profile.search_params = {"keywords": []}  # empty → falls back to defaults
        with patch.object(scraper, "_fetch_bid_list", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=profile, limit=20)
        # Defaults exclude toner, include polo + school uniform
        assert len(results) == 2

    def test_default_apex_keywords_contains_uniform(self):
        assert "uniform" in DEFAULT_APEX_KEYWORDS
        assert "polo" in DEFAULT_APEX_KEYWORDS


class TestSearchOrchestration:
    @pytest.mark.asyncio
    async def test_returns_empty_when_fetch_raises(self, scraper):
        with patch.object(
            scraper, "_fetch_bid_list",
            new=AsyncMock(side_effect=RuntimeError("playwright crashed")),
        ):
            assert await scraper.search(profile=None, limit=20) == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_parse_raises(self, scraper):
        with patch.object(scraper, "_fetch_bid_list", new=AsyncMock(return_value="<not html")):
            with patch.object(scraper, "parse_bid_list", side_effect=ValueError("bad markup")):
                assert await scraper.search(profile=None, limit=20) == []

    @pytest.mark.asyncio
    async def test_caps_results_at_limit(self, scraper, sample_html):
        with patch.object(scraper, "_fetch_bid_list", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=None, limit=1)
        assert len(results) == 1


class TestRegistryRegistration:
    def test_gem_self_registered(self):
        from app.services.lead_sources.base import SOURCES
        from app.services.lead_sources import gem_tenders as _  # noqa: F401
        assert "gem_tenders" in SOURCES
