#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_url="${HAILA_API_URL:-http://127.0.0.1:8000}"
front_port="${HAILA_FRONT_PORT:-4173}"

cd "$project_dir"
exec python3 server.py --backend "$backend_url" --port "$front_port"
