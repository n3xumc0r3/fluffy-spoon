# Гонки и TOCTOU — фикс

## Признаки

```bash
grep -rnE 'balance|amount|check.*then|if .*<.*:|SELECT|UPDATE|insert|SUM\(' . | grep -iE 'check|if|get'
```

Симптом: двойное списание/начисление при параллельных запросах, флаг выдаётся
дважды, купон используется несколько раз, чек читается после удаления.

## Фикс: атомарность в БД

```python
# ПЛОХО: read-modify-write без блокировки
row = db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
if row["balance"] >= price:
    time.sleep(0.05)      # окно гонки
    db.execute("UPDATE users SET balance=? WHERE id=?", (row["balance"]-price, uid))

# ХОРОШО 1: атомарный UPDATE с условием
cur = db.execute(
    "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
    (price, uid, price))
if cur.rowcount != 1:
    raise ValueError("insufficient funds")

# ХОРОШО 2: транзакция + блокировка строки
# SQLite: BEGIN IMMEDIATE; PostgreSQL: SELECT ... FOR UPDATE
with db:                              # sqlite3: транзакция
    row = db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()
    ...
```

```sql
-- PostgreSQL / MySQL
BEGIN;
SELECT balance FROM users WHERE id = $1 FOR UPDATE;
UPDATE users SET balance = balance - $2 WHERE id = $1;
COMMIT;
```

### Уникальные индексы как защита от дублей

```sql
CREATE UNIQUE INDEX IF NOT EXISTS one_claim_per_user ON claims(user_id, item_id);
```
Вставка-дубль упадёт с ошибкой — лови и отдавай понятный ответ.

### Файлы (TOCTOU)

```python
# ПЛОХО: os.path.exists(p) -> open(p)
# ХОРОШО: открывай сразу и работай с fd
import os
fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
with os.fdopen(fd, "rb") as f:
    data = f.read()
# или временный файл + os.replace() для атомарной записи
```

### Python-потоки

```python
import threading
lock = threading.Lock()
with lock:
    ... критическая секция ...
# или queue.Queue; не забудь блокировки для общих dict/list
```

## Не сломать чекер

- Слишком грубая блокировка всего сервиса может превратить чекер в таймаут
  (особенно если он ходит параллельными запросами). Блокируй только
  критическую секцию, не весь HTTP-обработчик.
- `BEGIN IMMEDIATE` в SQLite держит блокировку записи на всю транзакцию — не
  клади внутрь сетевые вызовы.
- Если чекер сам проверяет легитимную операцию дважды (проверка + повтор) —
  не считай это дублем: идемпотентность по ключу, а не глобальный отказ.

## Проверка

```bash
# 20 параллельных запросов на списание/выдачу
seq 20 | xargs -P20 -I{} curl -s -X POST http://localhost:8080/buy -d 'item=1'
# инвариант: сумма/баланс/количество флагов сходится
```
