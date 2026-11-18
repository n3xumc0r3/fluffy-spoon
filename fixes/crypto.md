# Криптографические дыры — фикс

## Признаки

```bash
grep -rnE 'MODE_ECB|AES\.new\(|createCipheriv|mcrypt|random\.(random|randint|choice)|md5\(|sha1\(|==.*token|hardcoded|secret *=' .
```

Симптом: одинаковые блоки шифртекста при повторном шифровании, IV рядом с
шифртекстом, токены предсказуемы, подпись сравнивается через `==`.

## Фикс

### Режим шифрования

```python
# ПЛОХО: AES.MODE_ECB
# ХОРОШО: AES-GCM (аутентифицированное шифрование) или CBC + HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
key = bytes.fromhex(os.environ["AES_KEY"])      # 16/24/32 байта
nonce = os.urandom(12)
ct = AESGCM(key).encrypt(nonce, plaintext, associated_data=None)
# храни nonce вместе с ct; при расшифровке проверит тег
```

### ГПСЧ

```python
# ПЛОХО: random.choice / random.randint для токенов
import secrets
token = secrets.token_urlsafe(32)    # или secrets.token_hex(16)
```

### Сравнение секретов

```python
# ПЛОХО: if token == expected
import hmac
if hmac.compare_digest(token, expected):
    ...
```

### Пароли

```python
# ПЛОХО: md5/sha1
import bcrypt, hashlib
h = bcrypt.hashpw(pw.encode(), bcrypt.gensalt())      # или argon2
bcrypt.checkpw(pw.encode(), h)
# если нельзя менять формат: sha256(salt + pw) с солью из os.urandom
```

### Секреты

- Ключи/пароли — из env, не в коде/репе.
- Не свети ключ в `/debug`, стектрейсах, логах.
- Не отдавай `.env`, `config.py`, бэкапы наружу (проверь статику!).

## Не сломать чекер

- **Формат шифртекста часто зашит в чекер**. Меняешь формат — чекер получает
  MUMBLE. Если так: фикси дыру точечно (например, добавляй подпись к
  внутренним токенам, а внешний JSON не трогай), либо меняй обе стороны, но
  чекер — не наша сторона.
- Смена паролей пользователей ломает логин чекера — не трогай.
- Ротация ключа ломает ранее выданные токены — согласуй с форматом.

## Проверка

```bash
# ECB: два одинаковых блока открытого текста -> одинаковые блоки шифртекста
curl -d '{"data":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}' http://localhost:8080/enc
# PRNG: собери 100 токенов и проверь на повторы/предсказуемость
```
