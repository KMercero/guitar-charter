import mido

mid = mido.MidiFile(r'C:\Users\gengh\OneDrive\Documents\guitarCharter\newborn.mid')
tpb = mid.ticks_per_beat

# Find each track's note count and pitch range
for i, track in enumerate(mid.tracks):
    notes = 0
    pitches = []
    abs_tick = 0
    for msg in track:
        abs_tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            notes += 1
            pitches.append(msg.note)
    
    if notes == 0:
        continue
    
    name = next((msg.name for msg in track if msg.type == 'track_name'), f'Track {i}')
    avg_pitch = sum(pitches) / len(pitches)
    min_pitch = min(pitches)
    max_pitch = max(pitches)
    
    # Average duration
    total_ticks = 0
    note_count = 0
    abs_tick = 0
    active = {}
    for msg in track:
        abs_tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            active[msg.note] = abs_tick
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active:
                total_ticks += abs_tick - active.pop(msg.note)
                note_count += 1
    avg_dur = (total_ticks / note_count / tpb) if note_count else 0

    print(f"  {i}: '{name}'")
    print(f"    n={notes} pitch={avg_pitch:.1f} range=[{min_pitch}-{max_pitch}] avg_dur={avg_dur:.2f}")