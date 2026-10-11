#!/usr/bin/env sh
# Создаёт deploy/stand/.env на сервере: секреты случайные, параметры стенда — из .env.example.
# Существующий .env не трогает: секреты стенда меняются только осознанно (база и токены зависят от них).
set -eu
cd "$(dirname "$0")"
if [ -f .env ]; then
  echo ".env стенда уже есть"
  exit 0
fi
secret() { openssl rand -hex 32; }
umask 077
while IFS= read -r line; do
  case "$line" in
    POSTGRES_PASSWORD=|NODE_SESSION_SECRET=|NODE_INDEX_KEY=|NODE_API_KEY_*=|BANK_SIM_API_KEY_NODE=|ANCHOR_API_KEY_NODE=|OPERATOR_*=)
      echo "${line}$(secret)" ;;
    *) echo "$line" ;;
  esac
done < .env.example > .env
echo ".env стенда создан; проверьте STAND_PORT и STAND_BIND"
