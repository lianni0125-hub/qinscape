# AutoDL 部署

## 建议硬件

- 最低建议：NVIDIA GPU 16 GB 显存，用于 Text2MIDI + Qwen3-1.7B。
- 更稳妥：24 GB 显存、30 GB 以上系统盘、50 GB 以上数据盘。
- 服务端口固定为 `6006`，通过 AutoDL 自定义服务映射访问。

## 原生 AutoDL 安装（推荐）

把整个 `qinscape` 目录上传或克隆到 AutoDL 数据盘，然后运行：

```bash
cd /root/autodl-tmp/qinscape-project
bash deploy/autodl_setup.sh
```

脚本会检查 GPU、安装音频与编译依赖、固定第三方提交、创建复用系统 CUDA PyTorch 的虚拟环境、构建网页，并把 Text2MIDI、Flan-T5 与 Qwen 下载到持久化模型目录。

首次完成后编辑 `.env`，至少核对：

```bash
SOUNDFONT_ENSEMBLE=/root/autodl-tmp/qinscape/assets/ensemble.sf2
```

然后启动：

```bash
bash deploy/start_autodl.sh
```

浏览器打开 AutoDL 提供的 6006 自定义服务地址。`GET /api/capabilities` 应显示 `gpu.available=true`、音源为 `true`，模型预下载后 `*_cached=true`。

## GPU 端到端验收

服务启动后另开终端执行：

```bash
.venv/bin/python deploy/gpu_smoke.py --arrangement ensemble --lyrics
```

脚本会走过规划、生成前检查、串行队列、Text2MIDI、Skill 全曲/局部塑形、编配、FluidSynth 渲染，以及可选的歌词和歌唱 MIDI，并实际下载检查结果文件。只有出现 `PASS` 才算该 GPU 环境验收完成。

## 人声

DiffSinger 代码为 Apache-2.0，但声库各自授权。为合法声库配置 `QINSCAPE_DIFFSINGER_RUNNER`，完成实测后再把对应 ID 加入 `QINSCAPE_VOCAL_VOICES`。未注册声线不会通过预检；没有声库时可选择“仅生成歌词与歌唱旋律”。

## Docker（可选）

仅在实例允许使用 Docker daemon 时采用：

```bash
docker build -t qinscape .
docker run --rm --env-file .env \
  -v /root/autodl-tmp/qinscape:/root/autodl-tmp/qinscape \
  qinscape python deploy/download_models.py
docker run --rm --gpus all --env-file .env -p 6006:6006 \
  -v /root/autodl-tmp/qinscape:/root/autodl-tmp/qinscape qinscape
```
