"""Map MIDI pitches to Clone Hero 0-5 frets, with rhythm-game chord rules."""
from __future__ import annotations
import numpy as np

def _pitch_of(s: int, f: int, tuning: list[int]) -> int:
    if s == 0 and 28 <= f <= 108:
        return int(f)
    if 0 <= s < len(tuning):
        return tuning[s] + int(f)
    return int(f)

def map_to_ch_frets(notes, tuning, is_bass=False):
    if not notes:
        return []

    sorted_notes = sorted(notes, key=lambda x: (x[0], x[2]))
    groups = []
    cur = [sorted_notes[0]]
    for n in sorted_notes[1:]:
        if abs(n[0] - cur[0][0]) < 1e-4:
            cur.append(n)
        else:
            groups.append(cur)
            cur = [n]
    groups.append(cur)

    all_pitches = []
    for g in groups:
        for (t, d, s, f) in g:
            all_pitches.append(_pitch_of(s, f, tuning))
    median_pitch = float(np.median(all_pitches)) if all_pitches else 60

    out = []
    WINDOW = 16

    for i, g in enumerate(groups):
        if i + 1 < len(groups):
            delta_beats = groups[i + 1][0][0] - g[0][0]
        else:
            delta_beats = 1.0

        if len(g) > 1 and delta_beats < 0.6:
            lowest = min(g, key=lambda x: _pitch_of(x[2], x[3], tuning))
            g = [lowest]

        start_w = max(0, i - WINDOW // 2)
        end_w = min(len(groups), i + WINDOW // 2)
        window_pitches = []
        for wg in groups[start_w:end_w]:
            for (_, _, s, f) in wg:
                window_pitches.append(_pitch_of(s, f, tuning))

        lo = min(window_pitches) if window_pitches else 0
        hi = max(window_pitches) if window_pitches else 12
        span = max(1.0, hi - lo)

        chord_data = []
        for (t, d, s, f) in g:
            p = _pitch_of(s, f, tuning)
            chord_data.append({'t': t, 'd': d, 's': s, 'f': f, 'p': p})
        chord_data.sort(key=lambda x: x['p'])

        used = set()
        for c in chord_data:
            if c['p'] <= 20:
                out.append((c['t'], c['d'], 5))
                used.add(5)
                continue

            if not is_bass and len(chord_data) == 1 and c['p'] < median_pitch - 8:
                fret = 1 if (i % 2 == 0) else 2
                out.append((c['t'], c['d'], fret))
                used.add(fret)
                continue

            rel = (c['p'] - lo) / span
            fret = int(round(rel * 4))
            fret = max(0, min(4, fret))

            base = fret
            offset = 1
            while fret in used and fret <= 4:
                fret = base + offset
                if fret > 4:
                    fret = base - offset
                offset += 1
            fret = max(0, min(4, fret))
            used.add(fret)
            out.append((c['t'], c['d'], fret))

    out.sort(key=lambda x: (x[0], x[2]))
    return out