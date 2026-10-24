from backend.app.schemas import IntentCard,JobRequest
from backend.app.services.prompt_compiler import compile_prompt

def test_skill_is_compiled_into_music_caption():
    card=IntentCard(mode='tiaoxin',current='悲伤',target='慢慢稳定',method='和 → 养',imagery=['秋水','远山'],sound=['疏缓'],avoid=['突然明快'],prompt='我很悲伤')
    plan=compile_prompt(JobRequest(card=card,arrangement='ensemble'))
    assert 'Chinese-inspired' in plan['caption']
    assert plan['references']
    assert plan['arrangement']=='ensemble'
    assert plan['five_tone_path']==['gong']
    assert len(plan['references'])>=3
    assert any(x['use']=='structure' for x in plan['references'])
    assert plan['form_plan']['section_count']>=3
    assert plan['form_plan']['roles'][0]=='opening'
    assert plan['form_plan']['roles'][-1]=='closing'
    assert 'harmonic_arc' in plan['form_plan']
    assert 'silence_arc' not in plan['form_plan']
