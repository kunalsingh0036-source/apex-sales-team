"""
Apex Sales Agent — FastAPI application entry point.
Includes startup validation, error handling, and health checks.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.config import get_settings

logger = logging.getLogger("apex")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

settings = get_settings()


# ─── Startup / Shutdown ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate dependencies on startup, clean up on shutdown."""
    logger.info("Starting Apex Sales Agent...")
    errors = []

    # Check PostgreSQL
    try:
        from app.dependencies import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("  ✓ PostgreSQL connected")
    except Exception as e:
        errors.append(f"PostgreSQL: {e}")
        logger.error(f"  ✗ PostgreSQL: {e}")

    # Check Redis
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_connect_timeout=3)
        r.ping()
        r.close()
        logger.info("  ✓ Redis connected")
    except Exception as e:
        errors.append(f"Redis: {e}")
        logger.error(f"  ✗ Redis: {e}")

    # Check critical API keys
    missing_keys = []
    if not settings.anthropic_api_key or settings.anthropic_api_key == "your-key-here":
        missing_keys.append("ANTHROPIC_API_KEY")
    if not settings.apollo_api_key:
        missing_keys.append("APOLLO_API_KEY")
    if missing_keys:
        logger.warning(f"  ! Missing API keys: {', '.join(missing_keys)}")
    else:
        logger.info("  ✓ API keys configured")

    if errors:
        logger.warning(f"Started with {len(errors)} dependency issue(s). Some features may not work.")
    else:
        logger.info("All startup checks passed")

    yield

    # Shutdown
    try:
        from app.dependencies import engine
        await engine.dispose()
        logger.info("Database connections closed")
    except Exception:
        pass


# ─── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="Apex Human Sales Agent",
    description="AI-powered sales system for The Apex Human Company",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://apex-sales-team.vercel.app",
]
extra_origin = os.getenv("CORS_ORIGIN", "")
if extra_origin:
    allowed_origins.append(extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global Error Handler ────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions and return structured JSON."""
    logger.exception(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
            "path": str(request.url.path),
        },
    )


# ─── Routes ──────────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check with dependency status."""
    checks = {"service": "apex-sales-agent"}

    # DB check
    try:
        from app.dependencies import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Redis check
    try:
        import redis
        r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    # Brief attachment file check
    try:
        from app.services.email_service import _BRIEF_PATH
        if _BRIEF_PATH.exists():
            checks["brief_attachment"] = {"status": "ok", "size_bytes": _BRIEF_PATH.stat().st_size}
        else:
            checks["brief_attachment"] = {"status": "missing", "path": str(_BRIEF_PATH)}
    except Exception as e:
        checks["brief_attachment"] = {"status": "error", "error": str(e)}

    all_ok = checks.get("database") == "ok" and checks.get("redis") == "ok"
    checks["status"] = "healthy" if all_ok else "degraded"
    return checks
