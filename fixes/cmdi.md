# Инъекции команд (CMDi) — фикс

## Признаки

```bash
grep -rnE 'os\.system|subprocess\.(run|call|Popen)\(.*shell=True|os\.popen|exec\(|system\(|\`' .
```

Симптом: `; id`, `| whoami`, `$(...)`, `%0a` в параметрах, ответ сервиса
содержит вывод системных команд.

## Фикс

### Python

```python
# ПЛОХО
os.system("ping -c 1 " + host)
subprocess.run(f"ping -c 1 {host}", shell=True)

# ХОРОШО: список аргументов, без shell
subprocess.run(["ping", "-c", "1", host], shell=False, timeout=3)

# Если shell реально нужен (редко) — shlex.quote
import shlex
subprocess.run(f"ping -c 1 {shlex.quote(host)}", shell=True, timeout=3)
```

### Валидация ввода (для ip/hostname)

```python
import ipaddress
try:
    ipaddress.ip_address(host)
except ValueError:
    return "bad ip", 400
```

### PHP

```php
$host = escapeshellarg($_GET['host']);
system("ping -c 1 $host");
// никогда не передавай в system() сырой ввод
```

### Node

```js
// ПЛОХО: exec(`ping ${host}`)
execFile("ping", ["-c", "1", host], { timeout: 3000 });   // без shell
```

### Go

```go
exec.Command("ping", "-c", "1", host).Output()   // без sh -c
```

### Java

```java
new ProcessBuilder("ping", "-c", "1", host).start();   // не Runtime.exec(concat)
```

## Не сломать чекер

- Если чекер передаёт сложные аргументы (с пробелами/кавычками), список
  аргументов может поменять разбор — проверь легитимные кейсы.
- Не меняй формат вывода команды, если чекер парсит ответ.

## Проверка

```bash
curl 'http://localhost:8080/ping?host=127.0.0.1;id'
curl 'http://localhost:8080/ping?host=127.0.0.1%0aid'
```
