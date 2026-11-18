# HTTP-инъекции, XSS, open redirect — фикс

## Признаки

```bash
grep -rnE 'header\(|Location:|redirect\(|res\.send\(|innerHTML|render_template|mark_safe|\|safe' .
```

Симптом: CRLF в параметре ломает заголовки; чужой скрипт исполняется в админке
бота; редирект на произвольный домен.

## CRLF / header injection

```python
# ПЛОХО
resp.headers["X-Info"] = user_value

# ХОРОШО: запрет CR/LF + whitelist символов
import re
if not re.fullmatch(r"[A-Za-z0-9 _.-]{1,128}", user_value):
    abort(400)
resp.headers["X-Info"] = user_value
```

То же для `Location`, `Set-Cookie` (имя/значение), любых заголовков из ввода.

## XSS

```python
# Flask/Jinja: включён автоэскейп, не используй |safe на пользовательских данных
return render_template("page.html", comment=text)

# если HTML собирается вручную — экранируй
import html
return f"<div>{html.escape(text)}</div>"
```

```js
// Node: экранируй или используй шаблонизатор с автоэскейпом
const escapeHtml = s => s.replace(/[&<>"']/g, c => ({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
```

```php
echo htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
```

Дополнительно: CSP-заголовок (`default-src 'self'`), `HttpOnly` куки — но
главное — эскейпинг по контексту (HTML/attr/JS/URL — разные правила).

## Open redirect

```python
from urllib.parse import urlparse

# ПЛОХО: return redirect(request.args["next"])
nxt = request.args.get("next", "/")
u = urlparse(nxt)
if nxt.startswith("//") or u.scheme or u.netloc:
    nxt = "/"                              # только относительные пути
return redirect(nxt)
```

## Не сломать чекер

- Чекер может слать HTML-контент и проверять, что сервис его **отдаёт как
  есть** (например, блог). Массовое экранирование сломает сравнение — смотри,
  что именно проверяет чекер. Часто достаточно экранировать только в
  админ-панели/уведомлениях, а не в хранимом контенте.
- CSP не должна блокировать легитимные inline-стили/скрипты страниц, которые
  проверяет чекер.
- Редирект-фикс: чекер может ожидать редирект на свой URL — не блокируй
  внешние домены полностью, если это фича.

## Проверка

```bash
curl -sI 'http://localhost:8080/go?next=https://evil.example'
curl 'http://localhost:8080/search?q=<script>alert(1)</script>'
curl -sI 'http://localhost:8080/set?name=x%0d%0aSet-Cookie:%20pwn=1'
```
