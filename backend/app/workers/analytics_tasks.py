"""
Celery tasks for analytics operations.
Handles daily metrics rollup from messages table into daily_metrics.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from sqlalchemy import select, func, case, and_
from app.workers.celery_app import celery_app


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.workers.analytics_tasks.daily_rollup")
def daily_rollup(target_date: str | None = None):
    """
    Aggregate daily metrics from messages table into daily_metrics.
    Runs at 11:55 PM IST via Celery Beat.
    """
    from app.dependencies import create_worker_session
    from app.models.message import Message
    from app.models.analytics import DailyMetric

    async def _rollup():
        rollup_date = (
            date.fromisoformat(target_date) if target_date else date.today()
        )
        day_start = datetime.combine(rollup_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        async with create_worker_session()() as db:
            # Get metrics grouped by channel and campaign
            result = await db.execute(
                select(
                    Message.channel,
                    Message.campaign_id,
                    func.count().filter(
                        and_(Message.direction == "outbound", Message.status == "sent")
                    ).label("sent"),
                    func.count().filter(
                        and_(Message.direction == "outbound", Message.status == "sent")
                    ).label("delivered"),  # Approximate
                    func.count().filter(
                        Message.direction == "inbound"
                    ).label("replied"),
                    func.count().filter(
                        and_(
                            Message.direction == "inbound",
                            Message.classification.in_(["interested", "meeting_request", "requesting_info"]),
                        )
                    ).label("positive_replies"),
                    func.count().filter(
                        and_(
                            Message.direction == "inbound",
                            Message.classification == "meeting_request",
                        )
                    ).label("meetings_booked"),
                    func.count().filter(
                        and_(Message.direction == "outbound", Message.status == "bounced")
                    ).label("bounced"),
                    func.count().filter(
                        and_(
                            Message.direction == "inbound",
                            Message.classification == "unsubscribe",
                        )
                    ).label("unsubscribed"),
                )
                .where(
                    Message.created_at >= day_start,
                    Message.created_at < day_end,
                )
                .group_by(Message.channel, Message.campaign_id)
            )

            rows = result.all()
            upserted = 0

            for row in rows:
                # Check if metric already exists
                existing = await db.execute(
                    select(DailyMetric).where(
                        DailyMetric.date == rollup_date,
                        DailyMetric.channel == row.channel,
                        DailyMetric.campaign_id == row.campaign_id,
                    )
                )
                metric = existing.scalar_one_or_none()

                if metric:
                    metric.sent = row.sent or 0
                    metric.delivered = row.delivered or 0
                    metric.replied = row.replied or 0
                    metric.positive_replies = row.positive_replies or 0
                    metric.meetings_booked = row.meetings_booked or 0
                    metric.bounced = row.bounced or 0
                    metric.unsubscribed = row.unsubscribed or 0
                else:
                    metric = DailyMetric(
                        date=rollup_date,
                        channel=row.channel,
                        campaign_id=row.campaign_id,
                        sent=row.sent or 0,
                        delivered=row.delivered or 0,
                        replied=row.replied or 0,
                        positive_replies=row.positive_replies or 0,
                        meetings_booked=row.meetings_booked or 0,
                        bounced=row.bounced or 0,
                        unsubscribed=row.unsubscribed or 0,
                    )
                    db.add(metric)
                upserted += 1

            await db.commit()
            return {"date": str(rollup_date), "metrics_upserted": upserted}

    return run_async(_rollup())


@celery_app.task(name="app.workers.analytics_tasks.backfill_metrics")
def backfill_metrics(days: int = 30):
    """Backfill daily metrics for the last N days."""
    results = []
    for i in range(days):
        target = (date.today() - timedelta(days=i)).isoformat()
        result = daily_rollup(target)
        results.append(result)
    return {"backfilled": len(results), "results": results}
