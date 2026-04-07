import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add the backend directory to path so 'app' is importable
backend_dir = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, backend_dir)

# Load .env from project root (for local dev)
env_file = os.path.join(backend_dir, "..", ".env")
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass  # dotenv not installed, rely on shell env

config = context.config

# Override sqlalchemy.url from environment if available
db_url = os.environ.get("DATABASE_URL_SYNC") or os.environ.get("DATABASE_URL")
if db_url:
    # Ensure sync driver (strip asyncpg/aiopg if present)
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.replace("postgresql+aiopg://", "postgresql://")
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Alembic can detect them
from app.models.base import Base
from app.models.user import User, SystemSetting
from app.models.lead import Company, Lead, LeadEvent
from app.models.sequence import Sequence, Campaign, CampaignEnrollment
from app.models.message import MessageTemplate, Message
from app.models.activity import Activity
from app.models.analytics import DailyMetric, ABTestResult
# CRM models
try:
    from app.models.client import Client, ClientContact, BrandAsset, Interaction, SampleKit
    from app.models.product import ProductCategory, Product
    from app.models.order import Order, OrderItem, OrderStageLog
    from app.models.quote import Quote, QuoteItem
except ImportError:
    pass  # CRM models may not exist yet

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
