# Attack data / flag IDs — шпаргалка

Flag IDs (attack data) — это **не флаги**, а идентификаторы (юзер, файл, id),
по которым сервис хранит флаг. Игра отдаёт их на каждый тик; сплойт берёт ID и
идёт за флагом.

Связано: [ферма](farm.md), [сплойт](sploit.md), [Tulip](traffic.md),
[инциденты](incident.md).

## CookieFarm (основной путь)

Сервер сам тянет JSON с `shared.url_flag_ids` каждый тик, нормализует по
`shared.flagids_format` и передаёт сплойту только нужный срез:

```python
flag_ids: list   # только текущая команда + текущий сервис (-n)
```

Синтаксис формата (токены):

- `[service]` — имя сервиса из `-n` (и ключ в JSON),
- `[team]` — ключ команды, по нему идёт обход,
- `[id]` — лист/узел с самими ID.
- Литеральные ключи — как есть: `flag_ids.[service].[team].[id]`.

Примеры раскладок:

```json
// [service].[team].[id]
{"Service1": {"team_1": {"1": ["id-a"], "2": ["id-b"]}}}
// [team].[service].[id]
{"team_1": {"Service1": ["id-a", "id-b"]}}
// faust: flagids.[service].[team].[id]
{"flagids": {"Service1": {"team_1": ["id-a"]}}}
```

Сплойт получает `["id-a", "id-b"]`. Наш `sploit_cookiefarm.py` умеет и
dict-элементы (`{"user":..., "password":...}`), и пары `[user, pass]`.

Диагностика:

```bash
# 1. что реально отдаёт endpoint
curl -s "$URL_FLAG_IDS" | head -c 500; echo
# 2. ключи верхнего уровня
curl -s "$URL_FLAG_IDS" | jq 'keys'
# 3. есть ли наш сервис и команда
curl -s "$URL_FLAG_IDS" | jq '.["Service1"] | keys'
```

- Пустой список — нормальная ситуация (нет ID в этом тике): сплойт не должен
  падать, просто 0 флагов.
- ID живут тик: не кэшируй между раундами, ходи за свежими.
- `-n` должен совпадать с именем сервиса **и** в `config.yml`, **и** в
  структуре flagids. Иначе — пусто без ошибок.
- Сервер и клиент сверяют конфиг: после правки `flagids_format` нужен
  `ckc login` заново («shared configuration has changed»).

## S4DFarm (запасной контур)

- `ATTACK_DATA_URL` в `sploit.py`; токен — `ATTACK_DATA_TOKEN`
  (`Authorization: Bearer`).
- `_pick_entry()` понимает `{"ip": {...}}`, `{"team_id": {...}}`,
  `{"service": {"ip"/"id": {...}}}`.
- История по тикам (анализ ротации, атаки старыми данными):

```bash
python3 fetch_attack_data.py --url "$ATTACK_DATA_URL" --token TOK \
    --out /tmp/ad.jsonl --period 60
```

- Ферма может сама раздавать attack data — тогда `farm_client.py` получает
  её из `/api/get_config`; локальный запуск — `--teams-file`.

## Tulip (скрейп и скан)

`.env`:

```env
FLAGID_ENDPOINT="http://flagidendpoint:8000/flagids.json"
FLAGID_SCRAPE=1          # тянуть flag IDs в Mongo (коллекция pcap.flagids)
FLAGID_SCAN=1            # сканировать pcaps на предмет flag IDs
FLAG_LIFETIME=-1         # -1 = не проверять (только для тестов)
TEAM_ID="10.10.3.1"      # чья команда в структуре flagids (обычно своя)
```

- Tulip хранит flag IDs в Mongo: `mongosh pcap --eval 'db.flagids.find()'`.
- UI: вкладка Flag IDs — сопоставление ID ↔ трафик, удобно для проверки
  «а этот ID мы уже используем?».
- Без `FLAGID_SCRAPE` вкладка пустая — не баг.

## Чеклист использования

- [ ] Понял раскладку JSON (curl + jq), записал формат в `config.yml`
- [ ] `-n` совпадает с именем сервиса в конфиге и в flagids
- [ ] Сплойт перебирает **все** ID из списка и переживает пустой список
- [ ] Для dict-ID пробуешь ключи `user/username/password/id/login`
- [ ] Не сабмитишь сами ID как флаги
- [ ] После смены формата — `ckc login` и тест на NOP
- [ ] Если flagids нет вообще — fallback на replay/брут по известным полям
      (аккуратно, без флуда)

## Типовые ошибки

- `-n CookieService`, а в JSON сервис называется `cookie` → пустые списки.
- Формат `[service].[team].[id]`, а в ответе `flagids`-обёртка → добавь
  литерал `flagids.` в начало.
- Кэширование ID между тиками → флаги протухают.
- Использование ID чужой команды → флаг не тот/пусто.
- Ожидание, что `flag_ids` — словарь с ником; проверяй тип и подстраивайся.
