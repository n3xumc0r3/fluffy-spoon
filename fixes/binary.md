# Бинарные сервисы — быстрые фиксы

Пересобрать бинарь из исходников в A/D часто невозможно (нет исходников) или
долго. Работаем обёртками и минимальными патчами.

## 0. Разведка

```bash
checksec --file=./service
rabin2 -I ./service          # mitigations: canary, nx, pie, relro
rabin2 -z ./service | rg -i 'flag|secret|/'
strings -a ./service | rg -i 'flag|system|exec'
```

## 1. Фильтр на входе (быстро и безопасно для SLA)

Прокси/обёртка перед сервисом проверяет входной поток на опасные паттерны:

```bash
# пример: сервис на 1337, обёртка на 1338
socat TCP-LISTEN:1338,fork,reuseaddr SYSTEM:'timeout 10 python3 /opt/guard.py | nc 127.0.0.1 1337'
```

```python
# guard.py — фильтр формат-строк и опасных последовательностей
import sys
BAD = [b"%n", b"%s%s%s%s", b"../" * 3]
for line in sys.stdin.buffer:
    if any(b in line for b in BAD):
        continue
    sys.stdout.buffer.write(line)
```

Лучше — Firegex-правило (см. cheatsheets/firegex.md), если сервис HTTP.

## 2. LD_PRELOAD-заглушки (Linux)

Перехват опасных libc-функций без правки бинаря:

```c
// noexec.c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdarg.h>
int system(const char *cmd) { return -1; }
FILE *popen(const char *cmd, const char *mode) { return NULL; }
int execve(const char *p, char *const a[], char *const e[]) { return -1; }
```

```bash
gcc -shared -fPIC -o noexec.so noexec.c -ldl
LD_PRELOAD=/opt/noexec.so ./service
```

Работает только для динамически слинкованных бинарей и вызовов через PLT.
Проверь `ldd ./service` (static — не сработает).

## 3. Байтовый патч

Одна инструкция часто закрывает дыру (например, убрать вызов `system`,
заменить `jne` на `jmp`):

```bash
cp service service.bak
r2 -w ./service
# > /x 90 90            (nop-out)
# > s 0x...; wx eb...   (патч перехода)
```

Обязательно: бэкап, повторный `checksec`, тест легитимных входов чекера.
Правильный патч — только с дизассемблером рядом (r2/objdump) и пониманием
потока.

## 4. Изоляция

- Запуск от непривилегированного пользователя.
- `systemd` unit с `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict`.
- Docker: `--read-only`, `--cap-drop=ALL`, `--user nobody`, `no-new-privileges`.
- Не поможет против чтения флага, если он в памяти — но режет RCE-эскалацию.

## Не сломать чекер

- Фильтр входа проверяй на реальных запросах чекера (собери из трафика до
  игры). Ложное срабатывание = MUMBLE.
- LD_PRELOAD может сломать легитимные вызовы (если сервис сам использует
  `popen` для фичи) — тестируй.
- Патч байтов меняет размер/смещения? Нет, если заменяешь инструкции той же
  длины; иначе правь ELF-структуры аккуратно.

## Проверка

```bash
# после обёртки/патча прогнать легитимный сценарий чекера
python3 /opt/checker_sim.py --host 127.0.0.1 --port 1338
```
