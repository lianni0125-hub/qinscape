from typing import Literal, Any
from pydantic import BaseModel, Field

class PlanRequest(BaseModel):
    session_id: str | None = None
    mode: Literal["xieyi", "tiaoxin"]
    prompt: str = Field(min_length=1, max_length=3000)
    answers: dict[str, Any] = {}
    imagery: list[str] = []
    arrangement: Literal["ensemble"] = "ensemble"
    lyrics: bool = False
    finish_dialogue: bool = False

class IntentCard(BaseModel):
    mode: Literal["xieyi", "tiaoxin"]
    current: str
    target: str
    method: str
    imagery: list[str]
    sound: list[str]
    avoid: list[str]
    five_tone_path: list[Literal["gong", "shang", "jue", "zhi", "yu"]] = ["gong"]
    five_tone_rationale: str = "以宫音建立稳定的中心"
    prompt: str = ""
    provenance: dict[str, Any] = {}

class JobRequest(BaseModel):
    session_id: str | None = None
    card: IntentCard
    arrangement: Literal["ensemble"] = "ensemble"
    ensemble_style: Literal["silk_bamboo", "plucked", "clear_space", "chamber", "orchestral"] = "silk_bamboo"
    lead_instrument: str = ""
    preferred_instruments: list[str] = []
    excluded_instruments: list[str] = []
    lyrics: bool = False
    approved_lyrics: dict[str, Any] | None = None
    voice: str = "instrumental-guide"
    vocal_balance: Literal["natural", "forward", "instrumental"] = "natural"
    duration_seconds: int = Field(default=90, ge=30, le=360)
    seed: int | None = None

class PreflightResult(BaseModel):
    ready: bool
    missing: list[str] = []
    capabilities: dict[str, Any] = {}

class TitleUpdate(BaseModel):
    title: str = Field(min_length=1,max_length=40)

class SuggestionRequest(BaseModel):
    mode: Literal["xieyi", "tiaoxin"]
    prompt: str = Field(default="", max_length=3000)
    exclude: list[str] = []

class JobState(BaseModel):
    id: str
    status: Literal["queued", "running", "complete", "failed"]
    stage: str
    progress: float
    error: str | None = None
    error_code: str | None = None
    error_stage: str | None = None
    artifacts: dict[str, str] = {}
    title: str | None = None
    original_title: str | None = None
