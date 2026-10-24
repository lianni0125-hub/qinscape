#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [ ! -x .venv/bin/python ]; then
  echo "基础环境尚未准备，请先运行 bash deploy/bootstrap.sh" >&2
  exit 2
fi
if [ -f .env ]; then set -a; source .env; set +a; fi
exec .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "${QINSCAPE_PORT:-6006}" --workers 1
