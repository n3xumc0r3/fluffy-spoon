#!/usr/bin/env python3
"""Manual flag submitter.

Backup channel if the farm dies mid-game: read flags from stdin (one per line)
or files and POST them to the board/farm directly.

Examples:
  echo 'AAA...=' | python3 submit_flags.py --url http://farm --token TOK
  python3 submit_flags.py --url http://farm --token TOK flags.txt more.txt
"""

import argparse
import re
import sys

import requests

DEFAULT_FLAG_RX = r"[A-Z0-9]{31}="


def main():
    p = argparse.ArgumentParser(description="submit flags manually")
    p.add_argument("--url", required=True, help="board/farm endpoint, e.g. http://farm/api/post_flags")
    p.add_argument("--token", required=True, help="team token (Authorization header)")
    p.add_argument("--sploit", default="manual", help="sploit name to attach")
    p.add_argument("--team", default="", help="team name for the flags")
    p.add_argument("--flag-format", default=DEFAULT_FLAG_RX)
    p.add_argument("files", nargs="*", help="files with flags (default: stdin)")
    args = p.parse_args()

    rx = re.compile(args.flag_format)
    text = ""
    if args.files:
        for path in args.files:
            with open(path, errors="ignore") as f:
                text += f.read() + "\n"
    else:
        text = sys.stdin.read()

    flags = list(dict.fromkeys(rx.findall(text)))
    if not flags:
        print("no flags found", file=sys.stderr)
        sys.exit(1)

    payload = [{"flag": f, "sploit": args.sploit, "team": args.team} for f in flags]
    r = requests.post(args.url, json=payload,
                      headers={"Authorization": args.token}, timeout=10)
    print(f"HTTP {r.status_code}: {len(flags)} flag(s) sent")
    if not r.ok:
        print(r.text, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
