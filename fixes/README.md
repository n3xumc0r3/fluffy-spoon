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

## Индекс (класс → файл → быстрый grep)

| Класс | Файл | grep-маркер |
|---|---|---|
| SQL-инъекции | `sqli.md` | `execute(.*f"`, `query(.*\+`, `raw(` |
| Инъекции команд | `cmdi.md` | `os.system`, `shell=True`, `exec(`, `backtick` |
| Path traversal | `path-traversal.md` | `open(`, `send_file`, `readfile`, `File(` |
| SSTI | `ssti.md` | `render_template_string`, `Template(`, `compile(` |
| SSRF | `ssrf.md` | `requests.get(.*input`, `http.Get(`, `curl` |
| Небезопасная десериализация | `deserialization.md` | `pickle.loads`, `yaml.load`, `unserialize` |
| Auth/IDOR/JWT/сессии | `auth.md` | `jwt.decode`, `user_id`, `session[` |
| Крипто | `crypto.md` | `AES.MODE_ECB`, `random.`, `md5`, `sha1` |
| Загрузка файлов / zip slip | `upload.md` | `save(`, `extractall`, `unzip`, `resolve()` |
| XXE | `xxe.md` | `etree.parse`, `simplexml_load`, `DocumentBuilder` |
| ReDoS | `redos.md` | `re.match`, `re.search`, `Pattern.compile` |
| Гонки/TOCTOU | `race-condition.md` | `balance`, `check.*then`, `SELECT.*FOR UPDATE` |
| HTTP-инъекции/XSS/redirect | `http-injection.md` | `header(`, `redirect(`, `render` |
| Бинарные сервисы | `binary.md` | `checksec` |

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
