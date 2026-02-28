from fastapi import APIRouter
from app.api.v1 import leads, companies, sequences, campaigns, templates, messages, dashboard, webhooks, discovery, analytics, settings

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(leads.router, prefix="/leads", tags=["Leads"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(sequences.router, prefix="/sequences", tags=["Sequences"])
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])
api_router.include_router(messages.router, prefix="/messages", tags=["Messages"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(discovery.router, prefix="/discovery", tags=["Discovery"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
