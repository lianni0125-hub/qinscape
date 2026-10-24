from __future__ import annotations
import json,re
from functools import lru_cache
from .. import config
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from .model_runtime import MODEL_RUNTIME_LOCK

@lru_cache(maxsize=1)
def load():
    # Production instances may be intentionally offline. Missing optional LLM
    # assets must fail immediately so the deterministic planner can take over.
    tok=AutoTokenizer.from_pretrained(config.LLM_MODEL,cache_dir=config.HF_CACHE,local_files_only=True)
    model=AutoModelForCausalLM.from_pretrained(config.LLM_MODEL,cache_dir=config.HF_CACHE,local_files_only=True,torch_dtype='auto',device_map='auto').eval();return tok,model
def complete(system:str,user:str,max_tokens=700):
    with MODEL_RUNTIME_LOCK:
        tok,model=load();messages=[{'role':'system','content':system},{'role':'user','content':user}]
        rendered=tok.apply_chat_template(messages,add_generation_prompt=True,tokenize=False,enable_thinking=False)
        inputs=tok(rendered,return_tensors='pt').to(model.device)
        with torch.inference_mode():out=model.generate(**inputs,max_new_tokens=max_tokens,do_sample=True,temperature=.65,top_p=.9,pad_token_id=tok.eos_token_id)
        return tok.decode(out[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True)
def _legacy_lyrics(card,form,duration_seconds=90):
    seconds=max(30,min(360,int(duration_seconds or 90)))
    line_count=4 if seconds<=45 else 6 if seconds<=75 else 8 if seconds<=120 else 10 if seconds<=210 else 12
    raw=complete(f'你是克制含蓄的中文古风歌词作者。只输出JSON，字段title和lines；lines必须恰好为{line_count}句，每句5到7个汉字。歌词要适合舒缓演唱，句意之间留有呼吸，不可声称治疗。',f'作品时长：{seconds}秒；意象：{card.imagery}；心境变化：{card.current}到{card.target}；结构：{form}')
    m=re.search(r'\{.*\}',raw,re.S)
    try:result=json.loads(m.group(0) if m else raw)
    except:result={'title':'无题','lines':[x.strip() for x in raw.splitlines() if x.strip()]}
    result['lines']=[str(x).strip() for x in (result.get('lines') or []) if str(x).strip()][:line_count]
    return result

def lyrics(card,form,duration_seconds=90):
    """Draft singable lyrics with restrained, stanza-level Chinese rhyme."""
    seconds=max(30,min(360,int(duration_seconds or 90)))
    line_count=4 if seconds<=45 else 6 if seconds<=75 else 8 if seconds<=120 else 10 if seconds<=210 else 12
    mode=getattr(card,'mode','xieyi')
    rhyme_character=(
        '调心模式的韵脚稳定、舒展，转韵要缓慢。'
        if mode=='tiaoxin' else
        '写意模式可以疏押和转韵，但不能整段完全散韵。'
    )
    system=(
        '你是克制、含蓄的中文古风歌词作者。只输出严格 JSON，'
        '只允许 title 和 lines 两个字段。lines 的每一项必须是纯歌词字符串，'
        '绝对不得输出分词、重音、呼吸、对象或其他内部分析。'
        f'lines 必须恰好 {line_count} 句，每句 5至8 个汉字。'
        '以四句为一个韵律单元：第2、4句句末用同韵或自然近韵，'
        '第1句可入韵也可自由，第3句优先自由。不足四句的尾段，最后两句用近韵轻轻收束。'
        '允许段落之间转韵，不要句句强押，不要重复同一个句末字，'
        '不要为押韵倒装或堆砌愁、楼、秋、舟等套语。'
        '句末优先选适合舒展演唱的实词和开口韵，不得以的、了、着、是等虚词收句。'
        '用现代普通话中自然、常见、易演唱的词组，少用生僻多音字和为仿古而生造的组合。'
        '句意之间要留有呼吸，不声称治疗效果。'+rhyme_character
    )
    user=(
        f'作品时长：{seconds}秒；'
        f'意象：{getattr(card,"imagery",[])}；'
        f'心境变化：{getattr(card,"current","")}到{getattr(card,"target","")}；'
        f'结构：{form}'
    )
    raw=complete(system,user)
    match=re.search(r'\{.*\}',raw,re.S)
    try:result=json.loads(match.group(0) if match else raw)
    except (json.JSONDecodeError,AttributeError):
        result={'title':'未题之作','lines':[line.strip() for line in raw.splitlines() if line.strip()]}
    raw_lines=result.get('lines') or []
    lines=[]
    for value in raw_lines:
        if isinstance(value,str):line=value.strip()
        elif isinstance(value,dict) and isinstance(value.get('phrases'),list):
            line=''.join(str(part).strip() for part in value['phrases'] if str(part).strip())
        else:continue
        if line:lines.append(line)
        if len(lines)>=line_count:break
    result={'title':str(result.get('title') or '未题之作').strip(),'lines':lines}
    return result

def analyze_lyric_prosody(lines:list[str])->list[dict]:
    """Analyze the final reviewed lyric once; never participate in writing it."""
    clean=[''.join(char for char in str(line) if '\u4e00'<=char<='\u9fff') for line in lines]
    clean=[line for line in clean if line]
    system=(
        '你是中文歌词的演唱韵律分析器，不得改写任何歌词。'
        '只输出严格 JSON：{"prosody":[...]}。prosody 必须与输入行数相同。'
        '每项只含 phrases、stress_index、breath_after。'
        'phrases 是二至四字的自然词组或演唱短语数组，顺序拼接后必须与原句逐字完全一致。'
        'stress_index 是整句唯一核心字在原句中从0开始的整数位置，优先选实词，不选的、了、而、与等虚词。'
        'breath_after 表示此句后是否需要明确换气。只分析，不输出解释。'
    )
    raw=complete(system,json.dumps({'lines':clean},ensure_ascii=False),520)
    candidate=raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    try:parsed=json.loads(candidate)
    except json.JSONDecodeError:
        obj=re.search(r'\{.*\}',candidate,re.S);array=re.search(r'\[.*\]',candidate,re.S)
        parsed=json.loads(obj.group(0) if obj else array.group(0) if array else candidate)
    items=parsed if isinstance(parsed,list) else parsed.get('prosody') if isinstance(parsed,dict) else None
    if not isinstance(items,list) or len(items)!=len(clean):raise ValueError('Lyric prosody analysis returned the wrong number of lines')
    result=[]
    for line,item in zip(clean,items):
        if not isinstance(item,dict):raise ValueError('Lyric prosody item is not an object')
        phrases=[str(value).strip() for value in item.get('phrases',[]) if str(value).strip()]
        if ''.join(phrases)!=line:raise ValueError('Lyric prosody phrases do not reproduce the reviewed lyric')
        stress=int(item.get('stress_index',max(0,len(line)-2)))
        if not 0<=stress<len(line):raise ValueError('Lyric stress index is outside the reviewed lyric')
        result.append({'phrases':phrases,'stress_index':stress,'breath_after':bool(item.get('breath_after',True))})
    return result

def enhance_card(card:dict)->dict:
    """Use the local model for nuance; keep therapeutic routing deterministic."""
    prompt=(
        '根据用户原话细化琴心卡。只输出JSON：current、target、imagery、sound、avoid。'
        'current和target各不超过18字；后三项是最多5个短语的字符串数组。'
        '不诊断、不承诺疗效、不强迫积极，不修改既定调心策略。\n'
        f"模式：{card['mode']}\n用户原话：{card['prompt']}\n"
        f"确定性基线：{json.dumps(card,ensure_ascii=False)}"
    )
    raw=complete('你是琴境的中文意象与心境理解器。输出必须克制、具体、可用于音乐编排。',prompt,420)
    match=re.search(r'\{.*\}',raw,re.S)
    parsed=json.loads(match.group(0) if match else raw)
    result=dict(card)
    for key in ('current','target'):
        if isinstance(parsed.get(key),str) and parsed[key].strip():result[key]=parsed[key].strip()[:36]
    for key in ('imagery','sound','avoid'):
        values=parsed.get(key)
        if isinstance(values,list):result[key]=[str(x).strip()[:24] for x in values if str(x).strip()][:5]
    result['provenance']={**card.get('provenance',{}),'semantic_enrichment':config.LLM_MODEL}
    return result

def enhance_dialogue(card:dict,baseline:dict,turn:int)->tuple[dict,dict]:
    """Infer nuance and one high-value follow-up while rules retain stopping authority."""
    prompt=(
        '理解用户原话，并判断为了作曲是否还值得追问一次。只输出JSON，字段：'
        'current、target、imagery、sound、avoid、should_continue、next_question、options。'
        'current和target不超过18字；数组最多5项；next_question只问一件事，语气温和具体。'
        '不要探问创伤原因、隐私或诊断；不要为了聊天而追问。若信息足以决定音乐的心境或意象、变化方向与边界，should_continue必须为false。'
        f'当前已追问{turn}轮，最多允许2轮。规则基线：{json.dumps(baseline,ensure_ascii=False)}\n'
        f"模式：{card['mode']}\n用户完整表达：{card['prompt']}\n琴心卡：{json.dumps(card,ensure_ascii=False)}"
    )
    raw=complete('你是琴境的克制型对话理解器。目标是用尽可能少的提问，取得足以作曲的高价值信息。',prompt,520)
    match=re.search(r'\{.*\}',raw,re.S);parsed=json.loads(match.group(0) if match else raw)
    result=dict(card)
    for key in ('current','target'):
        if isinstance(parsed.get(key),str) and parsed[key].strip():result[key]=parsed[key].strip()[:36]
    for key in ('imagery','sound','avoid'):
        values=parsed.get(key)
        if isinstance(values,list) and values:result[key]=[str(x).strip()[:24] for x in values if str(x).strip()][:5]
    result['provenance']={**card.get('provenance',{}),'semantic_enrichment':config.LLM_MODEL}
    # The deterministic information-gain policy owns stopping. The language
    # model may make the one required question more natural, but cannot skip a
    # missing high-value slot or prolong an already sufficient conversation.
    dialogue=dict(baseline)
    if not dialogue.get('should_continue'):
        dialogue.pop('question',None)
    return result,dialogue
