#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
  apt-get update
  apt-get install -y --no-install-recommends git curl ca-certificates ffmpeg fluidsynth build-essential libsndfile1-dev python3-venv
fi

if [ ! -x .venv/bin/python ]; then python3 -m venv --system-site-packages .venv; fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt

if command -v npm >/dev/null 2>&1; then
  npm ci
  npm ci --prefix web
  npm run build
elif [ ! -f web/dist/index.html ]; then
  echo "缺少 Node.js/npm，且仓库中没有可用的网页构建。" >&2
  exit 3
fi

if [ ! -f .env ]; then cp .env.example .env; fi
echo "琴境基础环境已就绪。"
echo "启动：bash deploy/start.sh"
echo "打开网页后，琴境会引导你点击部署模型、音源与人声资源。"
