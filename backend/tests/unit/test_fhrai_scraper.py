"""
Unit tests for FHRAI hotels scraper.

Two halves:
- HTTP fetch (Playwright-driven) — mocked end-to-end
- HTML parsing — tested against tests/fixtures/fhrai_sample.html, which
  mirrors the real FHRAI markup discovered via the live integration probe
  (table.search_member_tb with name/city/category/website columns).

The fixture was rebuilt from a real FHRAI page snapshot. If you tweak the
parser, eyeball /tmp/fhrai_real.html (saved during integration debug) to
verify the change against actual markup.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lead_sources.fhrai_scraper import FHRAIScraper


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def sample_html() -> str:
    return (FIXTURE_DIR / "fhrai_sample.html").read_text()


@pytest.fixture
def scraper() -> FHRAIScraper:
    return FHRAIScraper()


class TestParser:
    """Parser is a pure function — highest-confidence test target."""

    def test_extracts_three_valid_rows_skipping_invalid(self, scraper, sample_html):
        """Fixture has 3 valid + multiple invalid (empty separators, empty
        name, single-cell row). Only the 3 valid rows should come through."""
        results = scraper.parse_directory(sample_html)
        assert len(results) == 3
        names = [r["company"]["name"] for r in results]
        # Names should be Title-Cased for readability (FHRAI publishes UPPERCASE)
        assert "The Taj Lake Palace" in names
        assert "12Th Avenue" in names or "12th Avenue" in names
        assert "ITC Grand Chola Chennai" in names

    def test_normalizes_uppercase_names_to_title_case(self, scraper, sample_html):
        """All-caps hotel names are title-cased so emails don't shout."""
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if "Taj" in r["company"]["name"])
        # Should NOT be "THE TAJ LAKE PALACE" anymore
        assert taj["company"]["name"] != "THE TAJ LAKE PALACE"
        assert taj["company"]["name"] == "The Taj Lake Palace"

    def test_preserves_already_mixed_case_names(self, scraper, sample_html):
        """Names that aren't ALL CAPS (e.g. 'ITC Grand Chola Chennai') stay as-is."""
        results = scraper.parse_directory(sample_html)
        itc = next(r for r in results if "ITC" in r["company"]["name"])
        assert itc["company"]["name"] == "ITC Grand Chola Chennai"

    def test_extracts_city_from_second_column(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        cities_by_name = {r["company"]["name"]: r["city"] for r in results}
        assert cities_by_name["The Taj Lake Palace"] == "Udaipur"
        assert cities_by_name["ITC Grand Chola Chennai"] == "Chennai"

    def test_records_fhrai_category_in_extra_data(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if "Taj" in r["company"]["name"])
        assert taj["extra_data"]["fhrai_category"] == "5 Star"

    def test_extracts_website_when_present(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if "Taj" in r["company"]["name"])
        assert taj["extra_data"]["website"] == "https://www.tajhotels.com"

    def test_handles_missing_website_gracefully(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        avenue = next(r for r in results if "Avenue" in r["company"]["name"])
        assert avenue["extra_data"]["website"] == ""

    def test_company_industry_is_hospitality(self, scraper, sample_html):
        for r in scraper.parse_directory(sample_html):
            assert r["company"]["industry"] == "Hospitality"

    def test_country_is_always_india(self, scraper, sample_html):
        for r in scraper.parse_directory(sample_html):
            assert r["country"] == "India"

    def test_default_contact_is_operations_team(self, scraper, sample_html):
        """FHRAI doesn't expose contact-person names in the listing. Scraper
        synthesizes a recognizable placeholder so downstream code (which
        expects first/last name) doesn't crash on None."""
        for r in scraper.parse_directory(sample_html):
            assert r["first_name"] == "Operations"
            assert r["last_name"] == "Team"
            assert r["title"] == "General Manager"

    def test_email_and_phone_are_none_in_listing(self, scraper, sample_html):
        """FHRAI listings never publish email/phone — those require the
        per-member modal we're not opening. Hunter.io fills these downstream."""
        for r in scraper.parse_directory(sample_html):
            assert r["email"] is None
            assert r["phone"] is None

    def test_extra_data_records_source(self, scraper, sample_html):
        for r in scraper.parse_directory(sample_html):
            assert r["extra_data"]["source"] == "fhrai_directory"

    def test_returns_empty_when_table_missing(self, scraper):
        """No table.search_member_tb in HTML → parser returns []."""
        html = "<html><body><h1>FHRAI</h1></body></html>"
        assert scraper.parse_directory(html) == []


class TestNameNormalization:
    def test_all_caps_name_is_title_cased(self, scraper):
        assert scraper._normalize_name("THE TAJ LAKE PALACE") == "The Taj Lake Palace"

    def test_mixed_case_name_is_preserved(self, scraper):
        assert scraper._normalize_name("ITC Grand Chola Chennai") == "ITC Grand Chola Chennai"

    def test_empty_name_returns_empty(self, scraper):
        assert scraper._normalize_name("") == ""

    def test_name_with_no_letters_is_returned_as_is(self, scraper):
        assert scraper._normalize_name("123-456") == "123-456"


class TestDomainExtraction:
    def test_strips_www_and_protocol(self, scraper):
        assert scraper._domain_from_website("https://www.tajhotels.com") == "tajhotels.com"
        assert scraper._domain_from_website("http://itchotels.com") == "itchotels.com"

    def test_handles_path(self, scraper):
        assert scraper._domain_from_website("https://www.example.com/about/team") == "example.com"

    def test_empty_returns_empty(self, scraper):
        assert scraper._domain_from_website("") == ""


class TestSearchOrchestration:
    """search() orchestrates _fetch_directory + parse_directory. Both halves
    are mocked here so tests don't launch a real browser."""

    @pytest.mark.asyncio
    async def test_returns_parsed_leads_capped_at_limit(self, scraper, sample_html):
        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=None, limit=2)
            assert len(results) == 2  # capped from 3 in fixture

    @pytest.mark.asyncio
    async def test_returns_empty_when_fetch_raises(self, scraper):
        with patch.object(
            scraper,
            "_fetch_directory",
            new=AsyncMock(side_effect=RuntimeError("playwright launch failed")),
        ):
            results = await scraper.search(profile=None, limit=20)
            assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_parse_raises(self, scraper):
        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value="<not html")):
            with patch.object(scraper, "parse_directory", side_effect=ValueError("bad markup")):
                results = await scraper.search(profile=None, limit=20)
                assert results == []

    @pytest.mark.asyncio
    async def test_passes_state_filter_from_profile_locations(self, scraper, sample_html):
        """Profile.search_params['locations'] = ['India', 'Rajasthan'] →
        'Rajasthan' passed as state_filter (we skip 'India' since it returns the full set)."""
        profile = MagicMock()
        profile.search_params = {"locations": ["India", "Rajasthan"]}

        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            await scraper.search(profile=profile, limit=20)
            mock_fetch.assert_awaited_once()
            assert mock_fetch.await_args.kwargs["state_filter"] == "Rajasthan"

    @pytest.mark.asyncio
    async def test_skips_state_filter_for_india_only(self, scraper, sample_html):
        profile = MagicMock()
        profile.search_params = {"locations": ["India"]}

        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            await scraper.search(profile=profile, limit=20)
            assert mock_fetch.await_args.kwargs["state_filter"] is None


class TestRegistryRegistration:
    def test_fhrai_scraper_self_registered(self):
        from app.services.lead_sources.base import SOURCES
        from app.services.lead_sources import fhrai_scraper as _  # noqa: F401
        assert "fhrai_scraper" in SOURCES
