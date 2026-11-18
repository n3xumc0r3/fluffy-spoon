#!/usr/bin/env python3
"""Manual flag submitter for CookieFarm servers.

CookieFarm already submits flags from `ckc exploit run`. This is the backup
channel (farm dead / flags found in pcaps / Tulip harvest): log in, then push
flags straight to the server.

API used:
  POST /api/v1/auth/login                {"username","password"} -> token cookie
  POST /api/v1/submit-flag               {"flag": {...}}         (immediate)
  POST /api/v1/submit-flags              {"flags": [...]}        (store only)
  POST /api/v1/submit-flags-standalone   {"flags": [...]}        (batch + submit)

Examples:
  cat flags.txt | cookiefarm_submit.py --url http://farm:8080 -P PASS -n CookieService -p 8081
  cookiefarm_submit.py --url ... -P PASS -n CookieService -p 8081 --team-id 3 flags.txt
"""

import argparse
import re
import sys

import requests

DEFAULT_FLAG_RX = r"[A-Z0-9]{31}="


def login(base, password, username):
    s = requests.Session()
    r = s.post(base + "/api/v1/auth/login",
               json={"username": username, "password": password}, timeout=10)
    if not r.ok:
        raise SystemExit(f"login failed: HTTP {r.status_code} {r.text}")
    token = s.cookies.get("token")
    if not token:
        raise SystemExit("login failed: no token cookie in response")
    s.headers["Cookie"] = "token=" + token
    return s


def main():
    p = argparse.ArgumentParser(description="submit flags to a CookieFarm server")
    p.add_argument("--url", required=True, help="server base, e.g. http://127.0.0.1:8080")
    p.add_argument("-P", "--password", required=True)
    p.add_argument("-u", "--username", default="cookieguest")
    p.add_argument("-n", "--service", default="", help="service name")
    p.add_argument("-p", "--port", type=int, default=0, help="service port")
    p.add_argument("-t", "--team-id", type=int, default=0, help="team id of the target")
    p.add_argument("-e", "--exploit-name", default="manual")
    p.add_argument("--store", action="store_true",
                   help="store only (/submit-flags), no game submit")
    p.add_argument("--flag-format", default=DEFAULT_FLAG_RX)
    p.add_argument("files", nargs="*", help="flag files (default: stdin)")
    args = p.parse_args()

    text = ""
    if args.files:
        for path in args.files:
            with open(path, errors="ignore") as f:
                text += f.read() + "\n"
    else:
        text = sys.stdin.read()

    flags = list(dict.fromkeys(re.compile(args.flag_format).findall(text)))
    if not flags:
        raise SystemExit("no flags found")

    s = login(args.url.rstrip("/"), args.password, args.username)
    endpoint = "/api/v1/submit-flags" if args.store else "/api/v1/submit-flags-standalone"
    payload = {"flags": [
        {"flag_code": f, "service_name": args.service, "port_service": args.port,
         "team_id": args.team_id, "exploit_name": args.exploit_name}
        for f in flags
    ]}
    r = s.post(args.url.rstrip("/") + endpoint, json=payload, timeout=15)
    print(f"HTTP {r.status_code}: {len(flags)} flag(s) -> {endpoint}")
    if not r.ok:
        print(r.text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
