from fastapi import APIRouter
from app.api.v1 import leads, companies, sequences, campaigns, templates, messages, dashboard, webhooks, discovery, analytics, settings
from app.api.v1 import clients, orders, products, quotes, revenue

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

# CRM
api_router.include_router(clients.router, prefix="/clients", tags=["Clients"])
api_router.include_router(orders.router, prefix="/orders", tags=["Orders"])
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["Quotes"])
api_router.include_router(revenue.router, prefix="/revenue", tags=["Revenue"])
