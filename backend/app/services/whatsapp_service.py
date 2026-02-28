"""
WhatsApp Business API service.
Uses the Meta Cloud API (graph.facebook.com) for WhatsApp Business.

Key concepts:
- Template messages: Pre-approved templates to initiate conversation
- Session messages: Free-form messages within 24hr reply window
- Media messages: Images, documents, catalogs
"""

import httpx
from app.config import get_settings


class WhatsAppService:
    """WhatsApp Business API integration via Meta Cloud API."""

    GRAPH_URL = "https://graph.facebook.com/v18.0"

    def _headers(self):
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

    def _phone_number_id(self) -> str:
        return get_settings().whatsapp_phone_number_id

    def _is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to international format (no + prefix)."""
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        if phone.startswith("0"):
            phone = "91" + phone[1:]  # Default to India
        return phone

    async def send_template_message(
        self,
        phone: str,
        template_name: str,
        language_code: str = "en",
        components: list | None = None,
    ) -> dict:
        """
        Send a pre-approved WhatsApp template message.

        Args:
            phone: Recipient phone number (international format)
            template_name: Approved template name
            language_code: Template language (default: en)
            components: Template components (header, body params, buttons)
        """
        if not self._is_configured():
            return {"status": "failed", "error": "WhatsApp not configured"}

        phone = self._normalize_phone(phone)
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{self._phone_number_id()}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id")
                return {
                    "status": "sent",
                    "type": "template",
                    "message_id": msg_id,
                    "phone": phone,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def send_text_message(
        self,
        phone: str,
        body: str,
        preview_url: bool = False,
    ) -> dict:
        """
        Send a free-form text message (only within 24hr session window).

        Args:
            phone: Recipient phone number
            body: Message text (max 4096 chars)
            preview_url: Whether to show URL previews
        """
        if not self._is_configured():
            return {"status": "failed", "error": "WhatsApp not configured"}

        phone = self._normalize_phone(phone)
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "body": body[:4096],
                "preview_url": preview_url,
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{self._phone_number_id()}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id")
                return {
                    "status": "sent",
                    "type": "text",
                    "message_id": msg_id,
                    "phone": phone,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def send_media_message(
        self,
        phone: str,
        media_type: str,
        media_url: str,
        caption: str = "",
    ) -> dict:
        """
        Send a media message (image, document, video).

        Args:
            phone: Recipient phone number
            media_type: "image", "document", or "video"
            media_url: Public URL of the media
            caption: Caption text
        """
        if not self._is_configured():
            return {"status": "failed", "error": "WhatsApp not configured"}

        phone = self._normalize_phone(phone)
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": media_type,
            media_type: {
                "link": media_url,
                "caption": caption[:1024] if caption else "",
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{self._phone_number_id()}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                msg_id = data.get("messages", [{}])[0].get("id")
                return {"status": "sent", "type": media_type, "message_id": msg_id}
            else:
                return {"status": "failed", "error": resp.text}

    async def mark_as_read(self, message_id: str) -> dict:
        """Mark an inbound message as read."""
        if not self._is_configured():
            return {"status": "failed", "error": "WhatsApp not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.GRAPH_URL}/{self._phone_number_id()}/messages",
                json=payload,
                headers=self._headers(),
            )
            return {"status": "read" if resp.status_code == 200 else "failed"}

    async def get_business_profile(self) -> dict:
        """Get the WhatsApp Business profile info."""
        if not self._is_configured():
            return {"error": "WhatsApp not configured"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.GRAPH_URL}/{self._phone_number_id()}/whatsapp_business_profile",
                params={"fields": "about,address,description,email,profile_picture_url,websites,vertical"},
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": resp.text}


whatsapp_service = WhatsAppService()
