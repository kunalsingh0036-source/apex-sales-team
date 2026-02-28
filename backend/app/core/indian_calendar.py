"""
Indian business calendar for outreach timing optimization.
Tracks festive seasons, corporate event cycles, and optimal send windows.
"""

from datetime import date, time, datetime
from typing import Optional
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# Optimal email send windows for Indian corporates (IST)
SEND_WINDOWS = {
    "primary": {"start": time(10, 0), "end": time(11, 30)},    # Best open rates
    "secondary": {"start": time(14, 30), "end": time(15, 30)},  # Post-lunch
    "avoid": [
        {"start": time(13, 0), "end": time(14, 0)},  # Lunch hour
        {"start": time(18, 0), "end": time(9, 0)},    # After hours
    ],
}

# Major Indian festive/corporate seasons for outreach planning
# Dates are approximate — update yearly
FESTIVE_SEASONS = {
    "diwali": {
        "name": "Diwali Corporate Gifting Season",
        "peak_month": 10,  # October-November
        "ramp_up_weeks_before": 10,
        "industries": ["all"],
        "message_angle": "festive corporate gifting, team celebration merchandise",
    },
    "republic_day": {
        "name": "Republic Day",
        "peak_month": 1,
        "ramp_up_weeks_before": 6,
        "industries": ["defence_government"],
        "message_angle": "commemorative merchandise, institutional pride apparel",
    },
    "independence_day": {
        "name": "Independence Day",
        "peak_month": 8,
        "ramp_up_weeks_before": 6,
        "industries": ["defence_government"],
        "message_angle": "patriotic themed merchandise, institutional events",
    },
    "financial_year_end": {
        "name": "Financial Year-End Budget Utilization",
        "peak_month": 3,
        "ramp_up_weeks_before": 8,
        "industries": ["all"],
        "message_angle": "utilize remaining budget on team merchandise before FY close",
    },
    "new_year": {
        "name": "New Year Corporate Kits",
        "peak_month": 1,
        "ramp_up_weeks_before": 8,
        "industries": ["all"],
        "message_angle": "new year welcome kits, onboarding merchandise for new hires",
    },
    "holi": {
        "name": "Holi Celebration Merchandise",
        "peak_month": 3,
        "ramp_up_weeks_before": 4,
        "industries": ["technology_saas", "retail_consumer"],
        "message_angle": "team celebration tees, cultural event merchandise",
    },
    "annual_day_season": {
        "name": "Corporate Annual Day Season",
        "peak_month": 12,  # Dec-Jan common
        "ramp_up_weeks_before": 10,
        "industries": ["all"],
        "message_angle": "annual day merchandise, team awards, event branding",
    },
}

# Industry-specific conference seasons
CONFERENCE_SEASONS = {
    "technology_saas": {"months": [1, 2, 9, 10], "note": "Tech summit season"},
    "healthcare_pharma": {"months": [2, 3, 8, 9], "note": "Medical congress season"},
    "banking_finance": {"months": [4, 10], "note": "Banking conferences, AGM season"},
    "real_estate": {"months": [1, 2, 11], "note": "Real estate expos"},
}


def get_active_seasons(target_date: Optional[date] = None) -> list[dict]:
    """Return festive seasons where we should be ramping up outreach."""
    if target_date is None:
        target_date = datetime.now(IST).date()

    active = []
    for key, season in FESTIVE_SEASONS.items():
        peak_month = season["peak_month"]
        ramp_weeks = season["ramp_up_weeks_before"]

        # Calculate ramp-up start (approximate)
        ramp_start_month = (peak_month - (ramp_weeks // 4) - 1) % 12 + 1

        current_month = target_date.month
        if ramp_start_month <= peak_month:
            in_window = ramp_start_month <= current_month <= peak_month
        else:
            in_window = current_month >= ramp_start_month or current_month <= peak_month

        if in_window:
            active.append({"key": key, **season})

    return active


def is_good_send_time(dt: Optional[datetime] = None) -> bool:
    """Check if the given datetime (IST) is within optimal send windows."""
    if dt is None:
        dt = datetime.now(IST)

    ist_time = dt.astimezone(IST).time()

    # Check if in primary or secondary window
    primary = SEND_WINDOWS["primary"]
    secondary = SEND_WINDOWS["secondary"]

    return (
        primary["start"] <= ist_time <= primary["end"]
        or secondary["start"] <= ist_time <= secondary["end"]
    )


def next_send_window(dt: Optional[datetime] = None) -> datetime:
    """Return the next optimal send time (IST)."""
    if dt is None:
        dt = datetime.now(IST)

    ist_dt = dt.astimezone(IST)
    ist_time = ist_dt.time()
    today = ist_dt.date()

    primary_start = SEND_WINDOWS["primary"]["start"]
    secondary_start = SEND_WINDOWS["secondary"]["start"]

    if ist_time < primary_start:
        return datetime.combine(today, primary_start, tzinfo=IST)
    elif ist_time < secondary_start:
        return datetime.combine(today, secondary_start, tzinfo=IST)
    else:
        # Next day primary window
        from datetime import timedelta
        next_day = today + timedelta(days=1)
        # Skip weekends
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return datetime.combine(next_day, primary_start, tzinfo=IST)
