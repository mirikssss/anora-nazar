#!/usr/bin/env sh
# Секреты стенда для локальной разработки: создаёт .env или дописывает в существующий недостающие ключи
# со случайными значениями. Существующие значения не меняет.
set -eu
cd "$(dirname "$0")/.."
secret() { openssl rand -hex 32; }

[ -f .env ] || { : > .env; chmod 600 .env; echo ".env создан"; }
if [ -s .env ] && [ -n "$(tail -c1 .env)" ]; then echo >> .env; fi  # дописываем с новой строки

added=0
ensure() {
  if ! grep -q "^$1=" .env; then
    printf '%s=%s\n' "$1" "$2" >> .env
    added=$((added + 1))
  fi
}

ensure POSTGRES_PASSWORD "$(secret)"
ensure POSTGRES_PORT 55432
ensure NODE_SESSION_SECRET "$(secret)"
ensure NODE_INDEX_KEY "$(secret)"
ensure NODE_API_KEY_CONVEYOR "$(secret)"
ensure NODE_API_KEY_CORE_BANKING "$(secret)"
ensure NODE_API_KEY_EVENTS "$(secret)"
ensure NODE_API_KEY_REALMS "$(secret)"
ensure NODE_API_KEY_HISTORY "$(secret)"
ensure BANK_SIM_API_KEY_NODE "$(secret)"
ensure ANCHOR_API_KEY_NODE "$(secret)"
# Оператор сети кредиторов: секрет ключей OPRF (32 байта hex), ключи кредиторов и стенда, ключ колбэка узла
ensure OPERATOR_OPRF_SEED "$(secret)"
ensure OPERATOR_API_KEY_A "$(secret)"
ensure OPERATOR_API_KEY_A_HISTORY "$(secret)"
ensure OPERATOR_API_KEY_B "$(secret)"
ensure OPERATOR_API_KEY_B_HISTORY "$(secret)"
ensure OPERATOR_API_KEY_C "$(secret)"
ensure OPERATOR_API_KEY_C_HISTORY "$(secret)"
ensure OPERATOR_API_KEY_BANK_SIM "$(secret)"
ensure OPERATOR_CALLBACK_KEY_A "$(secret)"

echo ".env: добавлено ключей — $added"
