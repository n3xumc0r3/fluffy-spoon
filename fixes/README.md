# Шаблоны фиксов уязвимостей для A/D

Стандартные заготовки «уязвимо → минимальный фикс» под типовые дыры в сервисах.
Каждый файл: как искать дыру, как патать в популярных стеках, что может сломать
чекер, как проверить после деплоя.

## Правила патчинга (нарушение = минус SLA)

1. **Сначала воспроизведи** атаку локально/на своём боксе. Патч без PoC =
   стрельба вслепую.
2. **Снапшот до патча**: `patch_snapshot.sh snapshot <dir>`. Передумал/сломал —
   `restore` за секунды.
3. **Минимальный диф**: чиним ТОЛЬКО дыру. Не рефакторим, не обновляем
   зависимости, не трогаем API, которым ходит чекер.
4. **Все точки, а не только найденная**: `grep` по классу дыры по всему сервису.
5. **После деплоя** — `watch_status.py` и глазами на борду 1-2 тика. MUMBLE /
   CORRUPT — немедленный откат, разбор потом.
6. **Фильтр (Firegex) — временная мера**, не фикс. Всегда потом закрываем код.
7. **Не создавай новых утечек**: не логируй флаги/секреты, не отдавай стектрейсы
   наружу, не открывай новые порты.

## Патч за 60 секунд (порядок действий)

1. **PoC**: воспроизвёл атаку (curl/скрипт), понял точку входа.
2. **Временный блок** (если атакуют прямо сейчас): Firegex/regex-правило или
   выключение эндпоинта — на 1-2 тика, чтобы выиграть время.
3. **Снапшот**: `patch_snapshot.sh snapshot <dir>`.
4. **Минимальный фикс** по шаблону класса (см. индекс).
5. **Обходы**: прогони PoC по `bypass-matrix.md` для этого класса.
6. **Регресс**: чекер-симулятор + `watch_status.py`, 1-2 тика.
7. **Снять фильтр**, закоммитить фикс с PoC в сообщении.

Если сомневаешься между «фикс, который может сломать чекер» и «временный
фильтр» — ставь фильтр, фикс доделывай без спешки.

## Индекс (класс → файл → быстрый grep)

| Класс | Файл | grep-маркер |
|---|---|---|
| **Flag store / утечка флага** | `flags.md` | `flag`, `admin`, `/debug`, `.env`, `backup` |
| SQL-инъекции | `sqli.md` | `execute(.*f"`, `query(.*\+`, `raw(` |
| NoSQL-инъекции | `nosql.md` | `find_one({`, `find({`, `$where`, `json()` |
| Инъекции команд | `cmdi.md` | `os.system`, `shell=True`, `exec(`, `backtick` |
| Path traversal | `path-traversal.md` | `open(`, `send_file`, `readfile`, `File(` |
| SSTI | `ssti.md` | `render_template_string`, `Template(`, `compile(` |
| Format string | `format-string.md` | `.format(`, `% (`, `sprintf`, `printf(` |
| SSRF | `ssrf.md` | `requests.get(.*input`, `http.Get(`, `curl` |
| Небезопасная десериализация | `deserialization.md` | `pickle.loads`, `yaml.load`, `unserialize` |
| Auth/IDOR/JWT/сессии | `auth.md` | `jwt.decode`, `user_id`, `session[` |
| Крипто | `crypto.md` | `AES.MODE_ECB`, `random.`, `md5`, `sha1` |
| Загрузка файлов / zip slip | `upload.md` | `save(`, `extractall`, `unzip`, `resolve()` |
| XXE | `xxe.md` | `etree.parse`, `simplexml_load`, `DocumentBuilder` |
| ReDoS | `redos.md` | `re.match`, `re.search`, `Pattern.compile` |
| Гонки/TOCTOU | `race-condition.md` | `balance`, `check.*then`, `SELECT.*FOR UPDATE` |
| HTTP-инъекции/XSS/redirect | `http-injection.md` | `header(`, `redirect(`, `render` |
| Утечка исходников/debug | `source-disclosure.md` | `.git`, `.env`, `debug=True`, `display_errors` |
| Бинарные сервисы | `binary.md` | `checksec` |

Сквозные файлы: `bypass-matrix.md` — обходы фиксов по каждому классу;
`snippets/safe_python.py` — готовые безопасные функции (пути, subprocess,
SSRF-чек, XML/YAML, ZIP, загрузки, токены, заголовки).

## Временный блок через Firegex (пока фиксишь код)

| Класс | Regex (проверить на чекере!) |
|---|---|
| SQLi | `(union\s+select|or\s+1=1|sleep\s*\(|benchmark\s*\()` |
| CMDi | `[;&|`]\s*(sh|bash|id|cat|nc|curl|wget|python)` |
| Traversal | `(\.\./|%2e%2e|%252e%252e)` |
| SSTI | `\{\{.*(__class__|__globals__|config|self)` |
| XXE | `<!DOCTYPE|<!ENTITY` |
| Source leak | `(^|/)\.(git|env|svn)(/|$)|\.(bak|sql|zip|tar\.gz)$` |

Это только чтобы выиграть тик: атакующие обходят по кодировке/регистру, а
ложный REJECT = MUMBLE. После фикса кода фильтр снять.


## Общий алгоритм

```bash
# 1. найти кандидатов
grep -rniE '<маркер класса>' --include='*.py' --include='*.php' --include='*.js' .
# 2. воспроизвести PoC
# 3. снапшот
patch_snapshot.sh snapshot /path/to/service
# 4. патч (шаблон из fixes/<класс>.md)
# 5. деплой + проверка
deploy.sh && python3 watch_status.py --url <борда> --token <токен>
```

## Памятка

- Чекер уже ходит по сервису легитимными запросами — после патча он должен
  проходить. Ломать «всё подозрительное» нельзя: MUMBLE дороже дыры.
- Если фикс требует поменять формат данных, которым обменивается чекер, — почти
  наверняка нельзя. Ищи фикс, сохраняющий внешний контракт.
- Дыры в чужих/своих сплойтах после патча обходим через Firegex или точечный
  патч, не переписывая сервис.
