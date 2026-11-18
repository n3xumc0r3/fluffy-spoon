# Анализ трафика — Tulip (наш стек) + tcpdump/tshark

**Tulip** (https://github.com/CzechCyberTeam/tulip-public) — flow-анализатор
для A/D: загружает pcaps/Suricata, ищет флаги, генерит Python-сниппеты для
реплея атак. Web UI на :3000.

## Поднять Tulip

```bash
git clone https://github.com/CzechCyberTeam/tulip-public
cd tulip-public && cp .env.example .env
# .env:
#   TRAFFIC_DIR_HOST=./traffic        # сюда кладём pcaps
#   FLAG_REGEX=[A-Z0-9]{31}=
#   TICK_START / TICK_LENGTH          # тайминг игры
#   VM_IP=<ip вулнбокса>               # для группировки сервисов
docker compose up -d --build
```

- UI: http://localhost:3000 (внутренняя сеть/VPN, наружу не светить!)
- API не публикуется в compose; для скриптов либо добавь `ports: 5000:5000`
  сервису `api`, либо `docker compose exec api curl ...`.
- `services/configurations.py` — список сервисов (ip/port/name), правится
  вручную и пересобирается: `docker compose up --build -d api`.

## Сбор трафика

```bash
# на вулнбоксе: ротация дампов
sudo tcpdump -i any -s0 -G 300 -w '/tmp/traffic/svc_%H%M.pcap' 'tcp port 8080'
# забираем к Tulip (rsync по cron или вручную)
rsync -av /tmp/traffic/ tulip-host:~/tulip-public/traffic/
```

Assembler сам подхватывает новые pcaps (inotify). Suricata `eve.json` тоже
читается; теги из `metadata: tag ...` автоматически вешаются на флоу.

## Что даёт UI

- Фильтры по сервису/порту/времени/IP и regex по данным флоу.
- Подсветка флоу с флагами (`contains_flag`).
- Diff флоу, графики, дееплинки (удобно для команды).
- **to_python_request** — готовый requests-скрипт атаки.
- **to_pwn** — pwntools-скрипт (`remote(host, port)` + байты).
- Flag IDs scraping/scanning (аналог attack data) — см. `.env`:
  `FLAGID_ENDPOINT`, `FLAGID_SCRAPE=1`, `FLAGID_SCAN=1`, `TEAM_ID`.

## Свой клиент (в ките): tulip_client.py

```bash
export TULIP_URL=http://127.0.0.1:5000
tulip_client.py flows --flag                     # флоу с флагами
tulip_client.py flows --ip 10.10.4.1 --port 8080 --since 30
tulip_client.py flows --tag path_traversal
tulip_client.py flags --since 60                 # вытащить сами флаги
tulip_client.py raw <flow_id> --out req.txt      # client->server байты
tulip_client.py pwn <flow_id> > sploit.py        # pwntools-скелет
tulip_client.py python <flow_id>                 # requests-скелет
```

Связка: `raw` → `replay.py --request req.txt --teams-file teams.json --port P`
— атака чужим эксплойтом по всем командам.

## tcpdump/tshark — быстрые команды

```bash
# HTTP-запросы с источниками и UA (чекер vs атакующий)
tshark -r svc.pcap -Y http.request -T fields -e ip.src -e http.user_agent | sort | uniq -c
# тела запросов/ответов
tshark -r svc.pcap -Y 'http.request or http.response' -T fields -e http.file_data | head
# поток целиком
tshark -r svc.pcap -q -z follow,tcp,ascii,3
# флаги из дампа
python3 flagscan.py svc.pcap
```

## Правила

- Чекер: стабильный UA/подсеть/интервалы. Атакующий: браузерные UA, странные
  параметры. Отделяй одно от другого перед фильтрацией.
- Tulip содержит флаги — доступ только по VPN/локалке.
- Дампы — в /tmp (ephemeral), полезные пейлоады — в git.
- Шифрованный трафик без ключей бесполезен; в Kubernetes трафик может не
  попадать на tcpdump ноды — снимай на pod/sidecar.
