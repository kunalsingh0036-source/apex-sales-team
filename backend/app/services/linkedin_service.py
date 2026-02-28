"""
LinkedIn service — handles connection requests, InMail, profile views.
Uses the LinkedIn Marketing/Community Management API.

For production scale, consider PhantomBuster or Dux-Soup as
LinkedIn doesn't offer a direct messaging API for non-partners.
This implementation uses the LinkedIn v2 REST API endpoints.
"""

import httpx
from app.config import get_settings


class LinkedInService:
    """LinkedIn outreach integration via LinkedIn API + fallback."""

    BASE_URL = "https://api.linkedin.com/v2"

    def _headers(self):
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.linkedin_access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def _is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.linkedin_access_token)

    async def get_profile(self) -> dict:
        """Get the authenticated user's LinkedIn profile."""
        if not self._is_configured():
            return {"error": "LinkedIn not configured"}

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/me",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def send_connection_request(
        self,
        profile_urn: str,
        note: str,
    ) -> dict:
        """
        Send a LinkedIn connection request with a personalized note.

        Args:
            profile_urn: LinkedIn member URN (e.g., "urn:li:person:abc123")
            note: Connection request note (max 300 chars)
        """
        if not self._is_configured():
            return {"status": "failed", "error": "LinkedIn not configured"}

        # Truncate note to LinkedIn's 300 character limit
        note = note[:300]

        payload = {
            "invitations": [
                {
                    "invitee": {
                        "com.linkedin.voyager.growth.invitation.InviteeProfile": {
                            "profileId": profile_urn.split(":")[-1],
                        }
                    },
                    "message": {"com.linkedin.voyager.growth.invitation.InvitationMessage": {"body": note}},
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/invitations",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                return {
                    "status": "sent",
                    "type": "connection_request",
                    "profile_urn": profile_urn,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def send_message(
        self,
        recipient_urn: str,
        body: str,
        subject: str | None = None,
    ) -> dict:
        """
        Send a LinkedIn message to an existing connection.

        Args:
            recipient_urn: LinkedIn member URN
            body: Message body
            subject: Optional subject (for InMail)
        """
        if not self._is_configured():
            return {"status": "failed", "error": "LinkedIn not configured"}

        # Get sender URN
        profile = await self.get_profile()
        sender_urn = f"urn:li:person:{profile.get('id', '')}"

        payload = {
            "recipients": [recipient_urn],
            "subject": subject or "",
            "body": body[:1900],
            "messageType": "MEMBER_TO_MEMBER",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                return {
                    "status": "sent",
                    "type": "message",
                    "recipient_urn": recipient_urn,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def send_inmail(
        self,
        recipient_urn: str,
        subject: str,
        body: str,
    ) -> dict:
        """
        Send an InMail to a non-connection.
        Requires LinkedIn Sales Navigator or premium API access.
        """
        if not self._is_configured():
            return {"status": "failed", "error": "LinkedIn not configured"}

        payload = {
            "recipients": [recipient_urn],
            "subject": subject[:200],
            "body": body[:1900],
            "messageType": "INMAIL",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                json=payload,
                headers=self._headers(),
            )

            if resp.status_code in (200, 201):
                return {
                    "status": "sent",
                    "type": "inmail",
                    "recipient_urn": recipient_urn,
                }
            else:
                return {
                    "status": "failed",
                    "error": resp.text,
                    "status_code": resp.status_code,
                }

    async def view_profile(self, profile_urn: str) -> dict:
        """
        View a LinkedIn profile (triggers 'who viewed your profile' notification).
        Useful as a warm-up before sending connection request.
        """
        if not self._is_configured():
            return {"status": "failed", "error": "LinkedIn not configured"}

        profile_id = profile_urn.split(":")[-1]
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/people/{profile_id}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return {"status": "viewed", "profile_urn": profile_urn}
            return {"status": "failed", "error": resp.text}


linkedin_service = LinkedInService()
