from fastapi.testclient import TestClient
from backend.app.main import app

client=TestClient(app)

def test_health_and_plan_roundtrip():
    health=client.get('/api/health')
    assert health.status_code==200
    assert health.json()['port']==6006
    response=client.post('/api/sessions/plan',json={'mode':'tiaoxin','prompt':'我只是有些悲伤'})
    assert response.status_code==200
    payload=response.json()
    stored=client.get(f"/api/sessions/{payload['session_id']}")
    assert stored.status_code==200
    assert stored.json()['card']['method']=='和 → 养'

def test_preflight_reports_local_cpu_and_missing_assets():
    planned=client.post('/api/sessions/plan',json={'mode':'xieyi','prompt':'松风入夜'}).json()
    response=client.post('/api/preflight',json={
        'session_id':planned['session_id'],'card':planned['card'],
        'arrangement':'ensemble','lyrics':False
    })
    assert response.status_code==200
    body=response.json()
    assert body['ready'] is False
    assert any('GPU' in item for item in body['missing'])

def test_followup_keeps_session_and_history():
    first=client.post('/api/sessions/plan',json={'mode':'tiaoxin','prompt':'我有些悲伤'}).json()
    second=client.post('/api/sessions/plan',json={
        'session_id':first['session_id'],'mode':'tiaoxin','prompt':'也觉得很疲惫'
    }).json()
    assert second['session_id']==first['session_id']
    stored=client.get(f"/api/sessions/{first['session_id']}").json()
    assert stored['revision']==2
    assert stored['history'][-1]['type']=='followup_prompt'
    assert '我有些悲伤' in stored['card']['prompt']
    assert '也觉得很疲惫' in stored['card']['prompt']

def test_first_followup_completes_the_guided_dialogue_without_repeating_question():
    first=client.post('/api/sessions/plan',json={'mode':'tiaoxin','prompt':'我有些悲伤，希望先被安静陪着'}).json()
    assert first['questions']
    second=client.post('/api/sessions/plan',json={
        'session_id':first['session_id'],'mode':'tiaoxin','prompt':'留给琴境来想象'
    }).json()
    assert second['questions']==[]
    assert second['dialogue']['should_continue'] is False

def test_first_required_followup_is_folded_into_the_card():
    first=client.post('/api/sessions/plan',json={'mode':'tiaoxin','prompt':'我有些悲伤，像在远山静水边'}).json()
    second=client.post('/api/sessions/plan',json={'session_id':first['session_id'],'mode':'tiaoxin','prompt':'我想慢慢恢复一点向前的力量'}).json()
    assert '力量' in second['card']['target']
    assert second['card']['provenance']['followup_integration']['considered'] is True

def test_followup_card_with_structured_provenance_passes_preflight_schema():
    first=client.post('/api/sessions/plan',json={'mode':'tiaoxin','prompt':'我还说不清，只想静静听一会'}).json()
    second=client.post('/api/sessions/plan',json={'session_id':first['session_id'],'mode':'tiaoxin','prompt':'朦胧的恋爱'}).json()
    response=client.post('/api/preflight',json={'session_id':second['session_id'],'card':second['card'],'arrangement':'ensemble','lyrics':False})
    assert response.status_code==200
    assert isinstance(response.json()['missing'],list)

def test_job_listing_endpoint_exists():
    response=client.get('/api/jobs')
    assert response.status_code==200
    assert isinstance(response.json(),list)

def test_completed_work_can_be_deleted(monkeypatch,tmp_path):
    from backend.app import config
    job_id='123e4567-e89b-12d3-a456-426614174000'
    folder=tmp_path/job_id;folder.mkdir();(folder/'job.json').write_text('{}',encoding='utf8')
    monkeypatch.setattr(config,'OUTPUTS',tmp_path)
    response=client.delete(f'/api/jobs/{job_id}')
    assert response.status_code==204
    assert not folder.exists()

def test_work_title_can_change_without_losing_original(monkeypatch,tmp_path):
    from backend.app import config
    import json
    job_id='123e4567-e89b-12d3-a456-426614174001'
    folder=tmp_path/job_id;folder.mkdir();manifest=folder/'job.json'
    manifest.write_text(json.dumps({'id':job_id,'title':'松风远山','original_title':'松风远山'}),encoding='utf8')
    monkeypatch.setattr(config,'OUTPUTS',tmp_path)
    response=client.patch(f'/api/jobs/{job_id}/title',json={'title':'月下归心'})
    assert response.status_code==200
    assert response.json()['title']=='月下归心'
    assert response.json()['original_title']=='松风远山'
    saved=json.loads(manifest.read_text(encoding='utf8'))
    assert saved['title']=='月下归心' and saved['original_title']=='松风远山'

def test_download_uses_current_renamed_title(monkeypatch,tmp_path):
    from backend.app import config
    import json
    job_id='123e4567-e89b-12d3-a456-426614174002'
    folder=tmp_path/job_id;folder.mkdir();(folder/'composition.mid').write_bytes(b'MThd')
    manifest=folder/'job.json'
    manifest.write_text(json.dumps({'id':job_id,'title':'初题','original_title':'初题'}),encoding='utf8')
    monkeypatch.setattr(config,'OUTPUTS',tmp_path)
    assert client.patch(f'/api/jobs/{job_id}/title',json={'title':'月下归心'}).status_code==200
    response=client.get(f'/api/jobs/{job_id}/download/midi')
    assert response.status_code==200
    assert '%E6%9C%88%E4%B8%8B%E5%BD%92%E5%BF%83-MIDI.mid' in response.headers['content-disposition']

def test_catalog_exposes_palettes_and_only_installed_selectable_voices():
    body=client.get('/api/catalog').json()
    assert len(body['ensemble_styles'])==5
    assert {x['id'] for x in body['voices']}==set()
    assert all(x['bundle'] is False for x in body['voice_candidates'])
    assert all(x['license'] for x in body['voice_candidates'])


def test_setup_status_exposes_clickable_components():
    response = client.get('/api/setup')
    assert response.status_code == 200
    body = response.json()
    assert {'text2midi', 'soundfont', 'llm', 'soulx', 'preset_voices'} <= set(body['components'])
    assert isinstance(body['ready'], bool)
    assert body['disk']['required_gb'] >= 20


def test_unknown_setup_component_is_rejected():
    response = client.post('/api/setup/start', json={'component': 'not-a-resource'})
    assert response.status_code == 404

def test_prompt_suggestions_endpoint_returns_three_choices():
    response=client.post('/api/suggestions',json={'mode':'xieyi','prompt':'月下的远山','exclude':[]})
    assert response.status_code==200
    assert len(response.json()['suggestions'])==3

def test_unregistered_vocal_voice_fails_preflight_early():
    planned=client.post('/api/sessions/plan',json={'mode':'xieyi','prompt':'月下松风'}).json()
    response=client.post('/api/preflight',json={
        'card':planned['card'],'arrangement':'ensemble','lyrics':True,'voice':'female-soft'
    })
    assert response.status_code==200
    assert any('female-soft' in item for item in response.json()['missing'])
