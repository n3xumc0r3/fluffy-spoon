# A/D Kit — свои скрипты для Attack/Defense CTF

Чистая авторская реализация. Стек команды: **CookieFarm** (ферма),
**Firegex** (защита/фильтры), **Tulip** (анализ трафика). Кит совместим и с
S4DFarm/destructive-farm (см. `farm_client.py`).

## sploit_cookiefarm.py — шаблон сплойта под CookieFarm (основной)
Формат `@exploit_manager`: `exploit(ip, port, name_service, flag_ids)`.
Декоратор сам гоняет по командам, тянет flag IDs и сабмитит флаги.

```bash
pip install --upgrade cookiefarm requests
ckc exploit create -n my_exploit   # либо взять наш шаблон
ckc exploit run -e sploit_cookiefarm.py -n CookieService -p 8081 -t 120 -W 40 -d
```

## sploit.py — универсальный шаблон сплойта (S4DFarm-контракт)
IP цели = `argv[1]`, флаги печатаются в stdout (`print(..., flush=True)`).
Два режима в одном файле:
- обычный сплойт: `ATTACK_DATA_URL = None`
- с attack data: `ATTACK_DATA_URL = "http://jury/api/client/attack_data"`,
  опционально `ATTACK_DATA_TOKEN`

`_pick_entry()` сам понимает типовые форматы attack data:
`{"ip": {...}}`, `{"team_id": {...}}`, `{"service": {"ip"/"id": {...}}}`.
Есть retry (`HTTP_RETRIES`) и рандомный User-Agent (`USE_RANDOM_UA`).

Вся логика атаки — в функции `exploit(ip, data)`: вернуть итерабл флагов
или печатать прямо оттуда.

## farm_client.py — клиент фермы (S4DFarm-протокол)
Запускает сплойт по всем командам в цикле, собирает флаги из stdout,
дедуплицирует, батчами шлёт на ферму. Для CookieFarm не нужен (там `ckc`),
но полезен на бордах/фермах с destructive-farm API.

```
python3 farm_client.py sploit.py \
    --server-url http://farm --server-pass TOKEN \
    --attack-period 55 --pool-size 50
```

Ключевые опции:
- `--teams-file teams.json` — локальный запуск без фермы (тест сплойтов)
- `--once` — один раунд и выход (проверка)
- `--distribute K/N` — шардирование по crc32(ip) (несколько клиентов)
- `--not-per-team` — один инстанс вместо одного на команду
- `--flag-format RX` — запасная регулярка флага
- `--sploit-arg ARG` — доп. аргументы сплойту (повторяемый)
- `--force` — игнорировать проверки shebang/flush
- `--endless` — без таймаутов
- env: `FARM_SERVER`, `FARM_PASSWORD`

Гарантии: graceful shutdown по SIGINT/SIGTERM (дети убиваются, флаги
финально сабмятся), дедуп в памяти, батч-сабмит раз в 5 c с ретраем-очередью.

## example_sploit.py — dummy для проверки фермы
Печатает флаг `AAAA...=`. Запускать против себя, чтобы проверить связку
ферма+клиент до игры.

## Вспомогательные скрипты
- **cookiefarm_submit.py** — ручной/запасной сабмит в CookieFarm (логин по
  паролю сервера, батч, `--store` без отправки в игру):
  `cat flags.txt | cookiefarm_submit.py --url http://farm:8080 -P PASS -n CookieService -p 8081 -t 3`
- **firegex_client.py** — управление Firegex без веб-UI (сервисы, фильтры,
  regex add/list/del, base64 внутри):
  `FIREGEX_PASSWORD=... firegex_client.py regex add web '(\.\./|%2e%2e)' --mode C`
- **tulip_client.py** — Tulip из консоли: флоу с флагами, вытащить флаги,
  `raw` (запрос для replay.py), `pwn`/`python` (готовые скелеты):
  `tulip_client.py flags --since 60` / `tulip_client.py raw <id> --out req.txt`
- **submit_flags.py** — ручной сабмит флагов на S4DFarm-совместимую борду
  (запасной канал, если ферма умерла):
  `cat flags.txt | python3 submit_flags.py --url http://farm/api/post_flags --token TOK`
- **fetch_attack_data.py** — пишет историю attack data в JSONL каждый раунд
  (анализ ротации, атаки по старым данным):
  `python3 fetch_attack_data.py --url http://jury/api/client/attack_data --token TOK --out /tmp/ad.jsonl`
- **flagscan.py** — офлайн-сканер флагов по pcap/дампам/логам (реплей чужих
  атак, поиск утечек): `tcpdump -i any -w d.pcap 'tcp port 8080'` →
  `python3 flagscan.py d.pcap`
- **teams.example.json** — формат файла команд для `farm_client.py --teams-file`

## Деплой и откат (vulnbox)
- **deploy.sh** — git pull + редеплой сервисов одной командой:
  `deploy.sh --dir ~/infra [svc1 svc2]` (per-service `deploy.sh` или
  `docker compose up -d --build`; только fast-forward pull; есть `--dry-run`)
- **patch_snapshot.sh** — снапшот до патча / откат за секунды:
  `patch_snapshot.sh snapshot ~/infra/svc1` → патч → сломался SLA →
  `patch_snapshot.sh restore ~/ad_snapshots/<файл>.tar.gz` (рестарт-хуки:
  `$RESTORE_CMD`, затем docker compose restart)

## Мониторинг и реплей
- **watch_status.py** — алерты на смену статусов с борды (board-agnostic:
  сам находит UP/MUMBLE/CORRUPT/DOWN в любом JSON):
  `watch_status.py --url http://board/api/... --token TOK [--period 15]`
- **replay.py** — реплей чужой атаки: сырой HTTP-запрос из Pacmate/tcpdump →
  во все команды (плейсхолдер `{IP}` или авто-подмена Host):
  `replay.py --request req.txt --teams-file teams.json --port 8080`

## Шаблоны фиксов уязвимостей — `fixes/`
Стандартные заготовки «уязвимо → минимальный фикс» под A/D, с правилами
«не сломать чекер». Индекс и общий алгоритм — `fixes/README.md`.

| Класс | Файл |
|---|---|
| SQLi | `fixes/sqli.md` |
| Инъекции команд | `fixes/cmdi.md` |
| Path traversal | `fixes/path-traversal.md` |
| SSTI | `fixes/ssti.md` |
| SSRF | `fixes/ssrf.md` |
| Десериализация | `fixes/deserialization.md` |
| Auth/IDOR/JWT/сессии | `fixes/auth.md` |
| Крипто | `fixes/crypto.md` |
| Аплоад/zip slip | `fixes/upload.md` |
| XXE | `fixes/xxe.md` |
| ReDoS | `fixes/redos.md` |
| Гонки/TOCTOU | `fixes/race-condition.md` |
| HTTP-инъекции/XSS/redirect | `fixes/http-injection.md` |
| Бинарные сервисы | `fixes/binary.md` |

## Шпаргалки — `cheatsheets/`
- `cheatsheets/checklist.md` — чеклист игры по фазам + роли
- `cheatsheets/farm.md` — CookieFarm: сервер, клиент, контракт сплойта, API
- `cheatsheets/firegex.md` — Firegex: слои, regex- и Python-фильтры, правила
- `cheatsheets/traffic.md` — Tulip (pcaps, флаги, pwn/raw) + tcpdump/tshark
- `cheatsheets/sploit.md` — чеклист сплойта и частые ошибки
- `cheatsheets/incident.md` — что делать при MUMBLE/DOWN/краже флагов/смерти фермы

## Проверено
Смоук-тест на стаб-сервере: конфиг fetched, сплойты по 2 командам,
дедуп (одинаковый флаг с 2 команд уходит 1 раз), POST доходит,
`--teams-file` и graceful shutdown работают.

## Памятка по плеюбуку (кратко)
- До игры: сменить SSH-пароль vulnbox, поднять ферму+Pacmate+Firegex, проверить
  сабмит тестовым флагом, снапшот бокса, сменить дефолт-креды сервисов.
- Сеть открылась: сплойты в ферме, мониторинг SLA после каждого деплоя патчей,
  фильтр чекера vs атакующих в трафике, replay чужих эксплойтов.
- Не поднимать чужие флаги себе: если кто-то завернул трафик под тебя —
  у тебя непропатченный сервис.
