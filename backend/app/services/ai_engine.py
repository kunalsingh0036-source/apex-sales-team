"""
AI Engine — Claude API integration for message generation, response classification,
lead scoring, and trend analysis.
"""

import json
from typing import Optional
import anthropic
from app.config import get_settings
from app.core.brand_voice import (
    BRAND_VOICE_SYSTEM_PROMPT,
    INDUSTRY_VOICE_OVERRIDES,
    RESPONSE_CLASSIFICATION_PROMPT,
    LEAD_SCORING_PROMPT,
)


class AIEngine:
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def generate_outreach_message(
        self,
        lead_name: str,
        lead_title: str,
        lead_company: str,
        lead_industry: str,
        channel: str,
        message_type: str = "cold_intro",
        context: str = "",
        custom_instructions: str = "",
    ) -> dict:
        """Generate a personalized outreach message in Apex brand voice."""

        # Build system prompt with industry override
        system = BRAND_VOICE_SYSTEM_PROMPT
        industry_key = lead_industry.lower().replace(" ", "_").replace("&", "").replace("/", "_")
        if industry_key in INDUSTRY_VOICE_OVERRIDES:
            system += "\n\n" + INDUSTRY_VOICE_OVERRIDES[industry_key]

        # Channel-specific instructions. LinkedIn connection_request has a separate
        # rule further down because 300 chars is a hard limit, not a guideline.
        is_linkedin_connection_request = (channel == "linkedin" and message_type == "connection_request")
        channel_notes = {
            "email": "Write a professional email with subject line and body. Keep it under 200 words.",
            "linkedin": (
                "Write a LinkedIn connection request note. HARD LIMIT: 300 characters "
                "total including signature. Warm, human, conversational. Sign with 'Radhika' "
                "only (no company, no phone — those are visible on the LinkedIn profile). "
                "Return subject as null."
            ) if is_linkedin_connection_request else (
                "Write a LinkedIn InMail message. Keep it under 500 words."
            ),
            "whatsapp": "Write a concise, professional WhatsApp message. Max 3-4 short paragraphs.",
            "instagram": "Write a brief, professional Instagram DM. Keep it under 150 words.",
        }

        type_notes = {
            "cold_intro": "This is the first contact. Introduce The Apex Human Company and why it's relevant to them.",
            "follow_up_1": "This is the first follow-up (3-5 days after initial outreach). Reference the previous message. Add new value.",
            "follow_up_2": "This is the second follow-up. More direct. Offer something concrete (samples, a quick call).",
            "breakup": "This is the final message. Graceful close. Leave the door open. No guilt or pressure.",
            "festive_gifting": "This is a seasonal outreach related to festive corporate gifting (Diwali, New Year, etc.).",
            "event_triggered": "This outreach is triggered by a specific company event. Reference the event naturally.",
            "referral": "Someone referred us to this contact. Mention the referral source.",
            "connection_request": (
                "This is a LinkedIn connection request note sent 1 day after an email. "
                "Reference the email naturally (e.g. 'sent you an email yesterday about X'). "
                "DO NOT re-pitch the company — you already did that in the email. Just warmly "
                "extend the invitation to connect on LinkedIn as well. Under 300 characters, strict."
            ),
        }

        prompt = f"""Generate a {channel} {message_type} message for the following lead:

Name: {lead_name}
Title: {lead_title}
Company: {lead_company}
Industry: {lead_industry}

Channel: {channel_notes.get(channel, "Write a professional outreach message.")}
Message type: {type_notes.get(message_type, "")}

{f"Additional context: {context}" if context else ""}
{f"Custom instructions: {custom_instructions}" if custom_instructions else ""}

Return your response as JSON:
{{"subject": "<email subject line, or null for non-email>", "body": "<the message body>", "notes": "<any internal notes about this message>"}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text
        # Parse JSON from response
        try:
            # Handle cases where Claude wraps JSON in markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {"subject": None, "body": text, "notes": "Failed to parse as JSON"}

    async def classify_response(self, message_text: str) -> dict:
        """Classify an inbound message response."""
        prompt = RESPONSE_CLASSIFICATION_PROMPT.format(message_text=message_text)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )

        classification = response.content[0].text.strip().lower()
        valid = [
            "interested", "not_interested", "out_of_office", "wrong_person",
            "requesting_info", "meeting_request", "objection", "referral", "unsubscribe",
        ]

        if classification not in valid:
            classification = "interested"  # Default to interested if unclear

        return {"classification": classification, "confidence": 0.85}

    async def score_lead(
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
        """Score a lead 0-100 using Claude."""
        prompt = LEAD_SCORING_PROMPT.format(
            name=name,
            job_title=job_title,
            department=department or "Unknown",
            seniority=seniority or "Unknown",
            company_name=company_name,
            industry=industry,
            employee_count=employee_count or "Unknown",
            city=city or "Unknown",
            events=events or "None detected",
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "score": 50,
                "breakdown": {
                    "industry_fit": 12,
                    "role_relevance": 12,
                    "company_size": 13,
                    "timing_signals": 13,
                },
                "reasoning": "Could not parse AI response, assigned default score.",
            }

    async def suggest_reply(
        self,
        original_message: str,
        response_text: str,
        lead_name: str,
        lead_company: str,
        classification: str,
    ) -> str:
        """Suggest a reply to an inbound message."""
        system = BRAND_VOICE_SYSTEM_PROMPT

        prompt = f"""A lead has replied to our outreach. Suggest a reply.

Original outreach message:
{original_message}

Their response:
{response_text}

Lead: {lead_name} at {lead_company}
Response classification: {classification}

Write a reply that:
- Maintains The Apex Human Company's brand voice
- Addresses their response appropriately
- Moves the conversation forward
- Is concise and respectful of their time

Just write the reply message, no JSON formatting needed."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text.strip()

    async def analyze_trends(self, metrics_summary: str) -> dict:
        """Analyze outreach metrics and recommend strategy adjustments."""
        prompt = f"""Analyze the following outreach metrics for The Apex Human Company and provide actionable recommendations.

{metrics_summary}

Provide your response as JSON:
{{
  "insights": ["<insight 1>", "<insight 2>", ...],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", ...],
  "best_performing": {{
    "channel": "<best channel>",
    "industry": "<best responding industry>",
    "message_type": "<best message type>"
  }},
  "areas_for_improvement": ["<area 1>", "<area 2>", ...]
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "insights": [text],
                "recommendations": [],
                "best_performing": {},
                "areas_for_improvement": [],
            }


ai_engine = AIEngine()
