"""Process-wide guard for model libraries that mutate PyTorch global state."""
from __future__ import annotations

import threading


# Transformers/Accelerate temporarily constructs modules on the meta device.
# That mechanism is not safe to overlap with Text2MIDI construction in another
# thread. QinScape already runs generation serially, so one re-entrant lock is
# the correct boundary for local model loading and inference.
MODEL_RUNTIME_LOCK = threading.RLock()
