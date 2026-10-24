import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const IN=path.join(ROOT,'data','derived'), OUT=path.join(ROOT,'skill','generated');

function parseCsv(text){const rows=[];let row=[],cell='',q=false;for(let i=0;i<text.length;i++){const c=text[i],n=text[i+1];if(c==='"'&&q&&n==='"'){cell+='"';i++;}else if(c==='"')q=!q;else if(c===','&&!q){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!q){if(c==='\r'&&n==='\n')i++;row.push(cell);cell='';if(row.some(x=>x!==''))rows.push(row);row=[];}else cell+=c;}if(cell||row.length){row.push(cell);rows.push(row);}const h=rows.shift().map(x=>x.replace(/^\uFEFF/,''));return rows.map(r=>Object.fromEntries(h.map((x,i)=>[x,r[i]??''])));}
const read=n=>parseCsv(fs.readFileSync(path.join(IN,n),'utf8'));
const mean=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
const sd=a=>{const m=mean(a);return Math.sqrt(mean(a.map(x=>(x-m)**2)))||1;};
const z=(x,a)=>(x-mean(a))/sd(a);
const round=x=>Math.round(x*1000)/1000;

const features=read('score_features.csv'), works=read('works.csv'), motifs=read('motifs.csv');
const culture=parseCsv(fs.readFileSync(path.join(ROOT,'data','knowledge','work_culture.csv'),'utf8'));
const cultureByWork=new Map(culture.map(x=>[x.work,x]));
const sections=features.filter(x=>x.scope==='section').map(x=>Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/^(section|measures|note_events|rest_events|pitch_|.*ratio|.*_q|notes_per)/.test(k)&&v!==''?Number(v):v])));
const metrics=['notes_per_quarter','rest_duration_ratio','harmonic_proxy_ratio','pitch_mean','pitch_range','leap_ratio','duration_mean_q'];
const distributions=Object.fromEntries(metrics.map(k=>[k,sections.map(x=>x[k]).filter(Number.isFinite)]));
const byWork=new Map();for(const s of sections){if(!byWork.has(s.work))byWork.set(s.work,[]);byWork.get(s.work).push(s);}
for(const xs of byWork.values())xs.sort((a,b)=>a.section-b.section);

function role(s,i,xs){
 const activity=z(s.notes_per_quarter,distributions.notes_per_quarter)+z(s.leap_ratio,distributions.leap_ratio)+z(s.pitch_mean,distributions.pitch_mean);
 const quiet=z(s.rest_duration_ratio,distributions.rest_duration_ratio)+z(s.duration_mean_q,distributions.duration_mean_q);
 if(i===0)return 'opening'; if(i===xs.length-1)return 'closing';
 const maxAct=Math.max(...xs.map(x=>z(x.notes_per_quarter,distributions.notes_per_quarter)+z(x.leap_ratio,distributions.leap_ratio)+z(x.pitch_mean,distributions.pitch_mean)));
 if(activity>=maxAct-0.15&&activity>0.5)return 'peak';
 if(i>=Math.floor(xs.length*.65)&&quiet>0.3)return 'settling';
 return 'development';
}

const sectionSkills=[];const workForms=[];
for(const w of works){const xs=byWork.get(w.work)||[], total=xs.reduce((s,x)=>s+x.duration_q,0)||1;
 const rows=xs.map((s,i)=>{const r=role(s,i,xs);return {work_id:w.work_id,work:w.work,section:s.section,position:round((i+.5)/xs.length),duration_share:round(s.duration_q/total),role:r,
  density_z:round(z(s.notes_per_quarter,distributions.notes_per_quarter)),register_z:round(z(s.pitch_mean,distributions.pitch_mean)),range_z:round(z(s.pitch_range,distributions.pitch_range)),
  silence_z:round(z(s.rest_duration_ratio,distributions.rest_duration_ratio)),harmonic_z:round(z(s.harmonic_proxy_ratio,distributions.harmonic_proxy_ratio)),leap_z:round(z(s.leap_ratio,distributions.leap_ratio)),
  opening_midi:s.opening_midi,closing_midi:s.closing_midi};}); sectionSkills.push(...rows);
 const peak=rows.reduce((best,x)=>x.density_z+x.register_z+x.leap_z>best.density_z+best.register_z+best.leap_z?x:best,rows[0]||{position:0});
 const trajectory=(key)=>rows.map(x=>x[key]).join('|');
 workForms.push({work_id:w.work_id,work:w.work,sections:rows.length,peak_position:peak.position,
  density_arc:trajectory('density_z'),register_arc:trajectory('register_z'),silence_arc:trajectory('silence_z'),harmonic_arc:trajectory('harmonic_z'),
  roles:rows.map(x=>x.role).join('|'),opening_midi:rows.at(0)?.opening_midi??'',closing_midi:rows.at(-1)?.closing_midi??''});
}

const motifSkills=motifs.map(m=>({...m,section:Number(m.section),note_length:Number(m.note_length),occurrences:Number(m.occurrences),first_index:Number(m.first_index)}))
 .filter(x=>x.occurrences>=3).sort((a,b)=>b.occurrences-a.occurrences);
const archetypes={version:'0.1.0',principle:'Corpus-derived values are priors, not rules.',feature_meanings:{
 density_z:'event density; positive is busier',register_z:'mean pitch height',range_z:'pitch span',silence_z:'rest proportion',harmonic_z:'staccato-coded overtone proxy',leap_z:'intervals >= 5 semitones'},
section_roles:{opening:'establish tonal field and pacing',development:'transform or extend material',peak:'local maximum of density/register/leap activity',settling:'reduce activity and prepare closure',closing:'confirm final center and release'},
runtime_contract:{inputs:['entry_mode','user_prompt','arrangement_mode','lyrics_enabled'],shared_outputs:['imagery_arc','form_plan','pitch_plan','rhythm_plan','texture_plan','gesture_plan'],entry_policies:['xieyi','tiaoxin']}};

function csv(rows){if(!rows.length)return'';const k=Object.keys(rows[0]),e=v=>`"${String(v??'').replaceAll('"','""')}"`;return '\uFEFF'+[k.map(e).join(','),...rows.map(r=>k.map(x=>e(r[x])).join(','))].join('\r\n')+'\r\n';}
fs.mkdirSync(OUT,{recursive:true});fs.writeFileSync(path.join(OUT,'section_skills.csv'),csv(sectionSkills));fs.writeFileSync(path.join(OUT,'work_forms.csv'),csv(workForms));fs.writeFileSync(path.join(OUT,'motif_skills.csv'),csv(motifSkills));fs.writeFileSync(path.join(OUT,'skill_contract.json'),JSON.stringify(archetypes,null,2));
// Mid-rank percentile prevents a large tied zero group (e.g. no explicit rests)
// from being mislabeled as "high".
const percentile=(v,a)=>round((a.filter(x=>x<v).length+.5*a.filter(x=>x===v).length)/a.length);
const label=p=>p<.25?'low':p>.75?'high':'medium';
const compositions=workForms.map(form=>{
 const w=works.find(x=>x.work===form.work), c=cultureByWork.get(form.work), xs=byWork.get(form.work)||[];
 const avg=k=>mean(xs.map(x=>x[k]).filter(Number.isFinite));
 const top=motifSkills.filter(x=>x.work===form.work).slice(0,12).map(x=>({section:x.section,note_length:x.note_length,interval_shape:x.interval_shape,rhythm_ratio:x.rhythm_ratio,occurrences:x.occurrences}));
 return {skill_id:`${w.work_id}-composition-v1`,work_id:w.work_id,work:w.work,provenance:{dataset_commit:'e7feb0c2e7e4a5ba471c70723e7f81b9ae893902',score_source:w['琴谱来源'],tuning:w['定弦'],culture_evidence_status:c?.evidence_status??'missing'},
  cultural_frame:c??null,
  macro:{section_count:form.sections,roles:form.roles.split('|'),peak_position:form.peak_position,density_arc:form.density_arc.split('|').map(Number),register_arc:form.register_arc.split('|').map(Number),silence_arc:form.silence_arc.split('|').map(Number),harmonic_arc:form.harmonic_arc.split('|').map(Number)},
  global_priors:{density:label(percentile(avg('notes_per_quarter'),distributions.notes_per_quarter)),register:label(percentile(avg('pitch_mean'),distributions.pitch_mean)),range:label(percentile(avg('pitch_range'),distributions.pitch_range)),silence:label(percentile(avg('rest_duration_ratio'),distributions.rest_duration_ratio)),harmonic_proxy:label(percentile(avg('harmonic_proxy_ratio'),distributions.harmonic_proxy_ratio)),leap_activity:label(percentile(avg('leap_ratio'),distributions.leap_ratio))},
  meso:sectionSkills.filter(x=>x.work===form.work),micro_motifs:top,
  usage:{do:['use as a structural and gestural precedent','transpose and recombine short interval/rhythm shapes','preserve contrast and release across sections'],avoid:['copying a whole source melody','inferring omitted guqin techniques from MusicXML','treating cultural interpretation as verified history when evidence_status is title_inference']}};
});
fs.writeFileSync(path.join(OUT,'composition_skills.jsonl'),compositions.map(x=>JSON.stringify(x)).join('\n')+'\n','utf8');
const missingCulture=works.filter(x=>!cultureByWork.has(x.work)).map(x=>x.work);
console.log(JSON.stringify({works:workForms.length,sections:sectionSkills.length,retained_motifs:motifSkills.length,cultural_records:culture.length,composition_skills:compositions.length,missingCulture},null,2));
