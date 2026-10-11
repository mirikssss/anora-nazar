# deploy

Выкладка на сервер ClusterOS в Hetzner (`49.13.148.21`), общий с дев-стендом ClusterOS.

| Что | Как |
| --- | --- |
| Адрес | `https://nazar.clusteros.co.uz` |
| Изоляция | отдельный compose-проект `anora-nazar`: своя сеть, свой PostgreSQL, лимиты CPU и памяти; контейнеры ClusterOS не трогаем |
| Сервисы | `node`, `bank-sim`, `network-operator`, `anchor`, `gateway` (статика интерфейса и прокси), `postgres` |
| HTTPS | через reverse proxy сервера; какой он — проверить до выкладки |
| Перед выкладкой | свободное место на диске, занятые порты, прогон сценариев с телефона и ноутбука |

Файлы выкладки и порядок — [`stand/`](stand/README.md): compose стенда, шлюз, `deploy.sh`, примеры reverse proxy.
