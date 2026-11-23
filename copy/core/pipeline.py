"""End-to-end chart generation."""
import os
import subprocess
import shutil
import numpy as np
import librosa
import soundfile as sf
from scipy.signal import butter, sosfilt
from collections import defaultdict

from .chart_writer import write_chart
from .pitch_basic import detect_notes_basic_pitch
from .tab_builder import build_tab_from_midi
from .bass_tab_builder import build_bass_tab_from_midi
from .fret_mapper import map_to_ch_frets


# Tick key precision. 960 PPQ means round(x, 2) throws away resolution.
_TICK_PRECISION = 4


def _tick_key(beat: float) -> float:
    return round(float(beat), _TICK_PRECISION)


def separate_stems(mp3_path, out_dir):
    subprocess.run(["demucs", "-n", "htdemucs_6s", "-o", out_dir, mp3_path], check=True)
    base = os.path.splitext(os.path.basename(mp3_path))[0]
    stem_dir = os.path.join(out_dir, "htdemucs_6s", base)
    guitar = os.path.join(stem_dir, "guitar.wav")
    if not os.path.exists(guitar):
        guitar = os.path.join(stem_dir, "other.wav")
    return guitar, os.path.join(stem_dir, "other.wav"), os.path.join(stem_dir, "bass.wav")


def _write_song_folder(out_dir, song_name, artist, guitar_frets, bass_frets,
                       tempo_map, audio_path=None, tabs_text=None):
    def safe(s):
        return "".join(c for c in s if c.isalnum() or c == " ").strip() or "Untitled"
    folder = os.path.join(out_dir, f"{safe(artist)} - {safe(song_name)}")
    os.makedirs(folder, exist_ok=True)
    
    write_chart(os.path.join(folder, "notes.chart"), guitar_frets, bass_frets,
                tempo_map, song_name, artist, delay_beats=8.0)
    
    if tabs_text:
        with open(os.path.join(folder, "tabs.txt"), "w", encoding="utf-8") as f:
            f.write(tabs_text)
            
    ini = f"""[song]
name = {song_name}
artist = {artist}
album = 
genre = 
year = , 
charter = Guitar Charter Bot
diff_guitar = -1
diff_bass = -1
diff_drums = -1
diff_keys = -1
diff_vocals = -1
previewstart = 30000
previewend = 60000
"""
    with open(os.path.join(folder, "song.ini"), "w", encoding="utf-8") as f:
        f.write(ini)
        
    if audio_path and os.path.exists(audio_path):
        try:
            from pydub import AudioSegment
            first_bpm = tempo_map[0][1] if tempo_map else 120.0
            silence_ms = int((8.0 / first_bpm) * 60.0 * 1000)
            print(f"AUDIO: Prepending {silence_ms}ms of silence…")
            audio = AudioSegment.from_file(audio_path)
            silence = AudioSegment.silent(duration=silence_ms)
            delayed_audio = silence + audio
            out_audio = os.path.join(folder, "song.ogg")
            delayed_audio.export(out_audio, format="ogg")
        except ImportError:
            print("WARNING: pydub not installed. Run: pip install pydub")
            shutil.copy(audio_path, os.path.join(folder, "song.ogg"))
        except Exception as e:
            print(f"AUDIO ERROR: {e}")
            shutil.copy(audio_path, os.path.join(folder, "song.ogg"))
            
    return folder


def _chart_from_midi(mid_path, mp3_path, out_dir, song_name, artist, progress):
    from .midi_parser import parse_midi_file
    if progress: progress(10, "Parsing MIDI…")
    tracks = parse_midi_file(mid_path)
    if not tracks:
        return None

    tempo_map = tracks[0]["tempo_map"]
    tm = {t["name"]: t for t in tracks}

    stats = []
    for t in tracks:
        if not t["notes"]:
            continue
        pitches = [n[3] for n in t["notes"]]
        durs = [n[1] for n in t["notes"]]
        by_start = defaultdict(list)
        for n in t["notes"]:
            by_start[_tick_key(n[0])].append(n)
        avg_chord = sum(len(c) for c in by_start.values()) / len(by_start)
        avg_dur = sum(durs) / len(durs)

        stats.append({
            "name": t["name"],
            "n": len(t["notes"]),
            "avg_pitch": sum(pitches) / len(pitches),
            "min_pitch": min(pitches),
            "first_start": min(n[0] for n in t["notes"]),
            "avg_dur": avg_dur,
            "avg_chord": avg_chord,
        })

    # --- Classification (bulletproof, with loud WARN on drops) ---
    drums = None
    main_bass = None
    dist_bass = None
    guitar_candidates = []
    vocals = []

    for s in stats:
        label = (
            f"'{s['name']}' n={s['n']} pitch={s['avg_pitch']:.1f} "
            f"minpitch={s['min_pitch']} dur={s['avg_dur']:.3f} chord={s['avg_chord']:.2f}"
        )
        if s["avg_dur"] < 0.10 and s["n"] > 3000:
            drums = s["name"]; print(f"CLASS drums       <- {label}"); continue
        if s["avg_dur"] > 1.0 and s["n"] < 500:
            vocals.append(s);  print(f"CLASS vocals      <- {label}"); continue
        if s["avg_pitch"] < 43 and s["min_pitch"] < 30 and s["n"] > 500:
            main_bass = s["name"]; print(f"CLASS main_bass   <- {label}"); continue
        if s["avg_pitch"] < 43 and s["n"] > 2000:
            dist_bass = s["name"]; print(f"CLASS dist_bass   <- {label}"); continue
        if 60 <= s["avg_pitch"] <= 75 and 200 <= s["n"] < 400 and s["avg_dur"] < 0.4:
            guitar_candidates.append(s); print(f"CLASS guitar(lead) <- {label}"); continue
        if 40 <= s["avg_pitch"] <= 60 and s["n"] > 1000:
            guitar_candidates.append(s); print(f"CLASS guitar(rhy)  <- {label}"); continue
        # Last resort: keep the track as guitar rather than silently dropping it.
        print(f"WARN: {label} matched NO bucket — adding to guitar_candidates")
        guitar_candidates.append(s)

    guitar_candidates.sort(key=lambda x: x["n"], reverse=True)
    if len(guitar_candidates) >= 2:
        rhythm = guitar_candidates[0]["name"]
        lead = guitar_candidates[1]["name"]
    elif len(guitar_candidates) == 1:
        rhythm = lead = guitar_candidates[0]["name"]
    else:
        rhythm = lead = None
        for s in sorted(stats, key=lambda x: x["n"], reverse=True):
            if s["name"] != drums and s["name"] != main_bass:
                rhythm = lead = s["name"]
                break

    piano_lh = piano_rh = None
    taken = {rhythm, lead, drums, main_bass}
    piano_candidates = [s for s in stats if 500 < s["n"] < 1000 and s["name"] not in taken]
    piano_candidates.sort(key=lambda x: x["n"], reverse=True)
    if len(piano_candidates) >= 2:
        piano_lh = piano_candidates[0]["name"]
        piano_rh = piano_candidates[1]["name"]

    vocals.sort(key=lambda x: x["first_start"])
    main_vocal = vocals[0]["name"] if vocals else None

    print(f"\n=== HIERARCHY ===")
    print(f"  Lead (Solo):     {lead}")
    print(f"  Rhythm (Chords): {rhythm}")
    print(f"  Piano LH:        {piano_lh}")
    print(f"  Piano RH:        {piano_rh}")
    print(f"  Main Bass:       {main_bass}")
    print(f"  Dist Bass:       {dist_bass}")
    print(f"  Vocals:          {main_vocal}")

    if rhythm is None:
        print("ERROR: No guitar tracks found!")
        return None

    # --- Build tick -> {track_name: [notes]} index (plain dicts, no silent defaultdicts) ---
    active_tracks = [t for t in [lead, rhythm, piano_lh, piano_rh, main_vocal, dist_bass] if t]
    tick_to_notes = {}
    for t_name in active_tracks:
        for n in tm[t_name]["notes"]:
            tk = _tick_key(n[0])
            tick_to_notes.setdefault(tk, {}).setdefault(t_name, []).append(n)

    if not tick_to_notes:
        raise RuntimeError(
            "tick_to_notes is empty — no active track produced notes. "
            "Classifier output above; check WARN lines."
        )

    # --- Merge loop with per-tier hit counters so we can see what actually merged ---
    merged_guitar_notes = []
    hits = {"lead": 0, "rhythm": 0, "piano": 0, "vocal": 0, "dist_bass": 0, "missing": 0}

    for tk in sorted(tick_to_notes.keys()):
        bucket = tick_to_notes[tk]

        if lead and bucket.get(lead):
            merged_guitar_notes.extend(bucket[lead]); hits["lead"] += 1; continue

        if rhythm and bucket.get(rhythm):
            merged_guitar_notes.extend(bucket[rhythm]); hits["rhythm"] += 1; continue

        if piano_lh or piano_rh:
            lh = bucket.get(piano_lh, []) if piano_lh else []
            rh = bucket.get(piano_rh, []) if piano_rh else []
            if rh:
                merged_guitar_notes.append((tk, rh[0][1], 0, rh[0][3]))
                merged_guitar_notes.append((tk, rh[0][1], 0, 0))
                hits["piano"] += 1
                continue
            if lh:
                merged_guitar_notes.append((tk, lh[0][1], 0, 0))
                hits["piano"] += 1
                continue

        if main_vocal and bucket.get(main_vocal):
            for vn in bucket[main_vocal]:
                merged_guitar_notes.append((vn[0], min(vn[1], 0.5), 0, vn[3]))
            hits["vocal"] += 1
            continue

        if dist_bass and bucket.get(dist_bass):
            for bn in bucket[dist_bass]:
                merged_guitar_notes.append((bn[0], min(bn[1], 0.3), 0, 0))
            hits["dist_bass"] += 1
            continue

        hits["missing"] += 1

    print(f"TAB: {len(merged_guitar_notes)} raw guitar notes to map "
          f"(hits: {hits})")

    if not merged_guitar_notes:
        raise RuntimeError(
            "Zero guitar notes merged even though tick_to_notes is populated. "
            f"hits={hits}. Classifier likely put the real guitar track in a bucket "
            "that isn't consumed — inspect the CLASS lines above."
        )

    # --- Bass ---
    if main_bass:
        bass_notes = tm[main_bass]["notes"]
        bass_tuning = tm[main_bass]["tuning"]
    else:
        print("WARN: no track classified as main_bass — skipping [ExpertDoubleBass] section")
        bass_notes = []
        bass_tuning = [28, 33, 38, 43]

    guitar_m = map_to_ch_frets(merged_guitar_notes, [40, 45, 50, 55, 59, 64], is_bass=False)
    bass_m = map_to_ch_frets(bass_notes, bass_tuning, is_bass=True)

    def beat_to_sec(beat):
        sec = 0.0
        for i, (b_start, bpm) in enumerate(tempo_map):
            b_end = tempo_map[i + 1][0] if i + 1 < len(tempo_map) else float("inf")
            if beat <= b_end:
                return sec + (beat - b_start) * 60.0 / bpm
            sec += (b_end - b_start) * 60.0 / bpm
        return sec

    guitar_sec = [(beat_to_sec(b), beat_to_sec(b + d), f) for (b, d, f) in guitar_m]
    bass_sec = [(beat_to_sec(b), beat_to_sec(b + d), f) for (b, d, f) in bass_m]

    gcounts = [0] * 6
    for _, _, f in guitar_sec:
        gcounts[min(5, f)] += 1
    print(f"TAB: guitar fret histogram={gcounts}")

    bcounts = [0] * 6
    for _, _, f in bass_sec:
        bcounts[min(5, f)] += 1
    print(f"TAB: bass fret histogram={bcounts}")

    if progress: progress(90, "Writing chart…")
    return _write_song_folder(out_dir, song_name, artist, guitar_sec, bass_sec,
                              tempo_map, audio_path=mp3_path, tabs_text="MIDI")


def _chart_from_audio(mp3_path, out_dir, song_name, artist, progress, manual_bpm):
    if progress: progress(5, "Separating stems…")
    guitar_path, other, bass_path = separate_stems(mp3_path, out_dir)

    if progress: progress(30, "Estimating tempo…")
    if manual_bpm:
        bpm = float(manual_bpm)
    else:
        y, sr = librosa.load(guitar_path, sr=22050, mono=True)
        t, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(np.atleast_1d(t)[0]) or 120.0

    if progress: progress(50, "Detecting guitar…")
    hn = detect_notes_basic_pitch(guitar_path)
    filtered = hn[:]
    filtered.sort(key=lambda x: x[0])
    midi = [(n[0], n[1], n[2]) for n in filtered if 40 <= n[2] <= 88]
    gtab = build_tab_from_midi(midi)
    spb = 60.0 / bpm
    guitar_sec = [(t, e, f) for (t, e, s, f) in gtab]

    bass_sec = []
    if os.path.exists(bass_path):
        if progress: progress(65, "Bass…")
        try:
            from .bass_transcriber import detect_bass_notes
            rb = detect_bass_notes(bass_path)
            if rb:
                btab = build_bass_tab_from_midi(rb)
                bass_sec = [(t, e, f) for (t, e, s, f) in btab]
        except Exception as e:
            print(f"BASS failed: {e}")

    tempo_map = [(0.0, bpm)]
    out = _write_song_folder(out_dir, song_name, artist, guitar_sec, bass_sec,
                              tempo_map, audio_path=mp3_path, tabs_text="AI output")
    try:
        shutil.rmtree(os.path.join(out_dir, "htdemucs_6s"))
    except Exception:
        pass
    if progress: progress(100, "Done.")
    return out


def chart_mp3(mp3_path=None, gp_path=None, out_dir=None, song_name="Untitled",
              artist="Unknown", cfg=None, progress=None, manual_bpm=None):
    os.makedirs(out_dir, exist_ok=True)

    if gp_path and os.path.exists(gp_path):
        ext = os.path.splitext(gp_path)[1].lower()
        if ext in (".mid", ".midi"):
            result = _chart_from_midi(gp_path, mp3_path, out_dir, song_name,
                                       artist, progress)
            if result is not None:
                return result
            print("MIDI: falling back to MP3")
        else:
            print(f"TAB: unsupported format '{ext}' — please export to .mid via TuxGuitar")

    if not mp3_path or not os.path.exists(mp3_path):
        raise ValueError("No tab notes and no valid MP3")

    return _chart_from_audio(mp3_path, out_dir, song_name, artist,
                              progress, manual_bpm)