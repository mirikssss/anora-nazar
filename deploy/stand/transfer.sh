#!/usr/bin/env bash
# Перенос мира и моделей с локального стенда на сервер: на общем сервере мало свободной памяти, поэтому загрузка
# мира и обучение идут локально, а на сервер едут копии баз и то, без чего они не читаются.
#
#   deploy/stand/transfer.sh        после deploy.sh: копии баз узла, имитатора, оператора и якоря → сервер
#
# Вместе с базами переносятся ключ подписи узла (журнал и контрольные точки подписаны им) и два секрета, от которых
# зависят данные: NODE_INDEX_KEY (ключи HMAC в индексе связей и кеше токенов) и OPERATOR_OPRF_SEED (токены сети).
# Остальные секреты стенда остаются своими. Окружение — как у deploy.sh: STAND_SSH, STAND_DIR.
set -euo pipefail

: "${STAND_SSH:?Задайте STAND_SSH: пользователь@сервер}"
: "${STAND_DIR:?Задайте STAND_DIR: каталог стенда на сервере}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCAL_PROJECT="${LOCAL_PROJECT:-anora-nazar}"
DATABASES=(node bank_sim network_operator anchor)
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

env_local() { sed -n "s/^$1=\([^ #]*\).*/\1/p" "$ROOT/.env" | tail -1; }

echo "копии баз локального стенда"
for db in "${DATABASES[@]}"; do
  docker exec "$LOCAL_PROJECT-postgres-1" pg_dump -U nazar -Fc "$db" > "$WORK/$db.dump"
done
docker run --rm -v "${LOCAL_PROJECT}_node-private-key:/keys:ro" alpine cat /keys/node-signing.key > "$WORK/node-signing.key"
printf 'NODE_INDEX_KEY=%s\nOPERATOR_OPRF_SEED=%s\n' "$(env_local NODE_INDEX_KEY)" "$(env_local OPERATOR_OPRF_SEED)" \
  > "$WORK/secrets.env"
du -sh "$WORK"

ssh "$STAND_SSH" "mkdir -p '$STAND_DIR/transfer' && chmod 700 '$STAND_DIR/transfer'"
scp -q "$WORK"/* "$STAND_SSH:$STAND_DIR/transfer/"

ssh "$STAND_SSH" "STAND_DIR='$STAND_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$STAND_DIR"
sha="$(sed -n 's/^GIT_SHA=\([^ #]*\).*/\1/p' shared/.env | tail -1)"
compose() { (cd "releases/$sha/deploy/stand" && GIT_SHA="$sha" docker compose "$@"); }
while IFS='=' read -r name value; do
  sed -i "s/^$name=.*/$name=$value/" shared/.env
done < transfer/secrets.env
compose stop node trainer bank-sim network-operator anchor gateway
for dump in transfer/*.dump; do
  db="$(basename "$dump" .dump)"
  docker exec anora-nazar-postgres-1 psql -U nazar -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)"
  docker exec anora-nazar-postgres-1 psql -U nazar -d postgres -qc "CREATE DATABASE \"$db\""
  docker exec -i anora-nazar-postgres-1 pg_restore -U nazar -d "$db" --no-owner < "$dump"
  echo "база $db восстановлена"
done
docker run --rm -v anora-nazar_node-private-key:/keys -v "$STAND_DIR/transfer:/in:ro" alpine \
  sh -c 'cp /in/node-signing.key /keys/node-signing.key && chown 10001 /keys/node-signing.key && chmod 600 /keys/node-signing.key'
compose up -d --no-build
rm -rf transfer
echo "данные перенесены; публичный ключ узла выпустит сервис keys при запуске"
REMOTE
