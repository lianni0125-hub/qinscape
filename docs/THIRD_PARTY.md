# 第三方组件与边界

| 组件 | 固定版本 | 用途 | 代码许可 | 资产边界 |
|---|---|---|---|---|
| AMAAI-Lab/Text2midi | `f3245ee` | 文本到符号 MIDI | MIT | Hugging Face 权重按其模型卡核验 |
| OpenVPI/DiffSinger | `76b75de` | 中文歌声合成框架 | Apache-2.0 | 声库与声线模型另行授权 |
| Qwen3-1.7B | 配置项 | 中文理解、歌词与结构化规划 | Apache-2.0 | 权重不提交仓库 |
| FluidSynth | 系统包 | MIDI + SF2 渲染 WAV | LGPL | SoundFont 单独授权 |
| Guqin-Dataset | `e7feb0c` | 古琴结构 Skill 研究 | 未发现许可证 | 原谱不随琴境发布 |

任何没有明确许可的民族乐器采样、游戏音频或歌手声库都不进入发布包。

## 默认乐器音源

| 资产 | 覆盖 | 许可 | 安装策略 |
|---|---|---|---|
| MuseScore General SF3 | GM 管弦、弦乐、吹管、弹拨、合唱音色 | MIT | AutoDL 安装器自动下载并保留许可通知 |
| VSCO 2 CE | 交响乐采样 | CC0 | 可选；为 SFZ/采样库，不由当前 FluidSynth 路径默认安装 |

MuseScore General 使一个合法的默认音源能覆盖琴境的五类编制。GM 中的 Shakuhachi、Fiddle、Shamisen 等只是近似路由，不会在产品文案中被宣称为真实箫、二胡或三弦采样。

## 人声引擎与声库

DiffSinger/OpenUTAU 的引擎许可不会自动授予任何歌手声库的权利。琴境只把已安装并通过 `QINSCAPE_VOCAL_VOICES` 显式注册的声库暴露给用户。已调查的 Asaritsu、Ria、棋璇和 Alemon 均有非商业或自定义条款，因此只进入 API 的“可选候选”清单，不会自动下载、打包或默认启用。开放在线服务前，必须逐个确认声库对网络服务、商业用途、角色名称和输出归属的条款。
