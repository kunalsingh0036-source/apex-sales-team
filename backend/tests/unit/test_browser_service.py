"""
Unit tests for BrowserService — the singleton that manages our headless
Chromium for scrapers.

We don't actually launch Chromium in these tests (CI containers don't have
the browser binaries reliably). We mock playwright's `async_playwright`
factory and verify the service's lifecycle, lazy-launch, lock contention,
and shutdown behavior.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.browser import BrowserService


@pytest.fixture
def browser_mock():
    """Mock browser instance — represents what playwright.chromium.launch returns."""
    browser = MagicMock()
    browser.is_connected = MagicMock(return_value=True)
    browser.version = "Chromium/131.0.0.0"
    browser.close = AsyncMock()
    # browser.new_context() returns a context; context.new_page() returns a page.
    # Both are awaited on real playwright; mock with AsyncMock.
    page = MagicMock()
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)
    return browser, context, page


@pytest.fixture
def playwright_mock(browser_mock):
    """Mock the async_playwright entrypoint."""
    browser, _ctx, _page = browser_mock

    pw = MagicMock()
    pw.stop = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=browser)

    pw_factory = MagicMock()
    pw_factory.start = AsyncMock(return_value=pw)
    return pw_factory


@pytest.fixture
def patched_playwright(playwright_mock):
    """Patches async_playwright at the call site inside BrowserService."""
    with patch("playwright.async_api.async_playwright", return_value=playwright_mock):
        yield playwright_mock


class TestStartup:
    @pytest.mark.asyncio
    async def test_startup_launches_browser(self, patched_playwright, browser_mock):
        browser, _, _ = browser_mock
        svc = BrowserService()
        assert not svc.is_running
        await svc.startup()
        assert svc.is_running
        assert svc._browser is browser

    @pytest.mark.asyncio
    async def test_startup_is_idempotent(self, patched_playwright):
        """Calling startup twice should not launch two browsers."""
        svc = BrowserService()
        await svc.startup()
        await svc.startup()
        # The mock playwright.chromium.launch should have been called exactly once.
        assert svc._playwright.chromium.launch.await_count == 1

    @pytest.mark.asyncio
    async def test_concurrent_startup_calls_launch_only_once(self, patched_playwright):
        """Two coroutines calling startup() simultaneously must serialize via the
        lock — otherwise we'd leak two browser instances."""
        svc = BrowserService()
        await asyncio.gather(svc.startup(), svc.startup(), svc.startup())
        assert svc._playwright.chromium.launch.await_count == 1


class TestPageContext:
    @pytest.mark.asyncio
    async def test_page_yields_a_page_and_closes_context(self, patched_playwright, browser_mock):
        browser, context, page = browser_mock
        svc = BrowserService()
        await svc.startup()

        async with svc.page() as p:
            assert p is page

        # Context must be closed after the async-with block exits, even on
        # the happy path — otherwise we'd leak BrowserContexts.
        context.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_page_closes_context_when_caller_raises(self, patched_playwright, browser_mock):
        browser, context, page = browser_mock
        svc = BrowserService()
        await svc.startup()

        with pytest.raises(RuntimeError, match="scraper bug"):
            async with svc.page():
                raise RuntimeError("scraper bug")

        # Context still closed despite the exception bubbling out.
        context.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_page_lazy_launches_browser(self, patched_playwright):
        """If page() is called without prior startup(), it should launch on demand."""
        svc = BrowserService()
        assert not svc.is_running
        async with svc.page():
            assert svc.is_running


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_closes_browser_and_stops_playwright(self, patched_playwright, browser_mock):
        browser, _, _ = browser_mock
        svc = BrowserService()
        await svc.startup()
        await svc.shutdown()
        browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self, patched_playwright, browser_mock):
        browser, _, _ = browser_mock
        svc = BrowserService()
        await svc.startup()
        await svc.shutdown()
        await svc.shutdown()  # Should not raise
        # close() called once, second shutdown is a no-op.
        assert browser.close.await_count == 1

    @pytest.mark.asyncio
    async def test_shutdown_swallows_close_exceptions(self, patched_playwright, browser_mock):
        """If browser.close() raises (Chromium already dead), shutdown should
        still complete without re-raising — we'd block app teardown otherwise."""
        browser, _, _ = browser_mock
        browser.close = AsyncMock(side_effect=RuntimeError("already closed"))

        svc = BrowserService()
        await svc.startup()
        await svc.shutdown()  # Should not raise
        assert svc._browser is None


class TestModuleSingleton:
    def test_singleton_exists_at_module_level(self):
        from app.services.browser import browser_service
        assert isinstance(browser_service, BrowserService)
