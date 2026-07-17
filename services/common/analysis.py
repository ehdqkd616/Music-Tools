"""§5.2.4 key / BPM / loudness detection.

Essentia (AGPL) and madmom (non-commercial license) are avoided on purpose —
see §6, they'd poison the license stack. This is librosa (ISC) + a
hand-rolled Krumhansl-Schmuckler correlation, ~60 lines, ~75-85% accuracy.

Lives in `common` (not `workers/dsp`) because both the API — which answers
GET /analyze/{media_id} synchronously since it usually finishes in seconds
(§7.1) — and the DSP worker's async `tasks.analyze_media` need it, and
neither should have to depend on the other's package tree.
"""

import librosa
import numpy as np
import pyloudnorm as pyln

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _z(p: np.ndarray) -> np.ndarray:
    return (p - p.mean()) / p.std()


def detect_key(y: np.ndarray, sr: int) -> dict:
    y_harm = librosa.effects.harmonic(y, margin=4)  # drop percussive content for accuracy
    chroma = librosa.feature.chroma_cqt(y=y_harm, sr=sr, bins_per_octave=36)
    profile = chroma.mean(axis=1)
    profile = (profile - profile.mean()) / (profile.std() + 1e-9)

    scores = []
    for i in range(12):
        maj = np.corrcoef(profile, np.roll(_z(MAJOR_PROFILE), i))[0, 1]
        mnr = np.corrcoef(profile, np.roll(_z(MINOR_PROFILE), i))[0, 1]
        scores.append((maj, f"{PITCHES[i]} Major", i, "major"))
        scores.append((mnr, f"{PITCHES[i]} Minor", i, "minor"))

    scores.sort(reverse=True, key=lambda x: x[0])
    best = scores[0]
    return {
        "key": best[1],
        "tonic": PITCHES[best[2]],
        "mode": best[3],
        "confidence": round(float(best[0]), 3),
        "alternates": [s[1] for s in scores[1:3]],
    }


def detect_bpm(y: np.ndarray, sr: int) -> dict:
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])

    # Octave-error correction — most tracks sit in 70-180 BPM. Guard tempo > 0:
    # beat_track returns 0.0 for signals with no detectable rhythm (silence, a
    # pure tone, etc), and `0 * 2` never climbs past 70 — that spun forever
    # before this guard existed.
    if tempo > 0:
        while tempo < 70:
            tempo *= 2
        while tempo > 180:
            tempo /= 2

    return {"bpm": round(tempo, 1), "beat_times": librosa.frames_to_time(beats, sr=sr).tolist()}


def measure_loudness(y: np.ndarray, sr: int) -> dict:
    meter = pyln.Meter(sr)  # ITU-R BS.1770-4
    return {
        "lufs_integrated": round(meter.integrated_loudness(y.T), 2),
        "true_peak_db": round(20 * np.log10(np.abs(y).max() + 1e-9), 2),
    }


def analyze_file(path: str) -> dict:
    y, sr = librosa.load(path, sr=None, mono=True)
    result = {}
    result.update(detect_key(y, sr))
    result.update(detect_bpm(y, sr))
    result.update(measure_loudness(y, sr))
    return result
