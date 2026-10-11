#!/usr/bin/env sh
# Создаёт .env для локальной разработки со случайными секретами. Существующий .env не трогает.
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  echo ".env уже есть"
  exit 0
fi
secret() { openssl rand -hex 32; }
{
  echo "POSTGRES_PASSWORD=$(secret)"
  echo "POSTGRES_PORT=55432"
  echo "NODE_SESSION_SECRET=$(secret)"
  echo "NODE_INDEX_KEY=$(secret)"
  echo "NODE_API_KEY_CONVEYOR=$(secret)"
  echo "NODE_API_KEY_CORE_BANKING=$(secret)"
  echo "NODE_API_KEY_EVENTS=$(secret)"
  echo "NODE_API_KEY_REALMS=$(secret)"
  echo "BANK_SIM_API_KEY_NODE=$(secret)"
  echo "ANCHOR_API_KEY_NODE=$(secret)"
} > .env
chmod 600 .env
echo ".env создан"
