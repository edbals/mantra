#!/usr/bin/env bash
# Mantra daily refresh — pulls fresh IDX market data, then re-runs the screener.
#
# Two stages:
#   1. cd $IDX_API_DIR && deno run -A sync_for_mantra.ts   (free IDX feed)
#   2. cd $MANTRA_DIR  && python3 main.py --incremental    (scoring + cache write)
#
# Schedule on a Linux VPS via cron (Asia/Jakarta is UTC+7; IDX closes ~16:00 WIB):
#   30 10 * * 1-5  /opt/mantra/scripts/daily_refresh.sh >> /var/log/mantra-refresh.log 2>&1
#   #              ^ 10:30 UTC = 17:30 WIB, ~90 min after close
#
# Or systemd: see scripts/mantra-refresh.{service,timer}.
#
# Env overrides:
#   MANTRA_DIR       repo root (default: script's parent dir)
#   IDX_API_DIR      IDX-API checkout (default: $MANTRA_DIR/../IDX-API)
#   PYTHON_BIN       python interpreter (default: python3)
#   DENO_BIN         deno interpreter   (default: deno)
#   SKIP_SYNC=1      run scoring only
#   SKIP_SCORE=1     run sync only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANTRA_DIR="${MANTRA_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
IDX_API_DIR="${IDX_API_DIR:-$(cd "$MANTRA_DIR/.." && pwd)/IDX-API}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DENO_BIN="${DENO_BIN:-deno}"

LOCK_FILE="${MANTRA_DIR}/output/.refresh.lock"
mkdir -p "$(dirname "$LOCK_FILE")"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }

# Single-instance guard — exit cleanly if a previous run is still going.
# flock is Linux-standard (util-linux); on macOS it isn't installed, so we
# skip the guard rather than failing — local manual runs don't need it.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    log "Another refresh is already running (lock $LOCK_FILE held). Exiting."
    exit 0
  fi
else
  log "flock not available (likely macOS) — skipping single-instance guard."
fi

log "=== Mantra daily refresh starting ==="
log "MANTRA_DIR=$MANTRA_DIR"
log "IDX_API_DIR=$IDX_API_DIR"

if [[ ! -d "$IDX_API_DIR" ]]; then
  log "ERROR: IDX_API_DIR not found at $IDX_API_DIR"
  log "Set IDX_API_DIR env var or clone https://github.com/NeaByteLab/IDX-API alongside mantra/."
  exit 1
fi

if [[ "${SKIP_SYNC:-0}" != "1" ]]; then
  log "Step 1/2: pulling fresh IDX data via $DENO_BIN sync_for_mantra.ts"
  ( cd "$IDX_API_DIR" && "$DENO_BIN" run -A sync_for_mantra.ts )
  log "Step 1/2 complete."
else
  log "Step 1/2 skipped (SKIP_SYNC=1)."
fi

if [[ "${SKIP_SCORE:-0}" != "1" ]]; then
  log "Step 2/2: running screener via $PYTHON_BIN main.py --incremental"
  ( cd "$MANTRA_DIR" && "$PYTHON_BIN" main.py --incremental )
  log "Step 2/2 complete."
else
  log "Step 2/2 skipped (SKIP_SCORE=1)."
fi

log "=== Mantra daily refresh finished ==="
