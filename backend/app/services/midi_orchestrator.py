from __future__ import annotations
from pathlib import Path
import copy,hashlib,math
import pretty_midi

try:
    import jieba
except ImportError:
    jieba=None

PALETTES={
    'silk_bamboo':[(73,'Dizi / Flute','lead'),(77,'Xiao / Shakuhachi','response'),(110,'Erhu / Fiddle','echo'),(48,'Soft strings','sustain')],
    'plucked':[(107,'Zheng','lead'),(15,'Yangqin / Dulcimer','response'),(106,'Sanxian / Shamisen','echo'),(108,'Kalimba','echo')],
    'clear_space':[(77,'Xiao / Shakuhachi','lead'),(46,'Harp','echo'),(52,'Breath choir','sustain'),(89,'Warm pad','sustain')],
    'chamber':[(73,'Flute','lead'),(68,'Oboe','response'),(42,'Cello','sustain'),(48,'Chamber strings','sustain')],
    'orchestral':[(68,'Oboe','lead'),(73,'Flute','response'),(40,'Violin','echo'),(42,'Cello','sustain'),(60,'French horn','sustain'),(48,'Orchestral strings','sustain')],
}
INSTRUMENTS={
    '笛':(73,'Dizi / Flute','lead'),'笛子':(73,'Dizi / Flute','lead'),'长笛':(73,'Flute','lead'),
    '箫':(77,'Xiao / Shakuhachi','lead'),'二胡':(110,'Erhu / Fiddle','lead'),
    '扬琴':(15,'Yangqin / Dulcimer','lead'),'竖琴':(46,'Harp','echo'),'三弦':(106,'Sanxian / Shamisen','lead'),
    '大提琴':(42,'Cello','sustain'),'小提琴':(40,'Violin','echo'),'双簧管':(68,'Oboe','lead'),
    '柔弦':(48,'Soft strings','sustain'),'弦乐':(48,'Soft strings','sustain'),'圆号':(60,'French horn','sustain'),
    '气声合唱':(52,'Breath choir','sustain'),'暖音垫':(89,'Warm pad','sustain'),
    '筝':(107,'Zheng','lead'),'西塔琴':(104,'Sitar','response'),'拇指琴':(108,'Kalimba','echo'),
    '木鱼':(115,'Woodblock','echo'),'钟铃':(112,'Tinkle bell','echo'),'太鼓':(116,'Taiko drum','echo'),
}
TONE_PITCH_CLASS={'gong':0,'shang':2,'jue':4,'zhi':7,'yu':9}
TONE_COLORS={
    'gong':['大提琴','柔弦','筝','暖音垫'],
    'shang':['箫','双簧管','笛','钟铃'],
    'jue':['笛','筝','扬琴','拇指琴'],
    'zhi':['长笛','小提琴','筝','圆号'],
    'yu':['箫','二胡','木鱼','大提琴'],
}
VOCAL_FUNCTION_CHARS=set('的了着过吗呢吧啊呀兔而与及于在把被将又也都很更便却')
LYRIC_WORDS={
    '不知','归处','月满','长亭','清风','徐来','水波','不兴','林深','竹影',
    '风过','声幽','竹风','林声','渐远','似诉','林外','竹间','流光','不息',
    '风起','声停','心远','意静','松风','松涛','云水','烟波','暮色','晨光',
    '月色','月影','疏影','空山','远山','青山','山水','江月','秋水','春水',
    '落花','飞花','归舟','孤舟','渔火','清泉','幽谷','竹林','梅影','鹤影',
    '琴声','弦音','余音','回声','心绪','此刻','梦里','人间','天涯','故园',
}
if jieba is not None:
    for _lyric_word in LYRIC_WORDS:
        jieba.add_word(_lyric_word,freq=200000)

def _fallback_lyric_phrases(line):
    phrases=[];cursor=0
    while cursor<len(line):
        width=2 if len(line)-cursor!=3 else 3
        phrases.append(''.join(line[cursor:cursor+width]));cursor+=width
    return phrases

def _segment_lyric_line(line):
    """Segment approved lyrics locally without ever changing a character."""
    text=''.join(line)
    if not text:return []
    if jieba is None:return _fallback_lyric_phrases(text)
    tokens=[token.strip() for token in jieba.cut(text,HMM=False) if token.strip()]
    phrases=[]
    for token in tokens:
        if len(token)<=4:phrases.append(token)
        else:phrases.extend(_fallback_lyric_phrases(token))
    merged=[]
    for token in phrases:
        if len(token)==1 and merged and len(merged[-1])<4:merged[-1]+=token
        elif merged and len(merged[-1])==1 and len(merged[-1])+len(token)<=4:merged[-1]+=token
        else:merged.append(token)
    return merged if ''.join(merged)==text else _fallback_lyric_phrases(text)

def _line_prosody(line,meta=None):
    meta=meta if isinstance(meta,dict) else {}
    phrases=meta.get('phrases') if isinstance(meta.get('phrases'),list) else []
    if ''.join(phrases)!=''.join(line):
        phrases=_segment_lyric_line(line)
    breaks=[];offset=0
    for phrase in phrases[:-1]:offset+=len(phrase);breaks.append(offset)
    try:stress=max(0,min(len(line)-1,int(meta.get('stress_index'))))
    except (TypeError,ValueError):
        # Prefer the end of a substantial content phrase near the latter half
        # of the sentence; this is closer to Mandarin sung emphasis than a
        # fixed character position.
        candidates=[];offset=0
        for phrase in phrases:
            local_content=[i for i,char in enumerate(phrase) if char not in VOCAL_FUNCTION_CHARS]
            end=offset+(local_content[-1] if local_content else len(phrase)-1)
            content=len(local_content)
            candidates.append((content,-abs((end+1)/max(1,len(line))-.64),end))
            offset+=len(phrase)
        stress=max(candidates)[2] if candidates else max(0,len(line)-2)
    return {'phrases':phrases,'breaks':set(breaks),'stress_index':stress,'breath_after':bool(meta.get('breath_after',True))}

def derive_lyric_prosody(lines):
    """Analyze only the final, user-approved lyric text for score planning."""
    result=[]
    for raw in lines or []:
        line=[char for char in str(raw) if '\u4e00'<=char<='\u9fff']
        if not line:continue
        item=_line_prosody(line)
        result.append({'phrases':item['phrases'],'stress_index':item['stress_index'],'breath_after':item['breath_after']})
    return result

def _lyric_rhythm_weights(line,meta=None):
    """Phrase-aware Mandarin timing: light particles yield to content/cadence."""
    prosody=_line_prosody(line,meta)
    weights=[]
    for index,char in enumerate(line):
        weight=1+.10*math.sin((index+1)*1.7)
        if char in VOCAL_FUNCTION_CHARS:weight*=.76
        if index==prosody['stress_index']:weight+=.24
        if index+1 in prosody['breaks'] and char not in VOCAL_FUNCTION_CHARS:weight+=.16
        if index in prosody['breaks']:weight+=.07
        if index==len(line)-1:weight+=.62
        elif index==len(line)-2 and char not in VOCAL_FUNCTION_CHARS:weight+=.12
        weights.append(max(.56,weight))
    return weights

def shape_accompaniment_for_vocals(path:Path,sections:list[dict]|None):
    """Create musical space for singing without another generation pass."""
    if not sections:return path
    midi=pretty_midi.PrettyMIDI(str(path));windows=[(float(x['start']),float(x['end'])) for x in sections if float(x.get('end',0))>float(x.get('start',0))]
    for track_index,track in enumerate(midi.instruments):
        if track.is_drum:continue
        shaped=[]
        for index,note in enumerate(sorted(track.notes,key=lambda item:(item.start,item.pitch))):
            active=next(((start,end) for start,end in windows if note.start<end and note.end>start),None)
            if active:
                # The principal melodic instrument becomes sparse and quieter
                # under lyrics; supporting parts retain harmony at lower level.
                if track_index==0 and note.duration<.7 and index%3==1:continue
                note.velocity=max(24,round(note.velocity*(.72 if track_index==0 else .84)))
                note.end=max(note.start+.04,min(note.end,active[1]-.025 if note.end>active[1] else note.end))
            shaped.append(note)
        track.notes=shaped
    midi.write(str(path));return path

def _nearest_singable_pitch(pitches,desired,previous=None,max_leap=5):
    candidates=list(pitches)
    if previous is not None:
        nearby=[value for value in candidates if abs(value-previous)<=max_leap]
        if nearby:candidates=nearby
    return min(candidates,key=lambda value:(abs(value-desired),abs(value-(previous if previous is not None else desired))))

def _apply_motif_grammar(track,motifs,seed,sections=3):
    """Recombine short corpus contours without copying source melodies."""
    notes=sorted(track.notes,key=lambda x:(x.start,x.pitch))
    if len(notes)<5 or not motifs:return
    gaps=[max(0,notes[i+1].start-notes[i].end) for i in range(len(notes)-1)]
    positive=sorted(x for x in gaps if x>0);median=positive[len(positive)//2] if positive else .08;threshold=max(.16,median*2.2)
    offsets=[i+1 for i,gap in enumerate(gaps) if gap>=threshold and 2<=i+1<len(notes)-2]
    for boundary in [round(len(notes)*i/max(1,sections)) for i in range(1,sections)]:
        nearest=min(range(2,len(notes)-2),key=lambda i:abs(i-boundary));offsets.append(nearest)
    offsets=sorted(set(offsets))[::2] or list(range(3,len(notes)-3,13))
    for offset in offsets:
        motif=motifs[(offset+(seed or 0))%len(motifs)]
        try:
            intervals=[int(x) for x in motif['interval_shape'].split('|')]
            ratios=[max(.1,float(x)) for x in motif['rhythm_ratio'].split('|')]
        except (KeyError,ValueError):continue
        count=min(len(intervals)+1,len(ratios),len(notes)-offset,5)
        if count<3:continue
        phrase=notes[offset:offset+count];invert=-1 if hashlib.sha256(f'{seed}:{offset}'.encode()).digest()[0]%3==0 else 1
        base=phrase[0].pitch
        for i in range(1,count):
            base=max(36,min(88,base+intervals[i-1]*invert));phrase[i].pitch=base
        start=phrase[0].start;span=max(.3,phrase[-1].end-start);weights=ratios[:count];unit=span/sum(weights);cursor=start
        for note,weight in zip(phrase,weights):
            note.start=cursor;note.end=cursor+unit*weight*.9;cursor+=unit*weight

def apply_skill_plan(source:Path,target:Path,plan:dict,seed:int|None=None):
    """Make corpus-derived macro arcs operational instead of prompt-only.

    Text2MIDI supplies material; QinScape shapes density, register and closure by
    section. Deterministic hashing thins notes without global random state.
    """
    midi=pretty_midi.PrettyMIDI(str(source));macro=plan.get('form_plan') or {};density=macro.get('density_arc') or [0];register=macro.get('register_arc') or [0];roles=macro.get('roles') or [];n=max(int(macro.get('section_count') or len(density)),1);end=max(midi.get_end_time(),.01);peak=float(macro.get('peak_position') or .62)
    for track in midi.instruments:
        kept=[]
        for note in track.notes:
            position=((note.start+note.end)/2)/end;idx=min(n-1,int(position*n));dz=float(density[idx] if idx<len(density) else 0);rz=float(register[idx] if idx<len(register) else 0);role=roles[idx] if idx<len(roles) else 'development'
            digest=hashlib.sha256(f'{seed}:{track.program}:{note.start:.4f}:{note.pitch}'.encode()).digest();u=int.from_bytes(digest[:4],'big')/2**32
            role_weight={'opening':-.08,'intro':-.08,'development':.03,'peak':.13,'climax':.13,'closing':-.1,'coda':-.1}.get(role,0);peak_weight=max(0,1-abs(position-peak)/.18)*.12
            keep=max(.34,min(1,.75+dz*.11+role_weight+peak_weight))
            if u>keep and not track.is_drum:continue
            if not track.is_drum:note.pitch=max(28,min(96,note.pitch+round(rz*1.5)))
            note.velocity=max(28,min(108,round(note.velocity*(.9+max(-1.5,min(1.5,dz))*.08))))
            kept.append(note)
        track.notes=kept
    # Give the final phrase an audible release and stable pentatonic landing.
    melodic=[x for x in midi.instruments if not x.is_drum and x.notes]
    if melodic:
        lead=max(melodic,key=lambda x:len(x.notes));refs=plan.get('references') or [];motifs=[motif for ref in refs[:3] for motif in ref.get('motifs',[])[:4]];_apply_motif_grammar(lead,motifs,seed,n)
        duration=float(plan.get('duration_seconds') or 0)
        if duration>0:
            for instrument in midi.instruments:instrument.notes=[x for x in instrument.notes if x.start<duration]
            for instrument in midi.instruments:
                for note in instrument.notes:note.end=min(note.end,duration)
        tail=sorted(lead.notes,key=lambda x:x.start)[-max(1,min(6,len(lead.notes))):]
        for i,note in enumerate(tail):note.velocity=max(30,round(note.velocity*(1-.06*i)))
        pcs={0,2,4,7,9};last=max(lead.notes,key=lambda x:x.end)
        tone_path=plan.get('five_tone_path') or ['gong'];target_pc=TONE_PITCH_CLASS.get(tone_path[-1],0)
        candidates=[p for p in range(last.pitch-6,last.pitch+7) if p%12==target_pc]
        last.pitch=min(candidates,key=lambda p:abs(p-last.pitch)) if candidates else last.pitch
    midi.write(str(target));return target

def _ensemble_from_lead(midi,lead,specs,form_plan=None):
    end=max(midi.get_end_time(),1);phrases=sorted(lead.notes,key=lambda n:n.start);tracks=[];bar=4*60/72;form=form_plan or {};sections=max(1,int(form.get('section_count') or 1));harmonic=form.get('harmonic_arc') or [0];roles=form.get('roles') or []
    def active(at,index):
        if not form_plan:return True
        section=min(sections-1,int(at/end*sections));hz=float(harmonic[section] if section<len(harmonic) else 0);role=roles[section] if section<len(roles) else 'development'
        allowance=1+(1 if hz>-.35 else 0)+(1 if hz>.25 else 0)+(1 if hz>.8 else 0)
        if role in {'peak','climax'}:allowance+=1
        if role in {'opening','intro','closing','coda'}:allowance=max(1,allowance-1)
        return index<allowance
    for index,(program,name,role) in enumerate(specs):
        track=pretty_midi.Instrument(program=program,name=name)
        if role=='sustain':
            root=43+index*2
            for start in [x*bar for x in range(math.ceil(end/bar)) if active(x*bar,index)]:
                pitch=root+[0,7,5,9][int(start/bar)%4];track.notes.append(pretty_midi.Note(velocity=28+index*2,pitch=pitch,start=start,end=min(start+bar*.92,end)))
        else:
            every=7+index
            for i,n in enumerate(phrases):
                if active(n.start,index) and i%every==(3+index)%every and n.duration>.16:
                    shift=12 if role=='response' else (-12 if index%2 else 7);track.notes.append(pretty_midi.Note(velocity=max(25,n.velocity-28-index*2),pitch=max(36,min(91,n.pitch+shift)),start=n.start+.06*(index+1),end=min(n.end+.22,end)))
        if track.notes:tracks.append(track)
    return tracks

def _selected_specs(style,preferred,excluded,tone_path=None,lead_instrument=''):
    excluded_text=' '.join(excluded).lower()
    excluded_programs={INSTRUMENTS[name.strip()][0] for name in excluded if name.strip() in INSTRUMENTS}
    main_tone=(tone_path or ['gong'])[0]
    ordered_names=[lead_instrument,*preferred,*(TONE_COLORS.get(main_tone,[]) if tone_path else [])]
    candidates=[INSTRUMENTS[name.strip()] for name in ordered_names if name.strip() in INSTRUMENTS]
    candidates.extend(PALETTES.get(style,PALETTES['silk_bamboo']))
    specs=[]
    for spec in candidates:
        if spec[0] in excluded_programs or any(token.lower() in excluded_text for token in spec[1].split(' / ')):continue
        if all(spec[1]!=current[1] for current in specs):specs.append(spec)
    # 气质模板只提供候选权重；实际编制由主音、偏好和排除项共同选出。
    target_size=(len(PALETTES.get(style,PALETTES['silk_bamboo'])) if not tone_path and not preferred and not lead_instrument else max(3,min(6,3+len(preferred)+(1 if len(tone_path or [])>1 else 0))))
    specs=specs[:target_size]
    return specs or PALETTES['clear_space'][:2]

def arrange(source:Path,target:Path,mode:str='ensemble',style:str='silk_bamboo',preferred:list[str]|None=None,excluded:list[str]|None=None,tone_path:list[str]|None=None,lead_instrument:str='',form_plan:dict|None=None):
    midi=pretty_midi.PrettyMIDI(str(source))
    melodic=[x for x in midi.instruments if not x.is_drum and x.notes]
    if not melodic:raise RuntimeError('Text2MIDI returned no melodic notes')
    specs=_selected_specs(style,preferred or [],excluded or [],tone_path,lead_instrument)
    lead=max(melodic,key=lambda x:sum(n.end-n.start for n in x.notes));lead.program=specs[0][0];lead.name=specs[0][1]
    midi.instruments=[lead,*_ensemble_from_lead(midi,lead,specs[1:],form_plan)]
    midi.write(str(target));return target

def fit_midi_duration(source:Path,target:Path,duration:float):
    """Remove leading silence, extend short forms, and cap at the chosen duration."""
    midi=pretty_midi.PrettyMIDI(str(source));notes=[note for track in midi.instruments for note in track.notes]
    if not notes:raise RuntimeError('The arranged MIDI contains no notes')
    shift=max(0,min(note.start for note in notes)-.04)
    for track in midi.instruments:
        original=[]
        for note in sorted(track.notes,key=lambda item:(item.start,item.pitch)):
            start=max(0,note.start-shift);end=max(start+.03,note.end-shift)
            original.append((note.velocity,note.pitch,start,end))
        fitted=[];source_end=max((item[3] for item in original),default=0)
        # Preserve the generated phrase, then repeat it as musical sections when
        # Text2MIDI returns a fragment shorter than the requested work.
        cycle=max(.5,source_end+.18)
        repeats=max(1,math.ceil(duration/cycle))
        for repeat in range(repeats):
            offset=repeat*cycle
            for velocity,pitch,start,end in original:
                at=start+offset
                if at>=duration:continue
                fitted.append(pretty_midi.Note(velocity=velocity,pitch=pitch,start=at,end=min(end+offset,duration)))
        track.notes=fitted
    midi.write(str(target));return target

def extract_vocal_melody(source:Path,target:Path,lyrics:dict|None=None,five_tone_path:list[str]|None=None):
    midi=pretty_midi.PrettyMIDI(str(source));tracks=[x for x in midi.instruments if not x.is_drum and x.notes]
    lead=max(tracks,key=lambda x:sum(n.end-n.start for n in x.notes))
    if lyrics and lyrics.get('lines'):
        import re
        lines=[[c for c in re.sub(r'[^\w\u4e00-\u9fff]','',str(line))] for line in lyrics['lines']]
        lines=[line for line in lines if line];syllables=[c for line in lines for c in line]
        source_notes=sorted(lead.notes,key=lambda n:n.start)
        if syllables and source_notes:
            total_chars=max(1,len(syllables))
            score_end=max(n.end for track in tracks for n in track.notes)
            intro=min(8.0,max(2.4,score_end*.09));outro=min(7.0,max(2.0,score_end*.08))
            start=intro;end=max(start+2.0,score_end-outro)
            # Divide the song into sung islands separated by real instrumental
            # responses instead of stretching one continuous vocal across it.
            block_count=2 if len(lines)<=6 else 3 if len(lines)<=10 else 4
            block_count=min(block_count,len(lines))
            interior=max(2.0,end-start)
            desired_interlude=min(14.0,max(5.0,score_end*.075)) if block_count>1 else 0
            interlude=min(desired_interlude,interior*.24/max(1,block_count-1))
            vocal_total=max(.8,interior-interlude*(block_count-1))
            base,extra=divmod(len(lines),block_count);groups=[];at_line=0
            for block in range(block_count):
                count=base+(1 if block<extra else 0);groups.append(lines[at_line:at_line+count]);at_line+=count
            windows=[];cursor=start
            for block,group in enumerate(groups):
                span=vocal_total*sum(len(x) for x in group)/total_chars
                windows.append((cursor,min(end,cursor+span),group));cursor+=span+interlude
            beats=list(midi.get_beats())
            beat_step=(sum(b-a for a,b in zip(beats,beats[1:]))/max(1,len(beats)-1)) if len(beats)>1 else .8
            grid=sorted(set([round(x,4) for x in beats]+[round(x+beat_step*.5,4) for x in beats if x+beat_step*.5<score_end]+[round(n.start,4) for n in source_notes]))
            def snap(value,lower,upper):
                choices=[x for x in grid if lower<=x<=upper and abs(x-value)<=beat_step*.34]
                return min(choices,key=lambda x:abs(x-value)) if choices else value
            notes=[];section_meta=[]
            from collections import Counter
            tonic=Counter(note.pitch%12 for note in source_notes).most_common(1)[0][0]
            pitch_classes={(tonic+interval)%12 for interval in (0,2,4,7,9)}
            vocal_pitches=[pitch for pitch in range(60,77) if pitch%12 in pitch_classes]
            center=min(vocal_pitches,key=lambda pitch:abs(pitch-66));previous=None
            tone_path=five_tone_path or ['gong']
            line_index=0;prosody_items=lyrics.get('prosody') if isinstance(lyrics.get('prosody'),list) else []
            for block_index,(window_start,window_end,group) in enumerate(windows):
                tone_name=tone_path[min(len(tone_path)-1,round(block_index*(len(tone_path)-1)/max(1,len(windows)-1)))]
                modal_pc=(tonic+TONE_PITCH_CLASS.get(tone_name,0))%12
                breath=min(.8,max(.42,(window_end-window_start)/max(1,len(group))*.1)) if len(group)>1 else 0
                usable=max(.5,window_end-window_start-breath*(len(group)-1));cursor=window_start
                section_meta.append({'index':block_index+1,'start':round(window_start,3),'end':round(window_end,3),'line_start':line_index,'line_count':len(group),'role':('initial' if block_index==0 else 'return' if block_index==len(windows)-1 else 'development')})
                group_chars=max(1,sum(len(x) for x in group))
                for line in group:
                    line_span=usable*len(line)/group_chars
                    line_meta=prosody_items[line_index] if line_index<len(prosody_items) else None
                    line_prosody=_line_prosody(line,line_meta);weights=_lyric_rhythm_weights(line,line_meta)
                    scale=line_span/max(.01,sum(weights));line_end=cursor+line_span
                    stress=line_prosody['stress_index']
                    for i,weight in enumerate(weights):
                        slot=max(.18,weight*scale)
                        desired=cursor
                        # Phrase onsets sit a hair behind the grid while the
                        # line's principal stress leans forward. This is tiny
                        # enough to retain ensemble alignment but removes the
                        # syllable-sequencer feel.
                        expressive_offset=(min(.035,beat_step*.035) if i in line_prosody['breaks'] else 0)
                        desired=max(window_start,desired+expressive_offset)
                        at=snap(desired,cursor,min(line_end-.12,cursor+beat_step*.45)) if i else snap(desired,max(window_start,desired-beat_step*.25),desired+beat_step*.25)
                        at=max(cursor,at)
                        if i<len(line)-1:
                            next_desired=cursor+slot;next_at=snap(next_desired,at+.18,min(line_end,next_desired+beat_step*.34));slot=max(.18,next_at-at)
                        else:slot=max(.18,line_end-at)
                        cursor=at
                        arc=math.sin(math.pi*(i+1)/(len(line)+1))
                        direction=-1 if line_index%3==2 else 1
                        # One clear stress peak and a tonic-facing cadence read
                        # as a sung sentence. Repeated pitches are allowed;
                        # forcing every syllable to move was a major source of
                        # the former synthetic, nursery-rhyme contour.
                        emphasis=2 if i==stress else 0
                        desired_pitch=center+direction*round(arc*4)+emphasis+(1 if line_index%2 else 0)
                        if i==len(line)-1:
                            # Each vocal section resolves toward the active
                            # five-tone centre; the last section may also land
                            # on gong for a stable whole-song close.
                            cadence_pcs={modal_pc}
                            if block_index==len(windows)-1:cadence_pcs.add(tonic)
                            cadence=[value for value in vocal_pitches if value%12 in cadence_pcs]
                            pitch=_nearest_singable_pitch(cadence or vocal_pitches,center-1,previous,5)
                        else:pitch=_nearest_singable_pitch(vocal_pitches,desired_pitch,previous,5)
                        phrase_release=.94 if i+1 in line_prosody['breaks'] else 1
                        release=(.91 if i==len(line)-1 else (.975 if line[i] in VOCAL_FUNCTION_CHARS else .995))*phrase_release
                        # Phrase and section arcs survive in MIDI and are also
                        # available to downstream renderers as expressive intent.
                        section_gain=.88+.12*math.sin(math.pi*(block_index+1)/(len(windows)+1))
                        velocity=max(48,min(96,round((68+13*arc-(5 if i==len(line)-1 else 0))*section_gain)))
                        notes.append(pretty_midi.Note(velocity=velocity,pitch=pitch,start=at,end=min(line_end,at+slot*release)))
                        previous=pitch;cursor=at+slot
                    cursor=line_end+breath;line_index+=1
            lyrics['vocal_sections']=section_meta
            lyrics['vocal_pitch_policy']={
                'authority':'five_tone_master_score',
                'tonic_pitch_class':tonic,
                'allowed_pitch_classes':sorted(pitch_classes),
                'five_tone_path':list(tone_path),
                'voice_adaptation':'octave_only',
            }
            lead.notes=notes
    lead.program=53;lead.name='Vocal melody';midi.instruments=[lead];midi.write(str(target));return target
