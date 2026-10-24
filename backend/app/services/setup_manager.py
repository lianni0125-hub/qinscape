from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .. import config
from .capabilities import detect

STATE_FILE = config.RUNTIME / "setup-state.json"
STAGING = config.RUNTIME / "setup-staging"
ASSETS = config.ROOT / "assets"
LOCK = threading.Lock()

COMPONENTS = {
    "text2midi": {"name": "音乐生成引擎", "size": "约 1.4 GB", "required": True},
    "soundfont": {"name": "多乐器合奏音源", "size": "约 220 MB", "required": True},
    "llm": {"name": "琴境文本模型", "size": "约 3.5 GB", "required": True},
    "soulx": {"name": "歌声生成引擎", "size": "约 8 GB", "required": False},
    "preset_voices": {"name": "琴境预设人声", "size": "约 3 MB", "required": False},
}


def _base_state() -> dict:
    return {
        "active": None,
        "components": {
            key: {**meta, "status": "pending", "progress": 0, "message": "等待检查", "error": None}
            for key, meta in COMPONENTS.items()
        },
        "updated_at": time.time(),
    }


def _read_state() -> dict:
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        base = _base_state()
        base.update({k: v for k, v in value.items() if k != "components"})
        for key in COMPONENTS:
            base["components"][key].update(value.get("components", {}).get(key, {}))
        return base
    except (OSError, json.JSONDecodeError):
        return _base_state()


def _write_state(value: dict) -> None:
    config.RUNTIME.mkdir(parents=True, exist_ok=True)
    value["updated_at"] = time.time()
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _installed() -> dict[str, bool]:
    caps = detect()
    preset_count = sum(1 for item in config.VOICE_LIBRARY.glob("*/voice.json") if '"source_kind": "preset"' in item.read_text(encoding="utf-8", errors="ignore"))
    soulx_python = config.ROOT / ".venv-soulx" / "bin" / "python"
    return {
        "text2midi": bool(caps["models"]["text2midi_code"] and caps["models"]["text2midi_cached"] and caps["models"]["flan_tokenizer_cached"]),
        "soundfont": bool(caps["renderers"]["fluidsynth"] and caps["assets"]["ensemble_soundfont"]),
        "llm": bool(caps["models"]["llm_cached"]),
        "soulx": bool((config.MODELS / "SoulX-Singer" / "model.pt").is_file() and (config.TEXT2MIDI_REPO.parent / "SoulX-Singer").is_dir() and soulx_python.is_file()),
        "preset_voices": preset_count >= 4,
    }


def status() -> dict:
    with LOCK:
        state = _read_state()
        installed = _installed()
        if not state.get("active"):
            for key, ready in installed.items():
                if ready:
                    state["components"][key].update(status="ready", progress=100, message="已就绪", error=None)
                elif state["components"][key]["status"] == "ready":
                    state["components"][key].update(status="pending", progress=0, message="需要部署")
        required = [key for key, meta in COMPONENTS.items() if meta["required"]]
        state["ready"] = all(installed[key] for key in required)
        state["complete"] = all(installed.values())
        state["gpu"] = detect()["gpu"]
        state["disk"] = _disk_status()
        state["setup_enabled"] = os.getenv("QINSCAPE_SETUP_ENABLED", "1") == "1"
        return state


def _disk_status() -> dict:
    usage = shutil.disk_usage(config.ROOT)
    return {"free_gb": round(usage.free / 1024**3, 1), "required_gb": 24}


def _update(component: str, progress: int, message: str, *, status_name: str = "installing", error: str | None = None) -> None:
    with LOCK:
        state = _read_state()
        state["active"] = component if status_name == "installing" else None
        state["components"][component].update(status=status_name, progress=progress, message=message, error=error)
        _write_state(state)


def _run(command: list[str], component: str, message: str, env: dict | None = None) -> None:
    _update(component, 35, message)
    merged = os.environ.copy()
    if env:
        merged.update(env)
    process = subprocess.run(command, cwd=config.ROOT, env=merged, text=True, capture_output=True, timeout=3600)
    if process.returncode:
        detail = (process.stderr or process.stdout or "未知错误").strip()[-1800:]
        raise RuntimeError(detail)


def _clone_with_fallback(repo: str, target: Path, component: str, revision: str | None = None) -> None:
    if not target.exists():
        errors = []
        for url in (repo, f"https://ghfast.top/{repo}"):
            try:
                _run(["git", "clone", "--filter=blob:none", url, str(target)], component, "正在获取引擎代码")
                break
            except Exception as exc:
                errors.append(str(exc))
                shutil.rmtree(target, ignore_errors=True)
        else:
            raise RuntimeError("主下载源与备用源均不可用：" + " / ".join(errors))
    if revision:
        _run(["git", "-C", str(target), "checkout", revision], component, "正在固定兼容版本")


def _hf_file(repo_id: str, filename: str, component: str) -> None:
    from huggingface_hub import hf_hub_download
    errors = []
    for endpoint in ("https://huggingface.co", os.getenv("QINSCAPE_HF_MIRROR", "https://hf-mirror.com")):
        try:
            hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=config.HF_CACHE, endpoint=endpoint, local_files_only=False)
            return
        except Exception as exc: errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("模型主源与镜像均失败：" + " / ".join(errors))


def _hf_snapshot(repo_id: str, component: str, **options) -> None:
    from huggingface_hub import snapshot_download
    errors = []
    for endpoint in ("https://huggingface.co", os.getenv("QINSCAPE_HF_MIRROR", "https://hf-mirror.com")):
        try:
            snapshot_download(repo_id=repo_id, endpoint=endpoint, local_files_only=False, **options)
            return
        except Exception as exc: errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("模型主源与镜像均失败：" + " / ".join(errors))


def _install_text2midi() -> None:
    _clone_with_fallback("https://github.com/AMAAI-Lab/Text2midi.git", config.TEXT2MIDI_REPO, "text2midi", "f3245ee402b29ba00b86c6eb9813032f3f05954f")
    _update("text2midi", 50, "正在下载旋律模型")
    for filename in ("pytorch_model.bin", "vocab_remi.pkl"):
        _hf_file(config.TEXT2MIDI_MODEL, filename, "text2midi")
    _update("text2midi", 82, "正在准备文本分词器")
    _hf_snapshot("google/flan-t5-base", "text2midi", local_dir=config.FLAN_TOKENIZER, allow_patterns=("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "spiece.model", "config.json"))


def _download(urls: tuple[str, ...], target: Path, component: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    errors = []
    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "QinScape-Setup/1.0"})
            with urllib.request.urlopen(request, timeout=40) as response, partial.open("wb") as output:
                total = int(response.headers.get("Content-Length") or 0); received = 0
                while True:
                    block = response.read(1024 * 1024)
                    if not block: break
                    output.write(block); received += len(block)
                    if total: _update(component, min(92, 12 + int(received / total * 80)), f"正在下载 {target.name}")
            partial.replace(target)
            return
        except Exception as exc:
            errors.append(str(exc)); partial.unlink(missing_ok=True)
    raise RuntimeError("所有下载链路均失败：" + " / ".join(errors))


def _install_soundfont() -> None:
    target = ASSETS / "MuseScore_General.sf3"
    _download(("https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/MuseScore_General.sf3", "https://github.com/musescore/MuseScore_General/raw/main/MuseScore_General.sf3"), target, "soundfont")
    _download(("https://raw.githubusercontent.com/Tenglon/music/main/public/soundfont/MuseScore_General_LICENSE.md",), ASSETS / "MuseScore_General_LICENSE.md", "soundfont")


def _install_llm() -> None:
    _update("llm", 10, "正在连接模型源")
    _hf_snapshot(config.LLM_MODEL, "llm", cache_dir=config.HF_CACHE)


def _install_soulx() -> None:
    source = config.TEXT2MIDI_REPO.parent / "SoulX-Singer"
    _clone_with_fallback("https://github.com/Soul-AILab/SoulX-Singer.git", source, "soulx", "81aeb3ae772c70093c3de74dc23c92d983801ae4")
    venv = config.ROOT / ".venv-soulx"
    if not (venv / "bin" / "python").exists():
        _run(["python", "-m", "venv", str(venv)], "soulx", "正在创建独立歌声环境")
    _run([str(venv / "bin" / "pip"), "install", "-r", str(source / "requirements.txt")], "soulx", "正在安装歌声依赖")
    _update("soulx", 70, "正在下载歌声模型")
    _hf_snapshot("Soul-AILab/SoulX-Singer", "soulx", local_dir=config.MODELS / "SoulX-Singer")
    _hf_snapshot("Soul-AILab/SoulX-Singer-Preprocess", "soulx", local_dir=config.MODELS / "SoulX-Singer-Preprocess")


def _install_preset_voices() -> None:
    source = config.ROOT / "assets" / "preset-voices"
    if not source.is_dir():
        raise RuntimeError("仓库中缺少已授权的琴境预设人声包")
    for folder in source.iterdir():
        if folder.is_dir() and (folder / "voice.json").is_file():
            target = config.VOICE_LIBRARY / folder.name
            if not target.exists(): shutil.copytree(folder, target)


INSTALLERS = {"text2midi": _install_text2midi, "soundfont": _install_soundfont, "llm": _install_llm, "soulx": _install_soulx, "preset_voices": _install_preset_voices}


def _worker(items: list[str]) -> None:
    os.environ["HF_HUB_OFFLINE"] = "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "0"
    for component in items:
        try:
            if _installed()[component]:
                _update(component, 100, "已就绪", status_name="ready")
                continue
            if _disk_status()["free_gb"] < 4:
                raise RuntimeError("磁盘剩余空间不足 4 GB，请先释放空间")
            _update(component, 2, "正在准备")
            INSTALLERS[component]()
            _update(component, 100, "已就绪", status_name="ready")
        except Exception as exc:
            _update(component, 0, "部署没有完成", status_name="failed", error=str(exc))


def start(component: str | None = None) -> dict:
    if os.getenv("QINSCAPE_SETUP_ENABLED", "1") != "1":
        raise PermissionError("当前实例已禁止页面部署")
    with LOCK:
        state = _read_state()
        if state.get("active"):
            raise RuntimeError("另一项资源正在部署")
    items = [component] if component else list(COMPONENTS)
    if any(item not in INSTALLERS for item in items):
        raise KeyError(component)
    threading.Thread(target=_worker, args=(items,), daemon=True, name="qinscape-setup").start()
    return status()


def install_package(component: str, filename: str, package: Path) -> dict:
    if component not in COMPONENTS: raise KeyError(component)
    STAGING.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    supplied_suffix = Path(safe_name).suffix.lower()
    if component == "soundfont" and supplied_suffix in {".sf2", ".sf3"}:
        ASSETS.mkdir(parents=True, exist_ok=True)
        # Keep one canonical configured path; FluidSynth detects the actual
        # SoundFont format from its header rather than the filename suffix.
        target = ASSETS / "MuseScore_General.sf3"
        shutil.copy2(package, target)
    else:
        target = {"text2midi": config.MODELS, "llm": config.MODELS, "soulx": config.ROOT, "preset_voices": config.VOICE_LIBRARY}.get(component)
        if not target: raise ValueError("该资源不支持此格式")
        digest = hashlib.sha256()
        with package.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
        unpack = STAGING / digest.hexdigest()[:16]; shutil.rmtree(unpack, ignore_errors=True); unpack.mkdir()
        if zipfile.is_zipfile(package):
            with zipfile.ZipFile(package) as archive:
                if any(Path(name).is_absolute() or ".." in Path(name).parts for name in archive.namelist()): raise ValueError("安装包路径不安全")
                archive.extractall(unpack)
        elif tarfile.is_tarfile(package):
            with tarfile.open(package) as archive:
                if any(Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in archive.getmembers()): raise ValueError("安装包路径不安全")
                archive.extractall(unpack, filter="data")
        else: raise ValueError("请选择 ZIP、TAR.GZ、SF2 或 SF3 安装包")
        shutil.copytree(unpack, target, dirs_exist_ok=True)
    package.unlink(missing_ok=True)
    _update(component, 100, "安装包已导入，正在校验", status_name="ready" if _installed().get(component) else "pending")
    return status()
