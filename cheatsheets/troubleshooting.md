# Troubleshooting стека — шпаргалка

Симптом → причина → что делать. Сначала проверяй самое дешёвое.

Связано: [ферма](farm.md), [Firegex](firegex.md), [Tulip](traffic.md),
[сплойт](sploit.md), [инциденты](incident.md), [тулзы](../docs/tools.md).

## CookieFarm

| Симптом | Причина/решение |
|---|---|
| `ckc login` → 401 | неверный пароль сервера; смотри `.env` сервера (`PASSWORD`) |
| `shared configuration has changed` | конфиг сервера изменился → `ckc login` заново |
| Сплойт крутится, флагов 0 | `-n` ≠ ключу в `services`; не тот порт/протокол; stdout не содержит флаг по `regex_flag` |
| Флагов 0 после смены флага | `ckc login` (обновить shared), проверить `regex_flag` |
| CKP-ошибки/ретраи | TCP :7777 недоступен → временно `ckc exploit run -S` (прямой HTTP) |
| Дашборд: UNSUBMITTED копится | чекер медленный/недоступен → меньше `-W`, меньше батч, проверить `protocol`/`team_token` |
| Всё DENIED | не тот `team_token`, формат флага, протокол борды |
| `ckc exploit run` сразу падает | нет `pip install cookiefarm requests`; у файла нет shebang; ошибка в шаблоне — запусти вручную |
| `ckc exploit listrun` пуст | сплойт упал/завершился; смотри вывод (без `-d`) |
| Не остановить сплойт | `ckc exploit listrun` → `ckc exploit stop -p <pid>`; крайний случай `pkill -f <файл>` |
| Эксплойт висит | нет таймаутов в requests/сокетах; добавь `timeout=` и общий дедлайн |
| 413/422 при сабмите | неверные поля флага; `cookiefarm_submit.py` шлёт `flags`/`flag` — сверь с API |

## Firegex

| Симптом | Причина/решение |
|---|---|
| Не логинится API | пароль задан при первом старте; `FIREGEX_PASSWORD`; UI :4444 доступен? |
| Regex не добавляется | пустой/битый паттерн; клиент кодирует base64 — не кодируй руками |
| Фильтр не срабатывает | не тот режим (`C`/`S`/`B`); сервис не на том слое (proxy/NFQUEUE); адреса сервиса неверные |
| Чекер получает MUMBLE | фильтр режет легитимные запросы → снять фильтр, сузить паттерн, проверить на чекере |
| После ребута фильтров нет | standalone-режим: `python3 run.py start`; docker — проверь контейнеры |
| TLS не фильтруется | нужен proxy-слой и TLS-протокол у сервиса; NFQUEUE видит только шифртекст |
| Паттерн «не матчится» | регистр (`--case-sensitive`), байты vs строки, urlencoded payload |

## Tulip

| Симптом | Причина/решение |
|---|---|
| Нет флоу после загрузки pcap | `TRAFFIC_DIR_HOST` не смонтирован/не тот; права; формат (pcap/pcapng); assembler жив? `docker compose logs assembler` |
| UI пуст, API отвечает | фильтры по времени/сервису; `TICK_START`/`TICK_LENGTH` неверные |
| API :5000 недоступен | порт не проброшен в compose → добавь `ports: 5000:5000` сервису `api` или `docker compose exec api ...` |
| Флаги не подсвечиваются | `FLAG_REGEX` не тот; флаг в сжатом/бинарном протоколе; pcap без payload |
| Flag IDs пусто | `FLAGID_SCRAPE=1`, `FLAGID_ENDPOINT` доступен из контейнера, `flagids` контейнер жив |
| Дубли флоу | перезалили тот же pcap; очисти Mongo/том или загружай уникальные |
| `tulip_client.py` ошибка b64 | флоу без данных/битый id; проверь `flow <id>` сырым API |
| Mongo жрёт диск | старые pcaps/индексы → чисти `traffic/` и коллекции вне игры |

## Наши скрипты

| Симптом | Решение |
|---|---|
| `farm_client.py`: 0 флагов | сплойт без shebang/`flush=True`; проверь `--teams-file` (формат `{"name":"ip"}`), IP доступен |
| `farm_client.py`: флаги не уходят | `--server-url`/`--server-pass` (или env), `/api/get_config` отвечает? |
| `replay.py`: connection reset | не тот порт/сервис; TLS не поддерживается (скрипт — plain HTTP) |
| `replay.py`: 400/404 у всех | `Host` не подменился (нужен `{IP}` в запросе или `--no-fix-host`); путь/метод из другого сервиса |
| `watch_status.py` не парсит | борда отдаёт не JSON → `--json-file` для отладки; добавь ключи статусов |
| `patch_snapshot.sh restore` не поднял | рестарт-хуки не сработали → `$RESTORE_CMD`, `docker compose restart`, `systemctl restart` вручную |
| `deploy.sh` non-fast-forward | на боксе локальные коммиты/грязное дерево → `git status`, `git stash`/reset, не force-push |
| `cookiefarm_submit.py` 422 | пустые/лишние поля, неверный `-t team_id`; сравни с payload `ckc` |
| `firegex_client.py` 401 | `FIREGEX_PASSWORD`/`--password`, URL :4444 |
| `tulip_client.py` пусто | `TULIP_URL` :5000 (проброшен?), фильтры времени (`--since`) |

## Чекер и SLA

- MUMBLE после патча → откат снапшотом, разбор локально.
- DOWN → процесс/контейнер/порт: `docker ps`, `ss -ltnp`, логи.
- Чекер «ходит», но сервис отвечает ошибкой → сыграй его запрос вручную
  (Tulip/tshark → curl/nc), сравни с ответом до патча.
- Не понимаешь, что шлёт чекер → `tshark -r dump.pcap -Y http.request -T fields
  -e ip.src -e http.user_agent -e http.host`, вычисли стабильный UA/подсеть.

## Общие правила

1. Одно изменение за раз + проверка борды 1-2 тика.
2. Снапшот до, откат при первом MUMBLE.
3. Логи — сначала локальные, не в прод-ответы.
4. Если чинишь дольше тика — временный фильтр/заглушка, потом нормальный фикс.
