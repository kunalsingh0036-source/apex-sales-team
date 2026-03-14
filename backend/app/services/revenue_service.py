"""
Revenue service — dashboard analytics for CRM revenue tracking,
AMA distribution, monthly trends, and pipeline value.
"""

from datetime import date, timedelta
from sqlalchemy import select, func, extract, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order
from app.models.client import Client
from app.models.quote import Quote


class RevenueService:

    async def get_revenue_dashboard(self, db: AsyncSession) -> dict:
        """Top-level revenue metrics."""
        # Total revenue from all orders
        result = await db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            )
        )
        row = result.first()

        # This month's revenue
        first_of_month = date.today().replace(day=1)
        month_result = await db.execute(
            select(
                func.coalesce(func.sum(Order.total_amount), 0).label("monthly_revenue"),
            ).where(Order.created_at >= first_of_month)
        )
        monthly = month_result.scalar() or 0

        # Active clients
        client_count = await db.execute(
            select(func.count(Client.id)).where(Client.status == "active")
        )

        # Pending quotes
        quote_result = await db.execute(
            select(
                func.count(Quote.id).label("count"),
                func.coalesce(func.sum(Quote.total_amount), 0).label("value"),
            ).where(Quote.status.in_(["draft", "sent", "viewed"]))
        )
        quote_row = quote_result.first()

        return {
            "total_revenue": float(row.total_revenue) if row else 0,
            "total_orders": row.total_orders if row else 0,
            "monthly_revenue": float(monthly),
            "active_clients": client_count.scalar() or 0,
            "pending_quotes_count": quote_row.count if quote_row else 0,
            "pending_quotes_value": float(quote_row.value) if quote_row else 0,
        }

    async def get_revenue_by_client(
        self, db: AsyncSession, limit: int = 10
    ) -> list[dict]:
        """Top clients by revenue."""
        result = await db.execute(
            select(
                Client.id,
                Client.primary_contact_name,
                Client.ama_tier,
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            )
            .join(Order, Order.client_id == Client.id)
            .group_by(Client.id, Client.primary_contact_name, Client.ama_tier)
            .order_by(func.sum(Order.total_amount).desc())
            .limit(limit)
        )
        return [
            {
                "client_id": str(row.id),
                "name": row.primary_contact_name,
                "ama_tier": row.ama_tier,
                "order_count": row.order_count,
                "total_revenue": float(row.total_revenue),
            }
            for row in result.all()
        ]

    async def get_monthly_trends(
        self, db: AsyncSession, months: int = 12
    ) -> list[dict]:
        """Monthly revenue for the last N months."""
        start_date = date.today() - timedelta(days=months * 30)
        result = await db.execute(
            select(
                extract("year", Order.created_at).label("year"),
                extract("month", Order.created_at).label("month"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .where(Order.created_at >= start_date)
            .group_by("year", "month")
            .order_by("year", "month")
        )
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "order_count": row.order_count,
                "revenue": float(row.revenue),
            }
            for row in result.all()
        ]

    async def get_ama_overview(self, db: AsyncSession) -> list[dict]:
        """AMA tier distribution with client counts and commitment totals."""
        result = await db.execute(
            select(
                Client.ama_tier,
                func.count(Client.id).label("client_count"),
                func.coalesce(func.sum(Client.ama_commitment), 0).label("total_commitment"),
            )
            .where(Client.ama_tier.isnot(None))
            .group_by(Client.ama_tier)
        )
        return [
            {
                "tier": row.ama_tier,
                "client_count": row.client_count,
                "total_commitment": float(row.total_commitment),
            }
            for row in result.all()
        ]
