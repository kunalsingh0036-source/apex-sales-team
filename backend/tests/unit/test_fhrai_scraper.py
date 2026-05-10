"""
Unit tests for FHRAI hotels scraper.

The scraper has two halves:
- HTTP fetch (tested via mock)
- HTML parsing (tested via frozen fixture in tests/fixtures/fhrai_sample.html)

We never hit FHRAI's real site from CI — that would be flaky and rude.
The fixture covers the variants we've seen in the wild: full member-list-item
with all fields, partial entries missing email/website, entries with phone
embedded in free text, and edge cases (empty name, missing name) that the
parser must skip cleanly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.lead_sources.fhrai_scraper import FHRAIScraper


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def sample_html() -> str:
    """The frozen FHRAI directory snippet used across parser tests."""
    return (FIXTURE_DIR / "fhrai_sample.html").read_text()


@pytest.fixture
def scraper() -> FHRAIScraper:
    return FHRAIScraper()


class TestParser:
    """Parser is a pure function — no I/O. Highest-confidence test target."""

    def test_extracts_three_valid_members_skipping_invalid(self, scraper, sample_html):
        """Fixture has 3 valid + 3 invalid (short name / missing name / empty
        name) entries. Only the valid ones should come through."""
        results = scraper.parse_directory(sample_html)
        assert len(results) == 3
        names = [r["company"]["name"] for r in results]
        assert "The Taj Lake Palace" in names
        assert "ITC Grand Chola Chennai" in names
        assert "Hotel Sea Princess Mumbai" in names

    def test_extracts_email_when_mailto_present(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if r["company"]["name"] == "The Taj Lake Palace")
        assert taj["email"] == "reservations@tajlakepalace.com"

    def test_returns_none_email_when_no_mailto_or_pattern(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        sea = next(r for r in results if r["company"]["name"] == "Hotel Sea Princess Mumbai")
        assert sea["email"] is None

    def test_extracts_phone_from_dedicated_class(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if r["company"]["name"] == "The Taj Lake Palace")
        assert taj["phone"] is not None
        assert "294" in taj["phone"]

    def test_extracts_phone_from_free_text_when_no_class(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        itc = next(r for r in results if r["company"]["name"] == "ITC Grand Chola Chennai")
        assert itc["phone"] is not None
        # The phone from "Tel: +91-44-2220-0000" should be extracted
        assert "2220" in itc["phone"]

    def test_extracts_website_when_present(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if r["company"]["name"] == "The Taj Lake Palace")
        assert taj["extra_data"]["website"] == "https://www.tajhotels.com"

    def test_parses_city_state_from_address(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        taj = next(r for r in results if r["company"]["name"] == "The Taj Lake Palace")
        # Address: "Pichola Lake, City Palace Complex, Udaipur, Rajasthan 313001"
        assert taj["city"] == "Udaipur"
        assert taj["state"] == "Rajasthan"

    def test_country_is_always_india(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        for r in results:
            assert r["country"] == "India"

    def test_company_industry_is_hospitality(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        for r in results:
            assert r["company"]["industry"] == "Hospitality"

    def test_default_contact_is_operations_team(self, scraper, sample_html):
        """FHRAI rarely publishes contact-person names. The scraper synthesizes
        a recognizable placeholder so downstream code (which expects first/last
        name) doesn't crash on None."""
        results = scraper.parse_directory(sample_html)
        for r in results:
            assert r["first_name"] == "Operations"
            assert r["last_name"] == "Team"
            assert r["title"] == "General Manager"

    def test_extra_data_records_source_origin(self, scraper, sample_html):
        results = scraper.parse_directory(sample_html)
        for r in results:
            assert r["extra_data"]["source"] == "fhrai_directory"
            assert "raw_address" in r["extra_data"]


class TestCityStateParsing:
    """Address parsing is fiddly — covers it directly."""

    def test_strips_pin_code(self, scraper):
        city, state = scraper._parse_city_state("Foo Road, Mumbai, Maharashtra 400049")
        assert (city, state) == ("Mumbai", "Maharashtra")

    def test_handles_no_pin(self, scraper):
        city, state = scraper._parse_city_state("Beach Road, Goa")
        assert (city, state) == ("Beach Road", "Goa")

    def test_empty_address(self, scraper):
        city, state = scraper._parse_city_state("")
        assert (city, state) == ("", "")

    def test_single_part_address(self, scraper):
        city, state = scraper._parse_city_state("Kolkata")
        assert (city, state) == ("Kolkata", "")


class TestDomainExtraction:
    def test_strips_www_and_protocol(self, scraper):
        assert scraper._domain_from_website("https://www.tajhotels.com") == "tajhotels.com"
        assert scraper._domain_from_website("http://itchotels.com") == "itchotels.com"

    def test_handles_path(self, scraper):
        assert scraper._domain_from_website("https://www.example.com/about/team") == "example.com"

    def test_empty_returns_empty(self, scraper):
        assert scraper._domain_from_website("") == ""


class TestSearchHTTPLayer:
    """search() exercises the HTTP fetch + dispatch. Mocked end-to-end."""

    @pytest.mark.asyncio
    async def test_search_returns_parsed_leads_capped_at_limit(self, scraper, sample_html):
        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value=sample_html)):
            results = await scraper.search(profile=None, limit=2)
            assert len(results) == 2  # capped from 3 valid in fixture

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_fetch_raises(self, scraper):
        with patch.object(
            scraper,
            "_fetch_directory",
            new=AsyncMock(side_effect=RuntimeError("network down")),
        ):
            # Should NOT raise — caller (orchestrator) treats [] as "tried, found nothing"
            results = await scraper.search(profile=None, limit=20)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_empty_when_parse_raises(self, scraper):
        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value="<not html")):
            with patch.object(scraper, "parse_directory", side_effect=ValueError("bad markup")):
                results = await scraper.search(profile=None, limit=20)
                assert results == []

    @pytest.mark.asyncio
    async def test_search_passes_state_filter_from_profile_locations(self, scraper, sample_html):
        """Profile.search_params['locations'] = ['India', 'Rajasthan'] → "Rajasthan"
        should be passed as state filter (we skip 'India' since it returns the full set)."""
        from unittest.mock import MagicMock
        profile = MagicMock()
        profile.search_params = {"locations": ["India", "Rajasthan"]}

        with patch.object(scraper, "_fetch_directory", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            await scraper.search(profile=profile, limit=20)
            mock_fetch.assert_awaited_once()
            assert mock_fetch.await_args.kwargs["state_filter"] == "Rajasthan"


class TestRegistryRegistration:
    def test_fhrai_scraper_self_registered(self):
        """Importing the module should add 'fhrai_scraper' to SOURCES."""
        from app.services.lead_sources.base import SOURCES
        from app.services.lead_sources import fhrai_scraper as _  # noqa: F401
        assert "fhrai_scraper" in SOURCES
