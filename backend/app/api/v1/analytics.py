"""
Analytics API endpoints.
Provides metrics, funnel analysis, channel comparison, and AI trend insights.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.services.analytics_service import analytics_service

router = APIRouter()


@router.get("/overview")
async def get_overview(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level metrics overview."""
    return await analytics_service.get_overview(db, days=days)


@router.get("/daily-trends")
async def get_daily_trends(
    days: int = Query(30, ge=1, le=365),
    channel: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get daily metric trends."""
    return await analytics_service.get_daily_trends(db, days=days, channel=channel)


@router.get("/channels")
async def get_channel_comparison(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Compare performance across channels."""
    return await analytics_service.get_channel_comparison(db, days=days)


@router.get("/funnel")
async def get_funnel(db: AsyncSession = Depends(get_db)):
    """Get pipeline funnel (leads by stage)."""
    return await analytics_service.get_funnel(db)


@router.get("/campaigns")
async def get_campaign_metrics(db: AsyncSession = Depends(get_db)):
    """Get metrics per campaign."""
    return await analytics_service.get_campaign_metrics(db)


@router.get("/ab-tests")
async def get_ab_tests(
    campaign_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get A/B test results."""
    return await analytics_service.get_ab_test_results(db, campaign_id=campaign_id)


@router.get("/lead-scores")
async def get_lead_score_distribution(db: AsyncSession = Depends(get_db)):
    """Get distribution of lead scores by tier."""
    return await analytics_service.get_lead_score_distribution(db)


@router.get("/ai-insights")
async def get_ai_insights(db: AsyncSession = Depends(get_db)):
    """Get AI-powered trend analysis and strategy recommendations."""
    return await analytics_service.get_ai_trend_analysis(db)


@router.post("/backfill")
async def backfill_metrics(days: int = Query(30, ge=1, le=365)):
    """Backfill daily metrics for the last N days."""
    from app.workers.analytics_tasks import backfill_metrics
    task = backfill_metrics.delay(days)
    return {"task_id": task.id, "status": "started", "days": days}
