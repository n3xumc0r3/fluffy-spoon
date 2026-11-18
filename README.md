# A/D Kit — Attack/Defense CTF

Свои скрипты и пособия для игры. Стек команды: **CookieFarm** (ферма),
**Tulip** (анализ трафика), **Firegex** (защита/фильтры). Запасной контур —
S4DFarm/destructive-farm (`farm_client.py`).

## Карта репозитория

| Раздел | Что внутри |
|---|---|
| `docs/tools.md` | подробный CLI всех скриптов |
| `cheatsheets/` | оперативные шпаргалки: чеклист, ферма, Firegex, Tulip, сплойт, инциденты |
| `fixes/` | 18 шаблонов фиксов уязвимостей, `bypass-matrix.md`, `snippets/safe_python.py` |
| `*.py`, `*.sh` | инструменты (таблица ниже) |

## Быстрый старт

```bash
# 1. Свой сплойт под CookieFarm
pip install --upgrade cookiefarm requests
ckc config edit -H <farm-ip> -p 8080 -u <ник> && ckc login -u <ник> -P <пароль>
ckc exploit create -n my_exploit        # заготовка в ~/.config/cookiefarm/exploits
ckc exploit test -e sploit_cookiefarm.py -n <service> -t 30 -W 10   # NOP-команда

# 2. В бой
ckc exploit run -e sploit_cookiefarm.py -n <service> -t 120 -W 40 -d
ckc exploit listrun

# 3. Защита: трафик -> PoC -> временный фильтр -> фикс кода
firegex_client.py regex add web '(\.\./|%2e%2e)' --mode C
patch_snapshot.sh snapshot ~/infra/<service>   # до патча
# фикс по fixes/<класс>.md, затем:
ckc exploit test ...                           # регресс на NOP
watch_status.py --url <борда> --token <токен>  # 1-2 тика

# 4. Чужая атака -> свой сплойт
tulip_client.py flags --since 60
tulip_client.py raw <flow_id> --out req.txt
replay.py --request req.txt --teams-file teams.json --port 8080
```

## Скрипты (кратко)

| Файл | Назначение |
|---|---|
| `sploit_cookiefarm.py` | шаблон сплойта под CookieFarm (`@exploit_manager`, flag IDs, авто-сабмит) |
| `sploit.py` | шаблон под S4DFarm-контракт (IP в argv, флаги в stdout, attack data) |
| `farm_client.py` | клиент S4DFarm-фермы: все команды, дедуп, батч-сабмит, graceful shutdown |
| `cookiefarm_submit.py` | запасной сабмит в CookieFarm (логин, батч, `--store`) |
| `firegex_client.py` | Firegex без веб-UI: сервисы, фильтры, regex add/list/del |
| `tulip_client.py` | Tulip из консоли: флаги из трафика, raw/pwn/python-скелеты |
| `submit_flags.py` | ручной сабмит на S4DFarm-борду |
| `fetch_attack_data.py` | история attack data в JSONL |
| `flagscan.py` | офлайн-поиск флагов в pcap/дампах/логах |
| `watch_status.py` | алерты SLA с борды (UP/MUMBLE/CORRUPT/DOWN) |
| `replay.py` | реплей сырого HTTP-запроса по всем командам |
| `deploy.sh` | git pull + редеплой сервисов |
| `patch_snapshot.sh` | снапшот/откат сервиса за секунды |
| `example_sploit.py` | dummy-сплойт для проверки связки фермы |
| `teams.example.json` | формат файла команд |

Подробные команды и опции — `docs/tools.md`.

## Документы

- **Шпаргалки** `cheatsheets/`:
  [чеклист](cheatsheets/checklist.md) ·
  [ферма CookieFarm](cheatsheets/farm.md) ·
  [Firegex](cheatsheets/firegex.md) ·
  [Tulip/трафик](cheatsheets/traffic.md) ·
  [сплойт](cheatsheets/sploit.md) ·
  [инциденты](cheatsheets/incident.md)
- **Патчинг** `fixes/`: [индекс и правила](fixes/README.md) ·
  [матрица обходов](fixes/bypass-matrix.md) ·
  [flag store](fixes/flags.md) ·
  [безопасные сниппеты](fixes/snippets/safe_python.py).
  Классы: SQLi, NoSQLi, CMDi, traversal, SSTI, format string, SSRF,
  десериализация, auth/IDOR/JWT, крипто, upload/zip slip, XXE, ReDoS, гонки,
  HTTP-инъекции, source disclosure, бинарь.

## Проверено

- `farm_client.py`: end-to-end на стабе (конфиг → сплойты → флаги → дедуп →
  POST), `--teams-file`, graceful shutdown.
- `replay.py`, `watch_status.py`, `patch_snapshot.sh`, `deploy.sh` — на стабах.
- `firegex_client.py`, `tulip_client.py`, `cookiefarm_submit.py` — на общем
  стаб-сервере (логин, сервисы/фильтры/regex, flows/flags/raw/pwn, сабмит).
- `fixes/snippets/safe_python.py` — самотесты (traversal, SSRF, XXE/UTF-16,
  YAML, zip slip, header injection).
- Все Python-файлы: `python3 -m py_compile` без ошибок.

## Правила игры (коротко)

- SLA важнее расследования: сначала подними/откати, потом разбирайся.
- Каждый патч — со снапшотом и проверкой чекера 1-2 тика.
- Firegex-фильтр — временная мера до фикса кода.
- Не логировать флаги/секреты, не отдавать стектрейсы наружу.
- Флаги — только через ферму; ручной сабмит — аварийный канал.
