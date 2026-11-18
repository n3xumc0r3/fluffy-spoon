#!/usr/bin/env python3
r"""Firegex API client — manage regex filters without the web UI.

Talks to a running Firegex (default http://127.0.0.1:4444):
  POST /api/login (password) -> bearer token
  GET/POST /api/services[/...]  — services, filters, regexes

Regexes are byte patterns for hyperscan; the API takes them base64-encoded.
Mode: C = client->server, S = server->client, B = both.

Examples:
  firegex_client.py services
  firegex_client.py regex list web
  firegex_client.py regex add web '(\.\./|%2e%2e)' --mode C
  firegex_client.py regex add web 'FLAG\\{' --mode S   # block flag exfil etc.
  firegex_client.py regex del web --filter <id> --regex-id <id>
"""

import argparse
import base64
import os
import sys

import requests

TIMEOUT = 5


class Firegex:
    def __init__(self, url, password, username="admin"):
        self.base = url.rstrip("/")
        r = requests.post(
            self.base + "/api/login",
            data={"username": username, "password": password},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            raise SystemExit(f"login failed: HTTP {r.status_code} {r.text}")
        token = r.json().get("access_token")
        if not token:
            raise SystemExit(f"login failed: no access_token in {r.text}")
        self.h = {"Authorization": "Bearer " + token}

    def _req(self, method, path, **kw):
        r = requests.request(method, self.base + "/api" + path,
                             headers=self.h, timeout=TIMEOUT, **kw)
        if not r.ok:
            raise SystemExit(f"{method} {path}: HTTP {r.status_code} {r.text}")
        return r.json() if r.text else None

    def services(self):
        return self._req("GET", "/services")

    def filters(self, service_id):
        return self._req("GET", f"/services/{service_id}/filters")

    def regexes(self, service_id, filter_id):
        return self._req("GET", f"/services/{service_id}/filters/{filter_id}/regexes")

    def add_regex(self, service_id, filter_id, pattern, mode="B",
                  case_sensitive=True):
        enc = base64.b64encode(pattern.encode()).decode()
        return self._req("POST", f"/services/{service_id}/filters/{filter_id}/regexes",
                         json={"regex": enc, "mode": mode,
                               "case_sensitive": case_sensitive, "active": True})

    def del_regex(self, service_id, filter_id, regex_id):
        return self._req("DELETE",
                         f"/services/{service_id}/filters/{filter_id}/regexes/{regex_id}")

    def add_filter(self, service_id, kind="regex", name="kit"):
        return self._req("POST", f"/services/{service_id}/filters",
                         json={"kind": kind, "name": name, "active": True})

    def stats(self, service_id):
        return self._req("GET", f"/services/{service_id}/stats")


def resolve_service(fx, name_or_id):
    for svc in fx.services():
        if name_or_id in (svc.get("service_id"), svc.get("name")):
            return svc
    raise SystemExit(f"service not found: {name_or_id}")


def ensure_regex_filter(fx, service_id):
    for f in fx.filters(service_id):
        if f.get("kind") == "regex":
            return f
    fx.add_filter(service_id, kind="regex", name="kit")
    return next(f for f in fx.filters(service_id) if f.get("kind") == "regex")


def print_table(rows, cols):
    if not rows:
        print("(empty)")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


def main():
    p = argparse.ArgumentParser(description="manage Firegex services and regex filters")
    p.add_argument("--url", default=os.environ.get("FIREGEX_URL", "http://127.0.0.1:4444"))
    p.add_argument("--password", default=os.environ.get("FIREGEX_PASSWORD", ""))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("services")

    sp = sub.add_parser("filters")
    sp.add_argument("service")

    sp = sub.add_parser("stats")
    sp.add_argument("service")

    rp = sub.add_parser("regex")
    ra = rp.add_subparsers(dest="action", required=True)
    ra.add_parser("list").add_argument("service")
    add = ra.add_parser("add")
    add.add_argument("service")
    add.add_argument("pattern")
    add.add_argument("--mode", default="B", choices=["C", "S", "B"])
    add.add_argument("--filter", dest="filter_name", help="regex filter name/id (default: first/auto-create)")
    add.add_argument("--case-sensitive", action="store_true", default=True)
    rm = ra.add_parser("del")
    rm.add_argument("service")
    rm.add_argument("--filter", dest="filter_id", required=True)
    rm.add_argument("--regex-id", required=True)

    args = p.parse_args()
    if not args.password:
        raise SystemExit("pass --password or set FIREGEX_PASSWORD")
    fx = Firegex(args.url, args.password)

    if args.cmd == "services":
        print_table(fx.services(), ["service_id", "name", "status", "proto",
                                    "transport", "n_filters", "n_blocked"])
    elif args.cmd == "filters":
        svc = resolve_service(fx, args.service)
        print_table(fx.filters(svc["service_id"]),
                    ["filter_id", "position", "kind", "name", "active",
                     "blocked", "n_regexes"])
    elif args.cmd == "stats":
        svc = resolve_service(fx, args.service)
        print(fx.stats(svc["service_id"]))
    elif args.cmd == "regex":
        svc = resolve_service(fx, args.service)
        if args.action == "list":
            for f in fx.filters(svc["service_id"]):
                if f.get("kind") != "regex":
                    continue
                print(f"# filter {f['name']} ({f['filter_id']})")
                print_table(fx.regexes(svc["service_id"], f["filter_id"]),
                            ["regex_id", "regex", "mode", "active", "blocked"])
        elif args.action == "add":
            f = None
            if args.filter_name:
                f = next((x for x in fx.filters(svc["service_id"])
                          if args.filter_name in (x["name"], x["filter_id"])), None)
            if f is None:
                f = ensure_regex_filter(fx, svc["service_id"])
            fx.add_regex(svc["service_id"], f["filter_id"], args.pattern,
                         mode=args.mode, case_sensitive=args.case_sensitive)
            print(f"[+] regex added to {svc['name']}/{f['name']} (mode {args.mode})")
        elif args.action == "del":
            fx.del_regex(svc["service_id"], args.filter_id, args.regex_id)
            print("[+] regex deleted")


if __name__ == "__main__":
    main()
