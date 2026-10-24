# QinScape completion audit

Updated: 2026-10-21

## Verified on the CPU development machine

| Requirement | Evidence |
|---|---|
| 写意／调心 UI | Production Vite build and desktop/mobile headless Edge renders |
| Structured, revisable multi-turn state | API session round-trip, revision/history tests |
| Safety routing | Crisis-language unit test blocks normal generation |
| Guqin knowledge layer | Validator: 71 works, 408 sections, 79,225 note rows |
| Whole-form Skill behavior | MIDI density/register/closure tests |
| Local motif behavior | MIDI transposition/inversion/rhythm recombination test |
| Pure guqin / ensemble | MIDI orchestration tests; ensemble produces independent parts |
| Lyrics without voicebank | Pipeline integration test produces lyric JSON and vocal MIDI |
| GPU/resource guard | API preflight tests for CPU, SoundFont and unregistered voices |
| Queue and results | Single GPU worker queue, persistent manifests, result listing API/UI |
| AutoDL service shape | FastAPI and built SPA served together on port 6006; health/capability endpoints exercised |
| Build quality | `npm run build`, Python compileall and 15 pytest tests pass |

## Requires AutoDL GPU and licensed assets

The following cannot be truthfully verified on the CPU-only development machine:

1. Real Text2MIDI checkpoint inference under CUDA.
2. FluidSynth output through a licensed true-guqin SoundFont and the selected ensemble SoundFont.
3. Qwen GPU semantic enrichment and lyric latency/memory behavior.
4. Final DiffSinger audio for each separately licensed and registered voicebank.
5. Docker image build/run with NVIDIA Container Toolkit (the local Docker daemon is not running).

Run `deploy/gpu_smoke.py` on AutoDL for instrumental acceptance. A voicebank is accepted only after its own license review, runner configuration and audible output test.
