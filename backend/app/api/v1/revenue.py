from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services.revenue_service import RevenueService
from app.services.order_service import OrderService

router = APIRouter()
revenue_service = RevenueService()
order_service = OrderService()


@router.get("/dashboard")
async def revenue_dashboard(db: AsyncSession = Depends(get_db)):
    return await revenue_service.get_revenue_dashboard(db)


@router.get("/by-client")
async def revenue_by_client(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await revenue_service.get_revenue_by_client(db, limit=limit)


@router.get("/monthly-trends")
async def monthly_trends(
    months: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
):
    return await revenue_service.get_monthly_trends(db, months=months)


@router.get("/pipeline-value")
async def pipeline_value(db: AsyncSession = Depends(get_db)):
    return await order_service.get_pipeline_summary(db)


@router.get("/ama-overview")
async def ama_overview(db: AsyncSession = Depends(get_db)):
    return await revenue_service.get_ama_overview(db)
