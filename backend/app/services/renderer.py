from __future__ import annotations
import shutil,subprocess,re,json
from pathlib import Path
from .. import config

def render_midi(midi:Path,wav:Path,mode:str='ensemble'):
    binary=shutil.which('fluidsynth')
    if not binary:raise RuntimeError('FluidSynth is not installed; run deploy/install_system.sh')
    sf=config.SOUNDFONT_ENSEMBLE
    if not sf or not Path(sf).exists():raise RuntimeError('Missing ensemble SoundFont. Configure SOUNDFONT_ENSEMBLE.')
    subprocess.run([binary,'-ni',sf,str(midi),'-F',str(wav),'-r','44100'],check=True,timeout=600,capture_output=True);return wav

def trim_leading_silence(wav:Path,duration_seconds:int):
    """Drop genuine leading silence, then cap the buffered render at the requested length."""
    ff=shutil.which('ffmpeg')
    if not ff:raise RuntimeError('ffmpeg is required to finish rendered audio')
    target=wav.with_name(f'{wav.stem}.trimmed{wav.suffix}')
    audio_filter=(f'silenceremove=start_periods=1:start_duration=0.06:start_threshold=-50dB,'
                  f'apad=pad_dur={duration_seconds},atrim=duration={duration_seconds},asetpts=N/SR/TB')
    subprocess.run([ff,'-y','-i',str(wav),'-af',audio_filter,'-ar','44100',str(target)],check=True,timeout=600,capture_output=True)
    target.replace(wav);return wav

def _loudness(path:Path,ff:str)->dict:
    """Measure gated programme loudness; silence between vocal sections is ignored by EBU gating."""
    result=subprocess.run([ff,'-hide_banner','-i',str(path),'-af','loudnorm=I=-18:TP=-2:LRA=9:print_format=json','-f','null','-'],timeout=600,capture_output=True,text=True)
    blocks=re.findall(r'\{[\s\S]*?"target_offset"\s*:\s*"[^\"]+"[\s\S]*?\}',result.stderr)
    try:return json.loads(blocks[-1]) if blocks else {}
    except Exception:return {}

def mix(instrumental:Path,vocal:Path,target:Path,duration_seconds:int|float|None=None,balance:str='natural',voice_description:str='',lead_instrument:str=''):
    ff=shutil.which('ffmpeg')
    if not ff:raise RuntimeError('ffmpeg is required to mix vocals')
    try:available_filters=subprocess.run([ff,'-hide_banner','-filters'],timeout=20,capture_output=True,text=True).stdout
    except Exception:available_filters=''
    # Keep these optional so older packaged FFmpeg builds still use the proven
    # fallback chain. Values are intentionally subtle: articulation should not
    # sound underwater or detached from the ensemble.
    deesser='deesser=i=0.08:m=0.25:f=0.48,' if ' deesser ' in available_filters else ''
    short_room='aecho=0.8:0.88:42:0.025,' if ' aecho ' in available_filters else ''
    # Measure before choosing the relationship: a dense, low-crest arrangement
    # needs more vocal lead than a sparse one, even at the same integrated LUFS.
    duration=max(1.0,float(duration_seconds or 90))
    music_stats=_loudness(instrumental,ff);crest=float(music_stats.get('input_tp',-2))-float(music_stats.get('input_i',-18))
    density_lead=3.0 if crest<8 else 1.0 if crest>13 else 2.0
    preference={'forward':1.5,'natural':0.0,'instrumental':-1.5}.get(balance,0.0)
    vocal_target=max(-19.0,min(-15.0,-19.0+density_lead+preference))
    duck_ratio={'forward':3.0,'natural':2.35,'instrumental':1.7}.get(balance,2.35)
    voice_text=(voice_description or '').lower();female='女' in voice_text or 'female' in voice_text;male='男' in voice_text or 'male' in voice_text
    highpass=72 if female else 55 if male else 62
    body=275 if female else 205 if male else 230
    presence_eq=3350 if female else 2550 if male else 2950
    lead=(lead_instrument or '').lower()
    if any(name in lead for name in ('笛','箫','flute','xiao','dizi')):split_low,split_high=1350,5200
    elif any(name in lead for name in ('二胡','小提琴','erhu','violin')):split_low,split_high=900,4200
    elif any(name in lead for name in ('筝','琵琶','扬琴','zheng','pipa','dulcimer')):split_low,split_high=1150,4700
    else:split_low,split_high=1000,4500
    common=(
        f'[0:a]apad=pad_dur={duration},atrim=duration={duration},highpass=f=32,'
        'loudnorm=I=-19:TP=-2.2:LRA=10[m];'
        f'[1:a]apad=pad_dur={duration},atrim=duration={duration},highpass=f={highpass},'
        f'equalizer=f={body}:t=q:w=1.1:g=-0.8,equalizer=f={presence_eq}:t=q:w=1:g=0.75,'
        f'{deesser}acompressor=threshold=0.105:ratio=1.38:attack=32:release=285:makeup=1.015,'
        f'{short_room}'
        f'loudnorm=I={vocal_target:.1f}:TP=-2.2:LRA=9,asplit=2[v][key];'
    )
    # Duck only the vocal-presence band (roughly 1–4.5 kHz). The fallback is
    # gentle full-band sidechain ducking for FFmpeg builds without acrossover.
    presence=(common+
        f"[m]acrossover=split='{split_low} {split_high}':order=8th[lo][mid][hi];"
        f'[mid][key]sidechaincompress=threshold=0.03:ratio={duck_ratio}:attack=30:release=380:makeup=1[midduck];'
        '[lo][midduck][hi]amix=inputs=3:duration=first:normalize=0[mduck];'
        '[mduck][v]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,'
        'acompressor=threshold=0.2:ratio=1.28:attack=34:release=300:makeup=1,'
        'loudnorm=I=-16:TP=-1.5:LRA=9,alimiter=limit=0.92:attack=8:release=100[out]'
    )
    fallback=(common+
        f'[m][key]sidechaincompress=threshold=0.03:ratio={duck_ratio}:attack=30:release=380:makeup=1[mduck];'
        '[mduck][v]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,'
        'acompressor=threshold=0.2:ratio=1.28:attack=34:release=300:makeup=1,'
        'loudnorm=I=-16:TP=-1.5:LRA=9,alimiter=limit=0.92:attack=8:release=100[out]')
    safe_common=common.replace(',asplit=2[v][key];','[v];')
    safe=(safe_common+
        '[m][v]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,'
        'acompressor=threshold=0.2:ratio=1.28:attack=34:release=300:makeup=1,'
        'loudnorm=I=-16:TP=-1.5:LRA=9,alimiter=limit=0.92:attack=8:release=100[out]')
    command=lambda filters:[ff,'-y','-i',str(instrumental),'-i',str(vocal),'-filter_complex',filters,'-map','[out]','-ar','44100',str(target)]
    try:subprocess.run(command(presence),check=True,timeout=600,capture_output=True)
    except subprocess.CalledProcessError:
        try:subprocess.run(command(fallback),check=True,timeout=600,capture_output=True)
        except subprocess.CalledProcessError:subprocess.run(command(safe),check=True,timeout=600,capture_output=True)
    return target
