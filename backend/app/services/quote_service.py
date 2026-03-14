"""
Quote service — handles quote creation, status management,
and quote-to-order conversion.
"""

import uuid
from datetime import date, datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.quote import Quote, QuoteItem
from app.models.order import Order
from app.services.order_service import OrderService


class QuoteService:

    def __init__(self):
        self.order_service = OrderService()

    async def create_quote(
        self, db: AsyncSession,
        client_id: uuid.UUID,
        valid_from: date,
        valid_until: date,
        line_items_data: list[dict],
        gst_rate: float = 18.0,
        discount_percent: float = 0,
        **kwargs,
    ) -> Quote:
        """Create a quote with auto-generated number and calculated financials."""
        quote_number = await self._generate_quote_number(db)

        subtotal = 0
        items = []
        for item_data in line_items_data:
            total_price = item_data["quantity"] * item_data["unit_price"]
            subtotal += total_price
            items.append(QuoteItem(
                product_id=item_data.get("product_id"),
                product_name=item_data["product_name"],
                description=item_data.get("description", ""),
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=total_price,
                size_breakdown=item_data.get("size_breakdown", {}),
                color=item_data.get("color"),
                gsm=item_data.get("gsm"),
                customization_type=item_data.get("customization_type"),
                customization_details=item_data.get("customization_details", ""),
            ))

        discount_amount = subtotal * discount_percent / 100
        taxable = subtotal - discount_amount
        gst_amount = taxable * gst_rate / 100
        total_amount = taxable + gst_amount

        quote = Quote(
            client_id=client_id,
            quote_number=quote_number,
            valid_from=valid_from,
            valid_until=valid_until,
            subtotal=subtotal,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            total_amount=total_amount,
            line_items=items,
            **kwargs,
        )
        db.add(quote)
        await db.flush()
        return quote

    async def update_status(
        self, db: AsyncSession,
        quote_id: uuid.UUID,
        status: str,
    ) -> Quote:
        """Update quote status with timestamp tracking."""
        quote = await db.get(Quote, quote_id)
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")

        now = datetime.now()
        quote.status = status
        if status == "sent":
            quote.sent_at = now
        elif status == "viewed":
            quote.viewed_at = now
        elif status == "accepted":
            quote.accepted_at = now

        await db.flush()
        return quote

    async def convert_to_order(
        self, db: AsyncSession,
        quote_id: uuid.UUID,
        **order_kwargs,
    ) -> Order:
        """Convert an accepted quote into an order."""
        result = await db.execute(
            select(Quote)
            .where(Quote.id == quote_id)
            .options(selectinload(Quote.line_items))
        )
        quote = result.scalar_one_or_none()
        if not quote:
            raise ValueError(f"Quote {quote_id} not found")
        if quote.status != "accepted":
            raise ValueError(f"Quote must be accepted before conversion (current: {quote.status})")

        # Build line item data from quote items
        line_items_data = []
        for qi in quote.line_items:
            line_items_data.append({
                "product_id": qi.product_id,
                "product_name": qi.product_name,
                "description": qi.description,
                "quantity": qi.quantity,
                "unit_price": float(qi.unit_price),
                "size_breakdown": qi.size_breakdown,
                "color": qi.color,
                "gsm": qi.gsm,
                "customization_type": qi.customization_type,
                "customization_details": qi.customization_details,
            })

        order = await self.order_service.create_order(
            db,
            client_id=quote.client_id,
            line_items_data=line_items_data,
            gst_rate=float(quote.gst_rate),
            discount_percent=float(quote.discount_percent),
            quote_id=quote.id,
            **order_kwargs,
        )

        quote.status = "converted"
        quote.converted_to_order_id = order.id
        await db.flush()
        return order

    async def get_quote(self, db: AsyncSession, quote_id: uuid.UUID) -> Quote | None:
        result = await db.execute(
            select(Quote)
            .where(Quote.id == quote_id)
            .options(selectinload(Quote.line_items), selectinload(Quote.client))
        )
        return result.scalar_one_or_none()

    async def list_quotes(
        self, db: AsyncSession,
        status: str | None = None,
        client_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[Quote], int]:
        query = select(Quote).options(selectinload(Quote.line_items), selectinload(Quote.client))
        count_query = select(func.count(Quote.id))

        if status:
            query = query.where(Quote.status == status)
            count_query = count_query.where(Quote.status == status)
        if client_id:
            query = query.where(Quote.client_id == client_id)
            count_query = count_query.where(Quote.client_id == client_id)

        total = (await db.execute(count_query)).scalar() or 0
        query = query.order_by(Quote.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def _generate_quote_number(self, db: AsyncSession) -> str:
        year = date.today().year
        prefix = f"QT-{year}-"
        result = await db.execute(
            select(func.count(Quote.id))
            .where(Quote.quote_number.like(f"{prefix}%"))
        )
        count = (result.scalar() or 0) + 1
        return f"{prefix}{count:04d}"
