#!/usr/bin/env python3
"""Self-written farm client for A/D CTF.

Runs a sploit against every team in a loop, harvests flags from the sploit's
stdout and submits them to the farm in batches.

Wire protocol (compatible with S4DFarm / destructive farm):
  GET  {server}/api/get_config   -> {"FLAG_FORMAT": "...", "TEAMS": {"name": "ip", ...}}
  POST {server}/api/post_flags   <- [{"flag": ..., "sploit": ..., "team": ...}]
  auth: plain token in the Authorization header

Extras over a bare client:
  * works without a farm server (--teams-file) for local testing
  * optional extra sploit arguments (--sploit-arg, repeatable)
  * graceful SIGINT/SIGTERM: children are killed, remaining flags get a
    best-effort final submit
  * --once for a single attack round, --force to skip sploit lint
"""

import argparse
import binascii
import collections
import itertools
import json
import logging
import math
import os
import random
import re
import signal
import stat
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests

SCRIPT_EXTS = {".py": "python3", ".pl": "perl", ".rb": "ruby"}
DEFAULT_FLAG_RX = r"[A-Z0-9]{31}="
POST_PERIOD = 5.0
POST_BATCH = 5000
SERVER_TIMEOUT = 5
TEAMS_PRINTED = 5

BANNER = r"""
    __         __  ___  ___
   / /  ___ _ / / / _ \/ __/
  / _ \/ _ `// _ \/ // /\ \
 /_//_/\_,_/_.__/____/___/
   attack/defense farm client
""".strip("\n")

log = logging.getLogger("farm")


def setup_logging():
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(format=fmt, datefmt="%H:%M:%S", level=logging.INFO)


def hl(text):
    if os.name == "nt":
        return text
    color = random.choice(["31", "32", "34", "35", "36"])
    return f"\033[1;{color}m{text}\033[0m"


# ---------------------------------------------------------------------------
# Flags: thread-safe dedup store + submit queue + per-team stats
# ---------------------------------------------------------------------------
class FlagPool:
    def __init__(self):
        self._seen = set()
        self._queue = []
        self._lock = threading.RLock()
        self.by_team = collections.Counter()

    def add(self, flags, team):
        fresh = []
        with self._lock:
            for flag in flags:
                if flag not in self._seen:
                    self._seen.add(flag)
                    self._queue.append({"flag": flag, "team": team})
                    fresh.append(flag)
            self.by_team[team] += len(fresh)
        return fresh

    def take(self, n):
        with self._lock:
            return self._queue[:n]

    def confirm(self, n):
        with self._lock:
            del self._queue[:n]

    @property
    def pending(self):
        with self._lock:
            return len(self._queue)

    @property
    def unique(self):
        with self._lock:
            return len(self._seen)


pool = FlagPool()
stop = threading.Event()
procs = {}
procs_lock = threading.RLock()


# ---------------------------------------------------------------------------
# Farm API
# ---------------------------------------------------------------------------
class FarmAPI:
    def __init__(self, url, password):
        self.base = url if "://" in url else "http://" + url
        self.headers = {"Authorization": password} if password else {}

    def get_config(self):
        url = urljoin(self.base, "/api/get_config")
        r = requests.get(url, headers=self.headers, timeout=SERVER_TIMEOUT)
        r.raise_for_status()
        return r.json()

    def post_flags(self, sploit_name, items):
        payload = [
            {"flag": i["flag"], "sploit": sploit_name, "team": i["team"]}
            for i in items
        ]
        url = urljoin(self.base, "/api/post_flags")
        r = requests.post(url, headers=self.headers, json=payload, timeout=SERVER_TIMEOUT)
        r.raise_for_status()


def submit_once(api, sploit_name):
    items = pool.take(POST_BATCH)
    if not items:
        return False
    api.post_flags(sploit_name, items)
    pool.confirm(len(items))
    log.info("%d flag(s) submitted (%d left in queue)", len(items), pool.pending)
    return True


def submit_loop(api, sploit_name):
    while not stop.is_set():
        stop.wait(POST_PERIOD)
        if stop.is_set():
            break
        if not pool.pending:
            continue
        try:
            submit_once(api, sploit_name)
        except Exception as e:
            log.error("submit failed, flags stay queued: %r", e)
    # best-effort final drain on shutdown
    try:
        submit_once(api, sploit_name)
    except Exception as e:
        log.error("final submit failed, %d flag(s) lost: %r", pool.pending, e)


# ---------------------------------------------------------------------------
# Sploit checks
# ---------------------------------------------------------------------------
def validate_sploit(path, force=False):
    if not os.path.isfile(path):
        raise SystemExit(f"No such sploit file: {path}")

    ext = os.path.splitext(path)[1].lower()
    is_script = ext in SCRIPT_EXTS

    if is_script:
        with open(path, encoding="utf-8", errors="ignore") as f:
            src = f.read()
        problems = []
        if os.name != "nt" and not src.startswith("#!"):
            problems.append("no shebang line (start the file with #!/usr/bin/env python3)")
        if not re.search(r"flush[(=]", src):
            problems.append('no print(..., flush=True) found: flags may be lost or delayed')
        if problems and not force:
            for p in problems:
                log.error("sploit check: %s", p)
            raise SystemExit("fix the sploit or pass --force")

    if os.name != "nt" and not os.stat(path).st_mode & stat.S_IXUSR:
        if is_script:
            log.info("setting executable bit on %s", path)
            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        else:
            raise SystemExit("sploit is not executable")


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
def resolve_teams(args, config):
    if args.teams_file:
        with open(args.teams_file, encoding="utf-8") as f:
            teams = json.load(f)
    else:
        teams = (config or {}).get("TEAMS") or {}

    if args.not_per_team:
        teams = {"*": "*"}

    if args.distribute:
        k, n = args.distribute
        teams = {
            name: addr
            for name, addr in teams.items()
            if binascii.crc32(addr.encode()) % n == k - 1
        }

    return teams


def log_teams(teams, verbose_attacks, attack_no):
    if not teams:
        log.error("no teams to attack: check TEAMS in the server config, "
                  "--teams-file or --distribute")
        return
    if attack_no <= verbose_attacks:
        names = sorted(teams)
        if len(names) > TEAMS_PRINTED:
            names = names[:TEAMS_PRINTED] + ["..."]
        log.info("attacking %d team(s): %s", len(teams), ", ".join(names))


# ---------------------------------------------------------------------------
# Sploit lifecycle
# ---------------------------------------------------------------------------
def pump_output(stream, team, flag_rx, verbose_attacks, attack_no):
    lines = []
    got = set()
    try:
        for raw in iter(stream.readline, b""):
            line = raw.decode(errors="replace")
            lines.append(line)
            found = set(flag_rx.findall(line))
            if found:
                got |= found
                pool.add(found, team)
    except Exception as e:
        log.error("output processing failed for %s: %r", team, e)
    finally:
        if attack_no <= verbose_attacks and not stop.is_set():
            if lines:
                prefix = hl(team + ": ")
                print("\n" + "\n".join(prefix + l.rstrip() for l in lines) + "\n")
            else:
                log.info("%s: no output", team)
            if got:
                log.info("%s: %d flag(s) captured", team, len(got))


def run_one(args, team, ip, flag_rx, attack_no, max_runtime):
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    cmd = [os.path.abspath(args.sploit)]
    if args.interpreter:
        cmd = [args.interpreter] + cmd
    if not args.not_per_team:
        cmd.append(ip)
    cmd.extend(args.sploit_args)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env)
    with procs_lock:
        procs[id(proc)] = proc

    reader = threading.Thread(target=pump_output,
                              args=(proc.stdout, team, flag_rx,
                                    args.verbose_attacks, attack_no),
                              daemon=True)
    reader.start()

    killed = False
    try:
        proc.wait(timeout=max_runtime)
    except subprocess.TimeoutExpired:
        proc.kill()
        killed = True
    reader.join(timeout=2)

    with procs_lock:
        procs.pop(id(proc), None)
    return killed


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def pacing(period):
    """Yield round numbers, pacing the loop so a round takes ~period seconds."""
    for n in itertools.count(1):
        started = time.time()
        yield n
        left = period - (time.time() - started)
        if left > 0:
            stop.wait(left)
        if stop.is_set():
            break


def main():
    args = parse_args()
    setup_logging()

    validate_sploit(args.sploit, force=args.force)
    api = FarmAPI(args.server_url, args.server_pass)
    sploit_name = os.path.basename(args.sploit)

    submit_thread = threading.Thread(target=submit_loop, args=(api, sploit_name), daemon=True)
    submit_thread.start()

    if args.endless:
        log.warning("--endless: sploits are never restarted or killed on timeout")

    if not args.server_url:
        log.info("no --server-url: running locally against --teams-file only")

    flag_rx = re.compile(args.flag_format)
    executor = ThreadPoolExecutor(max_workers=args.pool_size)

    def on_signal(signum, frame):
        log.info("signal %s received, shutting down", signum)
        stop.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    for attack_no in pacing(args.attack_period):
        config = None
        if args.server_url:
            try:
                config = api.get_config()
                if config.get("FLAG_FORMAT"):
                    flag_rx = re.compile(config["FLAG_FORMAT"])
            except Exception as e:
                log.error("can't fetch config: %r", e)
                if attack_no == 1:
                    raise SystemExit(1)
                log.info("reusing previous config/teams")

        teams = resolve_teams(args, config)
        log_teams(teams, args.verbose_attacks, attack_no)
        if not teams:
            if attack_no == 1:
                raise SystemExit(1)
            continue

        max_runtime = None
        if not args.endless:
            waves = max(1, math.ceil(len(teams) / args.pool_size))
            max_runtime = args.attack_period / waves

        log.info("attack #%d: %d team(s), time limit %.1fs",
                 attack_no, len(teams), max_runtime or -1)

        futures = [
            executor.submit(run_one, args, team, ip, flag_rx, attack_no, max_runtime)
            for team, ip in teams.items()
        ]
        if args.once:
            for f in futures:
                f.result()
            break

        log.info("round %d done: %d unique flag(s) so far, %d queued",
                 attack_no, pool.unique, pool.pending)

    stop.set()
    executor.shutdown(wait=True)
    submit_thread.join(timeout=POST_PERIOD + SERVER_TIMEOUT + 2)
    submit_thread.join(timeout=POST_PERIOD + SERVER_TIMEOUT)
    if pool.pending:
        log.warning("%d flag(s) never made it to the farm", pool.pending)


def parse_args():
    p = argparse.ArgumentParser(
        description="Run a sploit against all teams in a loop and submit flags to the farm",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("sploit", help="sploit executable; receives the victim IP as argv[1]")
    p.add_argument("--server-url", metavar="URL", default=os.environ.get("FARM_SERVER", ""),
                   help="farm URL (or FARM_SERVER env); empty = local run")
    p.add_argument("--server-pass", metavar="TOKEN", default=os.environ.get("FARM_PASSWORD", ""),
                   help="farm token (or FARM_PASSWORD env)")
    p.add_argument("--interpreter", metavar="CMD",
                   help="force an interpreter for the sploit (mainly for Windows)")
    p.add_argument("--pool-size", metavar="N", type=int, default=50,
                   help="max concurrent sploit instances")
    p.add_argument("--attack-period", metavar="SEC", type=float, default=55,
                   help="seconds between attack rounds")
    p.add_argument("--verbose-attacks", metavar="N", type=int, default=1,
                   help="show full sploit output for the first N rounds")
    p.add_argument("--endless", action="store_true",
                   help="never time out or restart sploit instances")
    p.add_argument("--once", action="store_true", help="run a single round and exit")
    p.add_argument("--force", action="store_true",
                   help="skip sploit lint failures (shebang/flush)")
    p.add_argument("--not-per-team", action="store_true",
                   help="run one sploit instance instead of one per team")
    p.add_argument("--distribute", metavar="K/N",
                   help="attack only the Kth of N shards (crc32(ip) mod N)")
    p.add_argument("--teams-file", metavar="JSON",
                   help='teams file {"name": "ip", ...}; overrides the server TEAMS')
    p.add_argument("--flag-format", metavar="RX", default=DEFAULT_FLAG_RX,
                   help="fallback flag regex if the server config has none")
    p.add_argument("--sploit-arg", metavar="ARG", dest="sploit_args",
                   action="append", default=[],
                   help="extra argument passed to every sploit invocation (repeatable)")
    args = p.parse_args()

    if args.distribute:
        m = re.fullmatch(r"(\d+)/(\d+)", args.distribute)
        if not m:
            raise SystemExit("--distribute expects K/N with N >= 2")
        k, n = int(m.group(1)), int(m.group(2))
        if n < 2 or not 1 <= k <= n:
            raise SystemExit("--distribute expects N >= 2 and 1 <= K <= N")
        args.distribute = (k, n)

    return args


if __name__ == "__main__":
    main()
