FROM node:22-bookworm-slim AS web
WORKDIR /src
COPY web/package*.json ./web/
RUN npm ci --prefix web
COPY web ./web
RUN npm --prefix web run build

FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ffmpeg fluidsynth curl ca-certificates build-essential libsndfile1-dev && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
RUN git clone https://github.com/AMAAI-Lab/Text2midi.git sources/Text2midi && git -C sources/Text2midi checkout f3245ee402b29ba00b86c6eb9813032f3f05954f \
 && git clone https://github.com/openvpi/DiffSinger.git sources/DiffSinger && git -C sources/DiffSinger checkout 76b75dec8a5233afa47ef0e1377d25a080af3289
RUN pip install -r sources/DiffSinger/requirements.txt
COPY backend ./backend
COPY skill ./skill
COPY data ./data
COPY deploy ./deploy
COPY --from=web /src/web/dist ./web/dist
EXPOSE 6006
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://127.0.0.1:6006/api/health || exit 1
CMD ["bash","deploy/start.sh"]
