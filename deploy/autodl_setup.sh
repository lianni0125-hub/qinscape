#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PERSIST_DIR="${QINSCAPE_HOME:-/root/autodl-tmp/qinscape}"
cd "$PROJECT_DIR"

mkdir -p "$PERSIST_DIR/models" "$PERSIST_DIR/assets" "$PERSIST_DIR/runtime" "$PERSIST_DIR/outputs" sources
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "未检测到 NVIDIA 驱动。请确认 AutoDL 实例已选择 GPU。"; exit 2
fi
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
  apt-get update
  apt-get install -y --no-install-recommends git curl ca-certificates ffmpeg fluidsynth build-essential libsndfile1-dev python3-venv
fi

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" -lt 22 ]; then
  if [ "$(id -u)" != "0" ]; then echo "需要 Node.js 22+ 构建网页，请先安装后重试。"; exit 3; fi
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

if [ ! -d sources/Text2midi/.git ]; then git clone https://github.com/AMAAI-Lab/Text2midi.git sources/Text2midi; fi
git -C sources/Text2midi fetch --all --tags
git -C sources/Text2midi checkout f3245ee402b29ba00b86c6eb9813032f3f05954f
if [ ! -d sources/DiffSinger/.git ]; then git clone https://github.com/openvpi/DiffSinger.git sources/DiffSinger; fi
git -C sources/DiffSinger fetch --all --tags
git -C sources/DiffSinger checkout 76b75dec8a5233afa47ef0e1377d25a080af3289

python -m venv --system-site-packages .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/pip install -r sources/DiffSinger/requirements.txt

npm ci
npm ci --prefix web
npm run build

if [ ! -f .env ]; then cp .env.example .env; fi
set -a; source .env; set +a
QINSCAPE_ASSETS="$PERSIST_DIR/assets" .venv/bin/python deploy/download_open_assets.py
if [ "${QINSCAPE_DOWNLOAD_MODELS:-1}" = "1" ]; then .venv/bin/python deploy/download_models.py; fi

echo "琴境依赖与模型已准备。"
echo "请把许可清晰的多乐器 SoundFont 放入 $PERSIST_DIR/assets，并核对 .env。"
echo "启动命令：bash deploy/start_autodl.sh"
