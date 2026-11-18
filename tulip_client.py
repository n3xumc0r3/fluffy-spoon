#!/usr/bin/env python3
"""Tulip API client — hunt traffic flows and turn them into exploits.

Talks to a running Tulip API (see docker-compose api service, default :5000):
  POST /query                    — filtered flow list
  GET  /flow/<id>                — full flow (data base64 in "b64")
  GET  /to_pwn/<id>              — generated pwntools script
  GET  /to_python_request/<id>   — generated requests script
  GET  /star/<id>/<0|1>

Examples:
  tulip_client.py flows --flag
  tulip_client.py flows --ip 10.10.4.1 --port 8080 --since 30
  tulip_client.py flags --since 60            # flags seen in recent traffic
  tulip_client.py pwn <id> > sploit.py        # pwntools skeleton
  tulip_client.py raw <id> --out req.txt      # client->server bytes for replay.py
"""

import argparse
import base64
import os
import re
import sys
import time

import requests

TIMEOUT = 10


class Tulip:
    def __init__(self, url):
        self.base = url.rstrip("/")

    def query(self, filters):
        r = requests.post(self.base + "/query", json=filters, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def flow(self, flow_id):
        r = requests.get(self.base + f"/flow/{flow_id}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def pwn(self, flow_id):
        r = requests.get(self.base + f"/to_pwn/{flow_id}", timeout=TIMEOUT)
        r.raise_for_status()
        return r.text

    def python_req(self, flow_id, tokenize=True, use_requests_session=True):
        r = requests.get(
            self.base + f"/to_python_request/{flow_id}",
            params={"tokenize": str(tokenize).lower(),
                    "use_requests_session": str(use_requests_session).lower()},
            timeout=TIMEOUT)
        r.raise_for_status()
        return r.text

    def star(self, flow_id, star=True):
        r = requests.get(self.base + f"/star/{flow_id}/{int(star)}", timeout=TIMEOUT)
        r.raise_for_status()


def build_filters(args):
    f = {}
    if args.regex:
        f["flow.data"] = args.regex
    if args.ip:
        f["dst_ip"] = args.ip
    if args.port:
        f["dst_port"] = args.port
    if args.since:
        now_ms = int(time.time() * 1000)
        f["from_time"] = now_ms - args.since * 60_000
        f["to_time"] = now_ms
    if args.tag:
        f["includeTags"] = [args.tag]
    return f


def stream_bytes(flow, direction):
    chunks = []
    for msg in flow.get("flow", []):
        if msg.get("from") == direction:
            chunks.append(base64.b64decode(msg.get("b64", "")))
    return b"".join(chunks)


def main():
    p = argparse.ArgumentParser(description="query Tulip flows and export exploits")
    p.add_argument("--url", default=os.environ.get("TULIP_URL", "http://127.0.0.1:5000"))
    p.add_argument("--flag-format", default=os.environ.get("FLAG_REGEX", r"[A-Z0-9]{31}="))
    sub = p.add_subparsers(dest="cmd", required=True)

    fl = sub.add_parser("flows")
    fl.add_argument("--flag", action="store_true", help="only flows containing flags")
    fl.add_argument("--regex", help="regex over flow data")
    fl.add_argument("--ip")
    fl.add_argument("--port", type=int)
    fl.add_argument("--since", type=int, help="last N minutes")
    fl.add_argument("--tag")

    fg = sub.add_parser("flags")
    fg.add_argument("--regex")
    fg.add_argument("--ip")
    fg.add_argument("--port", type=int)
    fg.add_argument("--since", type=int, help="last N minutes")
    fg.add_argument("--tag")
    fg.add_argument("--limit", type=int, default=50)

    for name in ("flow", "pwn", "python"):
        sp = sub.add_parser(name)
        sp.add_argument("id")

    raw = sub.add_parser("raw")
    raw.add_argument("id")
    raw.add_argument("--dir", default="client", choices=["client", "server"],
                     help="which side to dump")
    raw.add_argument("--out")

    st = sub.add_parser("star")
    st.add_argument("id")

    args = p.parse_args()
    api = Tulip(args.url)

    if args.cmd == "flows":
        rows = api.query(build_filters(args))
        flags = [r for r in rows if r.get("contains_flag")] if args.flag else rows
        for r in flags:
            ts = time.strftime("%H:%M:%S", time.localtime(r.get("time", 0) / 1000))
            print(f"{r.get('_id')}  {ts}  {r.get('src_ip')}:{r.get('src_port')} -> "
                  f"{r.get('dst_ip')}:{r.get('dst_port')}  "
                  f"flag={r.get('contains_flag')}  tags={','.join(r.get('tags') or [])}")
        print(f"-- {len(flags)} flow(s)", file=sys.stderr)

    elif args.cmd == "flags":
        rows = api.query(build_filters(args))
        rx = re.compile(args.flag_format)
        found = {}
        for r in rows[:args.limit]:
            if not r.get("contains_flag"):
                continue
            detail = api.flow(r["_id"])
            for direction in ("c", "s"):
                for flag in rx.findall(stream_bytes(detail, direction).decode(errors="ignore")):
                    found.setdefault(flag, r["_id"])
        for flag, flow_id in found.items():
            print(f"{flag}  (flow {flow_id})")
        print(f"-- {len(found)} unique flag(s)", file=sys.stderr)

    elif args.cmd == "flow":
        print(api.flow(args.id))
    elif args.cmd == "pwn":
        print(api.pwn(args.id))
    elif args.cmd == "python":
        print(api.python_req(args.id))
    elif args.cmd == "raw":
        flow = api.flow(args.id)
        data = stream_bytes(flow, "c" if args.dir == "client" else "s")
        if args.out:
            with open(args.out, "wb") as f:
                f.write(data)
            print(f"[+] {len(data)} bytes -> {args.out}", file=sys.stderr)
        else:
            sys.stdout.buffer.write(data)
    elif args.cmd == "star":
        api.star(args.id)
        print("[+] starred")


if __name__ == "__main__":
    main()
