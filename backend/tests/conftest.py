"""
Top-level pytest conftest — shared fixtures.

The integration tests run against an in-memory SQLite database with the
schema from app.models. We don't run real Alembic migrations here because
they include Postgres-specific constructs (UUID gen, JSONB triggers, sequences).
For unit tests of pure logic (registry resolution, parsers), no DB is needed.

Tests that exercise SQLAlchemy models go through `db_session` which uses
SQLite + create_all so the model layer is type-checked against real metadata.
For Postgres-specific behavior (sequences, triggers, JSONB), system smoke
tests against the production Railway API are the source of truth.
"""

import asyncio
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session — required for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """In-memory SQLite session for model-level tests.

    Skips Postgres-only constructs (UUID(as_uuid=True) defaults, JSONB-typed
    columns work via SQLite's JSON extension, sequences/triggers are no-ops).
    Sufficient for testing relationships, queries, and adapter dispatch logic.
    """
    # Import inside the fixture so the test collection doesn't require the
    # full app to import cleanly when only running pure unit tests.
    from app.models.base import Base
    from app.models import (  # noqa: F401 — registers all tables on Base.metadata
        lead, sequence, message, activity, analytics, user, client, product,
        order, quote,
    )

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()
