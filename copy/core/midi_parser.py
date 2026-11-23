"""Parse a MIDI file (.mid / .midi) into the pipeline's track format."""
from __future__ import annotations
import os
import mido

_DEFAULT_GUITAR = [40, 45, 50, 55, 59, 64]
_DEFAULT_BASS = [28, 33, 38, 43]

def _is_bass_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("bass", "bass guitar", "electric bass"))

def _is_drum_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("drum", "kit", "percussion", "starclassic"))

def _is_vocal_name(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("vocal", "voice", "choir", "sax", "harmonica", "piano", "synth"))

def parse_midi_file(mid_path: str) -> list[dict]:
    if not os.path.exists(mid_path):
        raise FileNotFoundError(mid_path)

    mid = mido.MidiFile(mid_path)
    ticks_per_beat = max(1, mid.ticks_per_beat)
    print(f"MIDI: type={mid.type} ticks_per_beat={ticks_per_beat} tracks={len(mid.tracks)}")

    # --- 1. Global tempo map ---
    tempo_events: list[tuple[float, float]] = []
    for track_idx, track in enumerate(mid.tracks):
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == "set_tempo":
                bpm = 60_000_000 / msg.tempo
                beat = abs_tick / ticks_per_beat
                tempo_events.append((beat, bpm))

    if not tempo_events:
        tempo_events = [(0.0, 120.0)]

    tempo_events.sort(key=lambda x: x[0])
    tempo_map = [tempo_events[0]]
    for beat, bpm in tempo_events[1:]:
        if abs(bpm - tempo_map[-1][1]) > 0.01:
            tempo_map.append((beat, bpm))
    print(f"MIDI: {len(tempo_map)} tempo change(s); BPM range "
          f"{tempo_map[0][1]:.1f} → {tempo_map[-1][1]:.1f}")

    # --- 2. Per-track notes ---
    tracks_out: list[dict] = []

    for track_idx, track in enumerate(mid.tracks):
        name = None
        for msg in track:
            if msg.type == "track_name":
                name = msg.name
                break
        name = name or f"Track {track_idx}"

        if _is_drum_name(name) or _is_vocal_name(name):
            print(f"MIDI: track {track_idx} '{name}' (skipped: drums/vocals)")
            continue

        is_bass = _is_bass_name(name)
        tuning = _DEFAULT_BASS if is_bass else _DEFAULT_GUITAR

        abs_tick = 0
        active_notes: dict[tuple[int, int], list[int]] = {}
        raw_notes: list[tuple[float, float, int]] = []

        channel_override = None
        for msg in track:
            if msg.type == "program_change":
                channel_override = msg.channel
                break

        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                ch = channel_override if channel_override is not None else msg.channel
                active_notes.setdefault((ch, msg.note), []).append(abs_tick)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                ch = channel_override if channel_override is not None else msg.channel
                stack = active_notes.get((ch, msg.note))
                if not stack:
                    continue
                start_tick = stack.pop()
                dur_tick = max(1, abs_tick - start_tick)
                start_beat = start_tick / ticks_per_beat
                dur_beat = dur_tick / ticks_per_beat
                raw_notes.append((start_beat, dur_beat, msg.note))

        for (ch, pitch), stack in active_notes.items():
            for start_tick in stack:
                start_beat = start_tick / ticks_per_beat
                raw_notes.append((start_beat, 0.25, pitch))

        if not raw_notes:
            print(f"MIDI: track {track_idx} '{name}' 0 notes (skipped)")
            continue

        notes_out = [(start_beat, dur_beat, 0, pitch)
                     for (start_beat, dur_beat, pitch) in raw_notes]

        print(f"MIDI: track {track_idx} '{name}' ({len(notes_out)} notes)"
              f"{' [BASS]' if is_bass else ''}")

        tracks_out.append({
            "name": name,
            "notes": notes_out,
            "tuning": tuning,
            "tempo_map": tempo_map,
        })

    print(f"MIDI: parsed {len(tracks_out)} chartable tracks")
    return tracks_out