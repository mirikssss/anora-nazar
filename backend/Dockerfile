# syntax=docker/dockerfile:1.7
# Один образ для всех сервисов бэкенда; сервис выбирается командой запуска.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src
# libgomp1 — OpenMP для LightGBM; libsodium23 — ristretto255 для OPRF (pysodium)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libsodium23 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN useradd --system --uid 10001 app && mkdir -p /keys && chown app /keys
USER app
# Версия сборки — коммит; её отдаёт /v1/system/health. Стенд передаёт GIT_SHA (deploy/stand), без него — пусто.
ARG GIT_SHA=""
ENV APP_VERSION=${GIT_SHA}

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project
COPY src ./src
COPY tests ./tests
