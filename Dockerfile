FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium for Playwright. We pin PLAYWRIGHT_BROWSERS_PATH to a
# stable absolute location so the binaries survive across HOME changes
# (Railway's runtime container can have a different default HOME than the
# build image, which would otherwise leave the binaries inaccessible).
#
# Both `chromium` (full browser) and `chromium-headless-shell` are needed:
# Playwright 1.49+ uses the headless-shell binary for `chromium.launch
# (headless=True)`. Skipping either causes "Executable doesn't exist" at
# runtime.
#
# --with-deps pulls every apt package the bundled Chromium needs (fonts,
# libnss, libgbm, libdrm, etc.). Adds ~300MB to the image but is the only
# way to scrape JS-rendered Indian institutional sites (FHRAI WebForms,
# CISCE Cloudflare, GeM AJAX).
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps chromium chromium-headless-shell

COPY backend/ .

CMD alembic upgrade head; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
