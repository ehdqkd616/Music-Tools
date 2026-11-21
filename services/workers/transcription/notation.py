"""Note events -> a score (MusicXML) and an engraved PDF.

The MIDI keeps the performance as played. The score is a readable
approximation: notes are snapped to a 16th-note grid along the tracked beats
and simultaneous notes on one staff are merged into a single chord (notes held
under a moving line are cut at the next onset). Piano gets two staves split at
middle C, every other instrument one staff. Triplets and time signatures other
than 4/4 aren't detected.
"""

import io
from collections import defaultdict

import numpy as np

GRID = 4  # positions per quarter note -> 16th notes
SPLIT_PITCH = 60  # middle C and above go to the right hand
MAX_NOTE_QL = 8.0
TEXT_FONT = "NanumMyeongjo"  # covers Hangul titles; cairo has no per-glyph font fallback


def beat_grid(y, sr: int) -> tuple[float, np.ndarray]:
    """Tempo and beat times, folded into 60-150 BPM so the score reads naturally."""
    import librosa

    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0]) or 100.0
    beats = librosa.frames_to_time(frames, sr=sr)
    while bpm > 150 and len(beats) >= 4:
        beats, bpm = beats[::2], bpm / 2
    while bpm < 60:
        if len(beats) >= 2:
            beats = np.sort(np.concatenate([beats, (beats[:-1] + beats[1:]) / 2]))
        bpm *= 2
    return bpm, beats


def _to_beats(t: np.ndarray, beats: np.ndarray, bpm: float) -> np.ndarray:
    """Seconds -> beat positions along the tracked beats (so the grid follows tempo
    drift), extrapolated at the average tempo outside them."""
    if len(beats) < 2:
        return t * bpm / 60.0
    idx = np.arange(len(beats), dtype=float)
    period = 60.0 / bpm
    pos = np.interp(t, beats, idx)
    pos = np.where(t < beats[0], (t - beats[0]) / period, pos)
    return np.where(t > beats[-1], idx[-1] + (t - beats[-1]) / period, pos)


def _quantize(x: np.ndarray) -> np.ndarray:
    return np.round(x * GRID) / GRID


# instrument -> (part name, General MIDI program)
PART_INFO = {
    "piano": ("Piano", 0),
    "guitar": ("Guitar", 25),
    "bass": ("Bass", 33),
    "vocals": ("Voice", 53),
    "strings": ("Strings", 40),
    "winds": ("Winds", 73),
    "other": ("Instrument", 0),
}


WRITTEN_OCTAVE_UP = {"guitar", "bass"}


def _staves(instrument_name: str, midi_notes: list[int]):
    """[(staff id, clef, which notes go on it)] for the instrument."""
    from music21 import clef

    if instrument_name == "piano":
        return [
            ("rh", clef.TrebleClef(), lambda m: m >= SPLIT_PITCH),
            ("lh", clef.BassClef(), lambda m: m < SPLIT_PITCH),
        ]
    everything = lambda m: True  # noqa: E731
    if instrument_name == "guitar":
        return [("main", clef.Treble8vbClef(), everything)]
    if instrument_name == "bass":
        return [("main", clef.BassClef(), everything)]
    median = float(np.median(midi_notes))
    if instrument_name == "vocals" and median < 60:
        return [("main", clef.Treble8vbClef(), everything)]  # lower voices, as in choral scores
    return [("main", clef.TrebleClef() if median >= 55 else clef.BassClef(), everything)]


def build_score(events: list[dict], bpm: float, beats: np.ndarray, title: str | None, instrument_name: str = "piano"):
    from music21 import chord, instrument, interval, key, layout, metadata, meter, note, pitch, stream, tempo

    onsets = _to_beats(np.array([e["onset_time"] for e in events], dtype=float), beats, bpm)
    offsets = _to_beats(np.array([e["offset_time"] for e in events], dtype=float), beats, bpm)
    origin = np.floor(onsets.min())  # the first note starts measure 1
    q_on = _quantize(onsets - origin)
    q_off = np.maximum(_quantize(offsets - origin), q_on + 1 / GRID)

    staves = _staves(instrument_name, [int(e["midi_note"]) for e in events])
    groups_by_staff: dict[str, dict[float, dict[int, float]]] = {sid: defaultdict(dict) for sid, _, _ in staves}
    for e, on, off in zip(events, q_on, q_off):
        midi = int(e["midi_note"])
        sid = next(s for s, _, accepts in staves if accepts(midi))
        group = groups_by_staff[sid][float(on)]
        group[midi] = max(group.get(midi, 0.0), float(off))

    # Key from the notes themselves (Krumhansl-Schmuckler), which beats audio chroma
    # once we already have clean pitches.
    probe = stream.Stream()
    for e in events:
        probe.append(note.Note(int(e["midi_note"]), quarterLength=1))
    detected_key = probe.analyze("key")
    use_flats = detected_key.sharps < 0

    def spell(midi: int):
        p = pitch.Pitch(midi=midi)
        if use_flats and p.accidental is not None and p.accidental.name == "sharp":
            p = p.getEnharmonic()
        return p

    part_name, midi_program = PART_INFO.get(instrument_name, PART_INFO["other"])
    score = stream.Score()
    # Notes go in at sounding pitch; parts written an octave up (octave clefs) get
    # their written pitches and a MusicXML <transpose> from this on export.
    score.atSoundingPitch = True
    score.metadata = metadata.Metadata(title=title or part_name)
    staffs = []
    for index, (sid, staff_clef, _) in enumerate(staves):
        part = stream.PartStaff() if len(staves) > 1 else stream.Part()
        # A plain Instrument, not music21's Guitar/ElectricBass classes: those carry
        # transpositions that would shift the exported pitches.
        part_instrument = instrument.Piano() if instrument_name == "piano" else instrument.Instrument()
        if instrument_name != "piano":
            part_instrument.partName = part_name
            part_instrument.instrumentName = part_name
            part_instrument.midiProgram = midi_program
            # Guitar, bass and low voices are written an octave above how they sound.
            if instrument_name in WRITTEN_OCTAVE_UP or staff_clef.octaveChange == -1:
                part_instrument.transposition = interval.Interval("P-8")
        part.insert(0, part_instrument)
        part.insert(0, staff_clef)
        part.insert(0, key.KeySignature(detected_key.sharps))
        part.insert(0, meter.TimeSignature("4/4"))
        if index == 0:
            part.insert(0, tempo.MetronomeMark(number=round(bpm)))

        groups = sorted(groups_by_staff[sid].items())
        if not groups:
            part.insert(0, note.Rest(quarterLength=4))
        for i, (on, pitches) in enumerate(groups):
            end = max(pitches.values())
            if i + 1 < len(groups):
                end = min(end, groups[i + 1][0])
            spelled = [spell(m) for m in sorted(pitches)]
            element = note.Note(spelled[0]) if len(spelled) == 1 else chord.Chord(spelled)
            element.quarterLength = min(end - on, MAX_NOTE_QL)
            part.insert(on, element)

        staffs.append(part)
        score.insert(0, part)

    if len(staffs) > 1:
        score.insert(0, layout.StaffGroup(staffs, symbol="brace", barTogether=True))
    return score.makeNotation(), detected_key


def render_pdf(musicxml_path: str, pdf_path: str) -> int:
    """MusicXML -> A4 pages engraved by Verovio (SVG) -> one PDF. Returns the page count."""
    import cairosvg
    import verovio
    from pypdf import PdfReader, PdfWriter

    tk = verovio.toolkit()
    tk.setOptions({
        "pageWidth": 2100,
        "pageHeight": 2970,
        "pageMarginTop": 80,
        "pageMarginBottom": 80,
        "pageMarginLeft": 100,
        "pageMarginRight": 100,
        "scale": 40,
        "footer": "none",
        "breaks": "auto",
    })
    if not tk.loadFile(musicxml_path):
        raise RuntimeError("Verovio could not read the MusicXML")

    writer = PdfWriter()
    pages = tk.getPageCount()
    for page in range(1, pages + 1):
        svg = tk.renderToSVG(page).replace('font-family="Times, serif"', f'font-family="{TEXT_FONT}"')
        for pdf_page in PdfReader(io.BytesIO(cairosvg.svg2pdf(bytestring=svg.encode()))).pages:
            writer.add_page(pdf_page)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pages
