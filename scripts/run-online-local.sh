#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -e ".[server,online]"

if [[ -f ".env.local" ]]; then
  set -a
  source .env.local
  set +a
fi

exec cryptclash server --host 0.0.0.0 --port "${CRYPTCLASH_PORT:-8000}"
