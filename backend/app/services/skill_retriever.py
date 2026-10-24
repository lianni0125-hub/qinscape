from __future__ import annotations
import json,re
from functools import lru_cache
from ..config import ROOT

@lru_cache
def _skills():
    p=ROOT/"skill"/"generated"/"composition_skills.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
def _grams(s):
    s=re.sub(r"[\s，。；：、,.!?！？]","",s);return set(s)|{s[i:i+2] for i in range(len(s)-1)}
def retrieve(text:str,limit:int=5):
    q=_grams(text);out=[]
    for s in _skills():
        c=s.get("cultural_frame") or {};hay=" ".join(str(c.get(k,"")) for k in ("work","background_layer","imagery_core","space_time","motion","affective_arc","cultural_archetype"));g=_grams(hay);score=sum(2 if len(x)==2 else 1 for x in q if x in g);out.append((score,s))
    return [s for score,s in sorted(out,key=lambda x:x[0],reverse=True)[:limit] if score>0] or [x[1] for x in sorted(out,key=lambda x:x[1]["work_id"])[:limit]]
