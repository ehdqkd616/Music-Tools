"""Splits an isolated vocal stem into lead and backing (chorus) vocals.

A karaoke model removes the lead vocal and keeps everything else. Fed the
Demucs vocal stem instead of a full mix, "everything else" is only the backing
vocals, so its two outputs are exactly lead and backing.

Like separator.py, `audio_separator` is imported lazily: workers/tasks/__init__.py
imports every task module in every worker, and only worker-mdx installs it.
"""

import os

from common.config import get_settings

_SEPARATORS: dict[str, object] = {}


def _get_separator(model_filename: str, output_dir: str):
    from audio_separator.separator import Separator

    if model_filename not in _SEPARATORS:
        separator = Separator(output_dir=output_dir, output_format="WAV")
        separator.load_model(model_filename=model_filename)
        _SEPARATORS[model_filename] = separator

    separator = _SEPARATORS[model_filename]
    # The loaded model keeps its own copy of the directory and is what actually
    # writes the files, so a reused separator has to have both updated.
    separator.output_dir = output_dir
    separator.model_instance.output_dir = output_dir
    return separator


def split_lead_backing(vocals_path: str, output_dir: str) -> dict[str, str]:
    """Returns {"lead": wav_path, "backing": wav_path}."""
    separator = _get_separator(get_settings().karaoke_model, output_dir)
    separator.separate(vocals_path, custom_output_names={"Vocals": "lead", "Instrumental": "backing"})

    paths = {stem: os.path.join(output_dir, f"{stem}.wav") for stem in ("lead", "backing")}
    missing = [path for path in paths.values() if not os.path.exists(path)]
    if missing:
        raise RuntimeError(f"karaoke model did not produce: {missing}")
    return paths
