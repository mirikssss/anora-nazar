#!/usr/bin/env bash
# Выкладка стенда на сервер. Код — архивом коммита (git archive) в releases/<коммит>, образы собираются на сервере,
# перед обновлением — копия базы, после — проверка версий через шлюз. Порядок и ручные шаги — README.md рядом.
#
#   deploy/stand/deploy.sh                 выложить HEAD
#   deploy/stand/deploy.sh setup           один раз на чистом стенде: мир и модели (профиль setup)
#   deploy/stand/deploy.sh rollback <sha>  вернуть прошлую выкладку без пересборки (образы с тегом <sha> на сервере)
#   deploy/stand/deploy.sh status          контейнеры, версии, свободное место
#
# Окружение: STAND_SSH — пользователь@сервер (root@49.13.148.21), STAND_DIR — каталог стенда (/opt/anora-nazar).
# STAND_MIN_FREE_GB — сколько гигабайт должно быть свободно под Docker перед сборкой (по умолчанию 10, предложено).
set -euo pipefail

: "${STAND_SSH:?Задайте STAND_SSH: пользователь@сервер, например root@49.13.148.21}"
: "${STAND_DIR:?Задайте STAND_DIR: каталог стенда на сервере, например /opt/anora-nazar}"
MIN_FREE_GB="${STAND_MIN_FREE_GB:-10}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMMAND="${1:-deploy}"

# Общая часть скрипта на сервере: каталоги, .env, проверка версий через шлюз.
REMOTE_LIB=$(cat <<'LIB'
set -euo pipefail
cd "$STAND_DIR"
mkdir -p releases backups shared
env_value() { sed -n "s/^$1=\([^ #]*\).*/\1/p" shared/.env | tail -1; }
set_sha() { sed -i "s/^GIT_SHA=.*/GIT_SHA=$1/" shared/.env; }
free_gb() { df -BG --output=avail "$(docker info -f '{{.DockerRootDir}}')" | tail -1 | tr -dc '0-9'; }
# Каталог выкладки — каталог проекта: оттуда .env (ссылка на shared/.env) и COMPOSE_FILE, если он там задан.
compose() { (cd "releases/$1/deploy/stand" && docker compose "${@:2}"); }
databases() {
  docker exec anora-nazar-postgres-1 psql -U nazar -d postgres -Atc \
    "SELECT datname FROM pg_database WHERE datname NOT IN ('postgres', 'template0', 'template1', 'nazar')"
}
wait_versions() {
  local sha="$1" base="http://$(env_value STAND_BIND):$(env_value STAND_PORT)"
  for _ in $(seq 1 60); do
    node=$(curl -fsS "$base/api/node/v1/system/health" 2>/dev/null || true)
    bank=$(curl -fsS "$base/api/bank/v1/system/health" 2>/dev/null || true)
    web=$(curl -fsS "$base/version" 2>/dev/null || true)
    # оператор сети наружу не опубликован — спрашиваем изнутри его контейнера
    operator=$(docker exec anora-nazar-network-operator-1 python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8003/v1/system/health').read().decode())" 2>/dev/null || true)
    if [[ "$node" == *"\"version\":\"$sha\""* && "$bank" == *"\"version\":\"$sha\""* && "$web" == "$sha" \
          && "$operator" == *"\"version\":\"$sha\""* ]]; then
      echo "стенд отвечает версией $sha"
      return 0
    fi
    sleep 5
  done
  echo "стенд не ответил версией $sha за 5 минут: docker compose ps и logs" >&2
  return 1
}
LIB
)

remote() {
  ssh "$STAND_SSH" "STAND_DIR='$STAND_DIR' MIN_FREE_GB='$MIN_FREE_GB' bash -s -- $*" <<<"$REMOTE_LIB
$(cat)"
}

deploy() {
  local sha
  sha="$(git -C "$ROOT" rev-parse --short=12 HEAD)"
  if [[ -n "$(git -C "$ROOT" status --porcelain)" ]]; then
    echo "В рабочем дереве есть незакоммиченные изменения — выкладывается только коммит $sha." >&2
  fi
  echo "Код коммита $sha → $STAND_SSH:$STAND_DIR/releases/$sha"
  ssh "$STAND_SSH" "mkdir -p '$STAND_DIR/releases/$sha'"
  git -C "$ROOT" archive --format=tar HEAD | ssh "$STAND_SSH" "tar -x -C '$STAND_DIR/releases/$sha'"

  remote "$sha" <<'REMOTE'
sha="$1"
avail="$(free_gb)"
echo "свободно под Docker: ${avail} ГБ"
if (( avail < MIN_FREE_GB )); then
  echo "меньше ${MIN_FREE_GB} ГБ — освободите место (docker image prune, старые releases) и повторите" >&2
  exit 1
fi
if [[ ! -f shared/.env ]]; then
  sh "releases/$sha/deploy/stand/stand-env.sh"
  mv "releases/$sha/deploy/stand/.env" shared/.env
  echo "создан shared/.env со случайными секретами: проверьте STAND_PORT и STAND_BIND и запустите выкладку снова" >&2
  exit 1
fi
ln -sfn "$STAND_DIR/shared/.env" "releases/$sha/deploy/stand/.env"
previous="$(env_value GIT_SHA)"
if docker ps --format '{{.Names}}' | grep -qx anora-nazar-postgres-1; then
  dump="backups/$(date -u +%Y%m%dT%H%M%SZ)-${previous:-unknown}"
  mkdir -p "$dump"
  for db in $(databases); do
    docker exec anora-nazar-postgres-1 pg_dump -U nazar -Fc "$db" > "$dump/$db.dump"
  done
  echo "копия баз: $dump"
  ls -1dt backups/*/ | tail -n +6 | xargs -r rm -rf   # пять последних копий: база узла с миром — сотни МБ
fi
export GIT_SHA="$sha"   # окружение важнее .env: в .env новый коммит попадает только после удачного запуска
compose "$sha" build --pull
compose "$sha" up -d --remove-orphans
wait_versions "$sha"
set_sha "$sha"
ln -sfn "releases/$sha" current
echo "$(date -u +%FT%TZ) deploy $sha (было: ${previous:-нет})" >> releases.log
# Код и образы пяти последних выкладок — для отката; остальное удаляется.
ls -1dt releases/*/ | tail -n +6 | xargs -r rm -rf
docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^anora-nazar-(backend|web):' | while read -r image; do
  [[ -d "releases/${image##*:}" ]] || docker rmi "$image" >/dev/null || true
done
REMOTE
}

setup() {
  remote <<'REMOTE'
sha="$(env_value GIT_SHA)"
compose "$sha" --profile setup run --rm world
compose "$sha" --profile setup run --rm train
echo "$(date -u +%FT%TZ) setup $sha" >> releases.log
REMOTE
}

rollback() {
  local sha="${1:?Укажите коммит: deploy.sh rollback <sha>; список — releases.log на сервере}"
  remote "$sha" <<'REMOTE'
sha="$1"
[[ -d "releases/$sha" ]] || { echo "нет кода выкладки releases/$sha" >&2; exit 1; }
docker image inspect "anora-nazar-backend:$sha" "anora-nazar-web:$sha" >/dev/null
previous="$(env_value GIT_SHA)"
export GIT_SHA="$sha"
compose "$sha" up -d --no-build --remove-orphans
wait_versions "$sha"
set_sha "$sha"
ln -sfn "releases/$sha" current
echo "$(date -u +%FT%TZ) rollback $sha (было: $previous)" >> releases.log
echo "если между версиями были миграции базы — восстановите копию из backups/ (README, «Откат»)"
REMOTE
}

status() {
  remote <<'REMOTE'
sha="$(env_value GIT_SHA)"
compose "$sha" ps
echo "свободно под Docker: $(free_gb) ГБ"
tail -n 5 releases.log 2>/dev/null || true
REMOTE
}

case "$COMMAND" in
  deploy) deploy ;;
  setup) setup ;;
  rollback) rollback "${2:-}" ;;
  status) status ;;
  *) echo "Команды: deploy | setup | rollback <sha> | status" >&2; exit 2 ;;
esac
