#!/usr/bin/env python3
"""HTTP request replay: steal-then-replay workflow from the playbook.

Feed it a raw HTTP request (copied from Tulip / tcpdump) and the list of
teams; it sends the same request to every team IP and prints any flags found
in the responses.

The request may contain the literal placeholder {IP} (substituted per team).
If there is no placeholder, the Host header is rewritten to the target IP
automatically (disable with --no-fix-host).

Getting the request from a pcap:
  tshark -r dump.pcap -q -z follow,tcp,raw,0     # pick the stream, decode
  tcpdump -A -s0 'host 10.10.10.5 and port 8080' # copy the request text

  python3 replay.py --request req.txt --teams-file teams.json --port 8080
"""

import argparse
import json
import re
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

DEFAULT_FLAG_RX = r"[A-Z0-9]{31}="
READ_TIMEOUT = 4


def load_teams(args):
    teams = {}
    if args.teams_file:
        with open(args.teams_file, encoding="utf-8") as f:
            teams = json.load(f)
    for item in args.teams or []:
        name, _, ip = item.partition("=")
        teams[name or ip] = ip
    if not teams:
        raise SystemExit("no teams: pass --teams-file or --teams name=ip")
    return teams


def build_request(raw, ip, port, fix_host=True):
    if b"{IP}" in raw:
        raw = raw.replace(b"{IP}", ip.encode())
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    fixed = []
    for line in lines:
        if fix_host and line.lower().startswith(b"host:"):
            line = b"Host: " + ip.encode() + b":" + str(port).encode()
        fixed.append(line)
    head = b"\r\n".join(fixed)
    if b"connection:" not in head.lower():
        head += b"\r\nConnection: close"
    return head + b"\r\n\r\n" + body


def hit(ip, port, payload, flag_rx, name):
    flags = []
    try:
        with socket.create_connection((ip, port), timeout=READ_TIMEOUT) as s:
            s.settimeout(READ_TIMEOUT)
            s.sendall(payload)
            chunks = []
            while True:
                try:
                    part = s.recv(65536)
                except socket.timeout:
                    break
                if not part:
                    break
                chunks.append(part)
        text = b"".join(chunks)
        flags = sorted(f.decode() for f in set(flag_rx.findall(text)))
        first_line = text.split(b"\r\n", 1)[0].decode(errors="replace")
        print(f"[{name}] {first_line}")
        for f in flags:
            print(f"[{name}] FLAG {f}", flush=True)
    except Exception as e:
        print(f"[{name}] error: {e!r}", file=sys.stderr)
    return flags


def main():
    p = argparse.ArgumentParser(description="replay a captured HTTP request against all teams")
    p.add_argument("--request", required=True, help="file with the raw HTTP request")
    p.add_argument("--teams-file", default="", help='JSON {"name": "ip", ...}')
    p.add_argument("--teams", nargs="*", help="extra targets name=ip (repeatable)")
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--flag-format", default=DEFAULT_FLAG_RX)
    p.add_argument("--no-fix-host", action="store_true")
    p.add_argument("--pool", type=int, default=32)
    args = p.parse_args()

    with open(args.request, "rb") as f:
        raw = f.read()
    if not raw:
        raise SystemExit("empty request file")

    flag_rx = re.compile(args.flag_format.encode())
    teams = load_teams(args)
    print(f"replaying to {len(teams)} team(s) on port {args.port}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=args.pool) as pool:
        futures = []
        for name, ip in teams.items():
            payload = build_request(raw, ip, args.port, fix_host=not args.no_fix_host)
            futures.append(pool.submit(hit, ip, args.port, payload, flag_rx, name))
        total = sum(len(f.result()) for f in futures)
    print(f"-- {total} flag(s) total", file=sys.stderr)


if __name__ == "__main__":
    main()
