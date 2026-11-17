#!/usr/bin/env python3
"""A/D sploit template.

Contract with the farm:
  * the farm runs this script with the target IP as argv[1];
  * flags are printed to stdout, one per line, via print(..., flush=True);
  * the farm extracts flags with its flag regex, so any extra output is fine.

One file covers both modes:
  * standalone sploit          -> leave ATTACK_DATA_URL = None
  * attack-data-driven sploit  -> set ATTACK_DATA_URL to the jury endpoint
"""

import random
import re
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
FLAG_RX = re.compile(r"[A-Z0-9]{31}=")

ATTACK_DATA_URL = None          # e.g. "http://10.10.0.1/api/client/attack_data"
ATTACK_DATA_TOKEN = None        # some boards want ?token=... or an auth header

USE_RANDOM_UA = True
HTTP_TIMEOUT = 4
HTTP_RETRIES = 1

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 Edg/124.0",
]
# Placeholder: replace with the checker UA of the current game if needed.
CHECKER_USER_AGENT = "{CHECKER USER-AGENT}"


def _headers():
    if not USE_RANDOM_UA:
        return {}
    return {"User-Agent": random.choice(USER_AGENTS)}


# ---------------------------------------------------------------------------
# HTTP helper with retry
# ---------------------------------------------------------------------------
def http_get(url, headers=None, timeout=HTTP_TIMEOUT, retries=HTTP_RETRIES):
    last_exc = None
    for _ in range(retries + 1):
        try:
            r = requests.get(url, headers=headers or _headers(), timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last_exc = e
            time.sleep(0.3)
    raise last_exc


# ---------------------------------------------------------------------------
# Attack data
# ---------------------------------------------------------------------------
def _pick_entry(data, ip):
    """Best-effort extraction of this team's entry from a JSON blob.

    Supports the usual farm layouts without manual editing:
      {"10.10.10.5": {...}}                 -> direct IP key
      {"5": {...}}                          -> last octet as team id
      {"service": {"10.10.10.5": {...}}}    -> nested by service
      {"service": {"5": {...}}}             -> nested by team id
    """
    if not isinstance(data, dict):
        return {}
    tid = ip.rsplit(".", 1)[-1]
    for key in (ip, tid):
        if key in data:
            return data[key]
    for value in data.values():
        if isinstance(value, dict):
            for key in (ip, tid):
                if key in value:
                    return value[key]
    return {}


def get_attack_data(ip):
    if not ATTACK_DATA_URL:
        return {}
    headers = _headers()
    if ATTACK_DATA_TOKEN:
        headers["Authorization"] = ATTACK_DATA_TOKEN
    url = ATTACK_DATA_URL
    if ATTACK_DATA_TOKEN and "?" not in url:
        url = f"{url}?token={ATTACK_DATA_TOKEN}"
    try:
        data = http_get(url, headers=headers).json()
    except (requests.RequestException, ValueError) as e:
        print(f"[-] attack data fetch failed: {e}", file=sys.stderr, flush=True)
        return {}
    return _pick_entry(data, ip)


# ---------------------------------------------------------------------------
# Exploit: TODO - put the real logic here
# ---------------------------------------------------------------------------
def exploit(ip, data):
    """Return an iterable of flag strings (may also print them directly)."""
    flags = set()

    # TODO: implement the actual attack against `ip` here.
    # `data` holds the per-team attack info (ids/tokens) if enabled.
    #
    # Example skeleton:
    #
    # token = data.get("token")
    # headers = _headers()
    # if token:
    #     headers["X-Auth-Token"] = token
    #
    # r = http_get(f"http://{ip}:8080/flag", headers=headers)
    # flags.update(FLAG_RX.findall(r.text))

    try:
        r = http_get(f"http://{ip}:8080/flag")
        flags.update(FLAG_RX.findall(r.text))
    except requests.RequestException as e:
        print(f"[-] {ip}: {e}", file=sys.stderr, flush=True)

    return flags


# ---------------------------------------------------------------------------
# Entry point: do not edit below unless you know the farm contract changed
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <target_ip>", file=sys.stderr, flush=True)
        sys.exit(1)

    ip = sys.argv[1]
    data = get_attack_data(ip)

    try:
        found = exploit(ip, data)
    except Exception as e:
        print(f"[-] exploit error: {e}", file=sys.stderr, flush=True)
        found = []

    if found is None:
        found = []
    elif isinstance(found, str):
        found = [found]

    for flag in found:
        flag = str(flag).strip()
        if FLAG_RX.fullmatch(flag):
            print(flag, flush=True)


if __name__ == "__main__":
    main()
