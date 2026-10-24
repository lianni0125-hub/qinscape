import fs from'node:fs';import path from'node:path';import{fileURLToPath}from'node:url';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const skills=fs.readFileSync(path.join(ROOT,'skill','generated','composition_skills.jsonl'),'utf8').trim().split('\n').map(JSON.parse);
const args=process.argv.slice(2),get=k=>{const i=args.indexOf(k);return i>=0?args[i+1]:''};
const prompt=get('--prompt')||get('--imagery')||'',work=get('--work'),mode=get('--mode')||'xieyi',limit=Number(get('--limit')||5);
if(!prompt&&!work){console.error('Usage: npm run query -- --mode xieyi --prompt "秋江月夜，先清冷后安定"');process.exit(2)}
const grams=s=>{s=String(s).replace(/[\s，。；：、,.!?！？]/g,'');const a=new Set([...s]);for(let i=0;i<s.length-1;i++)a.add(s.slice(i,i+2));return a};
const q=grams(`${prompt}${work}`),weight={official_work_note:1.2,literary_anchor:1.1,traditional_lore:1,source_score_context:.9,composer_context_needed:.7,title_inference:.65};
const scored=skills.map(s=>{const c=s.cultural_frame||{},text=[s.work,c.background_layer,c.imagery_core,c.space_time,c.motion,c.affective_arc,c.cultural_archetype].join(' '),t=grams(text);let overlap=0;for(const x of q)if(t.has(x))overlap+=x.length===2?2:1;if(work===s.work)overlap+=100;return{score:overlap*(weight[c.evidence_status]||.5),skill:s}}).sort((a,b)=>b.score-a.score).slice(0,limit);
const output={mode,prompt,notice:mode==='tiaoxin'?'Separate classical mapping, traditional inference, and product strategy; choose 和/泄/制/养 before tones, with no fixed tone sequence and wellbeing-only claims.':'Build an imagery arc before selecting.',matches:scored.map(({score,skill:s})=>({score,skill_id:s.skill_id,work:s.work,cultural_frame:s.cultural_frame,global_priors:s.global_priors,macro:s.macro,micro_motifs:s.micro_motifs.slice(0,5)}))};
console.log(JSON.stringify(output,null,2));
