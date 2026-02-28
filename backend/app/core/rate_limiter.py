"""
Redis-backed rate limiter for per-channel outreach limits.
Prevents exceeding daily sending limits across email, LinkedIn, WhatsApp, Instagram.
"""

import redis.asyncio as redis
from datetime import date
from app.config import get_settings


class RateLimiter:
    def __init__(self):
        settings = get_settings()
        self.redis = redis.from_url(settings.redis_url)
        self.limits = {
            "email": settings.email_daily_limit,
            "linkedin": settings.linkedin_daily_limit,
            "whatsapp": settings.whatsapp_daily_limit,
            "instagram": settings.instagram_daily_limit,
        }

    def _key(self, channel: str, day: date | None = None) -> str:
        if day is None:
            day = date.today()
        return f"rate_limit:{channel}:{day.isoformat()}"

    async def can_send(self, channel: str) -> bool:
        """Check if we can send on this channel today."""
        key = self._key(channel)
        count = await self.redis.get(key)
        if count is None:
            return True
        return int(count) < self.limits.get(channel, 0)

    async def record_send(self, channel: str) -> int:
        """Record a send and return the new count."""
        key = self._key(channel)
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400 * 2)  # TTL 2 days for safety
        results = await pipe.execute()
        return results[0]

    async def remaining(self, channel: str) -> int:
        """Return remaining sends for today."""
        key = self._key(channel)
        count = await self.redis.get(key)
        current = int(count) if count else 0
        limit = self.limits.get(channel, 0)
        return max(0, limit - current)

    async def get_all_remaining(self) -> dict[str, int]:
        """Return remaining sends for all channels."""
        result = {}
        for channel in self.limits:
            result[channel] = await self.remaining(channel)
        return result


rate_limiter = RateLimiter()
