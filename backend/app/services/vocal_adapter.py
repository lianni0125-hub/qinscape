from __future__ import annotations
import json,shlex,subprocess,shutil
from pathlib import Path
from .. import config
from .voice_library import get_voice,audio_path

def _shape_section_dynamics(output:Path,lyrics:dict)->Path:
    sections=lyrics.get('vocal_sections') or []
    ff=shutil.which('ffmpeg')
    if not ff or not sections:return output
    gains={'initial':.94,'development':1.055,'return':.98}
    filters=[]
    for section in sections:
        start=float(section.get('start',0));end=float(section.get('end',start));gain=gains.get(section.get('role'),1.0)
        if end>start:
            # A short ramp at both edges makes the section breathe without the
            # audible level steps caused by enable/disable volume switches.
            ramp=min(.55,max(.18,(end-start)*.07));plateau=max(start+ramp,end-ramp)
            expression=(
                f"if(lt(t,{start:.3f}),1,"
                f"if(lt(t,{start+ramp:.3f}),1+({gain}-1)*(t-{start:.3f})/{ramp:.3f},"
                f"if(lt(t,{plateau:.3f}),{gain},"
                f"if(lt(t,{end:.3f}),{gain}+(1-{gain})*(t-{plateau:.3f})/{max(ramp,.001):.3f},1))))"
            )
            filters.append(f"volume='{expression}':eval=frame")
    if not filters:return output
    shaped=output.with_name(f'{output.stem}.shaped{output.suffix}')
    subprocess.run([ff,'-y','-i',str(output),'-af',','.join(filters),str(shaped)],check=True,timeout=600,capture_output=True)
    shaped.replace(output);return output

def synthesize(melody:Path,lyrics:dict,voice:str,output:Path,workdir:Path):
    uploaded=get_voice(voice)
    if uploaded:
        if not config.SOULX_COMMAND:raise RuntimeError('SoulX-Singer is not configured. Set QINSCAPE_SOULX_COMMAND.')
        reference=audio_path(voice)
        lyric_path=workdir/'lyrics.json';lyric_path.write_text(json.dumps(lyrics,ensure_ascii=False,indent=2),encoding='utf8')
        command=config.SOULX_COMMAND.format(midi=melody,lyrics=lyric_path,voice=reference,reference_text=uploaded['transcript'],language=uploaded['language'],output=output)
        subprocess.run(shlex.split(command),check=True,timeout=1800,cwd=workdir);return _shape_section_dynamics(output,lyrics)
    if not config.DIFFSINGER_COMMAND:raise RuntimeError('DiffSinger is not configured. Set DIFFSINGER_COMMAND with {midi}, {lyrics}, {voice}, {output}.')
    if voice not in config.VOCAL_VOICES:raise RuntimeError(f'Voice {voice} is not registered in QINSCAPE_VOCAL_VOICES.')
    lyric_path=workdir/'lyrics.json';lyric_path.write_text(json.dumps(lyrics,ensure_ascii=False,indent=2),encoding='utf8')
    command=config.DIFFSINGER_COMMAND.format(midi=melody,lyrics=lyric_path,voice=voice,output=output)
    subprocess.run(shlex.split(command),check=True,timeout=1800,cwd=workdir);return _shape_section_dynamics(output,lyrics)
