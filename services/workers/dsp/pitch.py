"""§5.2.2 / §5.2.3 — Rubber Band CLI (GPL v2). Invoked as a separate process,
never linked, and never via ffmpeg's --enable-gpl rubberband filter (§6.2).
Server-side use only — GPL's "distribution" trigger doesn't cover a network
service, so no source-disclosure obligation attaches here (§6.1).
"""

import subprocess


def pitch_shift(src: str, dst: str, semitones: float, stem_type: str = "other", fast: bool = False) -> None:
    """`fast=True` uses the R2 engine (`--fast`) instead of R3 (`--fine`) — R3
    "almost always produces better results... but with significantly higher
    CPU load" per the CLI's own help text, which is exactly why previews (which
    get thrown away the moment the user nudges the slider again) shouldn't pay
    for it — only the final export needs R3."""
    opts = ["rubberband", "--pitch", str(semitones), "--fast" if fast else "--fine"]

    if stem_type == "vocals":
        opts += ["--formant"]  # preserve formants — otherwise a raised key sounds like a chipmunk
    elif stem_type == "drums":
        opts += ["--percussive"]  # preserve transients
    elif not fast:
        # phase continuity for bass/other — measured at ~1.6x the runtime of plain
        # --fast on a real instrumental stem, so previews skip it and only pay for
        # it on the final export.
        opts += ["--smoothing"]

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
