from __future__ import annotations

import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline


PRESETS = [
    ("清商", "zf_001", 1, "清透女声"),
    ("疏月", "zf_002", 2, "温润女声"),
    ("松声", "zm_009", 3, "清朗男声"),
    ("远岫", "zm_010", 4, "沉静男声"),
]
TEXT = "清风徐来，水波不兴。愿此刻的心绪，随声音缓缓舒展。"
NAMESPACE = uuid.UUID("2fd2afbd-7fe2-478c-b4f8-ae7f1dafcd0e")


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "runtime/voices").resolve()
    root.mkdir(parents=True, exist_ok=True)
    pipeline = KPipeline(lang_code="z", repo_id="hexgrad/Kokoro-82M-v1.1-zh")
    for name, kokoro_voice, order, description in PRESETS:
        voice_id = str(uuid.uuid5(NAMESPACE, kokoro_voice))
        folder = root / voice_id
        folder.mkdir(parents=True, exist_ok=True)
        chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipeline(TEXT, voice=kokoro_voice, speed=.92)]
        if not chunks:
            raise RuntimeError(f"No audio generated for {kokoro_voice}")
        raw = folder / "reference.raw.wav"
        output = folder / "reference.wav"
        sf.write(raw, np.concatenate(chunks), 24000)
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
            "loudnorm=I=-20:TP=-2:LRA=11", "-ac", "1", "-ar", "44100",
            "-c:a", "pcm_s16le", str(output),
        ], check=True)
        raw.unlink()
        info = sf.info(output)
        duration = info.frames / info.samplerate
        metadata = {
            "id": voice_id, "name": name, "language": "zh", "transcript": TEXT,
            "duration_seconds": round(duration, 2), "sample_rate": info.samplerate,
            "channels": info.channels, "created_at": datetime.now(timezone.utc).isoformat(),
            "consent_confirmed": True, "status": "ready", "source_kind": "preset",
            "preset_order": order, "description": description,
            "audio_url": f"/api/voices/{voice_id}/audio", "requirements_version": 1,
            "loudness_normalization": {"applied": True, "target_lufs": -20, "true_peak_dbtp": -2},
            "provenance": {
                "generator": "hexgrad/Kokoro-82M-v1.1-zh", "voice": kokoro_voice,
                "license": "Apache-2.0", "synthetic": True,
            },
        }
        (folder / "voice.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(name, voice_id, metadata["duration_seconds"])


if __name__ == "__main__":
    main()
