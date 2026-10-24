"""End-to-end acceptance test for a running QinScape GPU deployment."""
import argparse,json,time,urllib.request,urllib.error

def request(base,path,method='GET',payload=None):
    data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
    req=urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)

parser=argparse.ArgumentParser()
parser.add_argument('--base',default='http://127.0.0.1:6006')
parser.add_argument('--arrangement',choices=['ensemble'],default='ensemble')
parser.add_argument('--lyrics',action='store_true',help='also verify lyric and vocal-MIDI generation without requiring a voicebank')
parser.add_argument('--timeout',type=int,default=1200)
args=parser.parse_args();base=args.base.rstrip('/')

caps=request(base,'/api/capabilities')
if not caps['gpu']['available']:raise SystemExit('FAIL: CUDA GPU not available')
planned=request(base,'/api/sessions/plan','POST',{'mode':'xieyi','prompt':'雨后空山，松风渐远，月色从云间缓缓显露'})
job_request={'session_id':planned['session_id'],'card':planned['card'],'arrangement':args.arrangement,'lyrics':args.lyrics,'voice':'instrumental-guide','duration_seconds':30,'seed':2026}
check=request(base,'/api/preflight','POST',job_request)
if not check['ready']:raise SystemExit('FAIL preflight: '+'; '.join(check['missing']))
created=request(base,'/api/jobs','POST',job_request);deadline=time.time()+args.timeout
while time.time()<deadline:
    state=request(base,f"/api/jobs/{created['id']}")
    print(f"{state['status']:>8} {state['progress']*100:5.1f}% {state['stage']}",flush=True)
    if state['status']=='failed':raise SystemExit('FAIL generation: '+str(state['error']))
    if state['status']=='complete':break
    time.sleep(3)
else:raise SystemExit('FAIL: generation timed out')

required={'midi','instrumental'}|({'lyrics','vocal_melody'} if args.lyrics else set())
missing=required-set(state['artifacts'])
if missing:raise SystemExit('FAIL missing artifacts: '+', '.join(sorted(missing)))
for name in required:
    with urllib.request.urlopen(base+state['artifacts'][name],timeout=60) as response:
        if len(response.read(64))==0:raise SystemExit(f'FAIL empty artifact: {name}')
print('PASS: QinScape GPU end-to-end smoke test')
