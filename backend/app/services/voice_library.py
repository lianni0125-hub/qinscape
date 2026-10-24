from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
import numpy as np

from .. import config

ALLOWED_SUFFIXES = {".wav", ".flac"}
RECORDING_SUFFIXES = {".webm", ".ogg"}
MAX_BYTES = 50 * 1024 * 1024


def _metadata_path(voice_id: str) -> Path:
    return config.VOICE_LIBRARY / voice_id / "voice.json"


def list_voices() -> list[dict]:
    voices = []
    for path in config.VOICE_LIBRARY.glob("*/voice.json"):
        try:
            voices.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(voices, key=lambda item: (item.get("source_kind") == "preset", item.get("preset_order", 99), item.get("created_at", "")))


def get_voice(voice_id: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f-]{36}", voice_id):
        return None
    path = _metadata_path(voice_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def create_voice(*, name: str, language: str, transcript: str, filename: str,
                 content: bytes, consent: bool) -> dict:
    if not consent:
        raise ValueError("必须确认已获得声音本人明确授权")
    if not 1 <= len(name.strip()) <= 40:
        raise ValueError("人声名称需为 1–40 个字符")
    if not 2 <= len(transcript.strip()) <= 500:
        raise ValueError("请填写与音频完全一致的演唱文本")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES | RECORDING_SUFFIXES:
        raise ValueError("只接受 WAV、FLAC 或浏览器录音")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("音频不能为空且不得超过 50 MB")

    voice_id = str(uuid.uuid4())
    folder = config.VOICE_LIBRARY / voice_id
    folder.mkdir(parents=True, exist_ok=False)
    audio = folder / f"reference{suffix}"
    try:
        audio.write_bytes(content)
        source_kind = "recorded" if suffix in RECORDING_SUFFIXES else "uploaded"
        if suffix in RECORDING_SUFFIXES:
            ffmpeg=shutil.which("ffmpeg")
            if not ffmpeg:raise ValueError("服务器尚未安装录音转换组件")
            normalized=folder/"reference.wav"
            # MediaRecorder WebM files often have a missing or zero container
            # duration. Decode first, then derive duration from actual PCM frames.
            command=[ffmpeg,"-y","-i",str(audio),"-ac","1","-ar","44100","-c:a","pcm_s16le",str(normalized)]
            try:subprocess.run(command,check=True,timeout=90,capture_output=True)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:raise ValueError("录音转换失败，请重录或改用 WAV/FLAC 上传") from exc
            audio.unlink();audio=normalized
        info = sf.info(str(audio))
        duration = info.frames / info.samplerate
        if info.samplerate < 16000:
            raise ValueError("采样率不得低于 16 kHz")
        if info.channels not in (1, 2):
            raise ValueError("音频必须为单声道或双声道")
        if not 5 <= duration <= 60:
            if source_kind == "recorded" and duration < 5:
                raise ValueError("录音总时长不足 5 秒，请再多唱或说一会儿")
            raise ValueError("参考人声时长需在 5–60 秒之间")
        samples, _ = sf.read(str(audio), dtype="float32", always_2d=True)
        mono = samples.mean(axis=1)
        peak = float(np.max(np.abs(mono))) if mono.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
        active_ratio = float(np.mean(np.abs(mono) >= 0.003)) if mono.size else 0.0
        clipped_ratio = float(np.mean(np.abs(mono) >= 0.995)) if mono.size else 0.0
        active_seconds = active_ratio * duration
        if peak < 0.0005 or rms < 0.00005:
            raise ValueError("没有检测到声音，请确认麦克风未静音后重录")
        if clipped_ratio > 0.02:
            raise ValueError("录音音量过大并出现明显爆音，请离麦克风稍远一些后重录")
        quality_result = "low_volume" if rms < 0.001 or active_seconds < 0.2 else "passed"
        normalizer = shutil.which("ffmpeg")
        normalization_applied = False
        if normalizer:
            normalized_audio = folder / "reference.normalized.wav"
            normalize_command = [
                normalizer, "-y", "-i", str(audio), "-af",
                "loudnorm=I=-20:TP=-2:LRA=11", "-ac", "1", "-ar", "44100",
                "-c:a", "pcm_s16le", str(normalized_audio),
            ]
            try:
                subprocess.run(normalize_command, check=True, timeout=90, capture_output=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError("响度调整失败，请重录或改用 WAV/FLAC 上传") from exc
            audio.unlink()
            audio = folder / "reference.wav"
            normalized_audio.replace(audio)
            normalization_applied = True
        normalized_info = sf.info(str(audio))
        item = {
            "id": voice_id, "name": name.strip(), "language": language,
            "transcript": transcript.strip(), "duration_seconds": round(duration, 2),
            "sample_rate": normalized_info.samplerate, "channels": normalized_info.channels,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "consent_confirmed": True, "status": "ready",
            "source_kind": source_kind,
            "quality_check": {
                "result": quality_result, "peak": round(peak, 5),
                "rms": round(rms, 5), "active_ratio": round(active_ratio, 4),
                "active_seconds": round(active_seconds, 2),
            },
            "loudness_normalization": {
                "applied": normalization_applied, "target_lufs": -20, "true_peak_dbtp": -2,
            },
            "audio_url": f"/api/voices/{voice_id}/audio",
            "requirements_version": 1,
        }
        _metadata_path(voice_id).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        return item
    except Exception:
        if folder.exists():
            for path in folder.iterdir():path.unlink()
            folder.rmdir()
        raise


def audio_path(voice_id: str) -> Path | None:
    voice = get_voice(voice_id)
    if not voice:
        return None
    files = [p for p in (_metadata_path(voice_id).parent).iterdir() if p.suffix.lower() in ALLOWED_SUFFIXES]
    return files[0] if files else None


def delete_voice(voice_id: str) -> bool:
    voice = get_voice(voice_id)
    if not voice or voice.get("source_kind") == "preset":
        return False
    folder = _metadata_path(voice_id).parent
    for path in folder.iterdir():
        path.unlink()
    folder.rmdir()
    return True
