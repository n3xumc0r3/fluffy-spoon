# Утечка исходников и отладочных данных

Часто самая дешёвая дыра: сервис отдаёт наружу `.git`, `.env`, бэкапы, debug.
Через неё атакующие получают пароли, секреты JWT и путь к flag store.

## Признаки

- Web-root = корень проекта (`app.py`, `.git`, `.env` лежат в статике).
- Включён debug: Flask `debug=True`, Django `DEBUG=True`, `display_errors=On`,
  Express `NODE_ENV != production`, Spring Actuator открыт.
- В репо/образе остались `*.bak`, `*.old`, `dump.sql`, `backup.zip`,
  `docker-compose.yml`, `.git/`.
- Source maps: `static/js/main.js.map`.

## PoC — прогнать вручную по списку

```bash
for p in .git/config .git/HEAD .env .env.bak backup.zip app.py.bak dump.sql \
         debug test phpinfo.php server-status .DS_Store static/js/main.js.map; do
  code=$(curl -s -o /tmp/o -w '%{http_code}' "http://SVC/$p")
  [ "$code" = 200 ] && echo "LEAK $p ($(wc -c </tmp/o) b)"
done
```

Плюс: `OPTIONS *`, `/robots.txt`, `/sitemap.xml`, `/api`, `/graphql` (introspection),
`/actuator/env`, `/actuator/heapdump`, `/__debug__/`.

## Фикс

1. Убрать файлы из web-root (не «закрывать» их регулярками изнутри кода):
   ```bash
   cd /srv/app
   rm -rf .git .env .env.* *.bak *.old *.sql backup*.zip docker-compose*.yml
   ```
   Конфиг — в переменные окружения/секреты вне web-root.
2. Web-server root — только публичная папка:
   ```nginx
   root /srv/app/public;              # не /srv/app
   location ~ /\.(git|env|svn|hg) { deny all; }
   location ~* \.(bak|old|orig|swp|sql|zip|tar\.gz)$ { deny all; }
   ```
   Apache: `DocumentRoot /srv/app/public` + `<FilesMatch "^\."> Require all denied`.
3. Выключить debug в проде:
   - Flask: `debug=False`, `use_reloader=False`, `PROPAGATE_EXCEPTIONS=False`.
   - Django: `DEBUG=False`, `ALLOWED_HOSTS`, свой `handler500`.
   - PHP: `display_errors=Off`, `log_errors=On`, `expose_php=Off`.
   - Node/Express: `NODE_ENV=production`, свой error-handler без stack.
   - Spring: `management.endpoints.web.exposure.include=health`, закрыть
     actuator сетью/firewall.
4. Не отдавать каталоги: `autoindex off`, листинг выключен.
5. Быстрый временный слой — Firegex/nginx: deny `.git|.env|.svn|.hg`,
   `\.(bak|old|orig|swp|sql|zip|tar\.gz)$`, `/(debug|phpinfo\.php)$`.

## Не сломать чекер

- Чекер ходит по конкретным путям API — проверь, что deny-правила их не
  задевают (исключи `/api/`, `/health` если нужны).
- После удаления `.env` перенеси значения в переменные окружения и перезапусти
  сервис — иначе сервис упадёт (это, кстати, тоже DOWN).
- Не удаляй файлы, которые сервис читает в рантайме (шаблоны, статику).

## Проверка

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://SVC/.git/config      # 403/404
curl -s -o /dev/null -w '%{http_code}\n' http://SVC/.env             # 403/404
curl -s -o /dev/null -w '%{http_code}\n' http://SVC/debug             # 404
curl -si http://SVC/api/<легитимный> | head -1                        # 200
```

## Обходы, которые проверить

- Регистр/кодирование: `%2e%67%69%74/config`, `/.GIT/config`, `/.git//config`,
  `/.git%2Fconfig`, двойной слэш, `/.git/HEAD`.
- Обход deny через вложенность: `/static/../.git/config` (нормализация должна
  резать до матчинга), `/static/.git/config`.
- Другие VCS/файлы: `.svn/entries`, `.hg/`, `.bzr/`, `composer.lock`,
  `package.json`, `requirements.txt` (версии → известные CVE).
- Debug-эндпоинты фреймворка под другими путями: `/console` (Werkzeug),
  `/__debug__/`, `/actuator/*`, `/swagger-ui.html`.
- Если `.git` закрыт, но `HEAD`/`config` доступны — этого достаточно для дампа.
