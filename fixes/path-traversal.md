# Path traversal — фикс

## Признаки

```bash
grep -rnE 'open\(|send_file|send_from_directory|FileResponse|readfile|file_get_contents|createReadStream' .
```

Симптом: `../../etc/passwd`, `..%2f`, `%252e%252e%252f` в имени файла.

## Фикс

### Python

```python
import os

BASE = os.path.realpath("/srv/app/files")

def safe_path(name):
    p = os.path.realpath(os.path.join(BASE, name))
    if os.path.commonpath([BASE, p]) != BASE:
        raise ValueError("bad path")
    return p
```

`realpath` важен: он же снимает symlink-атаки.

### Flask отдача файлов

```python
from flask import send_from_directory
return send_from_directory(BASE, name)   # встроенная защита от ../
# но не: send_file(BASE + "/" + name)
```

### PHP

```php
$base = realpath('/srv/app/files');
$p = realpath($base . '/' . $_GET['f']);
if ($p === false || !str_starts_with($p, $base . DIRECTORY_SEPARATOR)) {
    http_response_code(400); exit;
}
readfile($p);
```

### Node

```js
const base = path.resolve('/srv/app/files');
const p = path.resolve(base, userPath);
if (!p.startsWith(base + path.sep)) return res.sendStatus(400);
```

### Java

```java
Path base = Paths.get("/srv/app/files").toRealPath();
Path p = base.resolve(user).normalize();
if (!p.startsWith(base)) throw new IllegalArgumentException();
```

## Не сломать чекер

- Не ломай URL-декодирование: некоторые чекеры шлют имена с `%20` — после
  декода и проверки всё нормально, но если ты декодируешь дважды, сломается.
- Если сервис по заданию отдаёт произвольные файлы из большой директории
  (например, `/files/<anything>`), проверяй только границу base-каталога.
- Symlink-ы внутри base обычно легитимны: `realpath`-проверка пропускает
  цели внутри, блокирует вылет наружу.

## Проверка

```bash
curl 'http://localhost:8080/file?name=../../etc/passwd'
curl 'http://localhost:8080/file?name=..%2f..%2fetc%2fpasswd'
curl 'http://localhost:8080/file?name=/etc/passwd'
```
