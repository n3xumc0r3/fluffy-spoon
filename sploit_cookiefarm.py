#!/usr/bin/env python3
"""CookieFarm exploit template (@exploit_manager decorator format).

Install and run:
    pip install --upgrade cookiefarm requests
    ckc login -P <server password>
    ckc exploit run -e sploit_cookiefarm.py -n CookieService -p 8081 -t 120 -W 40

The decorator loops over all teams for you, fetches the current flag IDs
(attack data), captures stdout per team and submits flags itself.
Function contract:
    exploit(ip, port, name_service, flag_ids)
      ip           - target team IP
      port         - service port from the farm config
      name_service - service name
      flag_ids     - this team's flag IDs for this service (list of dicts/values)
Print flags to stdout; everything else is ignored.
"""

import random
import re
import sys

import requests
from cookiefarm import exploit_manager

FLAG_RX = re.compile(r"[A-Z0-9]{31}=")
TIMEOUT = 4
RETRIES = 1

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def http_get(url, **kw):
    last = None
    for _ in range(RETRIES + 1):
        try:
            r = requests.get(url, timeout=TIMEOUT,
                             headers={"User-Agent": random.choice(USER_AGENTS)}, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
    raise last


def flag_id_variants(flag_id):
    """Yield (user, password) style pairs whatever the flagids format is."""
    if isinstance(flag_id, dict):
        yield flag_id
    elif isinstance(flag_id, (list, tuple)) and len(flag_id) >= 2:
        yield {"user": flag_id[0], "password": flag_id[1]}
        yield {"username": flag_id[0], "password": flag_id[1]}
    else:
        yield {"id": str(flag_id)}


@exploit_manager
def exploit(ip, port, name_service, flag_ids: list):
    # TODO: real attack for this service.
    # `flag_ids` already contains only this team's ids for this service.
    for fid in flag_ids:
        for ids in flag_id_variants(fid):
            try:
                user = ids.get("username") or ids.get("user") or ids.get("login")
                password = ids.get("password") or ids.get("pass")
                if not (user and password):
                    continue
                # Example: log in with the flag ID and read the flag.
                r = http_get(f"http://{ip}:{port}/profile",
                             params={"username": user, "password": password})
                for flag in FLAG_RX.findall(r.text):
                    print(flag, flush=True)
            except requests.RequestException as e:
                print(f"[-] {ip}:{port} {e}", file=sys.stderr, flush=True)

    # Simple unauthenticated path (common in A/D): remove if not needed.
    try:
        r = http_get(f"http://{ip}:{port}/flag")
        for flag in FLAG_RX.findall(r.text):
            print(flag, flush=True)
    except requests.RequestException as e:
        print(f"[-] {ip}:{port} {e}", file=sys.stderr, flush=True)
