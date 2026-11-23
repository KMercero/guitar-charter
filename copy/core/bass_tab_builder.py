"""Converts bass MIDI notes into playable fret numbers via a 4-string DP."""
import numpy as np

BASS_TUNING = [28, 33, 38, 43]
MAX_FRET = 20
STRING_NAMES = ["G", "D", "A", "E"]

def _get_possible_positions(midi_pitch):
    positions = []
    for string_idx, open_note in enumerate(BASS_TUNING):
        fret = midi_pitch - open_note
        if 0 <= fret <= MAX_FRET:
            positions.append((string_idx, fret))
    if positions:
        return positions
    for shift in (-12, 12):
        for string_idx, open_note in enumerate(BASS_TUNING):
            fret = (midi_pitch + shift) - open_note
            if 0 <= fret <= MAX_FRET:
                positions.append((string_idx, fret))
        if positions:
            return positions
    return [(0, MAX_FRET)]

def _move_cost(prev_pos, curr_pos):
    if prev_pos is None:
        return 0.0
    ps, pf = prev_pos
    cs, cf = curr_pos
    return abs(ps - cs) * 0.5 + abs(pf - cf) * 1.0

def build_bass_tab_from_midi(notes):
    if not notes:
        return []
    notes = sorted(notes, key=lambda x: x[0])
    options = [_get_possible_positions(pitch) for _, _, pitch in notes]

    costs = [[0.0] * len(options[0])]
    paths = [[None] * len(options[0])]
    for i in range(1, len(options)):
        curr_costs, curr_paths = [], []
        for curr_opt in options[i]:
            best_cost, best_prev = float("inf"), 0
            for prev_idx, prev_opt in enumerate(options[i - 1]):
                c = costs[i - 1][prev_idx] + _move_cost(prev_opt, curr_opt)
                if c < best_cost:
                    best_cost, best_prev = c, prev_idx
            curr_costs.append(best_cost)
            curr_paths.append(best_prev)
        costs.append(curr_costs)
        paths.append(curr_paths)

    best_end = int(np.argmin(costs[-1]))
    chosen = []
    for i in range(len(options) - 1, -1, -1):
        chosen.append(options[i][best_end])
        best_end = paths[i][best_end]
    chosen.reverse()

    return [(t, end_t, s, f)
            for (t, end_t, _), (s, f) in zip(notes, chosen)]

def render_ascii_tab(tab_notes, bpm):
    if not tab_notes:
        return "No notes detected."
    tab = {s: "" for s in range(4)}
    tab_notes = sorted(tab_notes, key=lambda x: x[0])
    last_time = 0.0
    sec_per_beat = 60.0 / bpm
    grid_size = sec_per_beat / 4.0
    for (t, end_t, string_idx, fret) in tab_notes:
        spaces = max(0, int(round((t - last_time) / grid_size)))
        fret_str = str(fret)
        col_width = max(3, len(fret_str) + 1)
        for s in range(4):
            if s == string_idx:
                if spaces > 0:
                    tab[s] += "-" * (spaces * col_width)
                tab[s] += f"-{fret_str}-"
            else:
                tab[s] += "-" * ((spaces + 1) * col_width)
        last_time = t
    return "\n".join(f"{STRING_NAMES[s]}|{tab[s]}|" for s in range(4))