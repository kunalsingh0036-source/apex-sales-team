import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.schemas.quote import (
    QuoteCreate, QuoteUpdate, QuoteResponse,
    QuoteStatusUpdate, QuoteToOrderConversion,
)
from app.schemas.order import OrderResponse
from app.schemas.common import PaginatedResponse
from app.services.quote_service import QuoteService

router = APIRouter()
quote_service = QuoteService()


@router.get("", response_model=PaginatedResponse[QuoteResponse])
async def list_quotes(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    quotes, total = await quote_service.list_quotes(
        db, status=status, client_id=client_id, page=page, per_page=per_page,
    )
    return PaginatedResponse(
        items=quotes, total=total, page=page, per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=QuoteResponse, status_code=201)
async def create_quote(data: QuoteCreate, db: AsyncSession = Depends(get_db)):
    line_items_data = [item.model_dump() for item in data.line_items]
    quote_data = data.model_dump(exclude={"line_items"})
    client_id = quote_data.pop("client_id")
    valid_from = quote_data.pop("valid_from")
    valid_until = quote_data.pop("valid_until")
    gst_rate = quote_data.pop("gst_rate")
    discount_percent = quote_data.pop("discount_percent")

    quote = await quote_service.create_quote(
        db,
        client_id=client_id,
        valid_from=valid_from,
        valid_until=valid_until,
        line_items_data=line_items_data,
        gst_rate=gst_rate,
        discount_percent=discount_percent,
        **quote_data,
    )
    await db.commit()
    quote = await quote_service.get_quote(db, quote.id)
    return quote


@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(quote_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    quote = await quote_service.get_quote(db, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


@router.patch("/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: uuid.UUID, data: QuoteUpdate, db: AsyncSession = Depends(get_db),
):
    from app.models.quote import Quote
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(quote, key, value)
    await db.commit()
    return await quote_service.get_quote(db, quote_id)


@router.post("/{quote_id}/status", response_model=QuoteResponse)
async def update_quote_status(
    quote_id: uuid.UUID, data: QuoteStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        await quote_service.update_status(db, quote_id, data.status)
        await db.commit()
        return await quote_service.get_quote(db, quote_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{quote_id}/convert-to-order", response_model=OrderResponse)
async def convert_quote_to_order(
    quote_id: uuid.UUID,
    data: QuoteToOrderConversion,
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await quote_service.convert_to_order(
            db, quote_id, **data.model_dump(exclude_unset=True),
        )
        await db.commit()
        from app.services.order_service import OrderService
        return await OrderService().get_order(db, order.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
