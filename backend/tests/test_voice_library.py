import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from backend.app import config
from backend.app.main import app


client = TestClient(app)


def wav_bytes(seconds=5.1, rate=16000, silent=False, amplitude=.12):
    buffer=io.BytesIO()
    t=np.arange(int(seconds*rate),dtype=np.float32)/rate
    samples=np.zeros_like(t) if silent else amplitude*np.sin(2*np.pi*220*t)
    sf.write(buffer,samples,rate,format='WAV')
    return buffer.getvalue()


def test_authorized_voice_upload_list_preview_and_delete(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'VOICE_LIBRARY',tmp_path)
    response=client.post('/api/voices',data={
        'name':'清柔女声','language':'zh','transcript':'山中明月静静照','consent':'true'
    },files={'audio':('voice.wav',wav_bytes(),'audio/wav')})
    assert response.status_code==201
    voice=response.json();assert voice['consent_confirmed'] is True
    assert client.get('/api/voices').json()[0]['id']==voice['id']
    preview=client.get(voice['audio_url']);assert preview.status_code==200
    assert client.delete(f"/api/voices/{voice['id']}").status_code==204
    assert client.get('/api/voices').json()==[]


def test_voice_upload_requires_explicit_consent(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'VOICE_LIBRARY',tmp_path)
    response=client.post('/api/voices',data={
        'name':'test','language':'zh','transcript':'matching words','consent':'false'
    },files={'audio':('voice.wav',wav_bytes(),'audio/wav')})
    assert response.status_code==422


def test_voice_upload_rejects_silence(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'VOICE_LIBRARY',tmp_path)
    response=client.post('/api/voices',data={
        'name':'test','language':'zh','transcript':'matching words','consent':'true'
    },files={'audio':('voice.wav',wav_bytes(silent=True),'audio/wav')})
    assert response.status_code==422
    assert '没有检测到声音' in response.json()['detail']


def test_voice_upload_accepts_quiet_but_audible_audio(monkeypatch,tmp_path):
    monkeypatch.setattr(config,'VOICE_LIBRARY',tmp_path)
    response=client.post('/api/voices',data={
        'name':'quiet','language':'zh','transcript':'matching words','consent':'true'
    },files={'audio':('voice.wav',wav_bytes(amplitude=.0008),'audio/wav')})
    assert response.status_code==201
    assert response.json()['quality_check']['result']=='low_volume'
