# A/D Kit — свои скрипты для Attack/Defense CTF

Чистая авторская реализация (протокол совместим с S4DFarm / destructive farm:
`GET /api/get_config`, `POST /api/post_flags`, токен в `Authorization`).

## sploit.py — шаблон сплойта
Контракт с фермой: IP цели = `argv[1]`, флаги печатаются в stdout
(`print(..., flush=True)`).

Два режима в одном файле:
- обычный сплойт: `ATTACK_DATA_URL = None`
- с attack data: `ATTACK_DATA_URL = "http://jury/api/client/attack_data"`,
  опционально `ATTACK_DATA_TOKEN`

`_pick_entry()` сам понимает типовые форматы attack data:
`{"ip": {...}}`, `{"team_id": {...}}`, `{"service": {"ip"/"id": {...}}}`.
Есть retry (`HTTP_RETRIES`) и рандомный User-Agent (`USE_RANDOM_UA`).

Вся логика атаки — в функции `exploit(ip, data)`: вернуть итерабл флагов
или печатать прямо оттуда.

## farm_client.py — клиент фермы
Запускает сплойт по всем командам в цикле, собирает флаги из stdout,
дедуплицирует, батчами шлёт на ферму.

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
- **submit_flags.py** — ручной сабмит флагов напрямую на борду/ферму
  (запасной канал, если ферма умерла):
  `cat flags.txt | python3 submit_flags.py --url http://farm/api/post_flags --token TOK`
- **fetch_attack_data.py** — пишет историю attack data в JSONL каждый раунд
  (анализ ротации, атаки по старым данным):
  `python3 fetch_attack_data.py --url http://jury/api/client/attack_data --token TOK --out /tmp/ad.jsonl`
- **flagscan.py** — офлайн-сканер флагов по pcap/дампам/логам (реплей чужих
  атак, поиск утечек): `tcpdump -i any -w d.pcap 'tcp port 8080'` →
  `python3 flagscan.py d.pcap`
- **teams.example.json** — формат файла команд для `farm_client.py --teams-file`

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
