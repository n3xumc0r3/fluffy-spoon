#!/usr/bin/env python3
"""Flag scanner for offline artifacts: pcaps, packet dumps, logs, raw files.

Reads files as raw bytes and extracts every flag matching the regex. Works on
tcpdump/pcap files, Firegex/Tulip exports, plain logs, anything. Plaintext
protocols only (HTTP etc.) — encrypted traffic needs the keys first.

  python3 flagscan.py dump.pcap [more files...]
  tcpdump -i any -w dump.pcap 'tcp port 8080'   # then scan offline
"""

import argparse
import re
import sys

DEFAULT_FLAG_RX = r"[A-Z0-9]{31}="


def main():
    p = argparse.ArgumentParser(description="extract flags from offline files/pcaps")
    p.add_argument("files", nargs="+")
    p.add_argument("--flag-format", default=DEFAULT_FLAG_RX)
    args = p.parse_args()

    rx = re.compile(args.flag_format.encode())
    found = set()
    for path in args.files:
        with open(path, "rb") as f:
            data = f.read()
        hits = set(rx.findall(data))
        if hits:
            for hit in sorted(hits):
                flag = hit.decode()
                print(flag, flush=True)
            found |= hits
    print(f"-- {len(found)} unique flag(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
