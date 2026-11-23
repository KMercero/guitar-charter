"""Bass transcription via spectral flux + harmonic product spectrum."""
import librosa
import numpy as np

BASS_FMIN = 40.0
BASS_FMAX = 400.0
N_FFT = 4096

def _hps_pitch(spectrum, freqs, sr, fmin=BASS_FMIN, fmax=BASS_FMAX):
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not mask.any():
        return None
    spec = spectrum[mask].copy()
    freq_slice = freqs[mask]
    hps = spec.copy()
    for h in range(2, 5):
        down_len = len(spec) // h
        if down_len < 2:
            break
        harm = np.zeros_like(spec)
        harm[:down_len] = spec[::h][:down_len]
        hps *= harm
    peak_idx = int(np.argmax(hps))
    if hps[peak_idx] <= 0:
        return None
    return float(freq_slice[peak_idx])

def detect_bass_notes(wav_path, min_note_dur=0.08, delta=0.02):
    y, sr = librosa.load(wav_path, sr=11025, mono=True)
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=128, backtrack=True, units="frames",
        pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=delta,
    )
    if len(onset_frames) == 0:
        return []
    hop = 128
    stft = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=hop))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)
    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=hop)[0]
    avg_vol = float(np.mean(rms))
    vol_thresh = avg_vol * 0.3
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop)

    notes = []
    for i, onset_frame in enumerate(onset_frames):
        onset_t = onset_times[i]
        window_start = onset_frame
        window_end = min(stft.shape[1], onset_frame + 3)
        if window_end <= window_start:
            continue
        avg_spec = np.mean(stft[:, window_start:window_end], axis=1)
        if avg_spec.sum() < avg_vol * 100:
            continue
        freq = _hps_pitch(avg_spec, freqs, sr)
        if freq is None or freq < BASS_FMIN or freq > BASS_FMAX:
            continue
        midi = int(round(librosa.hz_to_midi(freq)))

        end_frame = onset_frame + 1
        max_frames = int(1.5 * sr / hop)
        while end_frame < min(len(rms), onset_frame + max_frames):
            if rms[end_frame] < vol_thresh:
                break
            end_frame += 1
        end_t = librosa.frames_to_time(end_frame, sr=sr, hop_length=hop)

        if end_t - onset_t < min_note_dur:
            end_t = onset_t + min_note_dur
        if i + 1 < len(onset_times):
            next_onset = onset_times[i + 1]
            if end_t > next_onset - 0.02:
                end_t = next_onset - 0.02
        notes.append((onset_t, end_t, midi))

    if len(notes) >= 2:
        retrig = []
        for n in notes:
            if retrig and n[2] == retrig[-1][2] and (n[0] - retrig[-1][0]) < 0.25:
                prev = retrig[-1]
                retrig[-1] = (prev[0], n[0] - 0.02, prev[2])
                retrig.append(n)
            else:
                retrig.append(n)
        notes = retrig

    if len(notes) >= 2:
        filled = []
        for i in range(len(notes) - 1):
            t, end_t, midi = notes[i]
            next_t = notes[i + 1][0]
            if next_t - end_t > 0.5:
                gap_start_frame = int(end_t * sr / hop)
                gap_end_frame = int(next_t * sr / hop)
                if gap_end_frame > gap_start_frame:
                    gap_energy = float(np.mean(rms[gap_start_frame:gap_end_frame]))
                    if gap_energy > vol_thresh * 0.5:
                        end_t = next_t - 0.02
            filled.append((t, end_t, midi))
        filled.append(notes[-1])
        notes = filled

    return notes