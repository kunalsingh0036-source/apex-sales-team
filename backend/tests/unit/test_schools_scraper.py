"""
Unit tests for the SchoolsScraper (schools.org.in CBSE directory).

Same testing pattern as FHRAI — pure parser tested against frozen fixture,
HTTP layer mocked. The fixture mirrors real schools.org.in markup observed
during live probing on 2026-05.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lead_sources.schools_scraper import SchoolsScraper


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def sample_html() -> str:
    return (FIXTURE_DIR / "schools_sample.html").read_text()


@pytest.fixture
def scraper() -> SchoolsScraper:
    return SchoolsScraper()


class TestParser:
    def test_extracts_three_valid_schools_skipping_invalid(self, scraper, sample_html):
        """Fixture has 3 valid + 2 invalid (empty anchor, single-char name).
        Only the valid ones should make it through."""
        results = scraper.parse_state_page(sample_html, state_slug="delhi")
        assert len(results) == 3

    def test_normalizes_uppercase_school_names(self, scraper, sample_html):
        results = scraper.parse_state_page(sample_html, state_slug="delhi")
        names = [r["company"]["name"] for r in results]
        # NAVYUG SR. SECONDARY ... → Title Case
        assert any("Navyug" in n for n in names)
        assert all(n != n.upper() for n in names if len(n) > 3)  # nothing all-caps

    def test_preserves_already_mixed_case_names(self, scraper, sample_html):
        results = scraper.parse_state_page(sample_html, state_slug="delhi")
        names = [r["company"]["name"] for r in results]
        assert any("Mater Dei" in n for n in names)

    def test_extracts_city_from_small_tag(self, scraper, sample_html):
        results = scraper.parse_state_page(sample_html, state_slug="delhi")
        cities = [r["city"] for r in results]
        assert "NEW DELHI" in cities
        assert "SOUTH DELHI" in cities

    def test_state_filled_from_slug(self, scraper, sample_html):
        results = scraper.parse_state_page(sample_html, state_slug="tamil-nadu")
        for r in results:
            assert r["state"] == "Tamil Nadu"  # slug → Title Case

    def test_industry_is_education(self, scraper, sample_html):
        for r in scraper.parse_state_page(sample_html, state_slug="delhi"):
            assert r["company"]["industry"] == "Primary/Secondary Education"

    def test_default_contact_is_principal(self, scraper, sample_html):
        for r in scraper.parse_state_page(sample_html, state_slug="delhi"):
            assert r["title"] == "Principal"
            assert r["first_name"] == "Principal"

    def test_records_detail_url_in_extra_data(self, scraper, sample_html):
        results = scraper.parse_state_page(sample_html, state_slug="delhi")
        for r in results:
            url = r["extra_data"]["schools_org_in_url"]
            assert url.startswith("https://schools.org.in/")

    def test_records_source(self, scraper, sample_html):
        for r in scraper.parse_state_page(sample_html, state_slug="delhi"):
            assert r["extra_data"]["source"] == "schools_org_in"

    def test_returns_empty_when_no_list_items(self, scraper):
        html = "<html><body><h1>Schools</h1></body></html>"
        assert scraper.parse_state_page(html) == []


class TestNameNormalization:
    def test_all_caps_school_name_title_cased(self, scraper):
        out = scraper._normalize_name("NAVYUG SR. SECONDARY SCHOOL")
        assert out == "Navyug Sr. Secondary School"

    def test_mixed_case_preserved(self, scraper):
        assert scraper._normalize_name("Mater Dei School") == "Mater Dei School"

    def test_empty_returns_empty(self, scraper):
        assert scraper._normalize_name("") == ""


class TestSearchOrchestration:
    @pytest.mark.asyncio
    async def test_search_uses_explicit_locations_when_given(self, scraper, sample_html):
        """profile.search_params.locations = ['India', 'Tamil Nadu', 'Kerala']
        → fetches Tamil Nadu + Kerala state pages (skipping 'India')."""
        profile = MagicMock()
        profile.search_params = {"locations": ["India", "Tamil Nadu", "Kerala"]}

        with patch.object(scraper, "_fetch_state_page", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            await scraper.search(profile=profile, limit=20)
            slugs = [c.kwargs.get("state_slug", c.args[0] if c.args else None) for c in mock_fetch.await_args_list]
            # Both states scraped; "India" stripped; case lowered + spaces dashed
            assert "tamil-nadu" in slugs
            assert "kerala" in slugs

    @pytest.mark.asyncio
    async def test_search_uses_default_states_when_no_explicit_location(self, scraper, sample_html):
        with patch.object(scraper, "_fetch_state_page", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            await scraper.search(profile=None, limit=2)
            # Should have called at least once with a default state slug
            assert mock_fetch.await_count >= 1

    @pytest.mark.asyncio
    async def test_search_caps_at_limit_across_states(self, scraper, sample_html):
        """Each fixture page returns 3 schools. With limit=4 and many states,
        we should stop fetching as soon as we hit 4."""
        profile = MagicMock()
        profile.search_params = {"locations": ["India"]}

        with patch.object(scraper, "_fetch_state_page", new=AsyncMock(return_value=sample_html)) as mock_fetch:
            results = await scraper.search(profile=profile, limit=4)
            assert len(results) == 4

    @pytest.mark.asyncio
    async def test_search_skips_state_on_fetch_error(self, scraper, sample_html):
        """One state failing shouldn't stall other states' fetches."""
        # Three states ("India" gets stripped); first errors, next two succeed.
        responses = [RuntimeError("network blip"), sample_html, sample_html]

        async def flaky_fetch(state_slug):
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        profile = MagicMock()
        profile.search_params = {"locations": ["India", "X", "Y", "Z"]}
        with patch.object(scraper, "_fetch_state_page", new=flaky_fetch):
            results = await scraper.search(profile=profile, limit=20)
            # First state errors (skipped), states Y and Z each yield 3 = 6 total.
            assert len(results) == 6


class TestRegistryRegistration:
    def test_schools_scraper_self_registered(self):
        from app.services.lead_sources.base import SOURCES
        from app.services.lead_sources import schools_scraper as _  # noqa: F401
        assert "schools_scraper" in SOURCES
