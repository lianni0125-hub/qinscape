from __future__ import annotations
import shutil, subprocess
from .. import config

def detect() -> dict:
    gpu={"available":False,"name":None,"memory_gb":None,"cuda":None}
    try:
        import torch
        gpu["cuda"]=torch.version.cuda
        if torch.cuda.is_available():
            p=torch.cuda.get_device_properties(0)
            gpu.update(available=True,name=p.name,memory_gb=round(p.total_memory/1024**3,1))
    except Exception:
        try:
            out=subprocess.check_output(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader,nounits"],text=True,timeout=3).splitlines()[0]
            name,mem=out.rsplit(",",1);gpu.update(available=True,name=name.strip(),memory_gb=round(float(mem)/1024,1))
        except Exception: pass
    llm_cache=config.HF_CACHE/f"models--{config.LLM_MODEL.replace('/','--')}"
    t2m_cache=config.HF_CACHE/f"models--{config.TEXT2MIDI_MODEL.replace('/','--')}"
    tokenizer_ready=all((config.FLAN_TOKENIZER/name).is_file() for name in ('spiece.model','tokenizer_config.json','special_tokens_map.json'))
    soulx_ready=(config.ROOT/'.venv-soulx'/'bin'/'python').is_file() and (config.MODELS/'SoulX-Singer'/'model.pt').is_file() and (config.TEXT2MIDI_REPO.parent/'SoulX-Singer').is_dir()
    return {"gpu":gpu,"models":{"text2midi_code":config.TEXT2MIDI_REPO.exists(),"text2midi_cached":t2m_cache.exists(),"flan_tokenizer_cached":tokenizer_ready,"llm_configured":bool(config.LLM_MODEL),"llm_cached":llm_cache.exists(),"vocal":bool(soulx_ready or (config.DIFFSINGER_COMMAND and config.VOCAL_VOICES)),"soulx_configured":soulx_ready,"vocal_voices":sorted(config.VOCAL_VOICES)},"renderers":{"fluidsynth":bool(shutil.which("fluidsynth")),"ffmpeg":bool(shutil.which("ffmpeg"))},"assets":{"ensemble_soundfont":bool(config.SOUNDFONT_ENSEMBLE and __import__('pathlib').Path(config.SOUNDFONT_ENSEMBLE).exists())},"mode":"gpu" if gpu["available"] else "cpu_preview"}
