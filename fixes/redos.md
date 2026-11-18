# ReDoS — фикс

## Признаки

```bash
grep -rnE 're\.(match|search|fullmatch|sub|findall)|new RegExp|Pattern\.compile' . | grep -E '\(\.\*|\.\+\)|\(\.\*\)\+|\(\.\+\)\+|\|'
```

Симптом: запрос с длинной строкой из `a`+спецсимвол подвешивает сервис / ест CPU.

## Фикс

### 1. Переписать регулярку

Плохие конструкции: вложенные квантификаторы `(a+)+`, `(.*)*`, альтернативы с
пересечением `(a|a)*`, `.*.*`.

```python
# ПЛОХО: email-валидация с backtracking
re.match(r"^(\w+)*@(\w+)*\.(\w+)*$", s)
# ХОРОШО: атомарные/простые квантификаторы
re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s)
```

### 2. Ограничить вход

```python
MAX_LEN = 4096
if len(s) > MAX_LEN:
    return "too long", 400
```

### 3. Библиотеки без backtracking

```python
# pip install re2
import re2
re2.match(pattern, s)
```

```js
// npm i re2
const RE2 = require("re2");
new RE2(pattern).test(s);
```

```go
// Go regexp — RE2 из коробки, ReDoS невозможен
regexp.MustCompile(pattern)
```

### 4. Таймаут (если движок умеет)

- Java: отдельный поток с `Future.get(timeout)` (regex API таймаута нет).
- .NET: `new Regex(p, RegexOptions.None, TimeSpan.FromSeconds(1))`.
- PHP: `pcre.backtrack_limit` / `pcre.jit` — ограничения, но не спасение.

## Не сломать чекер

- Не урезай длину ниже того, что шлёт чекер (посмотри реальные запросы).
- Если регулярка — фича сервиса (поиск по шаблону), не отключай её, а ограничь
  вход и/или смени движок на RE2.

## Проверка

```bash
python3 - <<'EOF'
import requests, time
s = "a"*28
t = time.time()
requests.get("http://localhost:8080/search", params={"q": s})
print("elapsed", time.time()-t)
EOF
# > 1-2 сек -> почти наверняка ReDoS
```
