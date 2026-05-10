# Microsoft's official Playwright Python image — Ubuntu 24.04 noble with
# Python 3.12 + Chromium preinstalled at /ms-playwright. We picked this
# over python:3.12-slim because:
#   1. Playwright's `--with-deps` step kept failing on Debian slim (tried
#      to install Ubuntu-only font packages: ttf-unifont, ttf-ubuntu-font-family)
#   2. Microsoft maintains this image — every Playwright release ships a
#      matching tag with all browser deps verified
#   3. Chromium binaries are pre-baked at /ms-playwright in the image, so
#      we don't pay download time on every build (~150MB saved)
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install Postgres client headers for asyncpg/psycopg2 wheels. Ubuntu base
# already has python3 + most build essentials; we just need the pq dev libs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tell Playwright where to find its pre-installed browsers in this image.
# Microsoft's image stages them at /ms-playwright by convention.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY backend/ .

CMD alembic upgrade head; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
