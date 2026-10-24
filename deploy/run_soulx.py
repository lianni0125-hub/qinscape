"""Bridge QinScape's reviewed lyrics/MIDI to SoulX-Singer inference."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import statistics
from pathlib import Path
from functools import lru_cache

import pretty_midi
from g2pM import G2pM


ROOT = Path(__file__).resolve().parents[1]
SOULX = Path(os.getenv("QINSCAPE_SOULX_REPO", ROOT / "sources" / "SoulX-Singer"))
MODELS = Path(os.getenv("QINSCAPE_MODELS", ROOT / "models"))
SOULX_PYTHON = Path(os.getenv("QINSCAPE_SOULX_PYTHON", ROOT / ".venv-soulx" / "bin" / "python"))
FUNCTION_CHARS = set("的了着过吗呢吧啊呀兔而与及于在把被将又也都很更便却")
SINGABLE_FINALS = ("a", "o", "e", "ai", "ei", "ao", "ou", "an", "en", "ang", "eng", "ong", "ian", "iang", "uan", "uang", "ing")
PRONUNCIATION_LEXICON = {
    "长亭": ["chang2", "ting2"], "长风": ["chang2", "feng1"], "行舟": ["xing2", "zhou1"],
    "行人": ["xing2", "ren2"], "还似": ["hai2", "si4"], "还有": ["hai2", "you3"],
    "乐声": ["yue4", "sheng1"], "乐曲": ["yue4", "qu3"], "空山": ["kong1", "shan1"],
    "重逢": ["chong2", "feng2"], "重来": ["chong2", "lai2"], "朝霞": ["zhao1", "xia2"],
}
PRONUNCIATION_LEXICON.update({
    "\u8584\u66ae":["bo2","mu4"], "\u671d\u4e91":["zhao1","yun2"],
    "\u6570\u58f0":["shu4","sheng1"], "\u7a7a\u6fdb":["kong1","meng2"],
    "\u66f2\u6c34":["qu1","shui3"], "\u76f8\u548c":["xiang1","he4"],
    "\u66f4\u6df1":["geng1","shen1"], "\u4e50\u97f3":["yue4","yin1"],
})

@lru_cache(maxsize=1)
def _mandarin_phones() -> set[str]:
    path=SOULX/'soulxsinger'/'utils'/'phoneme'/'phone_set.json'
    payload=json.loads(path.read_text(encoding='utf-8'))
    values=payload.keys() if isinstance(payload,dict) else payload
    return {str(value)[3:] for value in values if str(value).startswith('zh_')}

def _supported_phone(candidate:str,original:str)->str:
    """Never emit a contextual tone token absent from SoulX's Mandarin set."""
    allowed=_mandarin_phones()
    if candidate in allowed:return candidate
    if original in allowed:return original
    base=re.sub(r'[1-6]$','',candidate)
    alternatives=[value for value in allowed if re.sub(r'[1-6]$','',value)==base]
    if not alternatives:return candidate
    match=re.search(r'([1-6])$',candidate);tone=int(match.group(1)) if match else 5
    return min(alternatives,key=lambda value:abs(int(re.search(r'([1-6])$',value).group(1))-tone))


def _supports_melisma(phone: str) -> bool:
    final = re.sub(r"[1-5]$", "", phone.lower())
    return any(final.endswith(value) for value in SINGABLE_FINALS)


def _contextual_pinyin(groups: list[list[str]]) -> list[str]:
    g2p=G2pM();result=[]
    for group in groups:
        sentence="".join(group);phones=list(g2p(sentence,tone=True,char_split=False))
        for phrase,replacement in PRONUNCIATION_LEXICON.items():
            start=sentence.find(phrase)
            while start>=0:
                phones[start:start+len(phrase)]=replacement;start=sentence.find(phrase,start+1)
        # Common Mandarin connected-speech forms. This remains deliberately
        # small; the score melody, not lexical tone, owns the large pitch arc.
        for index,phone in enumerate(list(phones)):
            original=phone
            next_tone=(re.search(r'([1-5])$',phones[index+1]).group(1) if index+1<len(phones) and re.search(r'([1-5])$',phones[index+1]) else '')
            candidate=phone
            if phone=='bu4' and next_tone=='4':candidate='bu2'
            elif phone=='yi1' and index>0 and group[index-1]=='第':pass
            elif phone=='yi1' and next_tone:candidate='yi2' if next_tone=='4' else 'yi4'
            elif phone.endswith('3') and next_tone=='3':candidate=phone[:-1]+'2'
            phones[index]=_supported_phone(candidate,original)
        result.extend(phones)
    return result


def _fit_score_range(notes, prompt_meta: Path | None) -> list[int]:
    pitches=[int(note.pitch) for note in notes]
    if not prompt_meta or not prompt_meta.exists() or len(pitches)<2:return pitches
    try:
        payload=json.loads(prompt_meta.read_text(encoding='utf-8'));item=payload[0] if isinstance(payload,list) else payload
        prompt=sorted(int(value) for value in str(item.get('note_pitch','')).split() if int(value)>0)
    except (OSError,ValueError,TypeError,json.JSONDecodeError):return pitches
    if len(prompt)<3:return pitches
    center=statistics.median(pitches);prompt_center=statistics.median(prompt)
    # Timbre conditioning may choose a more comfortable octave, but it must
    # never transpose by an arbitrary interval or compress scale degrees. The
    # five-tone master score remains the sole pitch authority.
    candidates=[shift for shift in (-24,-12,0,12,24)
                if min(pitches)+shift>=48 and max(pitches)+shift<=81]
    shift=min(candidates,key=lambda value:abs((center+value)-prompt_center)) if candidates else 0
    return [pitch+shift for pitch in pitches]


def _lyrics(path: Path) -> tuple[list[list[str]],list[dict],dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    lines = value.get("lines", []) if isinstance(value, dict) else value
    prosody = value.get("prosody", []) if isinstance(value, dict) else []
    pitch_policy=value.get('vocal_pitch_policy',{}) if isinstance(value,dict) else {}
    groups = [[c for c in str(line) if "\u4e00" <= c <= "\u9fff"] for line in lines]
    groups = [group for group in groups if group]
    if not groups:
        raise ValueError("SoulX Mandarin synthesis needs reviewed Chinese lyrics")
    return groups,prosody if isinstance(prosody,list) else [],pitch_policy if isinstance(pitch_policy,dict) else {}


def _notes(path: Path):
    midi = pretty_midi.PrettyMIDI(str(path))
    notes = sorted((n for inst in midi.instruments for n in inst.notes), key=lambda n: (n.start, n.pitch))
    if not notes:
        raise ValueError("vocal MIDI contains no notes")
    return notes


def build_target(midi_path: Path, lyrics_path: Path, output: Path, prompt_meta: Path | None = None) -> Path:
    (groups,prosody,pitch_policy),notes=_lyrics(lyrics_path),_notes(midi_path)
    chars = [char for group in groups for char in group]
    count = min(len(chars), len(notes))
    chars, notes = chars[:count], notes[:count]
    # Match SoulX's official Mandarin preprocessing: resolve pronunciation from
    # each complete lyric sentence, not isolated characters. Context is crucial
    # for polyphones and natural Mandarin coarticulation (e.g. 行、长、重、还).
    pinyin = _contextual_pinyin(groups)
    if len(pinyin) != len(chars):
        raise ValueError("Mandarin G2P did not align one pronunciation per lyric character")
    fitted_pitches=_fit_score_range(notes,prompt_meta)
    allowed={int(value)%12 for value in pitch_policy.get('allowed_pitch_classes',[]) if isinstance(value,(int,float))}
    if allowed and any(pitch%12 not in allowed for pitch in fitted_pitches):
        raise ValueError('Vocal score escaped the five-tone master score')
    durations=[];texts=[];phones=[];pitches=[];types=[];previous=0.0
    line_starts=set();offset=0
    for group in groups[:-1]:
        offset+=len(group);line_starts.add(offset)
    phrase_starts=set();offset=0
    for line_index,group in enumerate(groups):
        item=prosody[line_index] if line_index<len(prosody) and isinstance(prosody[line_index],dict) else {}
        phrases=item.get('phrases') if isinstance(item.get('phrases'),list) else []
        if ''.join(str(value) for value in phrases)==''.join(group):
            within=0
            for phrase in phrases[:-1]:
                within+=len(str(phrase));phrase_starts.add(offset+within)
        offset+=len(group)
    line_ends=set();offset=0
    for group in groups:
        offset+=len(group);line_ends.add(offset-1)
    for index,(char,phone,note,fitted_pitch) in enumerate(zip(chars,pinyin,notes,fitted_pitches)):
        gap=max(0.0,float(note.start)-previous)
        # A score may contain tiny articulation gaps between adjacent syllables.
        # SoulX should hear those as one sung phrase, not a fresh breath per word.
        boundary=index==0 or index in line_starts or index in phrase_starts
        if gap>(.025 if index in phrase_starts else .12) and boundary:
            durations.append(gap);texts.append('<SP>');phones.append('<SP>');pitches.append(0);types.append(1)
        next_start=float(notes[index+1].start) if index+1<count else float(note.end)
        next_boundary=index+1 in line_starts or index+1 in phrase_starts
        sung_end=float(note.end) if next_boundary else max(float(note.end),next_start)
        duration=max(0.08,sung_end-float(note.start))
        clean_phone=re.sub(r"\s+","",phone)
        tone_match=re.search(r"([1-5])$",clean_phone)
        tone=int(tone_match.group(1)) if tone_match else 5
        # SoulX natively understands note_type=3 as a continuation of the
        # preceding syllable.  Use it sparingly for sustained content words and
        # cadences, so Chinese is sung in phrases instead of one detached block
        # per character.  The second pitch gives tonal motion without inventing
        # another lyric syllable.
        expressive=(index in line_ends or (char not in FUNCTION_CHARS and index % 7 == 4)) and _supports_melisma(clean_phone)
        if duration >= .56 and expressive:
            first_ratio=.66 if index in line_ends else .76
            first=max(.18,duration*first_ratio);second=duration-first
            # Sung Mandarin does not mechanically trace lexical tones. A single
            # scale-degree hint is enough to retain intelligibility without the
            # exaggerated scoops that make synthesis sound synthetic.
            contour={1:0,2:1,3:-1,4:-1,5:0}.get(tone,0)
            durations.extend((first,second));texts.extend((char,char))
            phones.extend(('zh_'+clean_phone,'zh_'+clean_phone))
            pitches.extend((fitted_pitch,max(36,min(88,fitted_pitch+contour))))
            types.extend((2,3))
        else:
            durations.append(duration);texts.append(char);phones.append('zh_'+clean_phone);pitches.append(fitted_pitch);types.append(2)
        previous=float(note.end)
    item = {
        "index": "qinscape_target",
        "language": "Mandarin",
        "time": [0, int(sum(durations) * 1000)],
        "duration": " ".join(f"{x:.4f}" for x in durations),
        "text": " ".join(texts),
        "phoneme": " ".join(phones),
        "note_pitch": " ".join(str(value) for value in pitches),
        "note_type": " ".join(str(value) for value in types),
    }
    output.write_text(json.dumps([item], ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def ensure_prompt(reference: Path, language: str, workdir: Path) -> Path:
    cached = reference.with_suffix(".json")
    if cached.exists():
        return cached
    save_dir = workdir / "soulx_prompt"
    command = [
        str(SOULX_PYTHON), "-m", "preprocess.pipeline",
        "--audio_path", str(reference), "--save_dir", str(save_dir),
        "--language", "Mandarin" if language.lower().startswith("zh") else language,
        "--device", "cuda", "--vocal_sep", "False",
        "--max_merge_duration", "60000", "--midi_transcribe", "True",
    ]
    subprocess.run(command, cwd=SOULX, check=True, timeout=1800)
    if not cached.exists():
        candidate = save_dir / "metadata.json"
        if candidate.exists():
            cached.write_bytes(candidate.read_bytes())
    if not cached.exists():
        raise RuntimeError("SoulX prompt preprocessing did not produce metadata")
    return cached


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--midi", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--reference-text", default="")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workdir = args.output.parent
    prompt_meta = ensure_prompt(args.voice.resolve(), args.language, workdir)
    target_meta = build_target(args.midi.resolve(), args.lyrics.resolve(), workdir / "soulx_target.json",prompt_meta)
    save_dir = workdir / "soulx_generated"
    command = [
        str(SOULX_PYTHON), "-m", "cli.inference", "--device", "cuda",
        "--model_path", str(MODELS / "SoulX-Singer" / "model.pt"),
        "--config", str(SOULX / "soulxsinger" / "config" / "soulxsinger.yaml"),
        "--prompt_wav_path", str(args.voice.resolve()),
        "--prompt_metadata_path", str(prompt_meta.resolve()),
        "--target_metadata_path", str(target_meta.resolve()),
        "--phoneset_path", str(SOULX / "soulxsinger" / "utils" / "phoneme" / "phone_set.json"),
        "--save_dir", str(save_dir), "--control", "score", "--auto_shift", "--fp16",
    ]
    env = {**os.environ, "PYTHONPATH": f"{SOULX}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    subprocess.run(command, cwd=SOULX, env=env, check=True, timeout=1800)
    generated = save_dir / "generated.wav"
    if not generated.exists():
        raise RuntimeError("SoulX inference did not produce generated.wav")
    args.output.write_bytes(generated.read_bytes())


if __name__ == "__main__":
    main()
