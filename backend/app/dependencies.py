from typing import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

settings = get_settings()

# FastAPI engine (shared, long-lived — bound to the main event loop)
engine = create_async_engine(settings.database_url, echo=False, pool_size=10)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


def create_worker_session() -> async_sessionmaker:
    """Create a fresh engine + session factory for Celery workers.
    Each call creates a new engine because Celery's run_async() creates
    a new event loop per task, and asyncpg engines are bound to one loop.
    Uses pool_size=1 and NullPool to minimize connections."""
    from sqlalchemy.pool import NullPool
    worker_engine = create_async_engine(
        settings.database_url, echo=False, poolclass=NullPool,
    )
    return async_sessionmaker(worker_engine, expire_on_commit=False)


async def verify_api_key(x_api_key: str = Header(default="")):
    """Simple API key authentication middleware."""
    settings = get_settings()
    # Skip auth if no secret is configured (dev mode)
    if settings.api_secret_key == "change-this-to-a-random-secret":
        return True
    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
