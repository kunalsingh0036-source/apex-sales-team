"""
Unit tests for the lead-source registry. Pure interface — no DB or HTTP.

These cover the contract that downstream phases (FHRAI/CBSE/GeM/Lusha
scrapers) will rely on. If any of these break, every adapter built on
top of the registry breaks silently. Belt-and-braces.
"""

import pytest
from typing import Any

from app.services.lead_sources.base import (
    LeadSource,
    UnknownSourceError,
    register_source,
    get_source,
    list_sources,
    SOURCES,
)


# ─── Test fixtures ────────────────────────────────────────────


class _FakeSource:
    """Minimal Protocol-conforming source for tests."""

    def __init__(self, name: str, returns: list | None = None) -> None:
        self.name = name
        self._returns = returns or []
        self.search_calls: list[tuple[Any, int]] = []

    async def search(self, profile, limit: int):
        self.search_calls.append((profile, limit))
        return list(self._returns)


@pytest.fixture(autouse=True)
def isolate_registry():
    """Snapshot SOURCES around each test so registrations don't leak.

    The real registry is a module-level dict that the production app
    populates on import. We let those built-in sources stay registered
    (apollo, csv_upload, website_form) and just clean up any test-added
    ones afterwards.
    """
    snapshot = dict(SOURCES)
    yield
    SOURCES.clear()
    SOURCES.update(snapshot)


# ─── Tests ────────────────────────────────────────────────────


class TestRegistryResolution:
    def test_built_in_sources_registered_at_import(self) -> None:
        """apollo, csv_upload, website_form must be present out of the box —
        autopilot's discovery loop dispatches on their names."""
        assert "apollo" in SOURCES
        assert "csv_upload" in SOURCES
        assert "website_form" in SOURCES

    def test_get_source_returns_registered_adapter(self) -> None:
        src = _FakeSource("test_adapter")
        register_source(src)
        assert get_source("test_adapter") is src

    def test_get_source_raises_unknown_source_error(self) -> None:
        with pytest.raises(UnknownSourceError) as exc_info:
            get_source("nope_does_not_exist")
        # Error must list available sources so callers can suggest alternatives.
        assert "apollo" in exc_info.value.available

    def test_register_rejects_objects_that_dont_satisfy_protocol(self) -> None:
        """Catch typos / missing async / missing name attribute at registration
        rather than at dispatch — prod debugging would be nightmarish otherwise."""

        class NotASource:
            # Missing both `name` and `search`
            pass

        with pytest.raises(TypeError):
            register_source(NotASource())  # type: ignore[arg-type]

    def test_register_overrides_same_name(self) -> None:
        """Re-registering the same name replaces the prior — needed because
        module re-imports during dev/test would otherwise raise."""
        a = _FakeSource("dup")
        b = _FakeSource("dup")
        register_source(a)
        register_source(b)
        assert get_source("dup") is b

    def test_list_sources_is_sorted(self) -> None:
        names = list_sources()
        assert names == sorted(names), "list_sources must return sorted output for stable UI dropdowns"


class TestPassiveSources:
    """Passive sources must no-op rather than crash when called."""

    @pytest.mark.asyncio
    async def test_csv_upload_search_returns_empty(self) -> None:
        src = get_source("csv_upload")
        # Pass a minimal stub profile — passive sources don't read its fields.
        result = await src.search(profile=None, limit=20)  # type: ignore[arg-type]
        assert result == []

    @pytest.mark.asyncio
    async def test_website_form_search_returns_empty(self) -> None:
        src = get_source("website_form")
        result = await src.search(profile=None, limit=20)  # type: ignore[arg-type]
        assert result == []


class TestProtocolConformance:
    def test_apollo_source_has_name(self) -> None:
        src = get_source("apollo")
        assert src.name == "apollo"

    def test_apollo_source_search_is_coroutine(self) -> None:
        import inspect
        src = get_source("apollo")
        assert inspect.iscoroutinefunction(src.search), \
            "ApolloSource.search must be async — orchestrator awaits it"

    def test_all_built_in_sources_satisfy_protocol(self) -> None:
        """isinstance check uses Protocol's runtime_checkable — verifies
        every registered adapter has the required attributes."""
        for name, src in SOURCES.items():
            assert isinstance(src, LeadSource), f"Source {name!r} fails Protocol check"
