import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router

app = FastAPI(
    title="Apex Human Outreach Agent",
    description="AI-powered sales outreach system for The Apex Human Company",
    version="1.0.0",
)

# Allow Vercel frontend + local dev
allowed_origins = [
    "http://localhost:3000",
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

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "apex-outreach-agent"}
