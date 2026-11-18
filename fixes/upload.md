# Загрузка файлов и zip slip — фикс

## Признаки

```bash
grep -rnE 'save\(|filename|secure_filename|extractall|unzip|ZipFile|tarfile|resolve\(\)' .
```

Симптом: аплоад `.php`/`.py`/`.html` и его исполнение; распаковка архива,
который пишет за пределы каталога; имя файла с `../`.

## Фикс: аплоад

### Python (Flask)

```python
import os, uuid
from werkzeug.utils import secure_filename

ALLOWED = {"png", "jpg", "jpeg", "txt"}

def store(file):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        raise ValueError("bad type")
    name = f"{uuid.uuid4().hex}.{ext}"          # имя не из ввода
    path = os.path.join(UPLOAD_DIR, name)
    file.save(path)
    return name
```

- Храни **вне webroot** (или отдавай через контроллер, не как статику).
- Права на директорию: без исполнения (`chmod 0644`, mount `noexec`).
- Проверяй магию файла (`PIL.Image.open`, `filetype`), а не только расширение,
  если сервис поддерживает.

### PHP

```php
$ext = strtolower(pathinfo($_FILES["f"]["name"], PATHINFO_EXTENSION));
if (!in_array($ext, ["png","jpg"], true)) { http_response_code(400); exit; }
$name = bin2hex(random_bytes(16)) . "." . $ext;
move_uploaded_file($_FILES["f"]["tmp_name"], "/srv/uploads/$name");
```

### Node (multer)

```js
const path = require("path");
const name = crypto.randomUUID() + path.extname(file.originalname);
// diskStorage destination вне public/, filename: name
```

## Фикс: zip slip

```python
import os, zipfile

BASE = os.path.realpath("/srv/unpack")

def safe_extract(zf, dest):
    for member in zf.namelist():
        p = os.path.realpath(os.path.join(dest, member))
        if os.path.commonpath([os.path.realpath(dest), p]) != os.path.realpath(dest):
            raise ValueError(f"zip slip: {member}")
    zf.extractall(dest)
```

Для `tarfile` в Python 3.12+: `tar.extractall(dest, filter="data")`.

## Не сломать чекер

- Чекер грузит файлы своих типов/размеров — allowlist должен их включать.
  Слишком узкий список = MUMBLE.
- Меняешь имена файлов на UUID, а чекер запоминает имя из ответа? Отдавай имя
  в ответе (или сохраняй исходное в метаданных). Если чекер использует исходное
  имя в последующих запросах — сохрани его как поле, не как путь.

## Проверка

```bash
curl -F 'f=@shell.php' http://localhost:8080/upload     # отказ
curl -F 'f=@ok.png' http://localhost:8080/upload        # успех (как чекер)
python3 -c 'import zipfile; z=zipfile.ZipFile("evil.zip","w"); z.writestr("../../x","1"); z.close()'
```
