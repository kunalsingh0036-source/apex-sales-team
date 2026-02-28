from typing import AsyncGenerator
from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, pool_size=10)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def verify_api_key(x_api_key: str = Header(default="")):
    """Simple API key authentication middleware."""
    settings = get_settings()
    # Skip auth if no secret is configured (dev mode)
    if settings.api_secret_key == "change-this-to-a-random-secret":
        return True
    if not x_api_key or x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
