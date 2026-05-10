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

# Install Chromium for Playwright. We pin PLAYWRIGHT_BROWSERS_PATH to a
# stable, predictable location so the binaries survive across HOME changes
# (e.g., Railway running with a different default HOME at runtime than at
# build time). Without this, `playwright install` downloads to ~/.cache/...
# which can disappear, leaving the Python lib unable to find Chromium.
#
# We install both `chromium` (full browser) and `chromium-headless-shell`
# (lightweight binary used by `chromium.launch(headless=True)` since
# Playwright 1.49). Skipping either causes "Executable doesn't exist" at
# runtime.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium chromium-headless-shell

COPY . .

CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
