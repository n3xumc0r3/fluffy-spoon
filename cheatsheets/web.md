# Веб-сервис A/D — аудит за 10 минут

Цель: быстро понять сервис и найти дыру. Работаем точечно руками (массовые
сканеры/брутфорс — не наш метод и часто запрещены правилами).

Связано: [сплойт](sploit.md), [патчинг](../fixes/README.md),
[инциденты](incident.md), [grep-индекс классов](../fixes/README.md#индекс-класс--файл--быстрый-grep).

## 1. Карта сервиса (2 мин)

```bash
# из исходников на вулнбоксе
grep -rnE "@app\.(route|get|post)|app\.(get|post)|router\.(get|post)|@(Get|Post)Mapping" .
grep -rnE "admin|debug|test|backup|flag" . --include=*.py --include=*.php --include=*.js
ls -la; find . -maxdepth 2 -name "*.db" -o -name "*.sqlite*" -o -name "*.json"
# живой сервис
curl -si http://TARGET:PORT/ | head -30
curl -si -X OPTIONS http://TARGET:PORT/
```

Смотри: язык/фреймворк, шаблоны, статика, БД, роли, куки, заголовки, версии.

## 2. Вход и сессии (2 мин)

- Дефолт-креды из репо/докера (`admin:admin`, пароль в `docker-compose`,
  `config.py`, `.env`, миграциях).
- Регистрация → сразу проверь `role`, `is_admin`, `team_id`, `id` в теле.
- Логин-ответ: куки (`HttpOnly`?), JWT (алг/подпись/`kid`), сессия.
- IDOR: `GET /user/1`, `/flag/1`, `?team=2` — меняй id, смотри 200/403/404.

```bash
curl -si -c /tmp/jar -d 'user=u&pass=p' http://TARGET:PORT/login
curl -si -b /tmp/jar http://TARGET:PORT/profile
python3 -c 'import base64,json,sys; t=sys.argv[1].split(".")[1]; t+="="*(-len(t)%4); print(json.loads(base64.urlsafe_b64decode(t)))' "$JWT"
```

## 3. Данные (2 мин)

- Поиск/фильтры/сортировка (SQLi, NoSQLi, wildcard в LIKE).
- JSON/POST-парсеры: массив вместо строки, `null`, объект с `$ne`.
- Шаблоны: имя/описание/комментарий, которые рендерятся (SSTI, XSS).
- Экспорт/импорт, отчёты, XML/CSV (XXE/CSV-инъекция).
- Upload: аватар/файл (расширения, content-type, размер, путь).

## 4. Файлы и пути (2 мин)

- `?file=`, `?page=`, `?template=`, `download?id=` → traversal/LFI.
- Отдача статики: `.git`, `.env`, бэкапы, source maps, `/debug`.
- Скачивание по имени/пути: абсолютный путь, `..`, двойной декод.

## 5. Сеть и интеграции (2 мин)

- `?url=`, webhook, импорт по URL, аватар по ссылке → SSRF.
- Ошибки/трейсы/`/debug`/`/actuator` — источник секретов и путей.
- Редиректы: `?next=`, `?redirect=` → open redirect/CRLF.

## 6. Приоритетные проверки (по опыту A/D)

1. Публичные админки и эндпоинты, которых нет в UI.
2. Предсказуемые id и отсутствие проверки владельца.
3. Поиск/фильтр → инъекция (SQL/NoSQL).
4. Upload/импорт → RCE/LFI.
5. Шаблонизация пользовательского текста → SSTI.
6. `url=`/webhook → SSRF во внутренний флаг-стор.
7. Debug/бэкапы/`.env` → креды и секреты.

## curl-заготовки

```bash
# JSON
curl -si http://T/PATH -H 'Content-Type: application/json' -d '{"k":"v"}'
# форма
curl -si http://T/PATH -d 'k=v&k2=v2'
# с куками
curl -si -b 'session=...' http://T/PATH
# с заголовком (Host/UA)
curl -si -H 'X-Forwarded-For: 127.0.0.1' http://T/PATH
# тайминг (слепые инъекции)
curl -so /dev/null -w '%{time_total}\n' http://T/PATH
```

## Что делать с находкой

1. Зафиксируй PoC (точный запрос) — он же основа сплойта.
2. Проверь, что баг воспроизводится на чужом/своём экземпляре.
3. Сплойт: `sploit_cookiefarm.py` (эндпоинт + фиксированный payload).
4. Защита: временный Firegex-фильтр → фикс по `fixes/<класс>.md`.
5. После патча врагов — байпассы: `fixes/bypass-matrix.md`.

## Анти-паттерны

- Долбить один эндпоинт флудом — сломаешь SLA/чекер.
- Деструктивные действия (`DROP`, удаление файлов) без нужды.
- Светить свои флаги/куки в отчётах и чате.
- Патчить «всё подозрительное» без PoC и без снапшота.
