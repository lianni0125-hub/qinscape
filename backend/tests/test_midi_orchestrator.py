import pretty_midi
from backend.app.services.midi_orchestrator import apply_skill_plan,arrange,fit_midi_duration

def source_midi(path):
    midi=pretty_midi.PrettyMIDI(initial_tempo=72);lead=pretty_midi.Instrument(program=0)
    for i in range(32):lead.notes.append(pretty_midi.Note(velocity=72,pitch=60+(i%5),start=i*.25,end=i*.25+.22))
    midi.instruments.append(lead);midi.write(str(path))

def test_skill_shaping_and_ensemble(tmp_path):
    raw=tmp_path/'raw.mid';shaped=tmp_path/'shaped.mid';ensemble=tmp_path/'ensemble.mid';source_midi(raw)
    apply_skill_plan(raw,shaped,{'form_plan':{'density_arc':[-1,1,-.5],'register_arc':[-1,1,0]}},7)
    arrange(shaped,ensemble,'ensemble');midi=pretty_midi.PrettyMIDI(str(ensemble))
    assert len(midi.instruments)>=3
    assert midi.instruments[0].name=='Dizi / Flute'

def test_every_ensemble_palette_creates_distinct_named_tracks(tmp_path):
    expected={'silk_bamboo':3,'plucked':3,'clear_space':3,'chamber':3,'orchestral':4}
    for style,minimum in expected.items():
        raw=tmp_path/f'{style}-raw.mid';out=tmp_path/f'{style}.mid';source_midi(raw)
        arrange(raw,out,'ensemble',style);midi=pretty_midi.PrettyMIDI(str(out))
        names=[x.name for x in midi.instruments]
        assert names[0] in {'Dizi / Flute','Zheng','Xiao / Shakuhachi','Flute','Oboe'}
        assert len(set(names))==len(names)
        assert len(names)>=minimum

def test_user_can_prefer_and_exclude_instruments(tmp_path):
    raw=tmp_path/'raw.mid';out=tmp_path/'custom.mid';source_midi(raw)
    arrange(raw,out,'ensemble','silk_bamboo',['大提琴'],['二胡'])
    names=[x.name for x in pretty_midi.PrettyMIDI(str(out)).instruments]
    assert names[0]=='Cello'
    assert 'Erhu / Fiddle' not in names

def test_eastern_instruments_are_selectable_and_can_lead(tmp_path):
    raw=tmp_path/'raw-east.mid';out=tmp_path/'east.mid';source_midi(raw)
    arrange(raw,out,'ensemble','plucked',['钟铃'],['太鼓'],['jue'],'筝')
    names=[x.name for x in pretty_midi.PrettyMIDI(str(out)).instruments]
    assert names[0]=='Zheng'
    assert 'Tinkle bell' in names
    assert 'Taiko drum' not in names

def test_local_motif_grammar_and_duration_are_operational(tmp_path):
    raw=tmp_path/'raw.mid';shaped=tmp_path/'shaped.mid';source_midi(raw)
    plan={
        'form_plan':{'density_arc':[0],'register_arc':[0]},'duration_seconds':4,
        'five_tone_path':['shang','gong'],
        'references':[{'motifs':[{'interval_shape':'2|-2','rhythm_ratio':'1|2|1'}]}]
    }
    apply_skill_plan(raw,shaped,plan,3)
    midi=pretty_midi.PrettyMIDI(str(shaped));notes=sorted(midi.instruments[0].notes,key=lambda n:n.start)
    assert midi.get_end_time()<=4.001
    assert any(notes[i+1].pitch-notes[i].pitch in (2,-2) for i in range(len(notes)-1))
    assert max(notes,key=lambda n:n.end).pitch%12==0

def test_form_plan_controls_ensemble_layers(tmp_path):
    raw=tmp_path/'form-raw.mid';sparse=tmp_path/'sparse.mid';full=tmp_path/'full.mid';source_midi(raw)
    arrange(raw,sparse,'ensemble','orchestral',form_plan={'section_count':3,'roles':['opening','development','closing'],'harmonic_arc':[-1.5,-1.2,-1.4]})
    arrange(raw,full,'ensemble','orchestral',form_plan={'section_count':3,'roles':['opening','peak','closing'],'harmonic_arc':[.4,1.4,.4]})
    sparse_score=pretty_midi.PrettyMIDI(str(sparse));full_score=pretty_midi.PrettyMIDI(str(full))
    assert sum(len(x.notes) for x in full_score.instruments)>sum(len(x.notes) for x in sparse_score.instruments)

def test_vocal_melody_aligns_one_note_per_lyric_character(tmp_path):
    from backend.app.services.midi_orchestrator import extract_vocal_melody
    raw=tmp_path/'raw.mid';vocal=tmp_path/'vocal.mid';source_midi(raw)
    extract_vocal_melody(raw,vocal,{'lines':['松风入夜','月照空山']})
    score=pretty_midi.PrettyMIDI(str(vocal))
    assert len(score.instruments[0].notes)==8

def test_short_score_is_extended_to_requested_duration(tmp_path):
    raw=tmp_path/'short.mid';fitted=tmp_path/'fitted.mid';source_midi(raw)
    fit_midi_duration(raw,fitted,30)
    score=pretty_midi.PrettyMIDI(str(fitted))
    assert 29.0 <= score.get_end_time() <= 30.001

def test_mandarin_particles_are_lighter_than_cadence_words():
    from backend.app.services.midi_orchestrator import _lyric_rhythm_weights
    weights=_lyric_rhythm_weights(list('山与水的梦'))
    assert weights[3] < weights[2]
    assert weights[-1] > max(weights[:-1])

def test_prosody_is_derived_after_final_lyrics_are_known():
    from backend.app.services.midi_orchestrator import derive_lyric_prosody
    result=derive_lyric_prosody(['林深竹影风过声幽'])
    assert ''.join(result[0]['phrases'])=='林深竹影风过声幽'
    assert 0<=result[0]['stress_index']<8

def test_local_segmentation_preserves_words_and_every_character():
    from backend.app.services.midi_orchestrator import derive_lyric_prosody
    lines=['\u6e05\u98ce\u5f90\u6765\u6c34\u6ce2\u4e0d\u5174','\u4e0d\u77e5\u5f52\u5904\u6708\u6ee1\u957f\u4ead']
    result=derive_lyric_prosody(lines)
    assert result[0]['phrases']==['\u6e05\u98ce','\u5f90\u6765','\u6c34\u6ce2','\u4e0d\u5174']
    assert result[1]['phrases']==['\u4e0d\u77e5','\u5f52\u5904','\u6708\u6ee1','\u957f\u4ead']
    assert all(''.join(item['phrases'])==line for item,line in zip(result,lines))

def test_vocal_pitch_motion_avoids_large_mechanical_leaps(tmp_path):
    from backend.app.services.midi_orchestrator import extract_vocal_melody
    raw=tmp_path/'raw-natural.mid';vocal=tmp_path/'vocal-natural.mid';source_midi(raw)
    extract_vocal_melody(raw,vocal,{'lines':['月光轻落在水中','清风缓缓经过山']})
    notes=pretty_midi.PrettyMIDI(str(vocal)).instruments[0].notes
    assert max(abs(right.pitch-left.pitch) for left,right in zip(notes,notes[1:])) <= 5
    assert any(left.pitch==right.pitch for left,right in zip(notes,notes[1:]))

def test_vocal_cadence_follows_active_five_tone_centre(tmp_path):
    from backend.app.services.midi_orchestrator import extract_vocal_melody
    raw=tmp_path/'raw-tone.mid';vocal=tmp_path/'vocal-tone.mid';source_midi(raw)
    lyric={'lines':['\u6e05\u98ce\u5f90\u6765','\u6c34\u6ce2\u4e0d\u5174']}
    extract_vocal_melody(raw,vocal,lyric,['shang'])
    notes=pretty_midi.PrettyMIDI(str(vocal)).instruments[0].notes
    assert notes[-1].pitch%12 in {0,2}
    assert lyric['vocal_pitch_policy']['authority']=='five_tone_master_score'
    assert lyric['vocal_pitch_policy']['voice_adaptation']=='octave_only'
    assert all(note.pitch%12 in lyric['vocal_pitch_policy']['allowed_pitch_classes'] for note in notes)

def test_phrase_boundary_survives_as_articulation_gap(tmp_path):
    from backend.app.services.midi_orchestrator import extract_vocal_melody
    raw=tmp_path/'raw-phrase.mid';vocal=tmp_path/'vocal-phrase.mid';source_midi(raw)
    lyric={'lines':['\u6e05\u98ce\u5f90\u6765\u6c34\u6ce2\u4e0d\u5174'],'prosody':[{'phrases':['\u6e05\u98ce','\u5f90\u6765','\u6c34\u6ce2','\u4e0d\u5174'],'stress_index':5,'breath_after':True}]}
    extract_vocal_melody(raw,vocal,lyric,['jue'])
    notes=pretty_midi.PrettyMIDI(str(vocal)).instruments[0].notes
    assert any(notes[index+1].start-notes[index].end>.02 for index in (1,3,5))

def test_vocal_phrases_leave_breath_between_lyric_lines(tmp_path):
    from backend.app.services.midi_orchestrator import extract_vocal_melody
    raw=tmp_path/'raw-breath.mid';vocal=tmp_path/'vocal-breath.mid';source_midi(raw)
    extract_vocal_melody(raw,vocal,{'lines':['松风入夜','月照空山']})
    notes=pretty_midi.PrettyMIDI(str(vocal)).instruments[0].notes
    gaps=[notes[i+1].start-notes[i].end for i in range(len(notes)-1)]
    assert max(gaps) >= .3
    assert max(gaps[:3]+gaps[4:]) < .05
    assert min(note.pitch for note in notes) >= 60
    assert max(note.pitch for note in notes) <= 76
    assert notes[0].start >= 1.79
    assert len({note.pitch for note in notes}) >= 3
