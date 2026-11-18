# Справочник по инструментам кита

Подробное использование всех скриптов. Быстрый старт и карта репо — в
корневом `README.md`, оперативные шпаргалки — в `cheatsheets/`.

## CookieFarm — ферма (основной стек)

Сервер разворачивается отдельно (см. `cheatsheets/farm.md`). Клиент:

```bash
pip install --upgrade cookiefarm requests
ckc config edit -H <farm-ip> -p 8080 -u <ник>
ckc login -u <ник> -P <пароль сервера>
```

### `ckc exploit` — сплоиты

Порт сервиса клиент берёт из конфига сервера (`services`), флаг `-p` не нужен.
`-n` должен совпадать с именем сервиса в `config.yml`.

```bash
ckc exploit create -n web_sqli          # шаблон в ~/.config/cookiefarm/exploits
ckc exploit test -e web_sqli -n CookieService -t 30 -W 10
ckc exploit run  -e web_sqli -n CookieService -t 60 -W 20 -d
ckc exploit list / listrun
ckc exploit stop -p <pid>
ckc exploit submit -f '<flag>' -n CookieService -t <team_id> [-m comment]
```

Флаги: `-e` путь/имя сплойта, `-n` сервис, `-d` detach, `-t` тик (сек),
`-W` воркеры, `-S` прямой HTTP-сабмит, `-P` multiprocessing вместо потоков.
`ckc exploit submit` — ручной одиночный сабмит.

### `sploit_cookiefarm.py` — наш шаблон

```python
@exploit_manager
def exploit(ip, port, name_service, flag_ids):
    ...  # печатать флаги в stdout
```

Декоратор сам идёт по всем командам, тянет flag IDs и сабмитит. В шаблоне —
HTTP-хелпер, retry, рандомный UA и разбор flag_ids любых форм. Запуск:

```bash
ckc exploit run -e sploit_cookiefarm.py -n CookieService -t 120 -W 40 -d
```

Проверка контракта: `python3 sploit_cookiefarm.py` без фермы бесполезен —
декоратор сразу уходит в цикл; тестируй через `ckc exploit test`.

### `cookiefarm_submit.py` — запасной сабмит

Логин по паролю сервера, батч флагов, по умолчанию
`/api/v1/submit-flags-standalone` (в БД + в игру), `--store` — только в БД.

```bash
cat flags.txt | cookiefarm_submit.py --url http://farm:8080 -P PASS \
    -n CookieService -p 8081 -t 3
cookiefarm_submit.py --url ... -P PASS -n CookieService -p 8081 flags.txt
```

`-n`/`-p`/`-t` — метаданные флага (сервис, порт, team_id цели); `-e` — имя
сплойта для статистики. Флаги ищутся регуляркой (`--flag-format`).

## S4DFarm-совместимый контур (запасной)

### `farm_client.py` — клиент фермы

Гоняет сплойт по всем командам, собирает флаги из stdout, дедуп, батч-сабмит
(`GET /api/get_config`, `POST /api/post_flags`). Для CookieFarm не нужен.

```bash
FARM_SERVER=http://farm FARM_PASSWORD=TOKEN \
python3 farm_client.py sploit.py --attack-period 55 --pool-size 50
```

| Опция | Назначение |
|---|---|
| `--server-url`, `--server-pass` | ферма (или env `FARM_SERVER`/`FARM_PASSWORD`) |
| `--teams-file teams.json` | локальный запуск без фермы (тест сплойтов) |
| `--once` | один раунд и выход |
| `--distribute K/N` | шардирование по `crc32(ip) mod N` (несколько клиентов) |
| `--not-per-team` | один инстанс вместо одного на команду |
| `--flag-format RX` | запасная регулярка флага |
| `--sploit-arg ARG` | доп. аргумент сплойту (повторяемый) |
| `--interpreter CMD` | интерпретатор для сплойта |
| `--force` | игнорировать проверки shebang/flush |
| `--endless` | без таймаутов/рестартов |
| `--verbose-attacks N` | показывать вывод первых N раундов |

Graceful shutdown по SIGINT/SIGTERM: дети убиваются, очередь флагов
досабмичивается.

### `sploit.py` — шаблон под S4DFarm-контракт

IP цели — `argv[1]`, флаги — в stdout с `flush=True`. Два режима:
`ATTACK_DATA_URL = None` (обычный) или URL attack data (авто-разбор форматов
`{"ip":...}`, `{"team_id":...}`, `{"service": {...}}`). Есть retry и
рандомный UA. Логика атаки — в `exploit(ip, data)`.

### `example_sploit.py` — dummy

Печатает `AAAA...=` и IP — проверка связки фермы и клиента до игры.

### `fetch_attack_data.py` — история attack data

```bash
python3 fetch_attack_data.py --url http://jury/api/client/attack_data \
    --token TOK --out /tmp/ad.jsonl [--period 60] [--once]
```

### `submit_flags.py` — ручной сабмит на S4DFarm-борду

```bash
cat flags.txt | python3 submit_flags.py \
    --url http://farm/api/post_flags --token TOK [--sploit name --team name]
```

## Firegex — API-клиент

```bash
export FIREGEX_URL=http://127.0.0.1:4444
export FIREGEX_PASSWORD=...
firegex_client.py services
firegex_client.py filters web
firegex_client.py regex list web
firegex_client.py regex add web '(\.\./|%2e%2e)' --mode C
firegex_client.py regex del web --filter f1 --regex-id r1
```

Паттерны в API кодируются base64 (клиент делает сам), режимы `C`/`S`/`B`.
Pyfilter-файлы (`@pyfilter`) этот клиент не деплоит — только regex-фильтры;
подробности Firegex и примеры pyfilter — `cheatsheets/firegex.md`.

## Tulip — анализ трафика

```bash
export TULIP_URL=http://127.0.0.1:5000
tulip_client.py flows --flag                    # флоу с флагами
tulip_client.py flows --ip 10.10.4.1 --port 8080 --since 30
tulip_client.py flows --tag path_traversal
tulip_client.py flags --since 60                # вытащить флаги из трафика
tulip_client.py raw <flow_id> --out req.txt     # client->server байты
tulip_client.py raw <flow_id> --dir server      # server->client
tulip_client.py pwn <flow_id> > sploit.py       # pwntools-скелет
tulip_client.py python <flow_id>                 # requests-скелет
tulip_client.py star <flow_id>                  # пометить флоу
```

API по умолчанию не проброшен наружу: добавь `ports: "5000:5000"` сервису
`api` в docker-compose Tulip либо работай через `docker compose exec api`.
Деплой и `.env` — `cheatsheets/traffic.md`.

## Деплой и откат (vulnbox)

```bash
deploy.sh --dir ~/infra [--dry-run] [svc1 svc2]
patch_snapshot.sh snapshot ~/infra/svc1 [ещё пути]
patch_snapshot.sh restore ~/ad_snapshots/<файл>.tar.gz
patch_snapshot.sh list
```

`deploy.sh`: fast-forward `git pull` + per-service `deploy.sh` или
`docker compose up -d --build`. `patch_snapshot.sh`: архивы в
`~/ad_snapshots/`, манифест с абсолютным путём, restore-хуки (`$RESTORE_CMD`,
`docker compose restart`, `systemctl restart`).

## Мониторинг, реплей, флаги

```bash
watch_status.py --url http://board/api/... --token TOK [--period 15] [--once]
replay.py --request req.txt --teams-file teams.json --port 8080 \
    [--teams name=ip ...] [--pool 32] [--no-fix-host] [--flag-format RX]
flagscan.py dump.pcap [more files] [--flag-format RX]
```

- `watch_status.py` — board-agnostic поиск UP/MUMBLE/CORRUPT/DOWN в JSON,
  алерты на смену статусов, state в `/tmp/watch_status_state.json`.
- `replay.py` — сырой HTTP-запрос (из Tulip/tcpdump) по всем командам;
  плейсхолдер `{IP}` или авто-подмена `Host`.
- `flagscan.py` — офлайн-поиск флагов в pcap/дампах/логах (в т.ч. бинарных).

## Файлы

- `teams.example.json` — формат `{"name": "ip"}` для `--teams-file`.
