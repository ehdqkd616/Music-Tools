"""Piano solo recording -> note events, using ByteDance's high-resolution piano
transcription model (piano_transcription_inference, MIT).

CPU inference in worker-mdx, roughly real time. Imports are lazy for the same
reason as separation/separator.py: every worker imports every task module.
"""

from common.config import get_settings

SAMPLE_RATE = 16000  # what the model was trained on (piano_transcription_inference.sample_rate)

_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from piano_transcription_inference import PianoTranscription

        _MODEL = PianoTranscription(device="cpu", checkpoint_path=get_settings().piano_checkpoint)
    return _MODEL


def transcribe(audio, midi_path: str) -> list[dict]:
    """`audio` is mono float at SAMPLE_RATE. Writes the as-played MIDI (with
    pedal) to `midi_path` and returns the note events
    ({onset_time, offset_time, midi_note, velocity}, times in seconds)."""
    import numpy as np

    result = _model().transcribe(np.asarray(audio, dtype=np.float32), midi_path)
    return result["est_note_events"]
