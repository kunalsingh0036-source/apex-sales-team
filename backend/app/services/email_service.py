"""
Gmail API email service for sending outreach emails.
Uses OAuth2 credentials for authentication.
"""

import base64
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from app.config import get_settings


class GmailService:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service

        settings = get_settings()
        creds = Credentials(
            token=None,
            refresh_token=settings.gmail_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            scopes=["https://www.googleapis.com/auth/gmail.send",
                     "https://www.googleapis.com/auth/gmail.readonly"],
        )
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[list[dict]] = None,
    ) -> dict:
        """Send an email via Gmail API.

        Args:
            attachments: list of {"filename": str, "content": bytes, "content_type": str}

        Returns dict with message_id and thread_id.
        """
        settings = get_settings()
        sender = settings.gmail_sender_email

        if attachments or html_body:
            message = MIMEMultipart("mixed")
            if html_body:
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(body, "plain"))
                alt.attach(MIMEText(html_body, "html"))
                message.attach(alt)
            else:
                message.attach(MIMEText(body, "plain"))

            for att in (attachments or []):
                mime_type = att.get("content_type", "application/octet-stream")
                maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
                part = MIMEBase(maintype, subtype)
                part.set_payload(att["content"])
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=att["filename"])
                message.attach(part)
        else:
            message = MIMEText(body, "plain")

        message["to"] = to
        message["from"] = sender
        message["subject"] = subject

        if reply_to:
            message["Reply-To"] = reply_to

        # Add unsubscribe header for compliance
        message["List-Unsubscribe"] = f"<mailto:{sender}?subject=unsubscribe>"

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        service = self._get_service()
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        return {
            "message_id": result.get("id"),
            "thread_id": result.get("threadId"),
        }

    async def check_replies(self, after_timestamp: Optional[str] = None) -> list[dict]:
        """Check for new replies in the inbox.

        Returns list of new messages with sender, subject, body, and thread_id.
        """
        service = self._get_service()

        query = "is:inbox is:unread"
        if after_timestamp:
            query += f" after:{after_timestamp}"

        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=50,
        ).execute()

        messages = results.get("messages", [])
        replies = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full",
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

            # Extract body
            body = ""
            payload = msg["payload"]
            if "parts" in payload:
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain":
                        data = part["body"].get("data", "")
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
            elif "body" in payload and payload["body"].get("data"):
                body = base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="replace")

            replies.append({
                "message_id": msg["id"],
                "thread_id": msg["threadId"],
                "from": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "body": body,
                "date": headers.get("date", ""),
            })

        return replies


    async def get_sent_messages(self, after_timestamp: Optional[str] = None) -> list[dict]:
        """Fetch sent messages from Gmail.

        Args:
            after_timestamp: Unix epoch string to filter messages after this time.

        Returns list of dicts with message_id, thread_id, to, subject, body, date.
        """
        service = self._get_service()

        query = "from:me"
        if after_timestamp:
            query += f" after:{after_timestamp}"

        results = service.users().messages().list(
            userId="me",
            q=query,
            labelIds=["SENT"],
            maxResults=100,
        ).execute()

        messages = results.get("messages", [])
        sent = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full",
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}

            # Extract body (same pattern as check_replies)
            body = ""
            payload = msg["payload"]
            if "parts" in payload:
                for part in payload["parts"]:
                    if part["mimeType"] == "text/plain":
                        data = part["body"].get("data", "")
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        break
            elif "body" in payload and payload["body"].get("data"):
                body = base64.urlsafe_b64decode(
                    payload["body"]["data"]
                ).decode("utf-8", errors="replace")

            # Extract just the email from "Name <email@domain.com>" format
            to_raw = headers.get("to", "")
            if "<" in to_raw:
                to_email = to_raw.split("<")[1].rstrip(">")
            else:
                to_email = to_raw.strip()

            sent.append({
                "message_id": msg["id"],
                "thread_id": msg["threadId"],
                "to": to_email,
                "to_raw": to_raw,
                "subject": headers.get("subject", ""),
                "body": body,
                "date": headers.get("date", ""),
            })

        return sent


gmail_service = GmailService()
