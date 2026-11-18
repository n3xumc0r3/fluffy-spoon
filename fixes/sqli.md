# SQL-инъекции — фикс

## Признаки

```bash
grep -rnE 'execute\(\s*f"|execute\(".*" ?\+|cursor\(\)\.execute\(".*%s.*" ?%|\.raw\(|query\(".*\+' .
```

Симптом: `login' OR '1'='1`, `UNION SELECT`, ошибки БД в ответе.

## Фикс

### Python: sqlite3 / psycopg / pymysql

```python
# ПЛОХО
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")

# ХОРОШО: параметризация (плейсхолдеры у каждого драйвера свои)
cur.execute("SELECT * FROM users WHERE name = ?", (name,))        # sqlite3
cur.execute("SELECT * FROM users WHERE name = %s", (name,))       # psycopg2
cur.execute("SELECT * FROM users WHERE name = %s", (name,))       # pymysql
```

### Имена таблиц/колонок/ORDER BY нельзя параметризовать

```python
# ПЛОХО
cur.execute(f"SELECT * FROM users ORDER BY {sort}")

# ХОРОШО: whitelist -> фиксированная строка
SORT = {"name": "name", "date": "created_at"}
order = SORT.get(sort, "id")
cur.execute(f"SELECT * FROM users ORDER BY {order}")   # безопасно: не из ввода
```

### PHP PDO

```php
$stmt = $pdo->prepare("SELECT * FROM users WHERE name = ?");
$stmt->execute([$name]);
$pdo->setAttribute(PDO::ATTR_EMULATE_PREPARES, false); // реальные prepared statements
```

### Node: mysql2 / pg

```js
await conn.execute("SELECT * FROM users WHERE name = ?", [name]);          // mysql2
await pool.query("SELECT * FROM users WHERE name = $1", [name]);           // pg
```

## Не сломать чекер

- Параметризация прозрачна: легитимные запросы работают как раньше.
- Не ставь глобальный blacklist символов (`'`, `--`) — чекер может легитимно
  передавать апострофы в имени/описании, получишь MUMBLE.
- `LIKE` и wildcard-ы: параметризуй значение, `%` оставляй в SQL-строке.
- Ошибки SQL не отдавай наружу (`detail`), но логируй.

## Проверка после фикса

```bash
curl -s "http://localhost:8080/search?q=%27%20OR%201%3D1%20--"   # пусто/ошибка, не дамп
sqlmap -u ...   # только свой сервис, в рамках разведки
```
