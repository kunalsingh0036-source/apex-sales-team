"""
Social media service — Instagram DMs via Meta Graph API.
Uses the Instagram Messaging API (part of Messenger Platform).

Requirements:
- Facebook Page linked to Instagram Professional Account
- Meta App with instagram_manage_messages permission
- Approved for Instagram Messaging API
"""

import httpx
from app.config import get_settings


class InstagramService:
    """Instagram DM integration via Meta Graph API."""

    GRAPH_URL = "https://graph.facebook.com/v18.0"

    def _headers(self):
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.meta_access_token}",
            "Content-Type": "application/json",
        }

    def _is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.meta_access_token and settings.meta_page_id)

    async def send_dm(
        self,
        recipient_id: str,
        message: str,
    ) -> dict:
        """
        Send an Instagram DM.

        Args:
            recipient_id: Instagram-scoped user ID (IGSID)
            message: Message text (max 1000 chars)

        Note: You can only message users who have messaged your business first,
        OR if you use the human_agent tag within 7 days of last user message.
        For cold outreach, use ice_breaker messages or story replies.
        """
        if not self._is_configured():
            return {"status": "failed", "error": "Instagram not configured"}

        settings = get_settings()
        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": message[:1000]},
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{settings.meta_page_id}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "status": "sent",
                    "type": "dm",
                    "message_id": data.get("message_id"),
                    "recipient_id": recipient_id,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def send_media_dm(
        self,
        recipient_id: str,
        media_url: str,
        media_type: str = "image",
    ) -> dict:
        """
        Send a media DM (image or video).

        Args:
            recipient_id: Instagram-scoped user ID
            media_url: Public URL of the media
            media_type: "image" or "video"
        """
        if not self._is_configured():
            return {"status": "failed", "error": "Instagram not configured"}

        settings = get_settings()
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": media_type,
                    "payload": {"url": media_url},
                }
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{settings.meta_page_id}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                return {
                    "status": "sent",
                    "type": f"media_{media_type}",
                    "message_id": data.get("message_id"),
                }
            else:
                return {"status": "failed", "error": resp.text}

    async def send_ice_breaker(
        self,
        recipient_id: str,
        question: str,
    ) -> dict:
        """
        Send an ice breaker question (for initiating conversations).
        Ice breakers appear as quick reply suggestions to the user.
        """
        if not self._is_configured():
            return {"status": "failed", "error": "Instagram not configured"}

        settings = get_settings()
        payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "text": question[:1000],
                "quick_replies": [
                    {
                        "content_type": "text",
                        "title": "Tell me more",
                        "payload": "INTERESTED",
                    },
                    {
                        "content_type": "text",
                        "title": "Not now",
                        "payload": "NOT_INTERESTED",
                    },
                ],
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{settings.meta_page_id}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                return {"status": "sent", "type": "ice_breaker"}
            return {"status": "failed", "error": resp.text}

    async def get_conversations(self, limit: int = 20) -> dict:
        """Get recent Instagram conversations."""
        if not self._is_configured():
            return {"error": "Instagram not configured"}

        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.GRAPH_URL}/{settings.meta_page_id}/conversations",
                params={
                    "platform": "instagram",
                    "limit": limit,
                    "fields": "participants,messages{message,from,created_time}",
                },
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.text}


instagram_service = InstagramService()
