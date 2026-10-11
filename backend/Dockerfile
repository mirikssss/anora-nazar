# Один образ для всех сервисов бэкенда; сервис выбирается командой запуска.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN useradd --system --uid 10001 app && mkdir -p /keys && chown app /keys
USER app

FROM base AS dev
RUN uv sync --frozen --no-install-project
COPY src ./src
COPY tests ./tests
