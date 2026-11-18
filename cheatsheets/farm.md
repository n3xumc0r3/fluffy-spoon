# CookieFarm — ферма (наш стек)

CookieFarm (ByteTheCookies): Go-сервер + Python-клиент `ckc`. Сервер сам
сабмитит флаги в игру под rate-limit, клиент гоняет сплойты по командам.

## Сервер

Установка: `bash -c "$(curl -sSL cookiefarm.bytethecookies.org/install.sh)"`,
затем `docker compose up --build -d`.

`.env`:
```env
DEBUG=false
PASSWORD=<сильный пароль>
CONFIG_FILE=config.yml
PORT=8080
```

`config.yml` (важное):
```yaml
server:
  url_flag_checker: "<ip:port жюри>"
  team_token: "<токен команды>"
  protocol: "cc_http"        # cc_http | faust | forcad_http
  tick_time: 120
  submit_flag_checker_time: 120
  max_flag_batch_size: 1000
  url_flag_ids: "<адрес flagids>"
shared:
  services:
    CookieService: 8081      # имя: порт
  format_ip_teams: "10.10.{}.1"
  range_ip_teams: 29
  my_team_id: 1
  nop_team: 0
  regex_flag: "[A-Z0-9]{31}="
  flagids_format: "[service].[team].[id]"
```

- Борды: `cc_http`, `faust`, `forcad_http` — выбирай протокол игры.
- `my_team_id` исключается из атак, `nop_team` — для тестов.
- Если игра даёт attack data — это `url_flag_ids` (flag IDs). Сервер проксирует
  их клиенту, `flagids_format` описывает структуру JSON.

## Клиент

```bash
pip install --upgrade cookiefarm requests
ckc config edit -H <ip фермы> -p 8080
ckc login -P <пароль> -u <ник>
ckc exploit create -n my_exploit      # шаблон в ~/.cookiefarm/exploits/
ckc exploit test -e my_exploit.py -n CookieService -p 8081 -t 120 -W 10   # NOP-команда
ckc exploit run  -e my_exploit.py -n CookieService -p 8081 -t 120 -W 40 -d  # detach
ckc exploit listrun / stop -p <pid>
ckc exploit submit -f <флаг> -n CookieService -t <team_id>   # ручной сабмит
```

Флаги клиент парсит сам из stdout сплойта.

## Контракт сплойта (важно!)

```python
#!/usr/bin/env python3
from cookiefarm import exploit_manager

@exploit_manager
def exploit(ip, port, name_service, flag_ids: list):
    # flag_ids — только для этой команды и сервиса, уже нормализованные
    print(flag)   # флаги в stdout, потокобезопасно
```

- Декоратор сам: логинится, тянет конфиг, гоняет по всем командам, ловит
  stdout по потокам, выцепает флаги regex-ом, логирует JSON.
- Один процесс = все команды; `-W` воркеры, `-t` тик, `-P` process_mode.
- Готовый шаблон с HTTP-хелпером: `sploit_cookiefarm.py` в корне кита.

## API сервера (для своих скриптов)

Авторизация: `POST /api/v1/auth/login {"username","password"}` → cookie
`token` (JWT). Дальше `Cookie: token=...` или `Authorization: Bearer ...`.

```http
POST /api/v1/submit-flag              {"flag": {"flag_code","service_name","port_service","team_id",...}}   # сразу в игру
POST /api/v1/submit-flags             {"flags": [...]}   # только в БД
POST /api/v1/submit-flags-standalone  {"flags": [...]}   # БД + батч в игру
GET  /api/v1/config                   # конфиг
GET  /api/v1/stats                    # статистика флагов
```

Ручной/запасной сабмит: `cookiefarm_submit.py` (в ките) — логин, батч,
`--store` для «только в БД».

## Эксплуатация в игре

1. До игры: сервер поднят, `protocol`/`team_token` верные, тестовый сабмит
   через `ckc exploit submit` или `cookiefarm_submit.py`.
2. Запуск: `ckc exploit run ... -d` (detach) для каждого сервиса/сплойта.
3. Смотри `GET /api/v1/stats` и дашборд; следи за rate-limit жюри.
4. Ферма умерла → `cookiefarm_submit.py` + `flagscan.py` по логам/дампам.
5. Наш `farm_client.py` — для S4DFarm/destructive-farm протокола
   (`/api/get_config`, `/api/post_flags`), не для CookieFarm.

## Статусы сервисов

CookieFarm статусов сервисов не знает — это делает борда. Мониторинг:
`watch_status.py --url <борда JSON> --token <токен>`.
