from backend.app.schemas import PlanRequest
from backend.app.services.planner import make_plan

def test_unspecified_sadness_uses_conservative_default():
    result=make_plan(PlanRequest(mode='tiaoxin',prompt='我很悲伤'))
    assert result['card']['target']=='被容纳 · 慢慢稳定'
    assert result['card']['method']=='和 → 养'
    assert result['questions'][0]['optional'] is True

def test_xieyi_does_not_medicalize():
    result=make_plan(PlanRequest(mode='xieyi',prompt='雨后的远山，云正在散'))
    assert result['card']['mode']=='xieyi'
    assert result['questions'][0]['id']=='aesthetic_boundary'

def test_tiaoxin_asks_for_direction_then_one_deeper_anchor():
    first=make_plan(PlanRequest(mode='tiaoxin',prompt='我很悲伤'))
    assert first['questions'][0]['id']=='desired_direction'
    second=make_plan(PlanRequest(mode='tiaoxin',prompt='我很悲伤\n补充：先安静陪着'),turn=0)
    assert second['questions'][0]['id']=='anchoring_imagery'
    final=make_plan(PlanRequest(mode='tiaoxin',prompt='我很悲伤\n补充：先安静陪着\n补充：雨夜微灯'),turn=1)
    assert final['questions']==[]
    assert final['dialogue']['should_continue'] is False

def test_user_can_finish_dialogue_without_more_questions():
    result=make_plan(PlanRequest(mode='xieyi',prompt='远山'),finish_dialogue=True)
    assert result['questions']==[]

def test_xieyi_deep_image_without_spatial_view_asks_one_precise_question():
    result=make_plan(PlanRequest(mode='xieyi',prompt='月光照在霜上，寒意随影流动'))
    assert result['questions'][0]['id']=='spatial_perspective'

def test_even_complete_tiaoxin_gets_one_final_confirmation():
    result=make_plan(PlanRequest(mode='tiaoxin',prompt='我有些疲惫，希望先被陪伴，像在远山静水边慢慢安定'))
    assert result['questions'][0]['id']=='final_preference'

def test_tiaoxin_followup_can_update_card_instead_of_being_ceremonial():
    result=make_plan(PlanRequest(mode='tiaoxin',prompt='我有些悲伤，像在远山静水边\n补充：安顿之后给我一点向前的力量'),turn=1)
    assert '力量' in result['card']['target']
    assert result['card']['five_tone_path'][-1]=='jue'
    assert 'target' in result['card']['provenance']['followup_integration']['updated_fields']

def test_xieyi_followup_updates_aesthetic_boundary():
    result=make_plan(PlanRequest(mode='xieyi',prompt='月光照着远山，云影缓慢流动\n补充：清冷但有微光'),turn=1)
    assert '清冷' in result['card']['sound']
    assert '有微光' in result['card']['sound']
    assert 'sound' in result['card']['provenance']['followup_integration']['updated_fields']

def test_neutral_followup_is_considered_without_forcing_a_change():
    result=make_plan(PlanRequest(mode='xieyi',prompt='月光照着远山，云影缓慢流动\n补充：留给琴境来安排'),turn=1)
    integration=result['card']['provenance']['followup_integration']
    assert integration['considered'] is True
    assert integration['updated_fields']==[]

def test_freeform_romantic_followup_changes_the_card():
    previous=make_plan(PlanRequest(mode='tiaoxin',prompt='我还说不清，只想静静听一会'))['card']
    result=make_plan(PlanRequest(mode='tiaoxin',prompt='我还说不清，只想静静听一会\n补充：朦胧的恋爱'),turn=1,previous_card=previous)
    assert result['card']['current']=='朦胧的爱意 · 尚未言明'
    assert '朦胧' in result['card']['sound']
    assert 'current' in result['card']['provenance']['followup_integration']['updated_fields']
    assert '随之调整' in result['reply']

def test_unchanged_followup_reply_does_not_claim_card_changed():
    previous=make_plan(PlanRequest(mode='xieyi',prompt='月光照着远山，云影缓慢流动'))['card']
    result=make_plan(PlanRequest(mode='xieyi',prompt='月光照着远山，云影缓慢流动\n补充：留给琴境来安排'),turn=1,previous_card=previous)
    assert result['card']['provenance']['followup_integration']['updated_fields']==[]
    assert '保持不变' in result['reply']

def test_crisis_language_stops_normal_generation():
    result=make_plan(PlanRequest(mode='tiaoxin',prompt='我觉得自己活不下去了'))
    assert result['ready'] is False
    assert result['blocked_reason']=='safety_crisis'
