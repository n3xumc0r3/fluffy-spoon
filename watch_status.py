#!/usr/bin/env python3
"""Board status watcher (board-agnostic).

Polls a JSON endpoint (or a local file) and alerts on status transitions.
It flattens the JSON into paths and tracks any leaf values that look like
service statuses: UP / MUMBLE / CORRUPT / DOWN (case-insensitive), so it
works with ForcAD, CTF01d and similar boards without per-board glue.

  python3 watch_status.py --url http://board/api/teams/selection --token TOK
  python3 watch_status.py --json-file board.json --state-file /tmp/st.json

Alerts print a bell (\a) when a service ENTERS a bad state.
"""

import argparse
import json
import sys
import time

import requests

STATUSES = {"up", "mumble", "corrupt", "down"}
BAD = {"mumble", "corrupt", "down"}


def flatten(obj, prefix=""):
    """Yield (path, value) pairs for JSON leaves."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}.{i}")
    else:
        yield prefix, obj


def statuses_of(obj):
    out = {}
    for path, value in flatten(obj):
        if isinstance(value, str) and value.strip().lower() in STATUSES:
            out[path] = value.strip().upper()
    return out


def fetch(args):
    if args.json_file:
        with open(args.json_file, encoding="utf-8") as f:
            return json.load(f)
    headers = {"Authorization": args.token} if args.token else {}
    r = requests.get(args.url, headers=headers, timeout=args.timeout)
    r.raise_for_status()
    return r.json()


def main():
    p = argparse.ArgumentParser(description="alert on board status transitions")
    p.add_argument("--url", default="", help="board JSON endpoint")
    p.add_argument("--token", default="")
    p.add_argument("--json-file", default="", help="poll this JSON file instead (testing)")
    p.add_argument("--state-file", default="/tmp/watch_status_state.json",
                   help="where to persist the last seen statuses")
    p.add_argument("--period", type=float, default=15)
    p.add_argument("--timeout", type=float, default=5)
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    if not args.url and not args.json_file:
        p.error("pass --url or --json-file")

    try:
        with open(args.state_file, encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}

    while True:
        try:
            cur = statuses_of(fetch(args))
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] fetch error: {e!r}", file=sys.stderr)
            cur = None

        if cur is not None:
            for path, status in sorted(cur.items()):
                old = prev.get(path)
                if old is None:
                    if status in BAD:
                        print(f"\a[{time.strftime('%H:%M:%S')}] NEW BAD: {path} = {status}", flush=True)
                    elif args.once or not prev:
                        print(f"[{time.strftime('%H:%M:%S')}] init: {path} = {status}", flush=True)
                elif old != status:
                    mark = "\a!! " if status.lower() in BAD else "   "
                    print(f"{mark}[{time.strftime('%H:%M:%S')}] {path}: {old} -> {status}", flush=True)
            for path in prev.keys() - cur.keys():
                print(f"   [{time.strftime('%H:%M:%S')}] {path}: gone from board", flush=True)
            prev = cur
            with open(args.state_file, "w") as f:
                json.dump(prev, f)

        if args.once:
            break
        time.sleep(args.period)


if __name__ == "__main__":
    main()
