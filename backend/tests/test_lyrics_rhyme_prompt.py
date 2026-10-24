import sys
from types import ModuleType, SimpleNamespace

if 'torch' not in sys.modules:
    sys.modules['torch']=ModuleType('torch')
if 'transformers' not in sys.modules:
    transformers=ModuleType('transformers')
    transformers.AutoModelForCausalLM=object
    transformers.AutoTokenizer=object
    sys.modules['transformers']=transformers

from backend.app.services import llm_adapter


def test_lyrics_prompt_requests_natural_stanza_rhyme(monkeypatch):
    captured={}
    def fake_complete(system,user,max_tokens=700):
        captured.update(system=system,user=user)
        return '{"title":"水边","lines":["月入清川","风过遥山","灯影微动","云落人间"]}'
    monkeypatch.setattr(llm_adapter,'complete',fake_complete)
    card=SimpleNamespace(mode='xieyi',imagery=['月','水'],current='微凉',target='安定')
    result=llm_adapter.lyrics(card,{},45)
    assert result['lines']==['月入清川','风过遥山','灯影微动','云落人间']
    assert '第2、4句' in captured['system']
    assert '自然近韵' in captured['system']
    assert '不要句句强押' in captured['system']
    assert '的、了、着、是' in captured['system']


def test_tiaoxin_uses_steadier_rhyme_direction(monkeypatch):
    captured={}
    def fake_complete(system,user,max_tokens=700):
        captured['system']=system
        return '{"title":"x","lines":[]}'
    monkeypatch.setattr(llm_adapter,'complete',fake_complete)
    card=SimpleNamespace(mode='tiaoxin',imagery=[],current='悲伤',target='平稳')
    llm_adapter.lyrics(card,{},45)
    assert '韵脚稳定、舒展' in captured['system']


def test_misplaced_prosody_objects_are_recovered_as_lyric_lines(monkeypatch):
    raw='''{"title":"月吟","lines":[{"phrases":["林深","竹影","风过","声幽"],"stress_index":[0,0,0,0],"breath_after":true},{"phrases":["竹风","林声","渐远","似诉"],"stress_index":[0,0,0,0],"breath_after":false}]}'''
    monkeypatch.setattr(llm_adapter,'complete',lambda *args,**kwargs:raw)
    card=SimpleNamespace(mode='xieyi',imagery=[],current='',target='')
    result=llm_adapter.lyrics(card,{},45)
    assert result['lines']==['林深竹影风过声幽','竹风林声渐远似诉']
    assert 'prosody' not in result


def test_final_lyric_prosody_is_analyzed_without_rewriting(monkeypatch):
    raw='''{"prosody":[{"phrases":["不知归处","月满长亭"],"stress_index":7,"breath_after":true}]}'''
    monkeypatch.setattr(llm_adapter,'complete',lambda *args,**kwargs:raw)
    result=llm_adapter.analyze_lyric_prosody(['不知归处月满长亭'])
    assert result==[{'phrases':['不知归处','月满长亭'],'stress_index':7,'breath_after':True}]


def test_invalid_model_segmentation_is_rejected(monkeypatch):
    monkeypatch.setattr(llm_adapter,'complete',lambda *args,**kwargs:'{"prosody":[{"phrases":["改写了"],"stress_index":0,"breath_after":true}]}')
    try:llm_adapter.analyze_lyric_prosody(['原句不变'])
    except ValueError:pass
    else:raise AssertionError('rewritten lyric analysis must be rejected')


def test_top_level_prosody_array_from_small_model_is_accepted(monkeypatch):
    raw='''[{"phrases":["不知归处","月满长亭"],"stress_index":1,"breath_after":true}]'''
    monkeypatch.setattr(llm_adapter,'complete',lambda *args,**kwargs:raw)
    result=llm_adapter.analyze_lyric_prosody(['不知归处月满长亭'])
    assert result[0]['phrases']==['不知归处','月满长亭']
