from __future__ import annotations
import re, uuid
from ..schemas import PlanRequest
from .. import config

IMAGES=["远山","秋水","松风","月色","月光","云影","微雨","归鸟","江","海","湖","溪","林","竹","庭院","小舟","灯","雪","霜","雾","花","风","雨","夜"]
def _pick_images(text:str)->list[str]:
    found=[x for x in IMAGES if x in text]
    return found[:4] or (["秋水","远山"] if re.search("悲|难过|失落",text) else ["松风","云影"])

def _apply_followup_signals(card:dict,text:str)->dict:
    """Fold a real follow-up into the card; neutral answers remain neutral."""
    if '补充：' not in text:return card
    answer=text.rsplit('补充：',1)[-1].strip();before={key:list(value) if isinstance(value,list) else value for key,value in card.items() if key in {'current','target','method','imagery','sound','avoid','five_tone_path','five_tone_rationale'}}
    if not answer:return card
    sound=list(card.get('sound') or []);avoid=list(card.get('avoid') or [])
    if card['mode']=='tiaoxin':
        if re.search('恋爱|爱意|心动|情意|思念|喜欢一个人',answer):
            hazy=bool(re.search('朦胧|说不清|若即若离|暧昧',answer))
            card['current']='朦胧的爱意 · 尚未言明' if hazy else '正在流动的情意'
            card['target']='让未明的情意有处停留';card['method']='和 → 养'
            sound=[*(['朦胧','若即若离'] if hazy else ['含蓄','温柔流动']),'温柔克制',*sound]
            avoid.extend(['过度甜腻','直白煽情']);card['five_tone_path']=['jue','gong'];card['five_tone_rationale']='以角音承接情意的萌动与未定，再向宫音的温厚与安顿收束'
        if re.search('安静陪|只陪伴|不催促|先陪着',answer):
            card['target']='被安静陪伴 · 不被催促';card['method']='和';sound=['贴近而克制','少推动',*sound]
        elif re.search('释放|松开|化开|流走',answer):
            card['target']='被承接 · 慢慢松开';card['method']='和 → 泄 → 养';sound=['先承接','逐段松开',*sound]
            if card.get('five_tone_path')==['shang','gong']:card['five_tone_path']=['shang','yu','gong'];card['five_tone_rationale']='先以商音承接，经羽音向下松动，再归于宫音的稳定'
        elif re.search('力量|向前|振作|生机',answer):
            card['target']='安顿后 · 恢复一点力量';card['method']='和 → 养 → 轻启';sound=['先稳住','后渐明朗',*sound]
            path=list(card.get('five_tone_path') or ['gong']);card['five_tone_path']=[*path[:-1],path[-1],'jue'] if path[-1]!='jue' else path;card['five_tone_rationale']=card.get('five_tone_rationale','')+'，末段以角音轻启生机'
        elif re.search('安定|平静|稳下来|放松',answer):
            card['target']='慢慢安定 · 恢复可承受的节律';sound=['缓慢减密','稳定收束',*sound]
        if re.search('疲惫|很累|无力|耗尽',answer):sound=['有支撑感','不强迫振奋',*sound];avoid.append('过度推动')
    else:
        if re.search('近乎静止|多留白|空灵',answer):sound=['疏静','多留白',*sound]
        if re.search('风与水|流动|展开|光影.*变',answer):sound=['缓慢流动','层次展开',*sound]
        if re.search('置身其中|从身边|耳畔',answer):sound=['近景包围','声部贴近',*sound]
        if re.search('隔岸|远望|辽远|由近.*远',answer):sound=['空间逐渐拉远','余音深长',*sound]
        if '清冷' in answer:sound=['清冷','有微光',*sound]
        if '温润' in answer:sound=['温润','不甜腻',*sound]
        if '辽远而不悲凉' in answer:sound=['辽远','克制',*sound];avoid.append('过度悲凉')
    for match in re.finditer(r'(?:避开|不要|不想听|不喜欢)([^\uff0c。；\n]{1,16})',answer):avoid.append(match.group(1).strip())
    card['sound']=list(dict.fromkeys(sound))[:5];card['avoid']=list(dict.fromkeys(x for x in avoid if x))[:5]
    after={key:card.get(key) for key in before};updated=[key for key in before if before[key]!=after[key]]
    card['provenance']={**card.get('provenance',{}),'followup_integration':{'considered':True,'updated_fields':updated}}
    return card
def _dialogue_baseline(mode:str,text:str,turn:int,finish:bool)->dict:
    if finish or turn>=1:return {"should_continue":False,"missing_high_value":[],"information_gain":0.0}
    if mode=='tiaoxin':
        has_direction=bool(re.search("希望|想要|陪|安定|平静|放下|释放|振作|力量|松开|缓一缓|不想被|不要",text))
        has_anchor=any(x in text for x in IMAGES)
        if not has_direction:return {"should_continue":True,"missing_high_value":["desired_direction"],"information_gain":.86,"question":{"id":"desired_direction","text":"这份心绪，此刻更需要被安静陪着，还是希望声音带它慢慢松开一些？","options":["先安静陪着","慢慢释放","走向安定","给我一点力量"],"optional":True}}
        if not has_anchor:return {"should_continue":True,"missing_high_value":["anchoring_imagery"],"information_gain":.58,"question":{"id":"anchoring_imagery","text":"如果给这份心绪一个可以停留的地方，它更接近怎样的景象？","options":["静水与远山","雨夜微灯","林下松风","留给琴境来想象"],"optional":True}}
    else:
        has_image=any(x in text for x in IMAGES)
        has_motion=bool(re.search("流|散|落|升|远去|靠近|掠过|摇|停|展开|消失|归|穿过|吹|动",text))
        has_spatial=bool(re.search("远|近|身边|耳畔|眼前|深处|天际|空旷|开阔|室内|屋内|岸边|山下|林中|置身|俯瞰|仰望",text))
        if not has_image:return {"should_continue":True,"missing_high_value":["core_imagery"],"information_gain":.84,"question":{"id":"core_imagery","text":"这段声音若先落成一幅景，你最先看见的是什么？","options":["山水深处","夜色与月光","风过林间","庭院灯影"],"optional":True}}
        if not has_motion:return {"should_continue":True,"missing_high_value":["movement"],"information_gain":.64,"question":{"id":"movement","text":"这幅景是近乎静止的，还是有某种事物正缓慢发生？","options":["近乎静止","风与水在流动","由近处走向远方","光影正在变化"],"optional":True}}
        if not has_spatial:return {"should_continue":True,"missing_high_value":["spatial_perspective"],"information_gain":.52,"question":{"id":"spatial_perspective","text":"在这幅景里，你更想置身其中感受它从身边经过，还是隔着一段距离静静望见？","options":["置身其中","隔岸远望","由近处走向远方","留给琴境来安排"],"optional":True}}
    if mode=='tiaoxin':
        return {"should_continue":True,"missing_high_value":["final_preference"],"information_gain":.32,"question":{"id":"final_preference","text":"在已经说清的心境里，这一次你更希望音乐把变化控制在怎样的分寸？","options":["只陪伴，不催促","轻轻松开一些","缓慢走向安定","保留一点向前的力量"],"optional":True}}
    return {"should_continue":True,"missing_high_value":["aesthetic_boundary"],"information_gain":.32,"question":{"id":"aesthetic_boundary","text":"这幅景已经很清晰了。最后确认一下，你最想保留怎样的余味，又希望避开什么？","options":["辽远而不悲凉","清冷但有微光","空灵且多留白","温润而不甜腻"],"optional":True}}

def make_plan(req:PlanRequest,turn:int=0,finish_dialogue:bool=False,previous_card:dict|None=None)->dict:
    text=req.prompt.strip(); crisis=bool(re.search("不想活|活不下去|结束生命|自杀|伤害自己|去死",text));sad=bool(re.search("悲|难过|伤心|失落|哀",text)); agitated=bool(re.search("乱|焦虑|烦|急|躁",text)); tired=bool(re.search("累|疲惫|无力|耗尽",text));
    if req.mode=='tiaoxin' and crisis:
        card={"mode":"tiaoxin","current":"你似乎正承受非常强烈的痛苦","target":"先获得现实中的即时支持","method":"安全优先","imagery":[],"sound":[],"avoid":["继续普通生成流程"],"prompt":text,"provenance":{"product_strategy":"危机性表达转入安全响应，不由音乐生成替代支持"}}
        return {"session_id":req.session_id or str(uuid.uuid4()),"card":card,"questions":[],"dialogue":{"should_continue":False},"reply":"现在最重要的是让现实中的人陪到你。","ready":False,"blocked_reason":"safety_crisis","safety_message":"现在最重要的不是生成音乐，而是让现实中的人知道你正在承受什么。请尽快联系你信任的人或当地紧急服务，并尽量不要独处。","source":"safety_router"}
    if req.mode=="xieyi":
        card={"mode":"xieyi","current":"一幅正在展开的景","target":"让景物形成可听见的流动","method":"意象 → 场景弧线 → 五声结构与古风配器","imagery":_pick_images(text),"sound":["清润","有呼吸","虚实相生"],"avoid":[],"five_tone_path":["jue","gong"],"five_tone_rationale":"以角音舒展意象，以宫音收束空间","prompt":text,"provenance":{"product_strategy":"QinScape xieyi policy"}}
    else:
        if sad: current="悲伤";target="被容纳 · 慢慢稳定";method="和 → 养";sound=["疏缓","留白","温和展开"];avoid=["突然明快","持续强化哀伤","强烈高潮"];tone_path=["shang","gong"];tone_reason="先以商音承接清肃与忧感，再向宫音的稳定中心过渡"
        elif agitated: current="烦乱 · 活动度偏高";target="松动 · 稳定";method="和 → 泄 → 养";sound=["先承接","逐段减密","稳定收束"];avoid=["突发强音","复杂节奏堆叠"];tone_path=["zhi","yu","gong"];tone_reason="先承接偏高活动度，再以羽音下行、宫音安定"
        elif tired: current="疲惫 · 支撑不足";target="安顿 · 微弱生机";method="养 → 轻启";sound=["稳定","温厚","缓慢拓展"];avoid=["过度清冷","强迫振奋"];tone_path=["gong","jue"];tone_reason="先由宫音提供支撑，再以角音引出温和生机"
        else: current="尚未细分的心绪";target="更稳定、可承受";method="和";sound=["克制","可预测","有呼吸"];avoid=["过度刺激"];tone_path=["gong"];tone_reason="以宫音建立稳定、可预测的音乐中心"
        card={"mode":"tiaoxin","current":current,"target":target,"method":method,"imagery":_pick_images(text),"sound":sound,"avoid":avoid,"five_tone_path":tone_path,"five_tone_rationale":tone_reason,"prompt":text,"provenance":{"classical_text":"五音与五脏五时的传统配属","traditional_inference":"五行与情志关系的审慎推演","product_strategy":"承接与渐变属于琴境现代策略"}}
    card=_apply_followup_signals(card,text)
    dialogue=_dialogue_baseline(req.mode,text,turn,finish_dialogue)
    source="deterministic_planner"
    if config.USE_LLM_PLANNER:
        try:
            import torch
            if torch.cuda.is_available():
                from .llm_adapter import enhance_dialogue
                policy_card=card;card,dialogue=enhance_dialogue(card,dialogue,turn)
                # A model may add nuance, but it cannot discard a concrete
                # preference the user just supplied in the required turn.
                locked=policy_card.get('provenance',{}).get('followup_integration',{}).get('updated_fields',[])
                for key in locked:card[key]=policy_card[key]
                card['provenance']={**card.get('provenance',{}),'followup_integration':policy_card.get('provenance',{}).get('followup_integration')};source="deterministic_policy+local_qwen"
        except Exception as exc:
            card['provenance']['semantic_enrichment_fallback']=type(exc).__name__
    if finish_dialogue or turn>=1:dialogue={**dialogue,"should_continue":False,"missing_high_value":[],"information_gain":0.0}
    if previous_card is not None:
        compared=('current','target','method','imagery','sound','avoid','five_tone_path','five_tone_rationale')
        updated=[key for key in compared if previous_card.get(key)!=card.get(key)]
        card['provenance']={**card.get('provenance',{}),'followup_integration':{'considered':True,'updated_fields':updated}}
    question=dialogue.get('question') if dialogue.get('should_continue') else None
    questions=[question] if question else []
    integration=card.get('provenance',{}).get('followup_integration',{})
    if question:reply=question['text']
    else:
        if turn>=1 and integration.get('updated_fields'):ack='我听见了刚才的补充，琴心卡也随之调整了。'
        elif turn>=1:ack='我也听见了刚才的补充。它与先前的声音方向一致，琴心卡便保持不变。'
        else:ack='我明白了。'
        reply=ack+('让这些心绪先停在这里，接下来把它们慢慢交给声音。' if req.mode=='tiaoxin' else '这幅景已经足够清晰。接下来，让它循着声音展开。')
    return {"session_id":req.session_id or str(uuid.uuid4()),"card":card,"questions":questions,"dialogue":dialogue,"reply":reply,"ready":True,"blocked_reason":None,"source":source}
