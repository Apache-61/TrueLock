FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend/ ./backend/
COPY config/ ./config/
COPY database/ ./database/
COPY scripts/migrate.sh scripts/seed_demo.sh scripts/_psql_env.sh scripts/render_start.sh ./scripts/

RUN pip install --no-cache-dir . \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /app/scripts/*.sh

ENV TRUELOCK_PROVIDERS_CONFIG=/app/config/agent-providers.json
ENV PYTHONPATH=/app/backend/src

EXPOSE 8000

CMD ["/app/scripts/render_start.sh"]
