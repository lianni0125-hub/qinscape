from pathlib import Path
import pretty_midi
from backend.app.schemas import IntentCard,JobRequest
from backend.app.services import pipeline

def _card():
    return IntentCard(mode='xieyi',current='一幅景',target='缓缓展开',method='写意展开',imagery=['松风'],sound=['疏朗'],avoid=[])

def _fake_generate(_caption: str, path: Path):
    midi=pretty_midi.PrettyMIDI(initial_tempo=72);lead=pretty_midi.Instrument(program=0)
    for i in range(24):lead.notes.append(pretty_midi.Note(velocity=70,pitch=60+i%5,start=i*.3,end=i*.3+.24))
    midi.instruments.append(lead);midi.write(str(path));return path

def _fake_render(_midi: Path, wav: Path, _mode: str):
    wav.write_bytes(b'RIFF-qinscape-test');return wav

def test_pipeline_reaches_instrumental_artifacts_without_gpu(monkeypatch,tmp_path):
    monkeypatch.setattr(pipeline,'generate',_fake_generate);monkeypatch.setattr(pipeline,'render_midi',_fake_render)
    monkeypatch.setattr(pipeline,'trim_leading_silence',lambda path,_duration:path)
    req=JobRequest(card=_card(),arrangement='ensemble',duration_seconds=30)
    plan={'caption':'test','form_plan':{'density_arc':[0],'register_arc':[0]},'references':[],'duration_seconds':30}
    artifacts=pipeline.run_pipeline(req,plan,tmp_path,lambda *_:None)
    assert Path(artifacts['midi']).exists()
    assert Path(artifacts['instrumental']).exists()
    assert len(pretty_midi.PrettyMIDI(artifacts['midi']).instruments)>=3

def test_pipeline_can_stop_at_lyrics_and_vocal_midi(monkeypatch,tmp_path):
    monkeypatch.setattr(pipeline,'generate',_fake_generate);monkeypatch.setattr(pipeline,'render_midi',_fake_render)
    monkeypatch.setattr(pipeline,'trim_leading_silence',lambda path,_duration:path)
    monkeypatch.setattr(pipeline,'make_lyrics',lambda *_:{'title':'松间','lines':['松风入弦','月照空山']})
    req=JobRequest(card=_card(),lyrics=True,voice='instrumental-guide',duration_seconds=30)
    plan={'caption':'test','form_plan':{'density_arc':[0],'register_arc':[0]},'references':[],'duration_seconds':30}
    artifacts=pipeline.run_pipeline(req,plan,tmp_path,lambda *_:None)
    assert Path(artifacts['lyrics']).exists()
    assert Path(artifacts['vocal_melody']).exists()
    assert 'song' not in artifacts
