#!/usr/bin/env bash
# patch_snapshot.sh — snapshot service dirs before patching, restore in seconds
# if the checker starts failing (MUMBLE after deploy => rollback, per playbook).
#
# Usage:
#   patch_snapshot.sh snapshot <path> [more paths...]
#   patch_snapshot.sh restore <snapshot.tar.gz>
#   patch_snapshot.sh list
#
# Snapshots go to ~/ad_snapshots/. Each archive carries a manifest with the
# original absolute path, docker container list and a timestamp, so restore
# puts files back where they were.
#
# After restoring, restart hooks (best effort, in order):
#   $RESTORE_CMD env var, docker compose restart, systemctl restart <name>

set -euo pipefail

SNAP_DIR="$HOME/ad_snapshots"
STAMP() { date +%Y%m%d_%H%M%S; }

require_dir() {
  [[ -d "$1" ]] || { echo "[!] no such dir: $1" >&2; exit 1; }
}

cmd=${1:-}; shift || true
case "$cmd" in
  snapshot)
    [[ $# -ge 1 ]] || { echo "usage: $0 snapshot <path> [more...]" >&2; exit 1; }
    mkdir -p "$SNAP_DIR"
    for path in "$@"; do
      require_dir "$path"
      path=$(realpath "$path")
      name=$(basename "$path")
      out="$SNAP_DIR/$(STAMP)_$name.tar.gz"
      tar -czf "$out" -C "$(dirname "$path")" "$name"
      {
        echo "orig_path=$path"
        echo "created=$(date -Iseconds)"
        echo "--- docker ps ---"
        docker ps 2>/dev/null || echo "(docker unavailable)"
      } > "${out%.tar.gz}.manifest"
      echo "[+] $out ($(du -h "$out" | cut -f1))"
    done
    ;;

  restore)
    [[ $# -eq 1 ]] || { echo "usage: $0 restore <snapshot.tar.gz>" >&2; exit 1; }
    archive="$1"
    [[ -f "$archive" ]] || { echo "[!] no such archive: $archive" >&2; exit 1; }
    manifest="${archive%.tar.gz}.manifest"
    if [[ -f "$manifest" ]]; then
      orig_path=$(grep '^orig_path=' "$manifest" | cut -d= -f2-)
    else
      read -rp "[?] original path to restore into: " orig_path
    fi
    require_dir "$(dirname "$orig_path")"
    parent=$(dirname "$orig_path")
    name=$(basename "$orig_path")
    echo "[*] restoring $name into $parent"
    tar -xzf "$archive" -C "$parent"
    echo "[+] files restored"
    # restart hooks, best effort
    if [[ -n "${RESTORE_CMD:-}" ]]; then
      echo "[*] running RESTORE_CMD: $RESTORE_CMD"
      (cd "$orig_path" && eval "$RESTORE_CMD") || true
    elif find "$orig_path" -maxdepth 1 -name 'docker-compose.y*ml' -o -maxdepth 1 -name 'compose.y*ml' | grep -q .; then
      echo "[*] docker compose restart in $orig_path"
      (cd "$orig_path" && docker compose restart) || true
    fi
    echo "[+] done — watch the board for status recovery"
    ;;

  list)
    ls -lht "$SNAP_DIR" 2>/dev/null || echo "(no snapshots yet)"
    ;;

  *)
    grep '^#' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
