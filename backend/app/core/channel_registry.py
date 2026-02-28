"""
Channel capability registry — defines what each outreach channel can do
and its constraints.
"""

CHANNELS = {
    "email": {
        "name": "Email",
        "supports_html": True,
        "supports_attachments": True,
        "max_body_length": 10000,
        "requires_opt_in": False,
        "cooldown_hours": 48,  # Min hours between emails to same lead
        "daily_limit_key": "email_daily_limit",
        "best_for": ["cold_outreach", "follow_up", "proposals", "newsletters"],
    },
    "linkedin": {
        "name": "LinkedIn",
        "supports_html": False,
        "supports_attachments": False,
        "max_body_length": 300,  # Connection request note limit
        "max_inmail_length": 1900,
        "requires_opt_in": False,
        "cooldown_hours": 72,
        "daily_limit_key": "linkedin_daily_limit",
        "best_for": ["connection_request", "inmail", "profile_engagement"],
    },
    "whatsapp": {
        "name": "WhatsApp Business",
        "supports_html": False,
        "supports_attachments": True,
        "max_body_length": 4096,
        "requires_opt_in": True,  # Must use approved templates for initiation
        "cooldown_hours": 24,
        "daily_limit_key": "whatsapp_daily_limit",
        "best_for": ["warm_outreach", "follow_up", "quick_updates"],
    },
    "instagram": {
        "name": "Instagram",
        "supports_html": False,
        "supports_attachments": True,
        "max_body_length": 1000,
        "requires_opt_in": False,
        "cooldown_hours": 72,
        "daily_limit_key": "instagram_daily_limit",
        "best_for": ["brand_engagement", "visual_showcase", "warm_dm"],
    },
    "gmb": {
        "name": "Google My Business",
        "supports_html": False,
        "supports_attachments": False,
        "max_body_length": 1500,
        "requires_opt_in": False,
        "cooldown_hours": 0,
        "daily_limit_key": None,
        "best_for": ["review_response", "q_and_a"],
    },
}

# Cross-channel coordination rules
CROSS_CHANNEL_RULES = {
    "min_gap_hours": 48,  # Minimum hours between different channel touches to same lead
    "max_channels_per_week": 2,  # Max different channels to use for one lead per week
    "channel_priority": ["email", "linkedin", "whatsapp", "instagram", "gmb"],
}
