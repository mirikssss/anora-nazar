#!/usr/bin/env sh
# Окружение для команд разработки на своей машине против PostgreSQL из compose.yaml.
# Использование: . scripts/local-env.sh  (из папки backend)
set -a
. "$(dirname "$0")/../../.env"
set +a
LOCAL_STATE="$(cd "$(dirname "$0")/.." && pwd)/.local"
mkdir -p "$LOCAL_STATE"
PG="postgresql+psycopg://nazar:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_PORT}"
export NODE_DATABASE_URL="$PG/node"
export NODE_SIGNING_KEY_PATH="$LOCAL_STATE/node-signing.key"
export NODE_BANK_SIM_URL="http://127.0.0.1:8001"
export NODE_BANK_SIM_API_KEY="$BANK_SIM_API_KEY_NODE"
export NODE_ANCHOR_URL="http://127.0.0.1:8002"
export NODE_ANCHOR_API_KEY="$ANCHOR_API_KEY_NODE"
export BANK_SIM_DATABASE_URL="$PG/bank_sim"
export ANCHOR_DATABASE_URL="$PG/anchor"
export TEST_POSTGRES_URL="$PG/postgres"
export NODE_PUBLIC_KEY_PATH="$LOCAL_STATE/node-public.key"
export BANK_SIM_NODE_URL="http://127.0.0.1:8000"
export BANK_SIM_NODE_KEY_CONVEYOR="$NODE_API_KEY_CONVEYOR"
export BANK_SIM_NODE_KEY_CORE_BANKING="$NODE_API_KEY_CORE_BANKING"
export BANK_SIM_NODE_KEY_EVENTS="$NODE_API_KEY_EVENTS"
export BANK_SIM_NODE_KEY_REALMS="$NODE_API_KEY_REALMS"
export BANK_SIM_NODE_PUBLIC_KEY_PATH="$NODE_PUBLIC_KEY_PATH"
export BANK_SIM_API_KEY_NODE="$BANK_SIM_API_KEY_NODE"
export ANCHOR_NODE_PUBLIC_KEY_PATH="$NODE_PUBLIC_KEY_PATH"
export ANCHOR_API_KEY_NODE="$ANCHOR_API_KEY_NODE"
