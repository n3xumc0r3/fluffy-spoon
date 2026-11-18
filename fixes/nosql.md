# NoSQL-инъекции (MongoDB и подобные)

Классика CTF-сервисов на Mongo: JSON/форму целиком передают в запрос.

## Признаки

```python
# Python
db.users.find_one({"username": data["username"], "password": data["password"]})
db.users.find_one({"user": request.json})            # ещё хуже
# Node
User.findOne({ username: req.body.username })
# PHP
$collection->findOne(["user" => $_POST["user"]]);
```

Любое место, где значение из запроса — **объект/массив**, а не строка.

## PoC

```bash
# оператор вместо строки
curl -s http://SVC/login -H 'Content-Type: application/json' \
     -d '{"username":{"$ne":null},"password":{"$ne":null}}'
# regex по паролю
curl -s http://SVC/login -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":{"$regex":"^a"}}'
# PHP-массивы в форме
curl -s 'http://SVC/login' -d 'user[$ne]=x&pass[$ne]=x'
# JS-инъекция через $where (если включена)
curl -s http://SVC/search -H 'Content-Type: application/json' \
     -d '{"q":{"$where":"sleep(5000) || true"}}'
```

## Фикс

Главное правило: **в запрос уходят только скаляры ожидаемого типа**.

```python
def as_str(v, name):
    if not isinstance(v, str) or len(v) > 128:
        raise BadRequest(name)
    return v

username = as_str(data.get("username"), "username")
password = as_str(data.get("password"), "password")
user = db.users.find_one({"username": username})
```

```php
if (!is_string($_POST["user"] ?? null)) { http_response_code(400); exit; }
$user = $collection->findOne(["user" => (string)$_POST["user"]]);
```

```js
// Node/Express: без mongo-sanitize тоже можно — проверяй типы
if (typeof req.body.username !== "string") return res.sendStatus(400);
const user = await User.findOne({ username: req.body.username });
// Mongoose со схемой String привидёт тип, но лучше проверять явно
```

Дополнительно:

- Отключи серверный JS: `security.javascriptEnabled: false` / `--noscripting`
  (закрывает `$where`, `$function`, `$accumulator`).
- Не пропускай в query поля вне whitelist:
  ```python
  allowed = {"username", "password"}
  data = {k: v for k, v in data.items() if k in allowed}
  ```
- Ограничь `$regex`-злоупотребление на уровне кода (длина, таймаут), если
  сервис реально принимает regex.

## Не сломать чекер

- Чекер шлёт нормальные строки — `isinstance str` их пропускает.
- Не блокируй JSON целиком и не меняй коды ответа успешного логина.
- Если чекер сам присылает числа (id, amount) — привод типов делай точечно,
  не превращай всё в строку.

## Проверка

```bash
# старые PoC → 400/401
curl -si http://SVC/login -H 'Content-Type: application/json' \
     -d '{"username":{"$ne":null},"password":{"$ne":null}}'
curl -si 'http://SVC/login' -d 'user[$ne]=x&pass[$ne]=x'
# легитимный логин → как раньше
curl -si http://SVC/login -H 'Content-Type: application/json' \
     -d '{"username":"u","password":"p"}'
```

## Обходы, которые проверить

- `$regex` вместо `$ne`; `$gt`/`$lt`; `$in`/`$nin`; `$exists`.
- Вложенный объект `{"username":{"$eq":{"$ne":null}}}`.
- `$where` с `this.password` (если JS включён — это отдельная дыра).
- Массивы в PHP (`user[]=...`), `Content-Type: application/x-www-form-urlencoded`
  и `multipart` — проверь все парсеры, не только JSON.
- Обход type-check через JSON `null`/число/булево — все должны отклоняться там,
  где ожидается строка.
