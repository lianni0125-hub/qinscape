"""Download QinScape's replaceable default models into the persistent model volume."""
from pathlib import Path
import os
from huggingface_hub import snapshot_download,hf_hub_download

root=Path(os.getenv('QINSCAPE_MODELS','/root/autodl-tmp/qinscape/models'))
cache=Path(os.getenv('HF_HOME',root/'huggingface'))
text2midi=os.getenv('TEXT2MIDI_MODEL','amaai-lab/text2midi')
llm=os.getenv('QINSCAPE_LLM_MODEL','Qwen/Qwen3-1.7B')

print(f'Downloading Text2MIDI: {text2midi}')
for filename in ('pytorch_model.bin','vocab_remi.pkl'):
    hf_hub_download(repo_id=text2midi,filename=filename,cache_dir=cache)
print('Downloading Flan-T5 tokenizer files')
snapshot_download(
    repo_id='google/flan-t5-base',
    cache_dir=cache,
    allow_patterns=(
        'tokenizer.json',
        'tokenizer_config.json',
        'special_tokens_map.json',
        'spiece.model',
        'config.json',
    ),
)
print(f'Downloading local language model: {llm}')
snapshot_download(repo_id=llm,cache_dir=cache)
print(f'Models ready under {root}')
