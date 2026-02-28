"""
Lead scoring service — combines rule-based scoring with AI scoring.
Uses Apex-specific criteria: industry fit, seniority, company size, buying signals.
"""

from app.services.ai_engine import ai_engine
from app.core.indian_calendar import get_active_seasons

# Rule-based scoring weights (these combine with AI score)
INDUSTRY_SCORES = {
    "Technology & SaaS": 85,
    "Banking & Financial Services": 90,
    "Defence & Government": 95,
    "Hospitality & Luxury Hotels": 90,
    "Healthcare & Pharmaceuticals": 80,
    "Real Estate & Infrastructure": 75,
    "Educational Institutions": 70,
    "Events & Activations": 85,
    "FMCG": 65,
    "Manufacturing": 70,
    "Consulting": 75,
    "Media & Entertainment": 60,
}

SENIORITY_SCORES = {
    "c_suite": 100,
    "vp": 90,
    "director": 85,
    "manager": 70,
    "senior": 60,
    "entry": 30,
    "intern": 10,
}

TITLE_KEYWORDS_HIGH = [
    "procurement", "purchase", "buying", "sourcing",
    "hr", "human resources", "people", "culture",
    "marketing", "brand", "communications",
    "admin", "administration", "operations",
    "ceo", "cfo", "coo", "cmo", "chro", "cpo",
    "founder", "co-founder", "owner",
    "managing director", "md",
]

TITLE_KEYWORDS_MEDIUM = [
    "manager", "head", "director", "vp", "vice president",
    "chief", "lead", "senior",
]


class LeadScoringService:
    """Hybrid lead scoring: rule-based + AI."""

    def _rule_based_score(
        self,
        job_title: str,
        seniority: str,
        industry: str,
        employee_count: str,
        city: str,
    ) -> dict:
        """Calculate rule-based score component (0-100)."""
        score = 50  # Base score
        breakdown = {}

        # Industry fit (0-20 points)
        industry_base = INDUSTRY_SCORES.get(industry, 50)
        industry_points = int((industry_base / 100) * 20)
        score += industry_points - 10  # Center around 0
        breakdown["industry"] = industry_points

        # Seniority (0-20 points)
        seniority_base = SENIORITY_SCORES.get(seniority.lower(), 50)
        seniority_points = int((seniority_base / 100) * 20)
        score += seniority_points - 10
        breakdown["seniority"] = seniority_points

        # Title relevance (0-15 points)
        title_lower = (job_title or "").lower()
        title_points = 5  # Base
        if any(kw in title_lower for kw in TITLE_KEYWORDS_HIGH):
            title_points = 15
        elif any(kw in title_lower for kw in TITLE_KEYWORDS_MEDIUM):
            title_points = 10
        score += title_points - 7
        breakdown["title_relevance"] = title_points

        # Company size (0-10 points)
        size_points = 5
        try:
            emp = int(str(employee_count).replace(",", "").strip()) if employee_count else 0
            if emp >= 1000:
                size_points = 10
            elif emp >= 500:
                size_points = 8
            elif emp >= 200:
                size_points = 7
            elif emp >= 50:
                size_points = 5
            else:
                size_points = 3
        except (ValueError, TypeError):
            pass
        score += size_points - 5
        breakdown["company_size"] = size_points

        # India-specific location boost (0-5 points)
        city_lower = (city or "").lower()
        metro_cities = ["mumbai", "delhi", "bangalore", "bengaluru", "hyderabad",
                       "pune", "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow"]
        if any(c in city_lower for c in metro_cities):
            score += 5
            breakdown["location"] = 5
        elif "india" in city_lower or city_lower:
            score += 2
            breakdown["location"] = 2
        else:
            breakdown["location"] = 0

        # Seasonal boost (0-5 points)
        active_seasons = get_active_seasons()
        if active_seasons:
            seasonal_boost = min(5, len(active_seasons) * 2)
            score += seasonal_boost
            breakdown["seasonal"] = seasonal_boost
        else:
            breakdown["seasonal"] = 0

        return {
            "score": max(0, min(100, score)),
            "breakdown": breakdown,
        }

    async def score(
        self,
        name: str,
        job_title: str,
        department: str,
        seniority: str,
        company_name: str,
        industry: str,
        employee_count: str,
        city: str = "",
        events: str = "",
    ) -> dict:
        """
        Score a lead using both rule-based and AI scoring.

        Returns combined score (0-100) with breakdown.
        """
        # Rule-based component (40% weight)
        rule_result = self._rule_based_score(
            job_title=job_title,
            seniority=seniority,
            industry=industry,
            employee_count=employee_count,
            city=city,
        )

        # AI component (60% weight) — falls back to rule-based if API unavailable
        try:
            ai_result = await ai_engine.score_lead(
                name=name,
                job_title=job_title,
                department=department,
                seniority=seniority,
                company_name=company_name,
                industry=industry,
                employee_count=employee_count,
                city=city,
                events=events,
            )
            ai_score = ai_result.get("score", rule_result["score"])

            # Weighted combination
            combined_score = int(ai_score * 0.6 + rule_result["score"] * 0.4)

            return {
                "score": max(0, min(100, combined_score)),
                "ai_score": ai_score,
                "rule_score": rule_result["score"],
                "breakdown": {
                    **rule_result["breakdown"],
                    "ai_reasoning": ai_result.get("reasoning", ""),
                },
                "tier": _score_tier(combined_score),
            }
        except Exception:
            # Fallback to pure rule-based
            return {
                "score": rule_result["score"],
                "ai_score": None,
                "rule_score": rule_result["score"],
                "breakdown": rule_result["breakdown"],
                "tier": _score_tier(rule_result["score"]),
            }


def _score_tier(score: int) -> str:
    if score >= 80:
        return "hot"
    if score >= 60:
        return "warm"
    if score >= 40:
        return "medium"
    return "cold"


lead_scoring = LeadScoringService()
