"""
Live integration test for schools.org.in CBSE scraper.
Skipped by default; runs when RUN_LIVE_SCRAPE=1.
"""

import os
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_SCRAPE", "0") != "1",
    reason="Set RUN_LIVE_SCRAPE=1 to enable live network test",
)


@pytest.mark.asyncio
async def test_schools_scraper_returns_real_schools():
    from app.services.lead_sources.schools_scraper import SchoolsScraper
    from app.services.browser import browser_service
    from unittest.mock import MagicMock

    scraper = SchoolsScraper()
    profile = MagicMock()
    profile.search_params = {"locations": ["Delhi"]}

    try:
        results = await scraper.search(profile=profile, limit=10)
    finally:
        await browser_service.shutdown()

    assert len(results) > 0, "schools.org.in returned 0 schools — site change?"

    first = results[0]
    assert first["company"]["industry"] == "Primary/Secondary Education"
    assert first["country"] == "India"
    assert first["company"]["name"], "Result is missing school name"
