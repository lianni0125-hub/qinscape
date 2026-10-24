<p align="center">
  <img src="docs/assets/qinscape-logo.svg" width="108" alt="琴境标志">
</p>

<h1 align="center">琴境</h1>
<p align="center"><strong>QINSCAPE</strong></p>
<p align="center">以五音为径，将心绪与意象安放于一段声音。</p>

---

琴境是一个面向古风音乐创作与东方调心体验的本地生成平台。用户可以从「写意」或「调心」进入，经由有边界的对话引导形成琴心卡，再将自然语言转译为五音路径、全曲结构、局部动机、多乐器编配，以及可选的歌词与人声。

> 琴境提供文化创作与自我觉察体验，不用于诊断、治疗，也不承诺医疗效果。

## 核心体验

- **写意**：从景象、时令、空间与情绪质地出发，让意象成为音乐结构。
- **调心**：参考《黄帝内经》五音思想，以承接、疏导、制衡与涵养组织声音，不机械地复刻负面情绪。
- **对话式澄清**：初始叙述后至少进行一次有效追问；琴心卡随新信息判断性更新。
- **灵活编配**：可指定想听或不想听的乐器，由主音、主奏、回应、铺底与点染共同构成合奏。
- **独立人声维度**：器乐谱面仍由五音路径主导；歌词、歌唱旋律与人声合成在其后适配，不反向破坏核心曲式。
- **作品与声线管理**：支持试听、歌词查看、标题修改、下载、删除，以及用户授权声音的上传与录制。

## 从文本到声音

```text
用户叙述
  → 写意 / 调心规划
  → 琴心卡与追问
  → 五音路径 + 古曲结构 Skill
  → Text2MIDI 符号旋律
  → 全曲弧线、局部动机与多乐器编配
  → SoundFont / FluidSynth 器乐渲染
  →（可选）歌词、歌唱旋律、人声合成与混音
  → 可试听、可管理的作品
```

古曲结构知识层来自对古琴数据的特征分析，覆盖全曲组织与局部句法。它提供结构约束与创作倾向，不复制原曲，也不把通用 MIDI 音色冒充为真实民族乐器采样。

## 运行要求

### 完整生成

- Linux（推荐 Ubuntu 22.04）
- NVIDIA GPU，CUDA 可用
- **推荐 24 GB 显存**（RTX 3090 / 4090 或同级）
- 16 GB 显存可尝试精简配置，但人声模型与模型切换余量较小
- 建议 32 GB 以上内存、50 GB 以上可用磁盘
- Python 3.10+、Node.js 20+、FFmpeg、FluidSynth

琴境以串行推理为主，不要求所有模型同时驻留显存。CPU 环境可以浏览页面、完成对话与规划，但完整音乐及人声生成需要 CUDA；前端会在生成前检查资源与 GPU 状态。

## 安装

```bash
git clone https://github.com/lianni0125-hub/qinscape.git
cd qinscape
bash deploy/bootstrap.sh
bash deploy/start.sh
```

服务默认监听：

```text
http://0.0.0.0:6006
```

首次打开页面时，「创作资源」会展示模型、音源与人声组件的初始化进度。缺失资源可以在页面内点击部署；失败会保留错误信息并允许重试，不需要用户手工寻找下载命令。

### 自动启动

直接启动入口：

```bash
bash deploy/start_autodl.sh
```

长期运行可参考 [`deploy/qinscape.service.example`](deploy/qinscape.service.example) 配置 systemd。环境变量模板见 [`.env.example`](.env.example)。

## 本地开发与验证

```bash
npm ci
npm ci --prefix web
npm run build

python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest backend/tests -q
```

Windows 激活虚拟环境时使用：

```powershell
.venv\Scripts\Activate.ps1
```

## 模型、音源与第三方组件

仓库不提交大型模型权重、运行输出、用户声音或授权不清晰的采样库。初始化器按配置下载或检查运行资源；各组件仍适用其自身许可证。

- Text2MIDI：文本到符号 MIDI
- Qwen：中文语义理解、追问与歌词辅助
- FluidSynth：SoundFont 器乐渲染
- SoulX-Singer / DiffSinger 接口：可选人声执行路径
- MuseScore General：默认通用音色覆盖；部分民族乐器为 GM 近似音色

详细边界见 [`docs/THIRD_PARTY.md`](docs/THIRD_PARTY.md)、[`THIRD_PARTY_VOICES.md`](THIRD_PARTY_VOICES.md) 与 [`NOTICE.md`](NOTICE.md)。任何用户上传声音都应获得声音本人明确同意，不得用于冒充、欺骗或侵害他人权益。

## 许可

琴境采用专有的源码可见许可。允许个人查看及运行未经修改的版本；**不允许商业使用、修改、改编、二次开发、重新分发或换牌发布**。具体以 [`LICENSE`](LICENSE) 为准。

本项目不是 OSI 定义下的开源软件。第三方依赖、模型、音源、数据与用户内容不因本许可证获得额外授权。

Copyright © 2026 lianni0125. All Rights Reserved.
