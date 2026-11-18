# Однострочники — шпаргалка

Быстрые команды на все случаи. Связано: [веб](web.md), [Tulip](traffic.md),
[тулзы](../docs/tools.md).

## HTTP / curl

```bash
curl -si http://T/PATH                                  # заголовки + тело
curl -si -X POST http://T/PATH -H 'Content-Type: application/json' -d '{"a":1}'
curl -si http://T/PATH -d 'user=u&pass=p'               # form-urlencoded
curl -si -b 'session=VAL' http://T/PATH                 # с кукой
curl -si -c /tmp/jar -b /tmp/jar http://T/PATH          # сохранить/послать куки
curl -so /dev/null -w '%{http_code} %{time_total}\n' http://T/PATH
curl -si --path-as-is 'http://T/static/../.git/config'  # без нормализации пути
curl -si -H 'Host: internal' -H 'X-Forwarded-For: 127.0.0.1' http://T/PATH
curl -sk https://T/PATH --resolve 'host:443:10.0.0.1'   # свой Host/IP
```

## Netcat / сокеты

```bash
nc -vz 10.10.4.1 8080                        # порт открыт?
printf 'GET / HTTP/1.0\r\nHost: x\r\n\r\n' | nc -w 3 10.10.4.1 80
nc -lvnp 4444                                # слушать (реверс/флаг-стор)
ss -ltnp                                     # что слушает локально
```

## JWT / кодировки

```bash
python3 -c 'import base64,json,sys; t=sys.argv[1].split(".")[1]; t+="="*(-len(t)%4); print(json.dumps(json.loads(base64.urlsafe_b64decode(t)),indent=1))' "$JWT"
python3 -c 'import sys,urllib.parse as u; [print(x) for x in [u.quote(sys.argv[1]), u.quote_plus(sys.argv[1])]]' 'a/b c'
python3 -c 'import base64,sys; print(base64.b64encode(sys.argv[1].encode()).decode())' 'payload'
python3 -c 'import sys; print(bytes.fromhex(sys.argv[1]))' '414243'
```

## JSON / борда (jq)

```bash
curl -s "$BOARD" | jq .
curl -s "$BOARD" | jq '.. | objects | select(has("status")) | [.name, .status] | @tsv'
curl -s "$BOARD" | jq '.. | objects | select(.status? == "DOWN")'
curl -s "$URL_FLAG_IDS" | jq 'keys'
curl -s "$URL_FLAG_IDS" | jq '.["Service1"] | keys'
```

## Трафик (Tulip/tcpdump/tshark)

```bash
tcpdump -i any -s0 -w /tmp/d.pcap 'tcp port 8080'
tcpdump -i any -s0 -A 'tcp port 8080' | head -100
tshark -r d.pcap -Y http.request -T fields -e ip.src -e http.user_agent -e http.host
tshark -r d.pcap -Y 'http.request' -T fields -e http.request.uri | sort | uniq -c | sort -rn
tshark -r d.pcap -q -z follow,tcp,ascii,3
```

## Флаги и файлы

```bash
python3 flagscan.py dump.pcap logs/*.log
grep -rhoE '[A-Z0-9]{31}=' . | sort -u
grep -rniE 'flag|secret|token|password' . --include=*.py --include=*.php --include=*.env
find / -maxdepth 4 -name '*flag*' -readable 2>/dev/null
strings -a bin | grep -iE 'flag|/tmp|system'
```

## Docker / сервисы

```bash
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
docker compose logs -f --tail=100 <service>
docker compose restart <service>
docker compose exec <service> sh
docker inspect <ctr> --format '{{json .Config.Env}}' | jq .
docker stats --no-stream
```

## Git / деплой

```bash
git status --short && git log --oneline -5
git diff --stat && git diff -- path/to/file
git stash push -m wip
git checkout -- .                          # сбросить локальные правки
git reset --hard origin/main && git clean -fd
bash deploy.sh --dir ~/infra --dry-run
bash patch_snapshot.sh snapshot ~/infra/svc1
```

## Python / requests

```bash
python3 - <<'EOF'
import requests
s = requests.Session()
r = s.get("http://T/PATH", timeout=3, verify=False)
print(r.status_code, r.headers.get("server"), len(r.content))
EOF
```

## Полезные мелочи

```bash
# декод base64 из ответа API
echo 'eyJhIjoxfQ==' | base64 -d
# сравнить два ответа
diff <(curl -s URL1) <(curl -s URL2)
# ждать открытия порта
until nc -z 127.0.0.1 5000; do sleep 0.5; done; echo up
# таймаут на любую команду
timeout 10 ./sploit 10.10.4.1
```
