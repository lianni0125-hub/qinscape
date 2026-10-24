from __future__ import annotations
from ..schemas import JobRequest
from .skill_retriever import retrieve

def _resample(values:list,n:int)->list[float]:
    values=[float(x) for x in (values or [0])]
    if len(values)==1:return [round(values[0],3)]*n
    out=[]
    for i in range(n):
        at=i*(len(values)-1)/max(1,n-1);left=int(at);right=min(len(values)-1,left+1);mix=at-left
        out.append(round(values[left]*(1-mix)+values[right]*mix,3))
    return out

def _roles(source:list[str],n:int)->list[str]:
    if not source:source=['opening','development','peak','closing']
    roles=[source[round(i*(len(source)-1)/max(1,n-1))] for i in range(n)]
    roles[0]='opening';roles[-1]='closing'
    return roles

def _form_from_references(refs:list,seconds:int)->dict:
    target=3 if seconds<=75 else 4 if seconds<=150 else 5 if seconds<=270 else 6
    ranked=list(enumerate(refs[:5]))
    structure=min(ranked,key=lambda item:(abs(int(item[1]['macro'].get('section_count') or 1)-target),item[0]))[1] if ranked else None
    if not structure:return {'section_count':target,'roles':_roles([],target),'density_arc':[0]*target,'register_arc':[0]*target,'harmonic_arc':[0]*target,'peak_position':.62}
    blend=refs[:3];weights=[.55,.3,.15][:len(blend)];total=sum(weights);arcs={}
    for key in ('density_arc','register_arc','harmonic_arc'):
        sampled=[_resample(ref['macro'].get(key) or [0],target) for ref in blend]
        arcs[key]=[round(sum(row[i]*weights[j] for j,row in enumerate(sampled))/total,3) for i in range(target)]
    source_roles=[x.get('role','development') for x in structure.get('meso',[])] or structure['macro'].get('roles') or []
    peaks=[float(ref['macro'].get('peak_position') or .62) for ref in blend]
    return {'section_count':target,'roles':_roles(source_roles,target),'density_arc':arcs['density_arc'],'register_arc':arcs['register_arc'],'harmonic_arc':arcs['harmonic_arc'],'peak_position':round(sum(value*weights[i] for i,value in enumerate(peaks))/total,3),'structure_skill_id':structure['skill_id']}

def compile_prompt(job:JobRequest)->dict:
    c=job.card;refs=retrieve(" ".join([c.prompt,*c.imagery,c.current,c.target]));generation_seconds=min(job.duration_seconds+12,372);form=_form_from_references(refs,generation_seconds)
    descriptions={'silk_bamboo':'bamboo flute, xiao, erhu and restrained strings','plucked':'zheng, yangqin, sanxian and small plucked strings','clear_space':'xiao, harp, breath choir and a very soft warm pad','chamber':'flute, oboe, cello and chamber strings','orchestral':'woodwinds, violin, cello, horn and restrained orchestral strings'}
    instruments=descriptions[job.ensemble_style];density=refs[0]['global_priors']['density'] if refs else 'medium';precedents=', '.join(x['work'] for x in refs[:3])
    caption=(f"A contemplative Chinese-inspired piece featuring {instruments}. Compose approximately {generation_seconds} seconds of usable music, allowing a little extra material for clean trimming to {job.duration_seconds} seconds. "
             f"The imagery is {', '.join(c.imagery)}. The emotional journey moves from {c.current} toward {c.target}. Use a {density} note density, {form['section_count']} perceptible sections, a structural peak near {round(form['peak_position']*100)} percent, pentatonic melodic emphasis, organic tempo breathing, and a gentle resolved ending. "
             f"Use the structural and gestural grammar abstracted from {precedents}; do not quote their melodies. Avoid {', '.join(c.avoid) or 'abrupt stylistic changes'}.")
    if job.preferred_instruments:caption+=f" Preferred ensemble colors: {', '.join(job.preferred_instruments)}."
    if job.lead_instrument:caption+=f" Feature {job.lead_instrument} as the principal melodic voice."
    if job.excluded_instruments:caption+=f" Strictly avoid: {', '.join(job.excluded_instruments)}."
    caption+=f" Five-tone modal journey: {' to '.join(c.five_tone_path)}. {c.five_tone_rationale}."
    selected=list(refs[:3]);structure=next((x for x in refs if x['skill_id']==form.get('structure_skill_id')),None)
    if structure and all(x['skill_id']!=structure['skill_id'] for x in selected):selected.append(structure)
    references=[{'skill_id':x['skill_id'],'work':x['work'],'use':'structure' if x['skill_id']==form.get('structure_skill_id') else ('gesture' if i==0 else 'contour'),'macro':x['macro'],'meso':x.get('meso',[]),'motifs':x['micro_motifs'][:8]} for i,x in enumerate(selected)]
    return {'caption':caption,'references':references,'form_plan':form,'five_tone_path':c.five_tone_path,'five_tone_rationale':c.five_tone_rationale,'arrangement':job.arrangement,'ensemble_style':job.ensemble_style,'lead_instrument':job.lead_instrument,'preferred_instruments':job.preferred_instruments,'excluded_instruments':job.excluded_instruments,'lyrics':job.lyrics,'duration_seconds':generation_seconds,'requested_duration_seconds':job.duration_seconds}
