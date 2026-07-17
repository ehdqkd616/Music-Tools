"""§5.2.2 / §5.2.3 — Rubber Band CLI (GPL v2). Invoked as a separate process,
never linked, and never via ffmpeg's --enable-gpl rubberband filter (§6.2).
Server-side use only — GPL's "distribution" trigger doesn't cover a network
service, so no source-disclosure obligation attaches here (§6.1).
"""

import subprocess


def pitch_shift(src: str, dst: str, semitones: float, stem_type: str = "other") -> None:
    opts = ["rubberband", "--pitch", str(semitones), "--fine"]

    if stem_type == "vocals":
        opts += ["--formant"]  # preserve formants — otherwise a raised key sounds like a chipmunk
    elif stem_type == "drums":
        opts += ["--percussive"]  # preserve transients
    else:
        opts += ["--smoothing"]  # phase continuity for bass/other

    opts += [src, dst]
    subprocess.run(opts, check=True, capture_output=True, shell=False)


def time_stretch(src: str, dst: str, ratio: float) -> None:
    """ratio 0.5 = half speed, 2.0 = double speed. Pitch stays constant."""
    subprocess.run(
        ["rubberband", "--tempo", str(ratio), "--fine", "--crisp", "5", src, dst],
        check=True,
        capture_output=True,
        shell=False,
    )
