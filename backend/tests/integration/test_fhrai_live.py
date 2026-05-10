"""
Live integration test for the FHRAI scraper.

Hits the real fhrai.com via Playwright. Skipped by default — runs only when
`RUN_LIVE_SCRAPE=1` is set, so CI doesn't burn time on it (or get rate-limited).

Local invocation:
    cd backend
    RUN_LIVE_SCRAPE=1 python -m pytest tests/integration/test_fhrai_live.py -s

This test is the truth-telling layer. Unit tests verify the parser against
a frozen fixture; this verifies the scraper still works against the real
site. If FHRAI redesigns their HTML or starts blocking us, this test goes
red and we know to update selectors.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_SCRAPE", "0") != "1",
    reason="Set RUN_LIVE_SCRAPE=1 to enable live network test",
)


@pytest.mark.asyncio
async def test_fhrai_scraper_returns_real_hotels():
    """End-to-end: launch real Chromium, hit FHRAI, parse, get >0 hotels."""
    from app.services.lead_sources.fhrai_scraper import FHRAIScraper
    from app.services.browser import browser_service

    scraper = FHRAIScraper()
    try:
        results = await scraper.search(profile=None, limit=20)
    finally:
        await browser_service.shutdown()

    # If we got zero, either FHRAI changed their site or the scraper broke.
    # Either way, that's a failure — fix the selectors or update the URL.
    assert len(results) > 0, "FHRAI returned 0 leads — parser drift or site change"

    # Sanity-check the shape of one result.
    first = results[0]
    assert first["company"]["industry"] == "Hospitality"
    assert first["country"] == "India"
    # Real FHRAI entries always have a name; address/phone may be missing.
    assert first["company"]["name"], "Result is missing company name"
