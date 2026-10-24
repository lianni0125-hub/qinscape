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

REPO = os.getenv("QINSCAPE_UPDATE_REPO", "lianni0125-hub/qinscape")
CHANNEL = os.getenv("QINSCAPE_UPDATE_CHANNEL", "main")
STATE_FILE = config.RUNTIME / "update-state.json"
STAGING = config.RUNTIME / "updates"
CHECK_INTERVAL = max(300, int(os.getenv("QINSCAPE_UPDATE_INTERVAL", "1800")))
LOCK = threading.Lock()
MANAGED = ("backend", "web/dist", "deploy", "scripts", "skill", "docs", "README.md", "NOTICE.md", "THIRD_PARTY_VOICES.md", "LICENSE", ".env.example", "package.json", "package-lock.json", "version.json")


def _version_tuple(value: str) -> tuple[int, ...]:
    clean = value.strip().lower().lstrip("v").split("+", 1)[0].split("-", 1)[0]
    try: return tuple(int(part) for part in clean.split("."))
    except ValueError: return (0,)


def current_version() -> str:
    try: return str(json.loads((config.ROOT / "version.json").read_text(encoding="utf-8"))["version"])
    except (OSError, KeyError, json.JSONDecodeError): return "0.0.0"


def _default_state() -> dict:
    return {"current_version": current_version(), "available": False, "latest_version": None, "notes": [], "status": "idle", "progress": 0, "message": "已是最新版本", "error": None, "checked_at": None, "manifest": None}


def _read() -> dict:
    try:return {**_default_state(), **json.loads(STATE_FILE.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):return _default_state()


def _write(state: dict) -> None:
    config.RUNTIME.mkdir(parents=True, exist_ok=True);state["current_version"] = current_version()
    temporary = STATE_FILE.with_suffix(".tmp");temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8");temporary.replace(STATE_FILE)


def _manifest_urls() -> list[str]:
    path = f"https://raw.githubusercontent.com/{REPO}/{CHANNEL}/update.json"
    return [path, f"https://ghfast.top/{path}", f"https://cdn.jsdelivr.net/gh/{REPO}@{CHANNEL}/update.json"]


def _load_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": f"QinScape-Updater/{current_version()}", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=12) as response:
        if int(response.headers.get("Content-Length") or 0) > 1024 * 1024: raise ValueError("更新清单过大")
        return json.loads(response.read(1024 * 1024).decode("utf-8"))


def check(force: bool = False) -> dict:
    with LOCK:
        state = _read()
        if state["status"] in {"downloading", "verifying", "installing", "restarting"}: return state
        if not force and state.get("checked_at") and time.time() - float(state["checked_at"]) < CHECK_INTERVAL:return state
        state.update(status="checking", message="正在检查新版本", error=None);_write(state)
    errors=[];manifest=None
    for url in _manifest_urls():
        try:
            candidate=_load_json(url)
            if not candidate.get("version") or not candidate.get("sha256"):raise ValueError("更新清单缺少版本或校验值")
            manifest=candidate;break
        except Exception as exc:errors.append(f"{url}: {type(exc).__name__}")
    with LOCK:
        state=_read();state["checked_at"]=time.time()
        if manifest:
            newer=_version_tuple(str(manifest["version"]))>_version_tuple(current_version())
            state.update(available=newer,latest_version=str(manifest["version"]) if newer else None,notes=manifest.get("notes") or [],manifest=manifest if newer else None,status="available" if newer else "idle",progress=0,message=f"发现新版本 {manifest['version']}" if newer else "已是最新版本",error=None)
        else:
            # A network or unpublished-manifest failure must never degrade use.
            state.update(status="idle",message="暂未获取到更新信息",error=None)
        _write(state);return state


def status() -> dict:
    with LOCK:
        state=_read()
        if state.get("latest_version") and _version_tuple(current_version())>=_version_tuple(str(state["latest_version"])) and state["status"] not in {"downloading","verifying","installing","restarting"}:
            state.update(available=False,latest_version=None,manifest=None,status="idle",progress=0,message="已是最新版本",error=None);_write(state)
        return state


def _set(status_name: str, progress: int, message: str, error: str | None = None) -> None:
    with LOCK:
        state=_read();state.update(status=status_name,progress=progress,message=message,error=error);_write(state)


def _safe_extract(archive: Path, target: Path) -> None:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as value:
            if any(Path(name).is_absolute() or ".." in Path(name).parts for name in value.namelist()):raise ValueError("更新包路径不安全")
            value.extractall(target)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as value:
            if any(Path(item.name).is_absolute() or ".." in Path(item.name).parts for item in value.getmembers()):raise ValueError("更新包路径不安全")
            value.extractall(target, filter="data")
    else:raise ValueError("更新包格式不受支持")


def _download(manifest: dict, target: Path) -> None:
    version=str(manifest["version"]);derived=f"https://github.com/{REPO}/releases/download/v{version}/qinscape-{version}.tar.gz"
    urls=list(manifest.get("urls") or ([manifest["url"]] if manifest.get("url") else []));urls.extend([derived,f"https://ghfast.top/{derived}"])
    errors=[]
    for url in dict.fromkeys(urls):
        partial=target.with_suffix(".part")
        try:
            request=urllib.request.Request(url,headers={"User-Agent":f"QinScape-Updater/{current_version()}"})
            with urllib.request.urlopen(request,timeout=40) as response,partial.open("wb") as output:
                total=int(response.headers.get("Content-Length") or manifest.get("size") or 0);received=0
                while block:=response.read(1024*1024):
                    output.write(block);received+=len(block)
                    if total:_set("downloading",min(78,5+int(received/total*73)),f"正在下载 {version}")
            partial.replace(target);return
        except Exception as exc:errors.append(f"{url}: {exc}");partial.unlink(missing_ok=True)
    raise RuntimeError("主下载源与备用源均失败："+" / ".join(errors))


def _release_root(extracted: Path) -> Path:
    if (extracted/"backend").is_dir():return extracted
    candidates=[item for item in extracted.iterdir() if item.is_dir() and (item/"backend").is_dir()]
    if len(candidates)!=1:raise ValueError("更新包结构无法识别")
    return candidates[0]


def _copy_item(source_root: Path, target_root: Path, relative: str) -> None:
    source=source_root/relative;target=target_root/relative
    if not source.exists():return
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.is_dir():shutil.copytree(source,target,dirs_exist_ok=True)
    else:shutil.copy2(source,target)


def _apply(release: Path, backup: Path) -> None:
    if not (release/"backend/app/main.py").is_file() or not (release/"web/dist/index.html").is_file() or not (release/"version.json").is_file():raise ValueError("更新包缺少可运行的后端或网页构建")
    subprocess.run([str(config.ROOT/'.venv'/'bin'/'python'),'-m','compileall','-q',str(release/'backend/app')],check=True,timeout=120)
    for item in MANAGED:_copy_item(config.ROOT,backup,item)
    try:
        for item in MANAGED:_copy_item(release,config.ROOT,item)
    except Exception:
        for item in MANAGED:_copy_item(backup,config.ROOT,item)
        raise


def _worker() -> None:
    archive=None
    try:
        state=status();manifest=state.get("manifest")
        if not state.get("available") or not manifest:raise RuntimeError("当前没有可安装的新版本")
        version=str(manifest["version"]);work=STAGING/version;shutil.rmtree(work,ignore_errors=True);work.mkdir(parents=True);archive=work/"release.pkg"
        _set("downloading",3,"正在连接更新源");_download(manifest,archive)
        _set("verifying",82,"正在校验更新包")
        checksum=hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):checksum.update(block)
        digest=checksum.hexdigest()
        if digest.lower()!=str(manifest["sha256"]).lower():raise ValueError("更新包校验失败，已拒绝安装")
        extracted=work/"extracted";extracted.mkdir();_safe_extract(archive,extracted);release=_release_root(extracted)
        backup=STAGING/"backups"/f"{current_version()}-{int(time.time())}";backup.mkdir(parents=True)
        _set("installing",90,"正在安全替换程序文件");_apply(release,backup)
        _set("complete",100,"更新已安装，重启服务后生效")
    except Exception as exc:_set("failed",0,"更新没有完成",str(exc))


def start() -> dict:
    with LOCK:
        state=_read()
        if state["status"] in {"downloading","verifying","installing"}:raise RuntimeError("更新正在进行")
        if not state.get("available"):raise RuntimeError("当前没有新版本")
    threading.Thread(target=_worker,daemon=True,name="qinscape-updater").start();return status()


def restart() -> dict:
    state=status()
    if state["status"]!="complete":raise RuntimeError("当前没有已安装待重启的更新")
    script=config.RUNTIME/"restart-after-update.sh"
    script.write_text(
        "#!/usr/bin/env bash\nset -u\npid=\"$1\"\nroot=\"$2\"\nsleep 2\nkill \"$pid\" 2>/dev/null || true\n"
        "for _ in $(seq 1 20); do kill -0 \"$pid\" 2>/dev/null || break; sleep .25; done\n"
        "cd \"$root\"\nnohup bash deploy/start.sh > runtime/qinscape.log 2>&1 < /dev/null &\n",
        encoding="utf-8",
    );script.chmod(0o700);_set("restarting",100,"更新已安装，正在重启琴境")
    subprocess.Popen(["/usr/bin/bash",str(script),str(os.getpid()),str(config.ROOT)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    return status()


def _background_checker() -> None:
    time.sleep(4)
    while True:
        try:check(force=True)
        except Exception:pass
        time.sleep(CHECK_INTERVAL)


def begin_background_checks() -> None:
    if os.getenv("QINSCAPE_UPDATE_ENABLED","1")=="1":threading.Thread(target=_background_checker,daemon=True,name="qinscape-update-checker").start()
