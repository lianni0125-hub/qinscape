from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
WEB_DIST = ROOT / "web" / "dist"
RUNTIME = Path(os.getenv("QINSCAPE_RUNTIME", ROOT / "runtime"))
OUTPUTS = Path(os.getenv("QINSCAPE_OUTPUTS", ROOT / "outputs"))
VOICE_LIBRARY = Path(os.getenv("QINSCAPE_VOICE_LIBRARY", RUNTIME / "voices"))
MODELS = Path(os.getenv("QINSCAPE_MODELS", ROOT / "models"))
HF_CACHE = Path(os.getenv("HF_HOME", MODELS / "huggingface"))
os.environ.setdefault("HF_HOME", str(HF_CACHE))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
FLAN_TOKENIZER = Path(os.getenv("QINSCAPE_FLAN_TOKENIZER", MODELS / "flan-t5-base"))
TEXT2MIDI_REPO = Path(os.getenv("TEXT2MIDI_REPO", ROOT / "sources" / "Text2midi"))
TEXT2MIDI_MODEL = os.getenv("TEXT2MIDI_MODEL", "amaai-lab/text2midi")
LLM_MODEL = os.getenv("QINSCAPE_LLM_MODEL", "Qwen/Qwen3-1.7B")
USE_LLM_PLANNER = os.getenv("QINSCAPE_USE_LLM_PLANNER", "1") == "1"
DIFFSINGER_COMMAND = os.getenv("DIFFSINGER_COMMAND", "")
SOULX_COMMAND = os.getenv("QINSCAPE_SOULX_COMMAND", f"{ROOT}/.venv-soulx/bin/python {ROOT}/deploy/run_soulx.py --midi {{midi}} --lyrics {{lyrics}} --voice {{voice}} --language {{language}} --output {{output}}")
VOCAL_VOICES = {x.strip() for x in os.getenv("QINSCAPE_VOCAL_VOICES", "").split(',') if x.strip()}
SOUNDFONT_ENSEMBLE = os.getenv("SOUNDFONT_ENSEMBLE", str(ROOT / "assets" / "MuseScore_General.sf3"))
ALLOW_CPU_INFERENCE = os.getenv("QINSCAPE_ALLOW_CPU_INFERENCE", "0") == "1"
for folder in (RUNTIME, OUTPUTS, MODELS, HF_CACHE, VOICE_LIBRARY): folder.mkdir(parents=True, exist_ok=True)
