"""
Order service — handles order creation, stage advancement,
pipeline summaries, and financial calculations.
"""

import uuid
from datetime import date
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.order import Order, OrderItem, OrderStageLog, ORDER_STAGES, VALID_STAGE_TRANSITIONS


class OrderService:

    async def create_order(
        self, db: AsyncSession,
        client_id: uuid.UUID,
        line_items_data: list[dict],
        gst_rate: float = 18.0,
        discount_percent: float = 0,
        **kwargs,
    ) -> Order:
        """Create order with auto-generated number and calculated financials."""
        order_number = await self._generate_order_number(db)

        # Calculate financials
        subtotal = 0
        items = []
        for item_data in line_items_data:
            total_price = item_data["quantity"] * item_data["unit_price"]
            subtotal += total_price
            items.append(OrderItem(
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

        order = Order(
            client_id=client_id,
            order_number=order_number,
            subtotal=subtotal,
            gst_rate=gst_rate,
            gst_amount=gst_amount,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            total_amount=total_amount,
            line_items=items,
            **kwargs,
        )
        db.add(order)

        # Log initial stage
        log = OrderStageLog(
            order_id=order.id,
            from_stage=None,
            to_stage="brief",
            notes="Order created",
        )
        db.add(log)

        await db.flush()
        return order

    async def advance_stage(
        self, db: AsyncSession,
        order_id: uuid.UUID,
        to_stage: str,
        notes: str = "",
        changed_by: uuid.UUID | None = None,
    ) -> Order:
        """Advance an order to a new stage with validation."""
        order = await db.get(Order, order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        valid_next = VALID_STAGE_TRANSITIONS.get(order.stage, [])
        if to_stage not in valid_next:
            raise ValueError(
                f"Cannot transition from '{order.stage}' to '{to_stage}'. "
                f"Valid transitions: {valid_next}"
            )

        log = OrderStageLog(
            order_id=order.id,
            from_stage=order.stage,
            to_stage=to_stage,
            notes=notes,
            changed_by=changed_by,
        )
        db.add(log)

        order.stage = to_stage
        if to_stage == "delivery":
            order.actual_delivery_date = date.today()

        await db.flush()
        return order

    async def get_order(self, db: AsyncSession, order_id: uuid.UUID) -> Order | None:
        result = await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.line_items),
                selectinload(Order.stage_history),
                selectinload(Order.client),
            )
        )
        return result.scalar_one_or_none()

    async def list_orders(
        self, db: AsyncSession,
        stage: str | None = None,
        client_id: uuid.UUID | None = None,
        priority: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[Order], int]:
        query = select(Order).options(selectinload(Order.line_items), selectinload(Order.client))
        count_query = select(func.count(Order.id))

        if stage:
            query = query.where(Order.stage == stage)
            count_query = count_query.where(Order.stage == stage)
        if client_id:
            query = query.where(Order.client_id == client_id)
            count_query = count_query.where(Order.client_id == client_id)
        if priority:
            query = query.where(Order.priority == priority)
            count_query = count_query.where(Order.priority == priority)

        total = (await db.execute(count_query)).scalar() or 0
        query = query.order_by(Order.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_pipeline_summary(self, db: AsyncSession) -> dict:
        """Count and value per pipeline stage."""
        result = await db.execute(
            select(
                Order.stage,
                func.count(Order.id).label("count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_value"),
            ).group_by(Order.stage)
        )
        stages = []
        total_orders = 0
        total_value = 0
        for row in result.all():
            stages.append({
                "stage": row.stage,
                "count": row.count,
                "total_value": float(row.total_value),
            })
            total_orders += row.count
            total_value += float(row.total_value)

        return {
            "stages": stages,
            "total_orders": total_orders,
            "total_pipeline_value": total_value,
        }

    async def _generate_order_number(self, db: AsyncSession) -> str:
        year = date.today().year
        prefix = f"APEX-{year}-"
        result = await db.execute(
            select(func.count(Order.id))
            .where(Order.order_number.like(f"{prefix}%"))
        )
        count = (result.scalar() or 0) + 1
        return f"{prefix}{count:04d}"
