from __future__ import annotations
import pickle,sys
from functools import lru_cache
from pathlib import Path
from .. import config
from huggingface_hub import hf_hub_download
from transformers import T5Tokenizer
import torch
from .model_runtime import MODEL_RUNTIME_LOCK

@lru_cache(maxsize=1)
def load():
    if not torch.cuda.is_available() and not config.ALLOW_CPU_INFERENCE: raise RuntimeError('CUDA GPU is required')
    tokenizer_files=('spiece.model','tokenizer_config.json','special_tokens_map.json')
    missing=[name for name in tokenizer_files if not (config.FLAN_TOKENIZER/name).is_file()]
    if missing:raise RuntimeError(f"LOCAL_MODEL_RESOURCE_MISSING: flan-t5-base tokenizer lacks {', '.join(missing)}")
    sys.path.insert(0,str(config.TEXT2MIDI_REPO))
    from model.transformer_model import Transformer
    model_path=hf_hub_download(repo_id=config.TEXT2MIDI_MODEL,filename='pytorch_model.bin',cache_dir=config.HF_CACHE,local_files_only=True)
    vocab_path=hf_hub_download(repo_id=config.TEXT2MIDI_MODEL,filename='vocab_remi.pkl',cache_dir=config.HF_CACHE,local_files_only=True)
    with open(vocab_path,'rb') as f:r_tokenizer=pickle.load(f)
    # Text2MIDI's serialized tokenizer predates the current miditok attribute
    # name. Restore the compatibility flag expected by REMI.decode().
    if not hasattr(r_tokenizer.config,'use_velocities'):
        r_tokenizer.config.use_velocities=bool(getattr(r_tokenizer.config,'num_velocities',0))
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # Accelerate/Qwen can leave PyTorch's process-wide default device on
    # ``meta``. Restoring that value after a temporary guard made the failure
    # recur later in the same server process. Build Text2MIDI and its position
    # buffers in real CPU memory, load there, then move the complete module to
    # CUDA. Keeping the ordinary default on CPU is also what third-party code
    # expects when it omits an explicit device.
    if hasattr(torch,'set_default_device'):torch.set_default_device('cpu')
    model=Transformer(len(r_tokenizer),768,8,2048,18,1024,False,8,device=torch.device('cpu'))
    state=torch.load(model_path,map_location='cpu',weights_only=False)
    model.load_state_dict(state);model.to(device).eval()
    tokenizer=T5Tokenizer.from_pretrained(str(config.FLAN_TOKENIZER),local_files_only=True)
    return model,tokenizer,r_tokenizer,device

def generate(caption:str,output:Path,temperature:float=.88,max_len:int=2000):
    with MODEL_RUNTIME_LOCK:
        model,tok,r_tok,device=load();inputs=tok(caption,return_tensors='pt',padding=True,truncation=True).to(device)
        with torch.inference_mode():tokens=model.generate(inputs['input_ids'],inputs['attention_mask'],max_len=max_len,temperature=temperature)[0].tolist()
        score=r_tok.decode(tokens);score.dump_midi(str(output));return output
