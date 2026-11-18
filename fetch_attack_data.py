#!/usr/bin/env python3
"""Attack data history dumper.

Polls the jury attack-data endpoint every round and appends each response to
a JSONL file. Keeping the history lets you attack stale (pre-patch) targets
and analyze how the board rotates per-team data.

  python3 fetch_attack_data.py --url http://jury/api/client/attack_data \
      --token TOK --out /tmp/work/attack_data.jsonl [--period 60]
"""

import argparse
import json
import sys
import time

import requests


def main():
    p = argparse.ArgumentParser(description="poll attack data into a JSONL history")
    p.add_argument("--url", required=True)
    p.add_argument("--token", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--period", type=float, default=60, help="seconds between polls")
    p.add_argument("--once", action="store_true")
    args = p.parse_args()

    headers = {"Authorization": args.token} if args.token else {}

    while True:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            r = requests.get(args.url, headers=headers, timeout=5)
            r.raise_for_status()
            data = r.json()
            with open(args.out, "a") as f:
                f.write(json.dumps({"ts": ts, "data": data}) + "\n")
            print(f"[{ts}] ok, {len(json.dumps(data))} bytes")
        except Exception as e:
            print(f"[{ts}] error: {e!r}", file=sys.stderr)

        if args.once:
            break
        time.sleep(args.period)


if __name__ == "__main__":
    main()
