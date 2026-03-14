"""
Client service — handles lead-to-client conversion, client management,
AMA tracking, and revenue summaries.
"""

import uuid
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.lead import Lead, Company
from app.models.client import Client, ClientContact, BrandAsset, Interaction, SampleKit
from app.models.order import Order
from app.models.activity import Activity
from app.schemas.client import LeadToClientConversion


class ClientService:

    async def convert_lead_to_client(
        self, db: AsyncSession, data: LeadToClientConversion
    ) -> Client:
        """Convert a won lead into a client record."""
        lead = await db.get(Lead, data.lead_id)
        if not lead:
            raise ValueError(f"Lead {data.lead_id} not found")
        if lead.stage != "won":
            raise ValueError(f"Lead must be in 'won' stage to convert (current: {lead.stage})")

        client = Client(
            company_id=lead.company_id,
            lead_id=lead.id,
            primary_contact_name=lead.full_name,
            primary_contact_email=lead.email,
            primary_contact_phone=lead.phone,
            primary_contact_title=lead.job_title,
            ama_tier=data.ama_tier,
            ama_commitment=data.ama_commitment,
            billing_address=data.billing_address,
            shipping_address=data.shipping_address,
            gst_number=data.gst_number,
            payment_terms=data.payment_terms,
        )
        db.add(client)

        # Log the conversion as an activity on the lead
        activity = Activity(
            lead_id=lead.id,
            type="lead_converted",
            description=f"Lead converted to client",
        )
        db.add(activity)

        await db.flush()
        return client

    async def get_client(self, db: AsyncSession, client_id: uuid.UUID) -> Client | None:
        result = await db.execute(
            select(Client)
            .where(Client.id == client_id)
            .options(
                selectinload(Client.contact_persons),
                selectinload(Client.brand_assets),
                selectinload(Client.company),
            )
        )
        return result.scalar_one_or_none()

    async def list_clients(
        self, db: AsyncSession,
        status: str | None = None,
        ama_tier: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[Client], int]:
        query = select(Client).options(selectinload(Client.company))
        count_query = select(func.count(Client.id))

        if status:
            query = query.where(Client.status == status)
            count_query = count_query.where(Client.status == status)
        if ama_tier:
            query = query.where(Client.ama_tier == ama_tier)
            count_query = count_query.where(Client.ama_tier == ama_tier)
        if search:
            search_filter = Client.primary_contact_name.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await db.execute(count_query)).scalar() or 0
        query = query.order_by(Client.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_client_revenue_summary(
        self, db: AsyncSession, client_id: uuid.UUID
    ) -> dict:
        """Total orders, total spend, and AMA utilization for a client."""
        result = await db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_spend"),
            ).where(Order.client_id == client_id)
        )
        row = result.first()

        client = await db.get(Client, client_id)
        ama_commitment = float(client.ama_commitment) if client and client.ama_commitment else 0
        total_spend = float(row.total_spend) if row else 0
        ama_utilization = (total_spend / ama_commitment * 100) if ama_commitment > 0 else 0

        return {
            "total_orders": row.total_orders if row else 0,
            "total_spend": total_spend,
            "ama_commitment": ama_commitment,
            "ama_utilization": round(ama_utilization, 1),
        }
