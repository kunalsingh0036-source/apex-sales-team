FROM python:3.12-slim

WORKDIR /app

# System deps:
# - build-essential, libpq-dev: Postgres driver compile (asyncpg/psycopg2)
# - Playwright Chromium runtime libs: installed by `playwright install --with-deps`
#   which pulls fonts, libs, etc. needed for headless Chromium.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright. --with-deps pulls every apt package the
# bundled Chromium needs (fonts, libnss, libdrm, libgbm, etc.). Adds ~300MB
# but lets us scrape Indian institutional sites that block plain HTTP clients
# (FHRAI ASP.NET WebForms, CISCE Cloudflare, GeM AJAX).
#
# We only install chromium (not firefox/webkit) because Chromium has the
# best compatibility with Cloudflare bot challenges and ASP.NET sites. If
# a target site requires Firefox specifically, add it back here.
RUN playwright install --with-deps chromium

COPY . .

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
