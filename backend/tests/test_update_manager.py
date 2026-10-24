import json

from backend.app.services import update_manager


def _prepare(monkeypatch,tmp_path):
    state=tmp_path/'update-state.json';version=tmp_path/'version.json';version.write_text(json.dumps({'version':'0.1.0'}),encoding='utf-8')
    monkeypatch.setattr(update_manager,'STATE_FILE',state);monkeypatch.setattr(update_manager.config,'ROOT',tmp_path)
    return state


def test_newer_remote_version_becomes_visible(monkeypatch,tmp_path):
    _prepare(monkeypatch,tmp_path)
    monkeypatch.setattr(update_manager,'_load_json',lambda url:{'version':'0.1.1','sha256':'a'*64,'notes':['更新说明']})
    result=update_manager.check(force=True)
    assert result['available'] is True
    assert result['latest_version']=='0.1.1'
    assert result['notes']==['更新说明']


def test_equal_remote_version_keeps_button_hidden(monkeypatch,tmp_path):
    _prepare(monkeypatch,tmp_path)
    monkeypatch.setattr(update_manager,'_load_json',lambda url:{'version':'0.1.0','sha256':'b'*64})
    result=update_manager.check(force=True)
    assert result['available'] is False
    assert result['status']=='idle'


def test_all_update_sources_failing_does_not_block_application(monkeypatch,tmp_path):
    _prepare(monkeypatch,tmp_path)
    def fail(_):raise OSError('offline')
    monkeypatch.setattr(update_manager,'_load_json',fail)
    result=update_manager.check(force=True)
    assert result['available'] is False
    assert result['status']=='idle'
    assert result['error'] is None
