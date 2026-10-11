# Публичный демо-стенд

Стенд для проверяющих: `https://nazar.clusteros.co.uz`. Сервер — Hetzner `49.13.148.21`, общий с дев-стендом ClusterOS. Стенд — отдельный compose-проект `anora-nazar`: своя сеть, свой PostgreSQL, лимиты CPU и памяти. Контейнеры, сети и тома ClusterOS не трогаем.

| Файл | Что внутри |
| --- | --- |
| `compose.yaml` | сервисы стенда, лимиты (значения «предложено»), проверки здоровья, ротация логов, профиль `setup` |
| `gateway/default.conf.template` | шлюз nginx: статика, `/api/node/` → узел, `/api/bank/` → имитатор, пределы запросов |
| `.env.example`, `stand-env.sh` | окружение стенда; скрипт создаёт `.env` со случайными секретами |
| `deploy.sh` | выкладка, первичная загрузка, откат, состояние — по ssh |
| `proxy/` | примеры для reverse proxy сервера: Caddy, nginx, Traefik |

## Как устроено

```
браузер ── https://nazar.clusteros.co.uz ── reverse proxy сервера (TLS)
                                               │
                                     ${STAND_BIND}:${STAND_PORT}
                                               │
                                          gateway (nginx)
                         ┌─────────────────────┼──────────────────────┐
                    статика SPA         /api/node/ → node:8000   /api/bank/ → bank-sim:8001
                                               │
               сеть backend (internal): node, bank-sim, anchor, network-operator (8003), postgres
```

- Наружу опубликован только шлюз и только на адрес хоста (`STAND_BIND`, по умолчанию `127.0.0.1`). PostgreSQL, якорь, оператор сети, узел и имитатор снаружи недоступны.
- Сеть `backend` — `internal`: у сервисов нет выхода в интернет, он им не нужен.
- Шлюз не пропускает из браузера вызовы систем банка по API-ключам: `/api/node/v1/{realms,history,events,permits,assessments,transfers}`, `/api/node/v1/network/notifications`, `/api/bank/v1/node/*` — ответ 404.
- Пределы на адрес посетителя: API — `GATEWAY_API_RATE` со всплеском `GATEWAY_API_BURST`, новые песочницы — `GATEWAY_SANDBOX_RATE`/`GATEWAY_SANDBOX_BURST`. Комиссия обычно за одним NAT площадки, поэтому пределы с запасом.
- Версия: образы помечены коммитом (`GIT_SHA`), сервисы отдают его в `version` у `/v1/system/health`, интерфейс — `/version`.

## 1. Подготовка сервера

```sh
ssh root@49.13.148.21
df -h / /var/lib/docker                 # свободно не меньше 10 ГБ: образы ~3 ГБ, база с миром ~1 ГБ, копии базы
docker info -f '{{.DockerRootDir}}'
ss -ltnp | grep -E ':(80|443|18480)\b'   # кто держит 80/443 и свободен ли STAND_PORT
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'   # reverse proxy в контейнере? (traefik, caddy, nginx-proxy)
docker compose version                  # нужен Compose v2 с BuildKit
```

Что выяснить и записать в `.env` стенда:

| Вопрос | Как понять | Что выбрать |
| --- | --- | --- |
| Кто держит 80/443 | `ss -ltnp`: процесс `caddy`, `nginx` или `docker-proxy` | пример из `proxy/` |
| Proxy на хосте или в контейнере | `docker-proxy` на 443 — в контейнере | на хосте — `STAND_BIND=127.0.0.1`; в контейнере — см. «Reverse proxy» |
| Свободный порт | `ss -ltnp` | `STAND_PORT` (предложено 18480) |
| DNS | `dig +short nazar.clusteros.co.uz` | A-запись на `49.13.148.21` (или wildcard `*.clusteros.co.uz`) |

## 2. Reverse proxy

Сабдомен `nazar.clusteros.co.uz` ведёт на шлюз стенда. TLS — у proxy сервера.

**На сервере ClusterOS (так и выложено).** 80 и 443 держит Caddy ClusterOS в контейнере `clusteros-caddy-1` с конфигом `/opt/clusteros/infra/server/Caddyfile`. Блок стенда добавлен с разрешения владельца 11.10.2026. Шлюз слушает `STAND_BIND=172.17.0.1` (мост `docker0`), порт `STAND_PORT=18480`:

```
nazar.clusteros.co.uz {
	reverse_proxy 172.17.0.1:18480
}
```

Затем `docker exec clusteros-caddy-1 caddy validate --config /etc/caddy/Caddyfile` и `caddy reload` в том же контейнере: Caddy перечитывает конфиг без перезапуска, сайты ClusterOS не прерываются.

Другие варианты:

- **Caddy на хосте** — `proxy/Caddyfile.example`: блок в Caddyfile, `caddy reload`; сертификат Caddy получит сам.
- **nginx на хосте** — `proxy/nginx.conf.example`: сайт в `sites-available`, `certbot --nginx -d nazar.clusteros.co.uz`, `nginx -t && nginx -s reload`.
- **Traefik в контейнере** — `proxy/traefik.compose.yaml`: шлюз подключается к сети Traefik, маршрут — метками. Подставить имя сети, entrypoint и certresolver из конфигурации Traefik ClusterOS. Включается строкой `COMPOSE_FILE=compose.yaml:proxy/traefik.compose.yaml` в `.env` стенда — её подхватывают и `deploy.sh`, и ручные `docker compose`.
- **Другой proxy в контейнере без сети хоста** (Caddy, nginx-proxy): `127.0.0.1` хоста из контейнера не виден. Либо подключить шлюз к сети proxy (как в примере Traefik), либо `STAND_BIND=172.17.0.1` (адрес моста `docker0`, проверить `ip -4 addr show docker0`) и в proxy — `172.17.0.1:${STAND_PORT}` / `host.docker.internal`.

Шлюз доверяет `X-Forwarded-For` от адресов хоста и частных сетей Docker: так в его журнале и в пределах запросов — настоящий адрес посетителя.

## 3. Выкладка

Выкладка — с машины разработчика скриптом по ssh; на сервере нужны только Docker с Compose v2 (git там не нужен).

```sh
export STAND_SSH=clusteros@49.13.148.21 STAND_DIR=/home/clusteros/anora-nazar
deploy/stand/deploy.sh            # выложить HEAD
```

Что делает `deploy.sh`:

1. Код коммита (`git archive HEAD`, без незакоммиченного) → `$STAND_DIR/releases/<коммит>`.
2. Проверка места под Docker (`STAND_MIN_FREE_GB`, предложено 10).
3. Первый запуск: создаёт `$STAND_DIR/shared/.env` (`stand-env.sh`: секреты случайные) и останавливается — проверьте `STAND_PORT`, `STAND_BIND`, затем запустите снова. `.env` живёт в `shared/` и ссылкой подключается в каждую выкладку.
4. Копия баз (`pg_dump -Fc` каждой базы) в `$STAND_DIR/backups/<время>-<прежний коммит>/`, хранятся пять последних.
5. `docker compose build --pull` и `docker compose up -d` с новым `GIT_SHA`; старые контейнеры работают, пока собираются новые.
6. Ждёт, пока узел, имитатор и интерфейс через шлюз ответят версией нового коммита; только тогда пишет `GIT_SHA` в `.env` и `releases.log`. Код и образы старше пяти выкладок удаляет.

Сборка на сервере — по умолчанию: не нужен реестр, архитектура образов совпадает с сервером. Перенос готовых образов (если сервер не должен собирать): на машине с той же архитектурой, что у сервера (`uname -m`; Mac на ARM собирает amd64 через эмуляцию — долго):

```sh
cd deploy/stand && export GIT_SHA=$(git rev-parse --short=12 HEAD)
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker compose --env-file /путь/к/stand.env build
docker save anora-nazar-backend:$GIT_SHA anora-nazar-web:$GIT_SHA | gzip | ssh $STAND_SSH 'gunzip | docker load'
```

затем на сервере в каталоге выкладки — `docker compose up -d --no-build`.

## 4. Первичная загрузка мира и моделей

**На сервере ClusterOS — переносом с локального стенда.** Свободной памяти на сервере около 2,4 ГБ, а загрузка мира и обучение берут 2–3 ГБ. Поэтому мир и модели считаются локально (`docker compose --profile setup run --rm world`, затем `train` в корне репозитория) и переносятся копиями баз:

```sh
deploy/stand/transfer.sh   # после deploy.sh; те же STAND_SSH и STAND_DIR
```

Вместе с базами узла, имитатора, оператора и якоря скрипт переносит ключ подписи узла и секреты, от которых зависят данные: `NODE_INDEX_KEY` и `OPERATOR_OPRF_SEED`.

Если на сервере хватает памяти — загрузка на месте, один раз после первой выкладки:

```sh
deploy/stand/deploy.sh setup
```

То же руками на сервере (`cd $STAND_DIR/current/deploy/stand`):

```sh
docker compose --profile setup run --rm world   # генерация мира и прогон истории через узел
docker compose --profile setup run --rm train   # обучение моделей и выпуск двумя подписантами (risk-1, risk-2)
```

Повторный `world` на заполненном стенде не запускать: мир один, история уже прогнана.

## 5. Сброс демо

- **Посетитель** — кнопка сброса в интерфейсе: `DELETE /api/bank/v1/sandboxes/current` удаляет его песочницу в имитаторе и в узле (заявки, события, индекс, разрешения, дела, журнал — каскадом). Общий мир не меняется.
- **Брошенные песочницы** удаляются сами: узел — `realms.sandbox_ttl_hours` в `backend/src/node/config/node.yaml`, имитатор — `sandboxes.ttl_hours` в `backend/src/bank_sim/config/bank_sim.yaml` (оба 24 ч без активности, проверка каждую секунду фоновой задачей под advisory lock).
- **Все песочницы разом** (например, перед показом):

  ```sh
  docker exec anora-nazar-postgres-1 psql -U nazar -d bank_sim -c "DELETE FROM sandboxes"
  docker exec anora-nazar-postgres-1 psql -U nazar -d node -c "DELETE FROM realms WHERE kind = 'sandbox'"
  ```

  Открытые вкладки после этого получат «Песочница не найдена» и начнут демо заново.
- **Стенд с нуля** (мир заново): `docker compose down -v` в каталоге выкладки — удаляет базу и ключи; затем выкладка и п. 4.

## 6. Откат

```sh
deploy/stand/deploy.sh rollback <коммит>   # список — $STAND_DIR/releases.log
```

Откат поднимает сохранённые образы этого коммита без сборки (код и образы пяти последних выкладок хранятся на сервере). Миграции Alembic только вперёд: если между версиями менялась схема, старая версия на новой базе не поднимется — восстановите копию, снятую перед неудачной выкладкой (каталог `backups/<время>-<коммит отката>`):

```sh
cd $STAND_DIR/current/deploy/stand
docker compose stop node bank-sim anchor network-operator gateway
for f in $STAND_DIR/backups/<время>-<коммит>/*.dump; do
  docker exec -i anora-nazar-postgres-1 pg_restore -U nazar --clean --if-exists -d "$(basename "$f" .dump)" < "$f"
done
docker compose up -d
```

## 7. Проверка после выкладки

1. `deploy/stand/deploy.sh status` — все сервисы `healthy`, версия в `releases.log`.
2. `curl https://nazar.clusteros.co.uz/version`, `.../api/node/v1/system/health`, `.../api/bank/v1/system/health` — один коммит (оператор сети — `docker exec anora-nazar-network-operator-1 ...`, его проверяет `deploy.sh`).
3. `curl -o /dev/null -w '%{http_code}' https://nazar.clusteros.co.uz/api/node/v1/realms` — 404 (вызовы систем закрыты).
4. С ноутбука (1440 px) и с телефона (390 px), в разных браузерах одновременно:
   - вход, выбор роли, переключатель ролей в шапке;
   - каждый готовый сценарий трёх зон в один клик: уровень и причины соответствуют описанию сценария;
   - своя заявка с «Заполнить примером»: решение по зелёной — секунды; АБС исполняет зачисление по разрешению;
   - очередь аналитика и дело; дело внутреннего контроля с графом; журнал и проверка целостности у риск-менеджера;
   - некорректный ввод — понятная ошибка, без пустых экранов;
   - во второй вкладке (другой посетитель) не видно заявок и дел первой;
   - сброс демо — всё своё исчезает, общий мир на месте.
5. Нагрузочный прогон через шлюз — с одного адреса, поэтому на время прогона поднять `GATEWAY_API_RATE` и `GATEWAY_API_BURST` (или запускать с нескольких машин):

   ```sh
   docker compose --profile test run --rm tests python -m tests.load.visitors --visitors 30 --gateway https://nazar.clusteros.co.uz
   ```

   Ожидаемо: 0 ответов 5xx, 0 нарушенных проверок, p95 решения по зелёной заявке — около секунды.

## Ресурсы

Лимиты в `compose.yaml` помечены «предложено»: машина общая с ClusterOS, её размер уточняется на месте (`nproc`, `free -h`). Потолок стенда — около 5,5 CPU и 4,5 ГБ памяти без профиля `setup`; `world` и `train` запускаются один раз и берут до 2 CPU и 2–3 ГБ. Логи — `json-file`, до 10 МБ × 5 файлов на контейнер.
