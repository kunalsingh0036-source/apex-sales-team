import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Resolve .env from project root (one level above backend/)
# Only load in development (when the file exists and not on Railway/production)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_FILE.exists() and not os.environ.get("RAILWAY_ENVIRONMENT"):
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=False)  # env vars take precedence over .env


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://apex:apex_dev_password@localhost:5432/apex_outreach"
    database_url_sync: str = ""

    @property
    def sync_database_url(self) -> str:
        """Derive sync URL from async URL or use explicit override."""
        if self.database_url_sync:
            return self.database_url_sync
        url = self.database_url
        url = url.replace("postgresql+asyncpg://", "postgresql://")
        url = url.replace("postgresql+aiopg://", "postgresql://")
        return url

    @property
    def async_database_url(self) -> str:
        """Ensure database_url uses asyncpg driver."""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic Claude API
    anthropic_api_key: str = ""

    # Gmail API
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""
    gmail_sender_email: str = "brand@apexhumancompany.com"

    # API Security
    api_secret_key: str = "change-this-to-a-random-secret"

    # Rate Limits (per day)
    email_daily_limit: int = 200
    linkedin_daily_limit: int = 25
    whatsapp_daily_limit: int = 100
    instagram_daily_limit: int = 50

    # Lead Enrichment APIs
    apollo_api_key: str = ""
    hunter_api_key: str = ""
    proxycurl_api_key: str = ""

    # WhatsApp Business API
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    # LinkedIn
    linkedin_access_token: str = ""

    # Meta Business API (Instagram)
    meta_access_token: str = ""
    meta_page_id: str = ""

    # Google My Business
    gmb_access_token: str = ""
    gmb_account_id: str = ""
    gmb_location_id: str = ""

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else None,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
