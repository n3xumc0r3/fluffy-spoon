# Анализ трафика — шпаргалка

## Снять дамп

```bash
# весь трафик сервиса
sudo tcpdump -i any -s0 -w /tmp/work/svc.pcap 'tcp port 8080'

# только подозрительные хосты (не чекер)
sudo tcpdump -i any -s0 -w /tmp/work/in.pcap 'tcp port 8080 and not host 10.10.0.1'

# ротация, чтобы не забить диск
sudo tcpdump -i any -s0 -G 300 -w '/tmp/work/svc_%H%M.pcap' 'tcp port 8080'
```

Pacmate — веб-морда над live-трафиком: смотреть Flag In/Flag Out, реплеить.

## tshark: быстрый разбор

```bash
# HTTP-запросы (метод, хост, uri)
tshark -r svc.pcap -Y http.request -T fields -e ip.src -e http.request.method -e http.host -e http.request.uri | head -50

# откуда какие User-Agent (чекер vs атакующий)
tshark -r svc.pcap -Y http.request -T fields -e ip.src -e http.user_agent | sort | uniq -c

# тела запросов/ответов
tshark -r svc.pcap -Y 'http.request or http.response' -T fields -e http.file_data | head

# по TCP-стриму целиком
tshark -r svc.pcap -q -z follow,tcp,ascii,3
```

## Флаги в трафике

```bash
# офлайн-сканер из кита
python3 flagscan.py svc.pcap

# вручную
tshark -r svc.pcap -T fields -e http.file_data | rg -o '[A-Z0-9]{31}='
```

## Отличить чекер от атакующего

- Чекер: стабильный источник (подсеть жюри), стабильный User-Agent
  (`python-requests/X.Y.Z`), ровные интервалы, легитимные запросы.
- Атакующий: браузерные UA, сканерные паттерны, аномальные параметры,
  неожиданные объёмы.

```bash
tshark -r svc.pcap -Y http.request -T fields -e ip.src -e http.user_agent | sort | uniq -c | sort -rn | head
```

## Из запроса — в реплей

1. Нашёл в Pacmate интересный запрос (кража флага, RCE).
2. Скопировал raw HTTP-запрос в файл `req.txt`.
3. `python3 replay.py --request req.txt --teams-file teams.json --port 8080`
4. Патчишься от этого же запроса.

## Если сервис шифрует трафик

Дамп бесполезен без ключей: смотри код на клиенте/сервере, вытаскивай ключ из
памяти/конфига, расшифровывай офлайн. Если A/D в Kubernetes — трафик может
уходить мимо tcpdump на ноде — используй sidecar/pcap на pod'е.

## Не забыть

- Дампы — в `/tmp` (ephemeral), итоги/интересные пейлоады — в git.
- Свои флаги в трафике наружу = утечка: ищи, кто их сдаёт (`Flag Out`), и
  патч.
