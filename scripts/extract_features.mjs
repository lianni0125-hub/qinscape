import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { XMLParser } from 'fast-xml-parser';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DATASET = path.join(ROOT, 'sources', 'Guqin-Dataset', 'Guqin_Dataset_v1');
const OUT = path.join(ROOT, 'data', 'derived');
const STEP = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const arr = x => x == null ? [] : Array.isArray(x) ? x : [x];
const num = (x, d = 0) => Number.isFinite(Number(x)) ? Number(x) : d;
const round = x => Math.round(x * 1e6) / 1e6;

function files(dir, suffix) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? files(p, suffix) : e.name.endsWith(suffix) ? [p] : [];
  });
}

function parseCsv(text) {
  const rows = []; let row = [], cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i], n = text[i + 1];
    if (c === '"' && quoted && n === '"') { cell += '"'; i++; }
    else if (c === '"') quoted = !quoted;
    else if (c === ',' && !quoted) { row.push(cell); cell = ''; }
    else if ((c === '\n' || c === '\r') && !quoted) {
      if (c === '\r' && n === '\n') i++;
      row.push(cell); cell = '';
      if (row.some(x => x !== '')) rows.push(row);
      row = [];
    } else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const headers = rows.shift().map(x => x.replace(/^\uFEFF/, ''));
  return rows.map(r => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ''])));
}

function identity(p) {
  const stem = path.basename(p, '.xml');
  const m = stem.match(/^(.*)_([0-9]+)$/);
  return { work: m ? m[1] : stem, section: m ? Number(m[2]) : null };
}

function parseScore(p, scope) {
  const parser = new XMLParser({ ignoreAttributes: false, attributeNamePrefix: '@_',
    preserveOrder: false, parseTagValue: false, processEntities: false });
  const doc = parser.parse(fs.readFileSync(p, 'utf8'))['score-partwise'];
  const id = identity(p), source = path.basename(path.dirname(p));
  if (scope === 'section' && id.section == null) id.section = 1;
  const notes = [], warnings = [], timeSigs = new Set();
  let divisions = 1, cursor = 0, maxCursor = 0, measureCount = 0;
  for (const part of arr(doc.part)) {
    cursor = 0;
    for (const measure of arr(part.measure)) {
      measureCount++;
      const measureNo = num(measure['@_number'], measureCount);
      // Some files contain multiple <attributes> blocks in one measure.
      for (const attributes of arr(measure.attributes)) {
        divisions = num(attributes.divisions, divisions);
        for (const t of arr(attributes.time)) timeSigs.add(`${t.beats}/${t['beat-type']}`);
      }
      // Scores are monophonic in this dataset; backups are rare. Event order is retained.
      let lastNonChordOnset = cursor;
      for (const n of arr(measure.note)) {
        const duration = num(n.duration) / divisions;
        const chord = Object.hasOwn(n, 'chord');
        const onset = chord ? lastNonChordOnset : cursor;
        if (!chord) lastNonChordOnset = onset;
        const rest = Object.hasOwn(n, 'rest');
        let midi = null, pc = null;
        if (!rest && n.pitch) {
          const octave = num(n.pitch.octave, NaN), step = n.pitch.step;
          if (STEP[step] != null && Number.isFinite(octave)) {
            midi = 12 * (octave + 1) + STEP[step] + num(n.pitch.alter);
            pc = ((midi % 12) + 12) % 12;
          } else warnings.push(`bad pitch at measure ${measureNo}`);
        }
        const harmonic = n.notations?.articulations && Object.hasOwn(n.notations.articulations, 'staccato');
        notes.push({ work: id.work, source, scope, section: id.section, measure: measureNo,
          onset_q: round(onset), duration_q: round(duration), midi, pitch_class: pc,
          rest: Number(rest), chord: Number(chord), harmonic_proxy: Number(Boolean(harmonic)),
          voice: n.voice ?? '1' });
        if (!chord) cursor += duration;
        maxCursor = Math.max(maxCursor, onset + duration);
      }
    }
  }
  return { notes, meta: { path: path.relative(DATASET, p).replaceAll('\\', '/'), ...id, source, scope,
    measures: measureCount, duration_q: round(maxCursor), time_signatures: [...timeSigs].join('|'),
    warnings: [...new Set(warnings)].join('|') } };
}

function entropy(values) {
  const c = new Map(); for (const x of values) c.set(x, (c.get(x) ?? 0) + 1);
  return values.length ? -[...c.values()].reduce((s, n) => s + n / values.length * Math.log2(n / values.length), 0) : 0;
}
const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;
const median = a => !a.length ? null : [...a].sort((x,y)=>x-y)[Math.floor(a.length / 2)];

function summarize(notes, meta) {
  const snd = notes.filter(n => !n.rest && n.midi != null), rests = notes.filter(n => n.rest);
  const pitches = snd.map(n => n.midi), intervals = pitches.slice(1).map((x, i) => x - pitches[i]);
  const abs = intervals.map(Math.abs), dur = snd.map(n => n.duration_q).filter(x => x > 0);
  const total = Math.max(meta.duration_q, 1e-9), pc = new Map();
  for (const n of snd) pc.set(n.pitch_class, (pc.get(n.pitch_class) ?? 0) + 1);
  const topPc = [...pc].sort((a,b)=>b[1]-a[1]).slice(0,5).map(x=>x[0]).join('|');
  const ratio = (a, d) => round(a / Math.max(d, 1));
  return { ...meta, note_events: snd.length, rest_events: rests.length,
    notes_per_quarter: round(snd.length / total),
    rest_duration_ratio: round(rests.reduce((s,n)=>s+n.duration_q,0)/total),
    harmonic_proxy_ratio: ratio(snd.reduce((s,n)=>s+n.harmonic_proxy,0),snd.length),
    chord_note_ratio: ratio(snd.reduce((s,n)=>s+n.chord,0),snd.length),
    pitch_min: pitches.length ? Math.min(...pitches) : null, pitch_max: pitches.length ? Math.max(...pitches) : null,
    pitch_mean: mean(pitches) == null ? null : round(mean(pitches)), pitch_range: pitches.length ? Math.max(...pitches)-Math.min(...pitches) : null,
    pitch_class_entropy: round(entropy(snd.map(n=>n.pitch_class))), top_pitch_classes: topPc,
    stepwise_ratio: ratio(abs.filter(x=>x<=2).length,abs.length), leap_ratio: ratio(abs.filter(x=>x>=5).length,abs.length),
    ascending_ratio: ratio(intervals.filter(x=>x>0).length,intervals.length), descending_ratio: ratio(intervals.filter(x=>x<0).length,intervals.length),
    duration_mean_q: mean(dur)==null?null:round(mean(dur)), duration_median_q: median(dur),
    opening_midi: pitches.at(0)??null, closing_midi:pitches.at(-1)??null };
}

function motifs(notes) {
  const groups = new Map();
  for (const n of notes.filter(n=>n.scope==='section'&&!n.rest&&n.midi!=null)) {
    const k = `${n.work}\t${n.section}`; if (!groups.has(k)) groups.set(k, []); groups.get(k).push(n);
  }
  const out=[];
  for (const [key, seq] of groups) {
    const [work, sec] = key.split('\t'), pitch=seq.map(x=>x.midi), dur=seq.map(x=>x.duration_q);
    for(let size=3;size<=7;size++){
      const map=new Map();
      for(let i=0;i+size<=pitch.length;i++){
        const shape=pitch.slice(i,i+size-1).map((x,j)=>pitch[i+j+1]-x).join('|');
        const old=map.get(shape)??{occurrences:0,first_index:i,rhythm_ratio:dur.slice(i,i+size).map(x=>round(x/(dur[i]||1))).join('|')}; old.occurrences++; map.set(shape,old);
      }
      for(const [interval_shape,v] of [...map].sort((a,b)=>b[1].occurrences-a[1].occurrences).slice(0,12)) if(v.occurrences>=2)
        out.push({work,scope:'section',section:Number(sec),note_length:size,interval_shape,...v});
    }
  } return out;
}

function csv(rows) {
  if (!rows.length) return '';
  const keys=Object.keys(rows[0]), esc=v=>`"${String(v??'').replaceAll('"','""')}"`;
  return '\uFEFF'+[keys.map(esc).join(','),...rows.map(r=>keys.map(k=>esc(r[k])).join(','))].join('\r\n')+'\r\n';
}
function write(name, rows){ fs.writeFileSync(path.join(OUT,name),csv(rows),'utf8'); }

fs.mkdirSync(OUT,{recursive:true});
const refs=parseCsv(fs.readFileSync(path.join(DATASET,'reference.csv'),'utf8'));
const allNotes=[], summaries=[], failures=[];
for(const [scope,folder] of [['section','xml'],['whole','xml_no_split']]) for(const p of files(path.join(DATASET,folder),'.xml').sort()) {
  try { const x=parseScore(p,scope); allNotes.push(...x.notes); summaries.push(summarize(x.notes,x.meta)); }
  catch(error){failures.push({path:path.relative(DATASET,p),error:String(error)});}
}
const sectionCount=new Map(), whole=new Set();
for(const s of summaries) s.scope==='section'?sectionCount.set(s.work,(sectionCount.get(s.work)??0)+1):whole.add(s.work);
const works=refs.map((r,i)=>({work_id:`GQ${String(i+1).padStart(3,'0')}`,work:r['曲谱名称'],...r,section_count:sectionCount.get(r['曲谱名称'])??0,has_whole_score:Number(whole.has(r['曲谱名称']))}));
const motifRows=motifs(allNotes);
write('works.csv',works); write('score_features.csv',summaries); write('notes.csv',allNotes); write('motifs.csv',motifRows); write('parse_failures.csv',failures);
const report={dataset_commit:'e7feb0c2e7e4a5ba471c70723e7f81b9ae893902',reference_works:refs.length,
 parsed_whole_scores:summaries.filter(x=>x.scope==='whole').length,parsed_section_scores:summaries.filter(x=>x.scope==='section').length,
 note_rows:allNotes.length,motif_rows:motifRows.length,failures,
 unmatched_reference_works:refs.map(x=>x['曲谱名称']).filter(x=>!whole.has(x)), unmatched_whole_scores:[...whole].filter(x=>!refs.some(r=>r['曲谱名称']===x))};
fs.writeFileSync(path.join(OUT,'audit.json'),JSON.stringify(report,null,2),'utf8'); console.log(JSON.stringify(report,null,2));
