# SSRF — фикс

## Признаки

```bash
grep -rnE 'requests\.(get|post)\(|urllib\.request|http\.Get|axios\.get|file_get_contents\(' .
```

Симптом: параметр `url=`, `webhook=`, `image=`; ответ сервиса содержит содержимое
внутренних ресурсов (`http://127.0.0.1:6379`, `169.254.169.254`).

## Фикс (минимальный и безопасный)

### Python

```python
import ipaddress, socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

def is_private(ip):
    a = ipaddress.ip_address(ip)
    return (a.is_private or a.is_loopback or a.is_link_local
            or a.is_reserved or a.is_multicast or a.is_unspecified)

def check_url(url):
    u = urlparse(url)
    if u.scheme not in ALLOWED_SCHEMES:
        raise ValueError("bad scheme")
    host = u.hostname or ""
    infos = socket.getaddrinfo(host, u.port or 80)
    for family, _, _, _, sockaddr in infos:
        if is_private(sockaddr[0]):
            raise ValueError("private address")
    return url
```

Ключевые моменты:
- резолвь DNS и проверяй **IP**, а не строку хоста;
- `allow_redirects=False` (или проверяй каждый redirect);
- блокируй IPv6-mapped (`::ffff:127.0.0.1`) — `ipaddress` это покрывает;
- если фича позволяет только известные домены — allowlist хостов лучше всего.

```python
ALLOWED_HOSTS = {"api.partner.example"}
if u.hostname not in ALLOWED_HOSTS:
    raise ValueError("host not allowed")
```

### Node

```js
const { URL } = require("url");
const dns = require("dns").promises;
const ipaddr = require("ipaddr.js");   // или net.isIP + свои проверки
```

### PHP

```php
$h = parse_url($url, PHP_URL_HOST);
$ip = gethostbyname($h);
if (filter_var($ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE) === false) {
    http_response_code(400); exit;
}
```

## Не сломать чекер

- Чекер часто просит сервис сходить на **его** URL внутри сети — если
  заблокируешь все private-адреса, чекер получит MUMBLE. Поэтому:
  allowlist хостов/подсети чекера + блок остального, или проверка порта.
- Не ломай `localhost`-фичи сервиса (webhook на себя), если чекер их тестит.

## Проверка

```bash
curl 'http://localhost:8080/fetch?url=http://127.0.0.1:80'
curl 'http://localhost:8080/fetch?url=http://169.254.169.254/latest/meta-data/'
curl 'http://localhost:8080/fetch?url=file:///etc/passwd'
```
