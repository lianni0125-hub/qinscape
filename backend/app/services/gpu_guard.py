from fastapi import HTTPException
from .capabilities import detect
from ..config import ALLOW_CPU_INFERENCE

def require_gpu():
    caps=detect()
    if not caps["gpu"]["available"] and not ALLOW_CPU_INFERENCE:
        raise HTTPException(status_code=409,detail={"code":"GPU_REQUIRED","message":"生成 MIDI、音频或人声需要 CUDA GPU。当前构思已保存，请在 AutoDL GPU 环境继续。","capabilities":caps})
    return caps
