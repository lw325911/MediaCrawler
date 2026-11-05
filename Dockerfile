# MediaCrawler Docker image (Linux, headless).
#   docker compose up -d                      -> WebUI on http://localhost:8080
#   docker compose run --rm crawler --platform xhs --lt cookie --cookies "..." --type search
# See docs/Docker部署.md

# ---------- WebUI build ----------
FROM node:20-slim AS webui
WORKDIR /build/webui
COPY webui/package.json webui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY webui/ ./
# vite outDir is ../api/webui
RUN mkdir -p /build/api && npm run build

# ---------- Runtime ----------
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    UV_FROZEN=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    TZ=Asia/Shanghai \
    # Container defaults: no local Chrome to attach to, no display.
    MC_ENABLE_CDP_MODE=false \
    MC_HEADLESS=true \
    MC_CDP_HEADLESS=true \
    MC_SAVE_DATA_PATH=/app/data

# nodejs: some platforms run JS signing via PyExecJS. fonts: word cloud / CJK pages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs ca-certificates fonts-noto-cjk tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-install-project --no-dev \
    && playwright install --with-deps chromium

COPY . .
COPY --from=webui /build/api/webui ./api/webui

RUN mkdir -p /app/data /app/browser_data
VOLUME ["/app/data", "/app/browser_data"]
EXPOSE 8080

# Default: WebUI + API. Override the command to run the crawler directly.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
