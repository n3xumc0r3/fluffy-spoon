# Небезопасная десериализация — фикс

## Признаки

```bash
grep -rnE 'pickle\.loads|yaml\.load\(|marshal\.loads|unserialize\(|ObjectInputStream|node-serialize|JSON\.parse\(.*reviver' .
```

Симптом: base64-куки/параметры, которые декодируются в объект; `__reduce__`,
`O:8:"stdClass"`, `!!python/object`, `rO0AB` (Java) в трафике.

## Фикс

### Python pickle / marshal

```python
# ПЛОХО: pickle.loads(user_data)
# ХОРОШО 1: смени формат на JSON
data = json.loads(user_data)

# ХОРОШО 2 (если формат нельзя менять): restricted unpickler
import pickle, io

class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("global access denied")

data = SafeUnpickler(io.BytesIO(user_data)).load()
```

Если нужны свои классы — allowlist `(module, name)`.

### PyYAML

```python
# ПЛОХО: yaml.load(data)
yaml.safe_load(data)   # ОБЯЗАТЕЛЬНО
```

### PHP

```php
// ПЛОХО: unserialize($_COOKIE['data'])
json_decode($_COOKIE['data'], true)
// если формат фиксирован — unserialize(..., ['allowed_classes' => false])
```

### Java

```java
// ObjectInputStream на ввод — RCE. Замени на JSON (Jackson/Gson).
// Если нельзя — ObjectInputFilter с allowlist классов.
```

### Node

Пакет `node-serialize` с `unserialize()` — прямой RCE. Замена на `JSON.parse`,
никаких `eval`.

## Не сломать чекер

- Формат данных часто зашит в куки/токены, которые проверяет чекер. Если
  меняешь формат — чекер сломается. Тогда: либо restricted-вариант (сохраняет
  формат, но без опасных классов), либо подпись/шифрование контейнера
  (см. crypto.md), а внутри — прежний формат.

## Проверка

```bash
# pickle-пейлоад из базового gzip+base64
python3 -c 'import pickle,base64; print(base64.b64encode(pickle.dumps(__import__("os").system("id"))).decode())'
curl --cookie "data=<пейлоад>" http://localhost:8080/
```
