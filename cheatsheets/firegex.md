# Firegex — прокси/фаервол с фильтрами (наш стек)

https://github.com/Pwnzer0tt1/firegex

Стоит перед сервисами, режет трафик до того, как он дойдёт до уязвимости.
Два слоя инспекции: **proxy** (терминирует соединения, умеет TLS/QUIC/HTTP2/3)
и **NFQUEUE** (поспакетно, без TLS). Фильтры: **regex** (hyperscan, байты) и
**pyfilter** (Python с парсингом HTTP/WebSocket/gRPC).

## Установка / запуск

```bash
sh <(curl -sLf https://pwnzer0tt1.it/firegex.sh)
# или из клона:
python3 run.py start --prebuilt
python3 run.py status / stop
python3 run.py config --show / --port 8080 / --password
```

UI/API на порту **4444**. Пароль задаётся при первом старте.
Docker-режим переживает ребут, standalone — надо `start` после перезагрузки.
`--allowed-ips` ограничивает доступ к UI.

## Модель

```
service = адреса (ip:port / CIDR / интерфейс) + протокол + слой
          + упорядоченная цепочка фильтров
```

- Протокол: `TCP`, `UDP`, `TLS`, `QUIC`, `HTTP(S)`.
- Слой: `proxy` (нужен для TLS/QUIC/HTTP(S)) или `NFQUEUE`.
- Фильтры выполняются по порядку; regex-матч **закрывает соединение**
  (перезаписи трафика нет — её убрали).
- Firewall-вкладка: обычные nftables allow/drop/reject (не инспекция).

## Regex-фильтры (быстро)

Паттерны — байтовые (hyperscan), в API передаются base64. Режимы:
`C` = клиент→сервис, `S` = сервер→клиент, `B` = оба.

Типовые (адаптировать под сервис, тестировать на чекере!):

```
(\.\./|%2e%2e|%252e%252e)                      # traversal
[;&|`$]\s*(id|cat|ls|sh|bash|nc|curl|wget)     # cmdi
(union\s+select|or\s+1\s*=\s*1|sleep\s*\()     # sqli
\{\{.*(__class__|__globals__|config).*\}\}     # ssti
<!DOCTYPE[^>]*\[|<!ENTITY                      # xxe
```

Свой клиент к API (в ките): `firegex_client.py`

```bash
export FIREGEX_PASSWORD=...
firegex_client.py services
firegex_client.py regex list web
firegex_client.py regex add web '(\.\./|%2e%2e)' --mode C
firegex_client.py filters web
```

## Python-фильтры (сильнее regex)

Один файл, функции `@pyfilter`; видят распарсенный HTTP, историю, потоки.
Возврат: `ACCEPT` / `REJECT` (закрыть) / `DROP`. `None` = ACCEPT.

```python
from firegex.pyfilters import pyfilter, ACCEPT, REJECT
from firegex.pyfilters.models import HttpRequest, HttpHistory, HttpResponse

@pyfilter
def no_traversal(req: HttpRequest):
    if req.url and ("../" in req.url or "%2e%2e" in req.url.lower()):
        return REJECT

@pyfilter
def no_flag_exfil(resp: HttpResponse):
    # пример: не дать сервису отдать флаг атакующему (осторожно с чекером!)
    if resp.body and b"FLAG{" in resp.body:
        return REJECT
    return ACCEPT

@pyfilter
def probe_flood(hist: HttpHistory):
    if len(hist.requests) > 50:
        return REJECT
```

- Один файл = один протокол (HTTP-модели или RawPacket/стримы).
- Глобалы модуля — на соединение; состояние можно копить между пакетами.
- HTTP/1.1, HTTP/2, HTTP/3 и gRPC показываются как HTTP/1.1.
- Локальный тест без инстанса: `fgex pyfilters test_http.py 127.0.0.1 8080`
  (слушает 7474).
- На proxy слое зависший фильтр убивается, трафик продолжает идти
  (fail-open, настраивается).

## Правила эксплуатации (не сломать SLA)

1. Сначала трафик (Tulip/Pacmate), потом фильтр.
2. Тестируй на легитимных запросах чекера — ложный REJECT = MUMBLE.
3. Фильтруй точечно: URL/метод/параметр, а не «всё со словом select».
4. Правки применяются без дропа соединений; всё равно смотри борду 1-2 тика.
5. Фильтр — временная мера; параллельно фикси код (fixes/).
6. REJECT на `S`-направлении (ответ с флагом) — мощно, но легко поймать
   легитимную отдачу флага чекеру. Проверяй дважды.
7. После деплоя фикса — фильтр снять, чтобы не мешал.
