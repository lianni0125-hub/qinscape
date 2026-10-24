import pytest
from fastapi import HTTPException
from backend.app.services import gpu_guard

def test_gpu_guard_blocks_cpu(monkeypatch):
    monkeypatch.setattr(gpu_guard,'ALLOW_CPU_INFERENCE',False)
    monkeypatch.setattr(gpu_guard,'detect',lambda:{'gpu':{'available':False}})
    with pytest.raises(HTTPException) as err:gpu_guard.require_gpu()
    assert err.value.status_code==409
    assert err.value.detail['code']=='GPU_REQUIRED'
