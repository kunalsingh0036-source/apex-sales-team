import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.order import (
    OrderCreate, OrderUpdate, OrderResponse,
    OrderStageChange, OrderStageLogResponse,
    PipelineSummary,
)
from app.schemas.common import PaginatedResponse
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    stage: str | None = None,
    client_id: uuid.UUID | None = None,
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.list_orders(
        db, stage=stage, client_id=client_id, priority=priority,
        page=page, per_page=per_page,
    )
    return PaginatedResponse(
        items=orders, total=total, page=page, per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(data: OrderCreate, db: AsyncSession = Depends(get_db)):
    line_items_data = [item.model_dump() for item in data.line_items]
    order_data = data.model_dump(exclude={"line_items"})
    client_id = order_data.pop("client_id")
    gst_rate = order_data.pop("gst_rate")
    discount_percent = order_data.pop("discount_percent")

    order = await order_service.create_order(
        db,
        client_id=client_id,
        line_items_data=line_items_data,
        gst_rate=gst_rate,
        discount_percent=discount_percent,
        **order_data,
    )
    await db.commit()
    # Re-fetch with relationships
    order = await order_service.get_order(db, order.id)
    return order


@router.get("/pipeline", response_model=PipelineSummary)
async def get_pipeline_summary(db: AsyncSession = Depends(get_db)):
    return await order_service.get_pipeline_summary(db)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: uuid.UUID, data: OrderUpdate, db: AsyncSession = Depends(get_db),
):
    from app.models.order import Order
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(order, key, value)
    await db.commit()
    return await order_service.get_order(db, order_id)


@router.delete("/{order_id}", status_code=204)
async def delete_order(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.order import Order
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.delete(order)
    await db.commit()


@router.post("/{order_id}/advance-stage", response_model=OrderResponse)
async def advance_stage(
    order_id: uuid.UUID,
    data: OrderStageChange,
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.advance_stage(
            db, order_id, data.to_stage, data.notes, data.changed_by,
        )
        await db.commit()
        return await order_service.get_order(db, order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{order_id}/stage-history", response_model=list[OrderStageLogResponse])
async def get_stage_history(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.order import OrderStageLog
    result = await db.execute(
        select(OrderStageLog)
        .where(OrderStageLog.order_id == order_id)
        .order_by(OrderStageLog.created_at.asc())
    )
    return list(result.scalars().all())
