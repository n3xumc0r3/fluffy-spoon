# Auth, IDOR, JWT, сессии — фиксы

## Признаки

```bash
grep -rnE 'jwt\.decode|jwt\.verify|algorithms=|user_id|get\(user_id|session\[|current_user|is_admin' .
```

Симптом: чужой `user_id`/`id` в запросе; JWT `alg=none`; подпись не
проверяется; admin-эндпоинты без роли.

## IDOR / broken access control

```python
# ПЛОХО
@app.route("/note/<int:nid>")
def note(nid):
    return db.get_note(nid)              # любой может читать любой

# ХОРОШО: проверка владельца на КАЖДОМ объекте
@app.route("/note/<int:nid>")
def note(nid):
    n = db.get_note(nid)
    if n is None or n.owner_id != session["uid"]:
        abort(404)                       # 404, не 403: не подтверждай существование
    return n.text
```

Частая дыра в A/D: **flag store доступен по прямому id**. Проверяй каждый
эндпоинт, который отдаёт данные по id, на ownership. Если сервис — «обменник»
с публичными объектами, ownership определяется по документации чекера, а не на
глаз.

## JWT

```python
import jwt

# ПЛОХО
data = jwt.decode(token, options={"verify_signature": False})
data = jwt.decode(token, key, algorithms=[algo_from_header])   # never

# ХОРОШО
ALLOWED = ["HS256"]
data = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=ALLOWED)
# + проверка exp, iss, aud если есть
```

Проверь: секрет не дефолтный (`secret`, `changeme`), не короткий, не в коде;
`kid` не используется как путь к файлу/`../`; нет `alg=none`.

## Сессии

```python
app.config.update(SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax")   # Secure=True на https
# при успешном логине: session.clear() / новая сессия (fixation)
```

## Дефолтные креды / админки

- Смени пароль админки (сохрани старый — вдруг кто-то не сменил).
- Закрой админку/БД из внешней сети: bind `127.0.0.1` или docker-сеть,
  фаервол на vulnbox.
- `grep -rn 'password\s*=\s*["\x27]' .` — найди все хардкоды.

## Не сломать чекер

- Чекер ходит под своими учётками — не ломай их авторизацию, не чисти
  пользователей, не меняй формат токена, которым он пользуется.
- Смена паролей: меняй только админские/дефолтные, не пользовательские.
- Не блокируй по IP «всё кроме себя» — чекер ходит с другого адреса.

## Проверка

```bash
curl -H 'Cookie: session=<чужой>' http://localhost:8080/notes/1
curl -H 'Authorization: Bearer <jwt algnone>' http://localhost:8080/admin
```
