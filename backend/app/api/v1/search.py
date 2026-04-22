"""Global search across every major entity in the agent.

One endpoint: GET /search?q=<keyword>&limit=8

Runs parallel ILIKE queries across Leads, Companies, Messages, Clients,
Orders, Quotes, Products, Campaigns, Sequences. Returns grouped results
so the UI can render a "jump to anything" palette.

Uses Postgres ILIKE for case-insensitive partial match. Fast enough at
current scale (thousands of rows per table). Upgrade to tsvector FTS
later if/when search latency becomes noticeable.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.lead import Lead, Company
from app.models.message import Message
from app.models.client import Client
from app.models.order import Order
from app.models.quote import Quote
from app.models.product import Product
from app.models.sequence import Campaign, Sequence


router = APIRouter()


@router.get("")
async def global_search(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(8, ge=1, le=25, description="Max results per category"),
    db: AsyncSession = Depends(get_db),
):
    """Search every major entity for the keyword. Returns grouped results."""
    needle = f"%{q.strip()}%"

    async def search_leads():
        result = await db.execute(
            select(Lead)
            .where(
                or_(
                    Lead.lead_code.ilike(needle),
                    Lead.first_name.ilike(needle),
                    Lead.last_name.ilike(needle),
                    Lead.email.ilike(needle),
                    Lead.job_title.ilike(needle),
                    Lead.phone.ilike(needle),
                    Lead.linkedin_url.ilike(needle),
                )
            )
            .order_by(Lead.lead_number.asc())
            .limit(limit)
        )
        leads = result.scalars().all()
        return [
            {
                "id": str(l.id),
                "lead_code": l.lead_code,
                "title": f"{l.first_name} {l.last_name}".strip(),
                "subtitle": l.job_title or l.email or "",
                "url": f"/leads/{l.id}",
            }
            for l in leads
        ]

    async def search_companies():
        result = await db.execute(
            select(Company)
            .where(
                or_(
                    Company.name.ilike(needle),
                    Company.domain.ilike(needle),
                    Company.industry.ilike(needle),
                )
            )
            .limit(limit)
        )
        companies = result.scalars().all()
        return [
            {
                "id": str(c.id),
                "title": c.name,
                "subtitle": c.industry or c.domain or "",
                # Companies don't have a dedicated detail page today; link to leads filtered by company.
                "url": f"/leads?company={c.id}",
            }
            for c in companies
        ]

    async def search_messages():
        result = await db.execute(
            select(Message)
            .where(
                or_(
                    Message.subject.ilike(needle),
                    Message.body.ilike(needle),
                )
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return [
            {
                "id": str(m.id),
                "title": (m.subject or (m.body or "")[:60]).strip(),
                "subtitle": f"{m.channel} · {m.status}",
                "url": "/messages",
            }
            for m in messages
        ]

    async def search_clients():
        result = await db.execute(
            select(Client)
            .where(
                or_(
                    Client.primary_contact_name.ilike(needle),
                    Client.primary_contact_email.ilike(needle),
                    Client.primary_contact_title.ilike(needle),
                )
            )
            .limit(limit)
        )
        clients = result.scalars().all()
        return [
            {
                "id": str(c.id),
                "title": c.primary_contact_name,
                "subtitle": c.primary_contact_title or c.primary_contact_email or "",
                "url": f"/clients/{c.id}",
            }
            for c in clients
        ]

    async def search_orders():
        result = await db.execute(
            select(Order)
            .where(
                or_(
                    Order.order_number.ilike(needle),
                    Order.notes.ilike(needle),
                )
            )
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()
        return [
            {
                "id": str(o.id),
                "title": o.order_number,
                "subtitle": f"{o.stage} · ₹{int(o.total_amount or 0):,}",
                "url": f"/orders/{o.id}",
            }
            for o in orders
        ]

    async def search_quotes():
        result = await db.execute(
            select(Quote)
            .where(
                or_(
                    Quote.quote_number.ilike(needle),
                    Quote.notes.ilike(needle),
                )
            )
            .order_by(Quote.created_at.desc())
            .limit(limit)
        )
        quotes = result.scalars().all()
        return [
            {
                "id": str(q.id),
                "title": q.quote_number,
                "subtitle": f"{q.status} · ₹{int(q.total_amount or 0):,}",
                "url": f"/quotes/{q.id}",
            }
            for q in quotes
        ]

    async def search_products():
        result = await db.execute(
            select(Product)
            .where(
                or_(
                    Product.name.ilike(needle),
                    Product.sku.ilike(needle),
                    Product.description.ilike(needle),
                )
            )
            .limit(limit)
        )
        products = result.scalars().all()
        return [
            {
                "id": str(p.id),
                "title": p.name,
                "subtitle": p.sku or "",
                "url": "/products",
            }
            for p in products
        ]

    async def search_campaigns():
        result = await db.execute(
            select(Campaign)
            .where(Campaign.name.ilike(needle))
            .order_by(Campaign.created_at.desc())
            .limit(limit)
        )
        campaigns = result.scalars().all()
        return [
            {
                "id": str(c.id),
                "title": c.name,
                "subtitle": c.status,
                "url": f"/campaigns/{c.id}",
            }
            for c in campaigns
        ]

    async def search_sequences():
        result = await db.execute(
            select(Sequence)
            .where(
                or_(
                    Sequence.name.ilike(needle),
                    Sequence.description.ilike(needle),
                )
            )
            .limit(limit)
        )
        sequences = result.scalars().all()
        return [
            {
                "id": str(s.id),
                "title": s.name,
                "subtitle": s.description or s.channel,
                "url": f"/sequences/{s.id}",
            }
            for s in sequences
        ]

    # Run all queries in parallel
    (
        leads,
        companies,
        messages,
        clients,
        orders,
        quotes,
        products,
        campaigns,
        sequences,
    ) = await asyncio.gather(
        search_leads(),
        search_companies(),
        search_messages(),
        search_clients(),
        search_orders(),
        search_quotes(),
        search_products(),
        search_campaigns(),
        search_sequences(),
    )

    total = (
        len(leads) + len(companies) + len(messages) + len(clients)
        + len(orders) + len(quotes) + len(products) + len(campaigns) + len(sequences)
    )

    return {
        "query": q,
        "total": total,
        "results": {
            "leads": leads,
            "companies": companies,
            "messages": messages,
            "clients": clients,
            "orders": orders,
            "quotes": quotes,
            "products": products,
            "campaigns": campaigns,
            "sequences": sequences,
        },
    }
