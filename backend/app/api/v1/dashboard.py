from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.lead import Lead
from app.models.sequence import Campaign
from app.models.message import Message
from app.models.client import Client
from app.models.order import Order
from app.models.quote import Quote
from app.core.indian_calendar import get_active_seasons

router = APIRouter()


@router.get("/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate stats for the dashboard home page."""

    # Total leads
    total_leads = (
        await db.execute(select(func.count()).select_from(Lead))
    ).scalar() or 0

    # Pipeline (leads by stage)
    stage_counts_result = await db.execute(
        select(Lead.stage, func.count())
        .group_by(Lead.stage)
    )
    pipeline = {row[0]: row[1] for row in stage_counts_result.all()}

    # Active campaigns
    active_campaigns = (
        await db.execute(
            select(func.count()).select_from(Campaign).where(Campaign.status == "active")
        )
    ).scalar() or 0

    # Messages sent this week
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    messages_sent_week = (
        await db.execute(
            select(func.count())
            .select_from(Message)
            .where(
                Message.direction == "outbound",
                Message.status == "sent",
                Message.sent_at >= week_ago,
            )
        )
    ).scalar() or 0

    # Total messages sent
    total_sent = (
        await db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.direction == "outbound", Message.status == "sent")
        )
    ).scalar() or 0

    # Total replies (inbound messages)
    total_replies = (
        await db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.direction == "inbound")
        )
    ).scalar() or 0

    # Response rate
    response_rate = (
        round((total_replies / total_sent) * 100, 1) if total_sent > 0 else None
    )

    # Recent inbound classifications
    classification_result = await db.execute(
        select(Message.classification, func.count())
        .where(
            Message.direction == "inbound",
            Message.classification.isnot(None),
        )
        .group_by(Message.classification)
    )
    classifications = {row[0]: row[1] for row in classification_result.all()}

    # Active seasons
    active_seasons = get_active_seasons()

    # CRM metrics
    total_clients = (
        await db.execute(
            select(func.count()).select_from(Client).where(Client.status == "active")
        )
    ).scalar() or 0

    active_orders = (
        await db.execute(
            select(func.count()).select_from(Order)
            .where(Order.stage.notin_(["delivery"]))
        )
    ).scalar() or 0

    pipeline_value = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0))
            .where(Order.stage.notin_(["delivery"]))
        )
    ).scalar() or 0

    first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0))
            .where(Order.created_at >= first_of_month)
        )
    ).scalar() or 0

    pending_quotes = (
        await db.execute(
            select(func.count()).select_from(Quote)
            .where(Quote.status.in_(["draft", "sent", "viewed"]))
        )
    ).scalar() or 0

    # AMA distribution
    ama_result = await db.execute(
        select(Client.ama_tier, func.count())
        .where(Client.ama_tier.isnot(None))
        .group_by(Client.ama_tier)
    )
    ama_distribution = {row[0]: row[1] for row in ama_result.all()}

    return {
        "total_leads": total_leads,
        "active_campaigns": active_campaigns,
        "messages_sent_week": messages_sent_week,
        "total_sent": total_sent,
        "total_replies": total_replies,
        "response_rate": response_rate,
        "pipeline": pipeline,
        "classifications": classifications,
        "active_seasons": [
            {"name": s["name"], "key": s.get("key", ""), "message_angle": s.get("message_angle", "")}
            for s in active_seasons
        ],
        # CRM
        "total_clients": total_clients,
        "active_orders": active_orders,
        "pipeline_value": float(pipeline_value),
        "monthly_revenue": float(monthly_revenue),
        "pending_quotes": pending_quotes,
        "ama_distribution": ama_distribution,
    }
