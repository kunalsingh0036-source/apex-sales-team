"""
Headless-browser service for scrapers that need real JS execution.

Some target sites (FHRAI ASP.NET WebForms, CISCE Cloudflare, GeM AJAX-rendered
bid lists) don't serve usable data to plain HTTP clients. This service lazily
launches one Chromium instance and hands out short-lived BrowserContext/Page
pairs to scrapers via an async context manager.

Design choices:
- One singleton browser per process. Launching Chromium takes 2-5s; sharing
  it across scrape calls amortizes that cost. ~500MB resident memory while
  alive — fits in Railway's apex-sales-team service memory budget.
- Fresh BrowserContext per scrape so cookies/storage don't leak between
  sources (FHRAI cookies wouldn't help on CBSE anyway, but isolation
  prevents weird cross-contamination).
- Lazy launch under an asyncio.Lock so concurrent first callers don't race
  to start two browsers.
- Graceful shutdown via FastAPI lifespan (see app/main.py).
- If launch fails for any reason (Playwright not installed locally, container
  missing system libs, etc.), `page()` re-raises so the scraper sees a clear
  error rather than silently returning empty.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from typing import AsyncIterator

logger = logging.getLogger(__name__)


# Browser config — env-var-overridable for ops tweaks without redeploy.
_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
_USER_AGENT = os.getenv(
    "PLAYWRIGHT_USER_AGENT",
    # A realistic UA so bot-detection treats us like a normal browser.
    # We're not pretending to be human — sites that ban scrapers should ban
    # us if they want — we just don't want to be flagged on UA alone.
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
)


class BrowserService:
    """Lazy singleton for a Chromium browser shared across all scrape calls.

    Public API:
    - `await browser_service.startup()` — explicit init (called from FastAPI lifespan)
    - `async with browser_service.page() as page:` — get a fresh Page for one scrape
    - `await browser_service.shutdown()` — clean teardown (called from lifespan)
    """

    def __init__(self) -> None:
        self._playwright = None  # type: ignore[var-annotated]
        self._browser = None  # type: ignore[var-annotated]
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def startup(self) -> None:
        """Eagerly launch the browser. Safe to call multiple times — no-op if
        already running. Use this from FastAPI lifespan so the first scrape
        request doesn't pay the 2-5s cold-start tax."""
        async with self._lock:
            await self._ensure_running_locked()

    async def _ensure_running_locked(self) -> None:
        """Caller must hold self._lock."""
        if self.is_running:
            return

        # Import here so the module imports cleanly even when Playwright isn't
        # installed (local dev without browser deps, certain test environments).
        # Failures bubble up only when a scraper actually tries to use the browser.
        from playwright.async_api import async_playwright

        logger.info("Launching Playwright Chromium (headless=%s)...", _HEADLESS)
        self._playwright = await async_playwright().start()

        # Container-friendly Chromium args:
        # --no-sandbox: required because we run as root in Railway's container
        # --disable-dev-shm-usage: avoid /dev/shm OOM on small containers
        # --disable-gpu: no GPU available; saves init time
        self._browser = await self._playwright.chromium.launch(
            headless=_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.info("Chromium launched, version=%s", self._browser.version)

    @contextlib.asynccontextmanager
    async def page(
        self,
        viewport: dict | None = None,
        wait_until: str = "domcontentloaded",
    ) -> AsyncIterator:
        """Yield a fresh Page in a fresh BrowserContext.

        The context is closed (and its cookies/storage discarded) when the
        `async with` block exits — no cross-scrape leakage. The caller is
        responsible for navigating with `await page.goto(url)`.
        """
        # Lazy-launch on first call if startup() wasn't invoked.
        if not self.is_running:
            async with self._lock:
                await self._ensure_running_locked()

        assert self._browser is not None  # type guard for the type checker

        context = await self._browser.new_context(
            user_agent=_USER_AGENT,
            viewport=viewport or {"width": 1366, "height": 768},
            # English locale so localized site variants don't trip parsers
            # that assume English column headers.
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = await context.new_page()
        try:
            yield page
        finally:
            # Always close the context to free resources, even if the scraper
            # raised mid-flight. Suppress exceptions during cleanup so the
            # original error (if any) surfaces unchanged.
            with contextlib.suppress(Exception):
                await context.close()

    async def shutdown(self) -> None:
        """Close the browser and stop Playwright. Idempotent."""
        async with self._lock:
            if self._browser is not None:
                with contextlib.suppress(Exception):
                    await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                with contextlib.suppress(Exception):
                    await self._playwright.stop()
                self._playwright = None
        logger.info("Playwright shutdown complete")


# Module-level singleton — scrapers import this directly.
browser_service = BrowserService()
