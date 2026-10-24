from __future__ import annotations
import json,threading,traceback,uuid,queue,shutil,re
from pathlib import Path
from fastapi import FastAPI,HTTPException,UploadFile,File,Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from . import config
from .schemas import PlanRequest,JobRequest,JobState,PreflightResult,TitleUpdate,SuggestionRequest
from .services.capabilities import detect
from .services.gpu_guard import require_gpu
from .services.planner import make_plan
from .services.prompt_compiler import compile_prompt
from .services.state_store import save as save_session,get as get_session
from .services.voice_library import list_voices,create_voice,get_voice,audio_path,delete_voice
from .services.title_service import compose_title,compose_legacy_title,clean_title
from .services.suggestion_service import suggestions
from .services.setup_manager import status as setup_status,start as start_setup,install_package as install_setup_package
from .services.update_manager import status as update_status,check as check_update,start as start_update,restart as restart_update,begin_background_checks

app=FastAPI(title="琴境 QinScape",version="0.1.0")
jobs:dict[str,dict]={}
job_queue:queue.Queue[tuple[str,JobRequest]]=queue.Queue()
@app.get('/api/health')
def health():return {"status":"ok","service":"qinscape","port":6006}
@app.get('/api/update')
def update_state():return update_status()
@app.post('/api/update/check')
def update_check():return check_update(force=True)
@app.post('/api/update/start')
def update_start():
    try:return start_update()
    except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc
@app.post('/api/update/restart')
def update_restart():
    try:return restart_update()
    except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc
@app.get('/api/setup')
def setup():return setup_status()
@app.post('/api/setup/start')
def setup_start(payload:dict|None=None):
    try:return start_setup((payload or {}).get('component'))
    except KeyError as exc:raise HTTPException(404,'部署项目不存在') from exc
    except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
    except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc
@app.post('/api/setup/components/{component}/package')
async def setup_package(component:str,file:UploadFile=File(...)):
    temporary=config.RUNTIME/'setup-staging'/f'{uuid.uuid4()}.upload';temporary.parent.mkdir(parents=True,exist_ok=True);size=0
    try:
        with temporary.open('wb') as output:
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>12*1024**3:raise ValueError('安装包超过 12 GB')
                output.write(chunk)
        return install_setup_package(component,file.filename or 'package',temporary)
    except KeyError as exc:raise HTTPException(404,'部署项目不存在') from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    finally:temporary.unlink(missing_ok=True)
@app.get('/api/capabilities')
def capabilities():return detect()
@app.get('/api/catalog')
def catalog():
    return {
        'ensemble_styles':[
            {'id':'silk_bamboo','name':'丝竹清和','instruments':['笛','箫','二胡','柔弦']},
            {'id':'plucked','name':'弹拨疏影','instruments':['扬琴','竖琴','三弦','轻拨弦']},
            {'id':'clear_space','name':'清空入境','instruments':['箫','竖琴','气声合唱','暖音垫']},
            {'id':'chamber','name':'东方室内乐','instruments':['长笛','双簧管','大提琴','室内弦乐']},
            {'id':'orchestral','name':'山河管弦','instruments':['木管','小提琴','大提琴','圆号','管弦乐团']},
        ],
        'instrument_groups':[
            {'id':'winds','name':'吹管','instruments':['箫','笛','长笛','双簧管']},
            {'id':'plucked','name':'弹拨','instruments':['筝','扬琴','三弦','竖琴','西塔琴','拇指琴']},
            {'id':'strings','name':'拉弦','instruments':['二胡','小提琴','大提琴','柔弦']},
            {'id':'space','name':'空间声部','instruments':['气声合唱','暖音垫','圆号']},
            {'id':'accents','name':'点景与节律','instruments':['木鱼','钟铃','太鼓']},
        ],
        'voices':[{'id':x['id'],'name':f"{x['name']}（{x.get('description', '预设人声')}）" if x.get('source_kind')=='preset' else x['name'],'installed':True,'source':'preset' if x.get('source_kind')=='preset' else 'user'} for x in list_voices()],
        'voice_candidates':[
            {'id':'asaritsu','name':'Asaritsu','languages':['zh','ja','en'],'license':'CC BY-NC-SA 4.0','commercial':False,'bundle':False,'url':'https://github.com/KakaruHayate/Asaritsu4Diffsinger'},
            {'id':'ria','name':'Ria','languages':['zh','yue','ja'],'license':'custom / whitelist','commercial':False,'bundle':False,'url':'https://github.com/RibosomeK/RiaDiffSinger'},
            {'id':'qixuan','name':'棋璇 Qixuan','languages':['zh','ja','en'],'license':'custom terms','commercial':False,'bundle':False,'url':'https://github.com/yqzhishen/qixuan-diffsinger'},
            {'id':'alemon','name':'Alemon','languages':['zh'],'license':'custom; online service requires permission','commercial':False,'bundle':False,'url':'https://github.com/tuskinekinase/alemon_ds'},
        ],
        'five_tones':[
            {'id':'gong','name':'宫','character':'稳定、承托、归中'},
            {'id':'shang','name':'商','character':'清肃、疏朗、收敛'},
            {'id':'jue','name':'角','character':'舒展、生发、流动'},
            {'id':'zhi','name':'徵','character':'明亮、温暖、通达'},
            {'id':'yu','name':'羽','character':'深静、下行、安定'},
        ],
    }
@app.get('/api/voices')
def voices():return list_voices()
@app.post('/api/suggestions')
def prompt_suggestions(req:SuggestionRequest):
    return suggestions(req.mode,req.prompt,req.exclude)
@app.post('/api/voices',status_code=201)
async def upload_voice(name:str=Form(...),language:str=Form('zh'),transcript:str=Form(...),consent:bool=Form(...),audio:UploadFile=File(...)):
    try:return create_voice(name=name,language=language,transcript=transcript,filename=audio.filename or '',content=await audio.read(),consent=consent)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@app.get('/api/voices/{voice_id}/audio')
def voice_audio(voice_id:str):
    path=audio_path(voice_id)
    if not path:raise HTTPException(404,'人声不存在')
    return FileResponse(path)
@app.delete('/api/voices/{voice_id}',status_code=204)
def remove_voice(voice_id:str):
    if not delete_voice(voice_id):raise HTTPException(404,'人声不存在')
@app.post('/api/sessions/plan')
def plan(req:PlanRequest):
    prior=get_session(req.session_id) if req.session_id else None
    if req.session_id and not prior:raise HTTPException(404,'会话不存在，无法继续诉说')
    effective=req
    event_type='initial_prompt'
    if prior:
        previous=prior['card'].get('prompt','').strip()
        combined=req.prompt.strip() if req.prompt.strip().startswith(previous) else f"{previous}\n补充：{req.prompt.strip()}"
        effective=req.model_copy(update={'prompt':combined});event_type='followup_prompt'
    turn=sum(1 for item in (prior or {}).get('history',[]) if item.get('type')=='followup_prompt')+(1 if prior else 0)
    result=make_plan(effective,turn=turn,finish_dialogue=req.finish_dialogue,previous_card=prior['card'] if prior else None)
    save_session(result['session_id'],result['card'],{"type":event_type,"prompt":req.prompt,"dialogue":result.get('dialogue',{})});return result
@app.get('/api/sessions/{session_id}')
def session(session_id:str):
    value=get_session(session_id)
    if not value:raise HTTPException(404,'会话不存在')
    return value
@app.patch('/api/sessions/{session_id}')
def revise_session(session_id:str,patch:dict):
    value=get_session(session_id)
    if not value:raise HTTPException(404,'会话不存在')
    card={**value['card'],**patch};return save_session(session_id,card,{"type":"user_revision","patch":patch})
@app.post('/api/preflight',response_model=PreflightResult)
def preflight(req:JobRequest):
    caps=detect();missing=[]
    if req.lyrics and req.approved_lyrics:
        lyric_chars=sum(len(re.sub(r'[^\w\u4e00-\u9fff]','',str(line))) for line in (req.approved_lyrics.get('lines') or []))
        natural_capacity=max(24,int(req.duration_seconds*1.1))
        if lyric_chars>natural_capacity:
            suggested=max(req.duration_seconds+15,min(360,int(lyric_chars/1.1+9)//10*10))
            missing.append(f'歌词共 {lyric_chars} 字，当前时长适合约 {natural_capacity} 字；请精简歌词或将时长延长至约 {suggested} 秒')
    if not caps['gpu']['available'] and not config.ALLOW_CPU_INFERENCE:missing.append('需要 CUDA GPU 才能开始生成')
    if not caps['models']['text2midi_code']:missing.append('Text2MIDI 代码尚未安装')
    if not caps['models']['text2midi_cached']:missing.append('Text2MIDI 模型权重尚未完整缓存')
    if not caps['models']['flan_tokenizer_cached']:missing.append('Text2MIDI 文本分词器尚未完整缓存')
    if not caps['renderers']['fluidsynth']:missing.append('FluidSynth 尚未安装，无法渲染合奏音频')
    if not caps['assets']['ensemble_soundfont']:missing.append('多乐器合奏音源尚未配置')
    known_voices={x['id'] for x in list_voices()}|set(caps['models']['vocal_voices'])
    if req.lyrics and req.voice!='instrumental-guide' and req.voice not in known_voices:missing.append(f'声线 {req.voice} 尚未安装或不存在；请先在人声库中选择可用声线')
    if req.lyrics and get_voice(req.voice) and not caps['models']['soulx_configured']:missing.append('SoulX-Singer 尚未在当前 GPU 环境配置')
    return {'ready':not missing,'missing':missing,'capabilities':caps}
@app.post('/api/lyrics/draft')
def draft_lyrics(req:JobRequest):
    require_gpu()
    from .services.pipeline import make_lyrics
    plan=compile_prompt(req)
    draft=make_lyrics(req.card,plan.get('form_plan'),req.duration_seconds)
    lines=draft.get('lines') or []
    draft['title']=compose_title(req.card,seed=req.seed or req.session_id or req.card.prompt,lyrics=True,lyric_lines=len(lines))
    return draft
@app.post('/api/jobs',response_model=JobState)
def create_job(req:JobRequest):
    require_gpu();check=preflight(req)
    if not check['ready']:raise HTTPException(409,{'code':'PREFLIGHT_FAILED','message':'；'.join(check['missing']),'missing':check['missing']})
    jid=str(uuid.uuid4());approved=clean_title((req.approved_lyrics or {}).get('title')) if req.lyrics else ''
    lyric_lines=len((req.approved_lyrics or {}).get('lines') or []) if req.lyrics else None
    initial=approved or compose_title(req.card,seed=req.seed if req.seed is not None else jid,lyrics=req.lyrics,lyric_lines=lyric_lines)
    jobs[jid]={"id":jid,"status":"queued","stage":"waiting","progress":0.0,"error":None,"artifacts":{},"title":initial,"original_title":initial,"request":req.model_dump()};job_queue.put((jid,req));return jobs[jid]
@app.get('/api/jobs')
def list_jobs():
    persisted=[]
    for manifest in sorted(config.OUTPUTS.glob('*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            item=json.loads(manifest.read_text(encoding='utf8'))
            if not item.get('title') or item.get('title')=='未题之作':
                lyric=manifest.parent/'lyrics.json';title=''
                if lyric.exists():title=clean_title(json.loads(lyric.read_text(encoding='utf8')).get('title'))
                plan=manifest.parent/'plan.json'
                if not title and plan.exists():title=compose_legacy_title(json.loads(plan.read_text(encoding='utf8')))
                item['title']=title or '未题之作';item['original_title']=item['title']
                manifest.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf8')
            persisted.append(item)
        except Exception:pass
    active=list(jobs.values());known={x['id'] for x in active};return active+[x for x in persisted if x.get('id') not in known]
@app.get('/api/jobs/{job_id}',response_model=JobState)
def get_job(job_id:str):
    if job_id in jobs:return jobs[job_id]
    manifest=config.OUTPUTS/job_id/'job.json'
    if manifest.exists():return json.loads(manifest.read_text(encoding='utf8'))
    raise HTTPException(404,"任务不存在")

DOWNLOAD_ARTIFACTS={
    'midi':('composition.mid','MIDI','audio/midi'),
    'instrumental':('instrumental.wav','纯音乐','audio/wav'),
    'song':('song.wav','歌曲','audio/wav'),
}

def _download_title(value:str|None)->str:
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',clean_title(value) or '琴境作品').strip(' .')
    return (value or '琴境作品')[:80]

@app.get('/api/jobs/{job_id}/download/{kind}')
def download_job_artifact(job_id:str,kind:str):
    try:canonical=str(uuid.UUID(job_id))
    except ValueError as exc:raise HTTPException(404,'作品不存在') from exc
    spec=DOWNLOAD_ARTIFACTS.get(kind)
    if not spec:raise HTTPException(404,'下载类型不存在')
    filename,label,media_type=spec;folder=config.OUTPUTS/canonical;path=folder/filename
    if not path.is_file():raise HTTPException(404,'作品文件不存在')
    manifest=folder/'job.json';data={}
    if manifest.exists():
        try:data=json.loads(manifest.read_text(encoding='utf8'))
        except (OSError,json.JSONDecodeError):data={}
    title=_download_title(data.get('title') or jobs.get(canonical,{}).get('title'))
    return FileResponse(path,media_type=media_type,filename=f'{title}-{label}{path.suffix}')
@app.delete('/api/jobs/{job_id}',status_code=204)
def delete_job(job_id:str):
    try:canonical=str(uuid.UUID(job_id))
    except ValueError as exc:raise HTTPException(404,'作品不存在') from exc
    active=jobs.get(canonical)
    if active and active.get('status') in {'queued','running'}:raise HTTPException(409,'作品仍在生成，暂时不能删除')
    root=config.OUTPUTS.resolve();target=(root/canonical).resolve()
    if target.parent!=root or not target.is_dir():raise HTTPException(404,'作品不存在')
    shutil.rmtree(target);jobs.pop(canonical,None)
@app.patch('/api/jobs/{job_id}/title')
def update_job_title(job_id:str,patch:TitleUpdate):
    try:canonical=str(uuid.UUID(job_id))
    except ValueError as exc:raise HTTPException(404,'作品不存在') from exc
    title=clean_title(patch.title)
    if not title:raise HTTPException(422,'标题不能为空')
    manifest=config.OUTPUTS/canonical/'job.json'
    active=jobs.get(canonical)
    if active:
        active.setdefault('original_title',active.get('title') or title);active['title']=title
    if manifest.exists():
        data=json.loads(manifest.read_text(encoding='utf8'));data.setdefault('original_title',data.get('title') or title);data['title']=title
        temporary=manifest.with_suffix('.json.tmp');temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(manifest)
        return {'id':canonical,'title':title,'original_title':data['original_title']}
    if active:return {'id':canonical,'title':title,'original_title':active['original_title']}
    raise HTTPException(404,'作品不存在')
def _run(jid:str,req:JobRequest):
    try:
        from .services.pipeline import run_pipeline
        jobs[jid].update(status='running',stage='compiling',progress=.08)
        plan=compile_prompt(req);folder=config.OUTPUTS/jid;folder.mkdir(parents=True,exist_ok=True);(folder/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
        artifacts=run_pipeline(req,plan,folder,lambda stage,p:jobs[jid].update(stage=stage,progress=p))
        title=jobs[jid].get('original_title') or compose_title(req.card,seed=req.seed if req.seed is not None else jid,lyrics=req.lyrics)
        urls={k:f'/media/{jid}/{Path(v).name}' for k,v in artifacts.items()};jobs[jid].update(status='complete',stage='complete',progress=1.0,artifacts=urls,title=title,original_title=title);(folder/'job.json').write_text(json.dumps({k:v for k,v in jobs[jid].items() if k!='request'},ensure_ascii=False,indent=2),encoding='utf8')
    except Exception as e:
        failed_stage=jobs[jid].get('stage','unknown');raw=str(e);low=raw.lower()
        if 'local_model_resource_missing' in low or 'local_files_only' in low:code,message='MODEL_RESOURCE','本地模型资源不完整，无法离线开始生成。'
        elif 'out of memory' in low or 'cuda' in low:code,message='GPU_RESOURCE','显卡资源不足，模型未能完成这一阶段。'
        elif 'timeout' in low or 'timed out' in low:code,message='STAGE_TIMEOUT','这一生成阶段超过了允许的等待时间。'
        elif 'soundfont' in low or 'fluidsynth' in low:code,message='AUDIO_RENDER','音色渲染没有完成，请检查合奏音源。'
        elif failed_stage=='text2midi':code,message='MELODY_GENERATION','旋律模型没有成功产出可用的 MIDI。'
        elif failed_stage in {'lyrics','mixing'} or 'voice' in low or 'singer' in low:code,message='VOCAL_GENERATION','歌词、人声或混音阶段没有完成。'
        elif 'no melodic notes' in low or 'midi' in low:code,message='INVALID_MIDI','生成结果中没有找到可继续编配的旋律。'
        else:code,message='GENERATION_FAILED','本次创作在生成过程中意外中止。'
        jobs[jid].update(status='failed',stage='failed',error=message,error_code=code,error_stage=failed_stage,error_detail=f"{raw}\n{traceback.format_exc()}");folder=config.OUTPUTS/jid;folder.mkdir(parents=True,exist_ok=True);(folder/'job.json').write_text(json.dumps({k:v for k,v in jobs[jid].items() if k!='request'},ensure_ascii=False,indent=2),encoding='utf8')

def _worker():
    while True:
        jid,req=job_queue.get()
        try:_run(jid,req)
        finally:job_queue.task_done()

threading.Thread(target=_worker,name='qinscape-gpu-worker',daemon=True).start()
begin_background_checks()

if config.WEB_DIST.exists():
    app.mount('/media',StaticFiles(directory=config.OUTPUTS),name='media')
    assets=config.WEB_DIST/'assets'
    if assets.exists():app.mount('/assets',StaticFiles(directory=assets),name='assets')
    @app.get('/{path:path}',include_in_schema=False)
    def spa(path:str):
        target=config.WEB_DIST/path
        return FileResponse(target if target.is_file() else config.WEB_DIST/'index.html')
