from __future__ import annotations
import json
from pathlib import Path
from ..schemas import JobRequest
from .midi_orchestrator import apply_skill_plan,arrange,derive_lyric_prosody,extract_vocal_melody,fit_midi_duration,shape_accompaniment_for_vocals
from .renderer import render_midi,mix,trim_leading_silence
from .vocal_adapter import synthesize
from .voice_library import get_voice

def generate(caption: str, output: Path):
    from .text2midi_adapter import generate as implementation
    return implementation(caption,output)

def make_lyrics(card,form,duration_seconds=90):
    from .llm_adapter import lyrics as implementation
    return implementation(card,form,duration_seconds)

def run_pipeline(req:JobRequest,plan:dict,out:Path,progress):
    raw=out/'raw.mid';shaped=out/'skill_shaped.mid';arranged=out/'render_ready.mid';final_midi=out/'composition.mid';instrumental=out/'instrumental.wav'
    progress('text2midi',.15);generate(plan['caption'],raw)
    progress('skill_shaping',.43);apply_skill_plan(raw,shaped,plan,req.seed)
    progress('arrangement',.5);arrange(shaped,arranged,req.arrangement,req.ensemble_style,req.preferred_instruments,req.excluded_instruments,req.card.five_tone_path,req.lead_instrument,plan.get('form_plan'))
    # Fit before vocal planning so both stems share an exact timeline. For a
    # song, derive the vocal windows first and let the arrangement make musical
    # space before FluidSynth renders the accompaniment.
    fit_midi_duration(arranged,final_midi,req.duration_seconds);lyric=None;melody=None
    if req.lyrics:
        progress('lyrics',.58);lyric=req.approved_lyrics or make_lyrics(req.card,plan.get('form_plan'),req.duration_seconds)
        lyric['prosody']=derive_lyric_prosody(lyric.get('lines'))
        lyric['prosody_source']='local_jieba'
        melody=extract_vocal_melody(final_midi,out/'vocal_melody.mid',lyric,req.card.five_tone_path);shape_accompaniment_for_vocals(final_midi,lyric.get('vocal_sections'))
    progress('rendering',.67);render_midi(final_midi,instrumental,req.arrangement);trim_leading_silence(instrumental,req.duration_seconds)
    artifacts={'midi':str(final_midi),'instrumental':str(instrumental),'plan':str(out/'plan.json')}
    if req.lyrics:
        lp=out/'lyrics.json';lp.write_text(json.dumps(lyric,ensure_ascii=False,indent=2),encoding='utf8');artifacts.update(lyrics=str(lp),vocal_melody=str(melody))
        if req.voice!='instrumental-guide':
            vocal=synthesize(melody,lyric,req.voice,out/'vocal.wav',out);profile=get_voice(req.voice) or {};progress('mixing',.92);song=mix(instrumental,vocal,out/'song.wav',req.duration_seconds,req.vocal_balance,profile.get('description',''),req.lead_instrument);trim_leading_silence(song,req.duration_seconds);artifacts.update(vocal=str(vocal),song=str(song))
    return artifacts
