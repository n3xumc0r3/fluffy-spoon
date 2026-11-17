#!/usr/bin/env bash
# deploy.sh — git pull + redeploy services on the vulnbox (playbook pipeline:
# edit locally -> push -> git pull here -> redeploy with one command).
#
# Usage:
#   deploy.sh [--dir ~/infra] [--dry-run] [service1 service2 ...]
#
# Per-service deploy order (first match wins):
#   1. <service>/deploy.sh                 — your own script
#   2. docker compose up -d --build        — compose file present
#   3. nothing (warn)
#
# Only fast-forward pulls are allowed: keep master clean per the playbook.

set -euo pipefail

DIR="$HOME/infra"
DRY_RUN=0
SERVICES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) SERVICES+=("$1"); shift ;;
  esac
done

if [[ ! -d "$DIR/.git" ]]; then
  echo "[!] not a git repo: $DIR (pass --dir /path/to/infra)" >&2
  exit 1
fi

echo "[*] git -C $DIR pull --ff-only"
if [[ $DRY_RUN -eq 0 ]]; then
  if ! git -C "$DIR" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
    echo "[?] no upstream configured, skipping pull"
  elif ! git -C "$DIR" pull --ff-only; then
    echo "[!] non-fast-forward: resolve locally, keep master clean" >&2
    exit 1
  fi
fi

# Collect service dirs: given as args, or every dir that looks deployable.
if [[ ${#SERVICES[@]} -gt 0 ]]; then
  targets=()
  for s in "${SERVICES[@]}"; do targets+=("$DIR/$s"); done
else
  targets=()
  while IFS= read -r d; do targets+=("$d"); done < <(
    find "$DIR" -maxdepth 2 \( -name deploy.sh -o -name 'docker-compose.y*ml' -o -name 'compose.y*ml' \) \
      -not -path '*/.git/*' -exec dirname {} \; | sort -u
  )
fi

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "[!] no deployable services found in $DIR" >&2
  exit 1
fi

fail=0
for svc in "${targets[@]}"; do
  name=$(basename "$svc")
  echo
  echo "=== $name ==="
  if [[ -x "$svc/deploy.sh" ]]; then
    echo "[*] $svc/deploy.sh"
    if [[ $DRY_RUN -eq 0 ]]; then
      (cd "$svc" && ./deploy.sh) || fail=1
    fi
  elif compgen -G "$svc/docker-compose.y*ml" >/dev/null || compgen -G "$svc/compose.y*ml" >/dev/null; then
    echo "[*] docker compose up -d --build in $svc"
    if [[ $DRY_RUN -eq 0 ]]; then
      (cd "$svc" && docker compose up -d --build) || fail=1
    fi
  else
    echo "[?] no deploy.sh / compose file in $svc, skipping"
  fi
done

echo
[[ $fail -eq 0 ]] && echo "[+] deploy done — watch the board status for 1-2 ticks" \
                   || echo "[-] some services failed, check output above"
exit $fail
