"""Emit .chart with tempo map and 2-bar delay."""
RESOLUTION = 480

def _clamp(fret):
    return max(0, min(5, int(fret)))

def _seconds_to_ticks(seconds, bpm_map):
    if not bpm_map:
        bpm_map = [(0, 120.0)]
    for i, (start_tick, bpm) in enumerate(bpm_map):
        next_tick = bpm_map[i + 1][0] if i + 1 < len(bpm_map) else float("inf")
        sec_per_tick = 60.0 / bpm / RESOLUTION
        seg_len_sec = (next_tick - start_tick) * sec_per_tick
        if seconds <= seg_len_sec or next_tick == float("inf"):
            return int(round(start_tick + seconds / sec_per_tick))
        seconds -= seg_len_sec
    return 0

def _bpm_map(tempo_map):
    out = []
    for beat, bpm in tempo_map:
        out.append((int(round(beat * RESOLUTION)), float(bpm)))
    if not out or out[0][0] != 0:
        out.insert(0, (0, float(tempo_map[0][1]) if tempo_map else 120.0))
    return out

def _note_lines(notes_with_ticks):
    notes_with_ticks = sorted(notes_with_ticks, key=lambda x: (x[0], x[2]))
    lines = []
    seen = set()
    for (tk, dur, fret) in notes_with_ticks:
        fret = _clamp(fret)
        key = (tk, fret)
        if key in seen:
            continue
        seen.add(key)
        if dur > 60:
            lines.append(f"  {tk} = N {fret} {dur}")
        else:
            lines.append(f"  {tk} = N {fret} 0")
    return lines

def write_chart(path, guitar_frets, bass_frets, tempo_map,
                song_name="Untitled", artist="Unknown", delay_beats=8.0):
    bpm = _bpm_map(tempo_map)
    first_bpm = tempo_map[0][1] if tempo_map else 120.0
    delay_ticks = int(round(delay_beats * RESOLUTION))

    guitar_ticks = []
    for (t, end_t, f) in guitar_frets:
        tk = _seconds_to_ticks(t, bpm)
        end_tk = _seconds_to_ticks(end_t, bpm)
        guitar_ticks.append((tk + delay_ticks, max(0, end_tk - tk), f))

    bass_ticks = []
    for (t, end_t, f) in bass_frets:
        tk = _seconds_to_ticks(t, bpm)
        end_tk = _seconds_to_ticks(end_t, bpm)
        bass_ticks.append((tk + delay_ticks, max(0, end_tk - tk), f))

    lines = [
        "[Song]", "{",
        f'  Name = "{song_name}"',
        f'  Artist = "{artist}"',
        "  Offset = 0",
        f"  Resolution = {RESOLUTION}",
        "}",
        "[SyncTrack]", "{",
        "  0 = TS 4",
    ]
    for (tk, b) in bpm:
        lines.append(f"  {tk} = B {int(b * 1000)}")
    lines.append("}")

    lines += ["[ExpertSingle]", "{"]
    lines.extend(_note_lines(guitar_ticks))
    lines += ["}", ""]

    if bass_ticks:
        lines += ["[ExpertDoubleBass]", "{"]
        lines.extend(_note_lines(bass_ticks))
        lines += ["}", ""]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))