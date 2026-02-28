"""
Google My Business service.
Monitors reviews, responds to reviews, and manages Q&A.
Uses the Google My Business API (mybusinessaccountmanagement + mybusinessbusinessinformation).

Primarily used for:
- Monitoring reviews from potential corporate clients
- Responding to reviews in Apex brand voice
- Posting updates (new product launches, festive gifting announcements)
"""

import httpx
from app.config import get_settings


class GMBService:
    """Google My Business integration."""

    BASE_URL = "https://mybusiness.googleapis.com/v4"

    def _headers(self):
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.gmb_access_token}",
            "Content-Type": "application/json",
        }

    def _is_configured(self) -> bool:
        settings = get_settings()
        return bool(
            settings.gmb_access_token
            and settings.gmb_account_id
            and settings.gmb_location_id
        )

    def _location_path(self) -> str:
        settings = get_settings()
        return f"accounts/{settings.gmb_account_id}/locations/{settings.gmb_location_id}"

    async def get_reviews(self, page_size: int = 20) -> dict:
        """Fetch recent reviews for the business location."""
        if not self._is_configured():
            return {"error": "GMB not configured"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/{self._location_path()}/reviews",
                params={"pageSize": page_size},
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.text}

    async def reply_to_review(self, review_id: str, reply_text: str) -> dict:
        """
        Reply to a Google review.

        Args:
            review_id: The review name/ID
            reply_text: Reply text in Apex brand voice
        """
        if not self._is_configured():
            return {"status": "failed", "error": "GMB not configured"}

        payload = {"comment": reply_text[:4096]}

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.BASE_URL}/{self._location_path()}/reviews/{review_id}/reply",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code in (200, 201):
                return {"status": "replied", "review_id": review_id}
            return {"status": "failed", "error": resp.text}

    async def create_post(
        self,
        summary: str,
        call_to_action_type: str = "LEARN_MORE",
        call_to_action_url: str = "",
    ) -> dict:
        """
        Create a Google My Business post (update/offer).

        Args:
            summary: Post text (max 1500 chars)
            call_to_action_type: BOOK, ORDER, SHOP, LEARN_MORE, SIGN_UP, CALL
            call_to_action_url: URL for the CTA button
        """
        if not self._is_configured():
            return {"status": "failed", "error": "GMB not configured"}

        payload = {
            "languageCode": "en",
            "summary": summary[:1500],
            "topicType": "STANDARD",
        }
        if call_to_action_url:
            payload["callToAction"] = {
                "actionType": call_to_action_type,
                "url": call_to_action_url,
            }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/{self._location_path()}/localPosts",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code in (200, 201):
                return {"status": "posted", "post": resp.json()}
            return {"status": "failed", "error": resp.text}

    async def get_insights(self, metric: str = "ALL") -> dict:
        """Get business insights/metrics."""
        if not self._is_configured():
            return {"error": "GMB not configured"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/{self._location_path()}/insights",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.text}


gmb_service = GMBService()
