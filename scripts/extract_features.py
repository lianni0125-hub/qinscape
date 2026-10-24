#!/usr/bin/env python3
"""Extract reproducible hierarchical features from Guqin-Dataset MusicXML."""

from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "sources" / "Guqin-Dataset" / "Guqin_Dataset_v1"
OUT = ROOT / "data" / "derived"
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SECTION_RE = re.compile(r"^(.*)_([0-9]+)$")


@dataclass
class Note:
    work: str
    source: str
    scope: str
    section: int | None
    measure: int
    onset_q: float
    duration_q: float
    midi: int | None
    pitch_class: int | None
    rest: int
    chord: int
    harmonic_proxy: int
    voice: str


def lname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child(el: ET.Element, name: str) -> ET.Element | None:
    return next((x for x in el if lname(x.tag) == name), None)


def text(el: ET.Element | None, name: str, default: str = "") -> str:
    if el is None:
        return default
    item = child(el, name)
    return (item.text or default).strip() if item is not None else default


def work_and_section(path: Path) -> tuple[str, int | None]:
    match = SECTION_RE.match(path.stem)
    return (match.group(1), int(match.group(2))) if match else (path.stem, None)


def parse_xml(path: Path, scope: str) -> tuple[list[Note], dict]:
    work, section = work_and_section(path)
    source = path.parent.name
    root = ET.parse(path).getroot()
    notes: list[Note] = []
    divisions = 1.0
    cursor = 0.0
    max_cursor = 0.0
    time_sigs: list[str] = []
    measures = 0
    parse_warnings: list[str] = []
    for part in (x for x in root if lname(x.tag) == "part"):
        cursor = 0.0
        for measure_el in (x for x in part if lname(x.tag) == "measure"):
            measures += 1
            try:
                measure_no = int(measure_el.attrib.get("number", measures))
            except ValueError:
                measure_no = measures
            measure_start = cursor
            last_nonchord_onset = cursor
            for item in measure_el:
                tag = lname(item.tag)
                if tag == "attributes":
                    d = text(item, "divisions")
                    if d:
                        divisions = float(d)
                    ts = child(item, "time")
                    if ts is not None:
                        sig = f"{text(ts, 'beats')}/{text(ts, 'beat-type')}"
                        if sig not in time_sigs:
                            time_sigs.append(sig)
                elif tag in {"backup", "forward"}:
                    amount = float(text(item, "duration", "0")) / divisions
                    cursor += -amount if tag == "backup" else amount
                elif tag == "note":
                    duration = float(text(item, "duration", "0")) / divisions
                    is_chord = child(item, "chord") is not None
                    onset = last_nonchord_onset if is_chord else cursor
                    if not is_chord:
                        last_nonchord_onset = onset
                    is_rest = child(item, "rest") is not None
                    midi = None
                    pc = None
                    if not is_rest:
                        pitch = child(item, "pitch")
                        try:
                            step = text(pitch, "step")
                            alter = int(float(text(pitch, "alter", "0")))
                            octave = int(text(pitch, "octave"))
                            midi = 12 * (octave + 1) + STEP[step] + alter
                            pc = midi % 12
                        except (KeyError, ValueError, TypeError):
                            parse_warnings.append(f"bad pitch at measure {measure_no}")
                    harmonic = any(lname(x.tag) == "staccato" for x in item.iter())
                    notes.append(Note(work, source, scope, section, measure_no,
                                      round(onset, 6), round(duration, 6), midi, pc,
                                      int(is_rest), int(is_chord), int(harmonic),
                                      text(item, "voice", "1")))
                    if not is_chord:
                        cursor += duration
                    max_cursor = max(max_cursor, onset + duration)
            cursor = max(cursor, measure_start)
    meta = {
        "path": str(path.relative_to(DATASET)).replace("\\", "/"),
        "work": work, "source": source, "scope": scope, "section": section,
        "measures": measures, "duration_q": round(max_cursor, 6),
        "time_signatures": "|".join(time_sigs),
        "warnings": "|".join(sorted(set(parse_warnings))),
    }
    return notes, meta


def entropy(values: Iterable[int]) -> float:
    counts = Counter(values)
    total = sum(counts.values())
    return 0.0 if not total else -sum((n / total) * math.log2(n / total) for n in counts.values())


def summarize(notes: list[Note], meta: dict) -> dict:
    sounding = [n for n in notes if not n.rest and n.midi is not None]
    rests = [n for n in notes if n.rest]
    pitches = [n.midi for n in sounding]
    intervals = [b - a for a, b in zip(pitches, pitches[1:])]
    durations = [n.duration_q for n in sounding if n.duration_q > 0]
    total_q = max(meta["duration_q"], 1e-9)
    pc = Counter(n.pitch_class for n in sounding)
    interval_abs = [abs(x) for x in intervals]
    top_pc = [k for k, _ in pc.most_common(5)]
    return {
        **meta,
        "note_events": len(sounding),
        "rest_events": len(rests),
        "notes_per_quarter": round(len(sounding) / total_q, 6),
        "rest_duration_ratio": round(sum(n.duration_q for n in rests) / total_q, 6),
        "harmonic_proxy_ratio": round(sum(n.harmonic_proxy for n in sounding) / max(len(sounding), 1), 6),
        "chord_note_ratio": round(sum(n.chord for n in sounding) / max(len(sounding), 1), 6),
        "pitch_min": min(pitches) if pitches else None,
        "pitch_max": max(pitches) if pitches else None,
        "pitch_mean": round(statistics.fmean(pitches), 6) if pitches else None,
        "pitch_range": max(pitches) - min(pitches) if pitches else None,
        "pitch_class_entropy": round(entropy(n.pitch_class for n in sounding), 6),
        "top_pitch_classes": "|".join(map(str, top_pc)),
        "stepwise_ratio": round(sum(x <= 2 for x in interval_abs) / max(len(interval_abs), 1), 6),
        "leap_ratio": round(sum(x >= 5 for x in interval_abs) / max(len(interval_abs), 1), 6),
        "ascending_ratio": round(sum(x > 0 for x in intervals) / max(len(intervals), 1), 6),
        "descending_ratio": round(sum(x < 0 for x in intervals) / max(len(intervals), 1), 6),
        "duration_mean_q": round(statistics.fmean(durations), 6) if durations else None,
        "duration_median_q": round(statistics.median(durations), 6) if durations else None,
        "opening_midi": pitches[0] if pitches else None,
        "closing_midi": pitches[-1] if pitches else None,
    }


def motifs(notes: list[Note], n_min: int = 3, n_max: int = 7) -> list[dict]:
    result = []
    grouped: dict[tuple[str, str, int | None], list[Note]] = {}
    for note in notes:
        if not note.rest and note.midi is not None:
            grouped.setdefault((note.work, note.scope, note.section), []).append(note)
    for (work, scope, section), seq in grouped.items():
        pitches = [x.midi for x in seq]
        durs = [x.duration_q for x in seq]
        for size in range(n_min, n_max + 1):
            counts: Counter[tuple[int, ...]] = Counter()
            first: dict[tuple[int, ...], int] = {}
            rhythm: dict[tuple[int, ...], tuple[float, ...]] = {}
            for i in range(0, len(pitches) - size + 1):
                shape = tuple(pitches[j + 1] - pitches[j] for j in range(i, i + size - 1))
                counts[shape] += 1
                first.setdefault(shape, i)
                base = durs[i] or 1.0
                rhythm.setdefault(shape, tuple(round(x / base, 3) for x in durs[i:i + size]))
            for shape, count in counts.most_common(12):
                if count < 2:
                    continue
                result.append({"work": work, "scope": scope, "section": section,
                               "note_length": size, "interval_shape": "|".join(map(str, shape)),
                               "rhythm_ratio": "|".join(map(str, rhythm[shape])),
                               "occurrences": count, "first_index": first[shape]})
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not DATASET.exists():
        raise SystemExit(f"Dataset not found: {DATASET}")
    OUT.mkdir(parents=True, exist_ok=True)
    works = list(csv.DictReader((DATASET / "reference.csv").open(encoding="utf-8-sig")))
    all_notes: list[Note] = []
    summaries: list[dict] = []
    failures: list[dict] = []
    for scope, folder in (("section", "xml"), ("whole", "xml_no_split")):
        for path in sorted((DATASET / folder).rglob("*.xml")):
            try:
                notes, meta = parse_xml(path, scope)
                all_notes.extend(notes)
                summaries.append(summarize(notes, meta))
            except Exception as exc:  # retain corpus audit instead of aborting all files
                failures.append({"path": str(path.relative_to(DATASET)), "error": repr(exc)})

    work_rows = []
    section_by_work = Counter(x["work"] for x in summaries if x["scope"] == "section")
    whole_names = {x["work"] for x in summaries if x["scope"] == "whole"}
    for i, row in enumerate(works, 1):
        name = row["曲谱名称"]
        work_rows.append({"work_id": f"GQ{i:03d}", "work": name, **row,
                          "section_count": section_by_work[name],
                          "has_whole_score": int(name in whole_names)})

    note_rows = [asdict(x) for x in all_notes]
    motif_rows = motifs([x for x in all_notes if x.scope == "section"])
    write_csv(OUT / "works.csv", work_rows)
    write_csv(OUT / "score_features.csv", summaries)
    write_csv(OUT / "notes.csv", note_rows)
    write_csv(OUT / "motifs.csv", motif_rows)
    write_csv(OUT / "parse_failures.csv", failures)

    report = {
        "dataset_commit": "e7feb0c2e7e4a5ba471c70723e7f81b9ae893902",
        "reference_works": len(works),
        "parsed_whole_scores": sum(x["scope"] == "whole" for x in summaries),
        "parsed_section_scores": sum(x["scope"] == "section" for x in summaries),
        "note_rows": len(note_rows), "motif_rows": len(motif_rows),
        "failures": failures,
        "unmatched_reference_works": sorted({x["曲谱名称"] for x in works} - whole_names),
        "unmatched_whole_scores": sorted(whole_names - {x["曲谱名称"] for x in works}),
    }
    (OUT / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    db = sqlite3.connect(OUT / "qinscape_features.sqlite")
    try:
        for name, rows in (("works", work_rows), ("score_features", summaries),
                           ("notes", note_rows), ("motifs", motif_rows)):
            if not rows:
                continue
            cols = list(rows[0])
            db.execute(f'DROP TABLE IF EXISTS "{name}"')
            db.execute(f'CREATE TABLE "{name}" ({", ".join(f"[{c}]" for c in cols)})')
            db.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" for _ in cols)})',
                           [[row.get(c) for c in cols] for row in rows])
        db.commit()
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
