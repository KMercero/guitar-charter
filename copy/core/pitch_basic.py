"""Guitar stem -> [(time_sec, end_sec, midi_pitch, velocity), ...] via Basic Pitch."""
import os
import subprocess
import csv
import tempfile
import shutil
import mido

def _find_bp_exe():
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "bp_venv", "Scripts", "basic-pitch.exe")
    )

def _run_basic_pitch(bp_exe, wav_path, extra_args=None):
    temp_dir = tempfile.mkdtemp()
    temp_wav = os.path.join(temp_dir, "input.wav")
    try:
        shutil.copy(wav_path, temp_wav)
        cmd = [bp_exe, temp_dir, temp_wav, "--save-note-events"]
        if extra_args:
            cmd.extend(extra_args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("=== BASIC PITCH ERROR ===")
            print(result.stderr)
            raise RuntimeError("Basic Pitch failed.")

        csv_path = os.path.join(temp_dir, "input_basic_pitch.csv")
        notes = []
        if os.path.exists(csv_path):
            with open(csv_path, "r") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    try:
                        start_time = float(row[0])
                        end_time = float(row[1])
                        pitch_str = row[2]
                        velocity = float(row[3])
                        try:
                            pitch = int(round(float(pitch_str)))
                        except ValueError:
                            pitch = mido.note_to_midi(pitch_str)
                        notes.append((start_time, end_time, pitch, velocity))
                    except Exception:
                        continue
        notes.sort(key=lambda x: x[0])
        return notes
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def detect_notes_basic_pitch(wav_path, two_pass=False):
    bp_exe = _find_bp_exe()
    args = ["--onset-threshold", "0.5", "--minimum-note-length", "120"]
    return _run_basic_pitch(bp_exe, wav_path, extra_args=args)