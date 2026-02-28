"""
Analytics service — aggregates metrics, detects trends, generates reports.
Provides funnel analysis, channel comparison, and AI-powered trend insights.
"""

from datetime import date, timedelta
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.analytics import DailyMetric, ABTestResult
from app.models.lead import Lead
from app.models.message import Message
from app.models.sequence import Campaign, CampaignEnrollment


class AnalyticsService:
    """Metrics aggregation, funnel analysis, and trend detection."""

    async def get_overview(self, db: AsyncSession, days: int = 30) -> dict:
        """Get high-level metrics for the last N days."""
        start_date = date.today() - timedelta(days=days)

        # Aggregate daily metrics
        result = await db.execute(
            select(
                func.sum(DailyMetric.sent).label("total_sent"),
                func.sum(DailyMetric.delivered).label("total_delivered"),
                func.sum(DailyMetric.opened).label("total_opened"),
                func.sum(DailyMetric.replied).label("total_replied"),
                func.sum(DailyMetric.positive_replies).label("total_positive"),
                func.sum(DailyMetric.meetings_booked).label("total_meetings"),
                func.sum(DailyMetric.bounced).label("total_bounced"),
                func.sum(DailyMetric.unsubscribed).label("total_unsubscribed"),
            ).where(DailyMetric.date >= start_date)
        )
        row = result.first()

        total_sent = row.total_sent or 0
        total_replied = row.total_replied or 0

        return {
            "period_days": days,
            "total_sent": total_sent,
            "total_delivered": row.total_delivered or 0,
            "total_opened": row.total_opened or 0,
            "total_replied": total_replied,
            "total_positive_replies": row.total_positive or 0,
            "total_meetings": row.total_meetings or 0,
            "total_bounced": row.total_bounced or 0,
            "total_unsubscribed": row.total_unsubscribed or 0,
            "reply_rate": round((total_replied / total_sent) * 100, 1) if total_sent > 0 else 0,
            "positive_rate": round(((row.total_positive or 0) / total_replied) * 100, 1) if total_replied > 0 else 0,
            "bounce_rate": round(((row.total_bounced or 0) / total_sent) * 100, 1) if total_sent > 0 else 0,
        }

    async def get_daily_trends(self, db: AsyncSession, days: int = 30, channel: str | None = None) -> list[dict]:
        """Get daily metric trends."""
        start_date = date.today() - timedelta(days=days)

        query = select(
            DailyMetric.date,
            func.sum(DailyMetric.sent).label("sent"),
            func.sum(DailyMetric.replied).label("replied"),
            func.sum(DailyMetric.positive_replies).label("positive"),
            func.sum(DailyMetric.meetings_booked).label("meetings"),
        ).where(DailyMetric.date >= start_date).group_by(DailyMetric.date).order_by(DailyMetric.date)

        if channel:
            query = query.where(DailyMetric.channel == channel)

        result = await db.execute(query)
        return [
            {
                "date": str(row.date),
                "sent": row.sent or 0,
                "replied": row.replied or 0,
                "positive": row.positive or 0,
                "meetings": row.meetings or 0,
            }
            for row in result.all()
        ]

    async def get_channel_comparison(self, db: AsyncSession, days: int = 30) -> list[dict]:
        """Compare performance across channels."""
        start_date = date.today() - timedelta(days=days)

        result = await db.execute(
            select(
                DailyMetric.channel,
                func.sum(DailyMetric.sent).label("sent"),
                func.sum(DailyMetric.delivered).label("delivered"),
                func.sum(DailyMetric.replied).label("replied"),
                func.sum(DailyMetric.positive_replies).label("positive"),
                func.sum(DailyMetric.meetings_booked).label("meetings"),
                func.sum(DailyMetric.bounced).label("bounced"),
            )
            .where(DailyMetric.date >= start_date)
            .group_by(DailyMetric.channel)
        )

        channels = []
        for row in result.all():
            sent = row.sent or 0
            replied = row.replied or 0
            channels.append({
                "channel": row.channel,
                "sent": sent,
                "delivered": row.delivered or 0,
                "replied": replied,
                "positive_replies": row.positive or 0,
                "meetings": row.meetings or 0,
                "bounced": row.bounced or 0,
                "reply_rate": round((replied / sent) * 100, 1) if sent > 0 else 0,
                "positive_rate": round(((row.positive or 0) / replied) * 100, 1) if replied > 0 else 0,
            })
        return channels

    async def get_funnel(self, db: AsyncSession) -> list[dict]:
        """Get pipeline funnel — leads by stage."""
        result = await db.execute(
            select(Lead.stage, func.count())
            .group_by(Lead.stage)
        )
        stage_order = ["prospect", "contacted", "engaged", "qualified",
                       "proposal_sent", "negotiation", "won", "lost"]
        stage_counts = {row[0]: row[1] for row in result.all()}

        total = sum(stage_counts.values()) or 1
        return [
            {
                "stage": stage,
                "count": stage_counts.get(stage, 0),
                "percentage": round((stage_counts.get(stage, 0) / total) * 100, 1),
            }
            for stage in stage_order
        ]

    async def get_campaign_metrics(self, db: AsyncSession) -> list[dict]:
        """Get metrics per campaign."""
        result = await db.execute(
            select(
                Campaign.id,
                Campaign.name,
                Campaign.status,
                func.count(CampaignEnrollment.id).label("enrollments"),
                func.sum(case((CampaignEnrollment.status == "active", 1), else_=0)).label("active"),
                func.sum(case((CampaignEnrollment.status == "replied", 1), else_=0)).label("replied"),
                func.sum(case((CampaignEnrollment.status == "completed", 1), else_=0)).label("completed"),
            )
            .join(CampaignEnrollment, CampaignEnrollment.campaign_id == Campaign.id, isouter=True)
            .group_by(Campaign.id, Campaign.name, Campaign.status)
            .order_by(Campaign.created_at.desc())
        )
        return [
            {
                "id": str(row.id),
                "name": row.name,
                "status": row.status,
                "enrollments": row.enrollments or 0,
                "active": row.active or 0,
                "replied": row.replied or 0,
                "completed": row.completed or 0,
                "reply_rate": round(((row.replied or 0) / (row.enrollments or 1)) * 100, 1),
            }
            for row in result.all()
        ]

    async def get_ab_test_results(self, db: AsyncSession, campaign_id: str | None = None) -> list[dict]:
        """Get A/B test results, optionally filtered by campaign."""
        query = select(ABTestResult).order_by(ABTestResult.created_at.desc())
        if campaign_id:
            query = query.where(ABTestResult.campaign_id == campaign_id)

        result = await db.execute(query.limit(50))
        tests = result.scalars().all()
        return [
            {
                "id": str(t.id),
                "campaign_id": str(t.campaign_id),
                "step_number": t.step_number,
                "variant_a": {
                    "sent": t.variant_a_sent,
                    "opened": t.variant_a_opened,
                    "replied": t.variant_a_replied,
                    "reply_rate": round((t.variant_a_replied / t.variant_a_sent) * 100, 1) if t.variant_a_sent > 0 else 0,
                },
                "variant_b": {
                    "sent": t.variant_b_sent,
                    "opened": t.variant_b_opened,
                    "replied": t.variant_b_replied,
                    "reply_rate": round((t.variant_b_replied / t.variant_b_sent) * 100, 1) if t.variant_b_sent > 0 else 0,
                },
                "winner": t.winner,
                "confidence": float(t.confidence) if t.confidence else None,
            }
            for t in tests
        ]

    async def get_lead_score_distribution(self, db: AsyncSession) -> list[dict]:
        """Get distribution of lead scores."""
        result = await db.execute(
            select(
                case(
                    (Lead.lead_score >= 80, "hot"),
                    (Lead.lead_score >= 60, "warm"),
                    (Lead.lead_score >= 40, "medium"),
                    (Lead.lead_score < 40, "cold"),
                    else_="unscored",
                ).label("tier"),
                func.count().label("count"),
            )
            .where(Lead.lead_score.isnot(None))
            .group_by("tier")
        )
        return [{"tier": row.tier, "count": row.count} for row in result.all()]

    async def get_ai_trend_analysis(self, db: AsyncSession) -> dict:
        """Get AI-powered trend analysis using Claude."""
        # Gather data for analysis
        overview = await self.get_overview(db, days=30)
        channels = await self.get_channel_comparison(db, days=30)
        funnel = await self.get_funnel(db)

        from app.services.ai_engine import ai_engine
        trends = await ai_engine.analyze_trends(
            metrics=overview,
            time_range="last 30 days",
        )
        return {
            "analysis": trends,
            "data_snapshot": {
                "overview": overview,
                "channels": channels,
                "funnel": funnel,
            },
        }


analytics_service = AnalyticsService()
