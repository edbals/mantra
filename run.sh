#!/usr/bin/env bash
# Usage:
#   ./run.sh              — score today (incremental)
#   ./run.sh --date 20260501
#   ./run.sh dashboard    — launch Streamlit
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  dashboard)
    exec python3 -m streamlit run app/dashboard.py --server.port 8501
    ;;
  *)
    exec python3 main.py --incremental "$@"
    ;;
esac
