"""Piano arrangement engine — melody extraction, LH accompaniment, difficulty grading.

Model-agnostic: works on any MIDI output (Basic Pitch, Aria-AMT, etc.)
Pure rule-based music theory — no ML training needed.
"""

import numpy as np
import pretty_midi

# Style presets for left-hand accompaniment
STYLES = {
    "arpeggio": {   # Classical arpeggio patterns (e.g. Moonlight Sonata)
        "name": "琶音",
        "pattern": [0, 1, 2, 1],   # root → 3rd → 5th → 3rd
        "rhythm": 0.25,              # 16th notes
    },
    "block": {      # Block chords (pop/rock style)
        "name": "柱式和弦",
        "pattern": [0, 1, 2],        # all notes together
        "rhythm": 1.0,               # quarter notes
    },
    "broken": {     # Broken chords (ballad style)
        "name": "分解和弦",
        "pattern": [0, 1, 2, 3, 2, 1],  # root-3rd-5th-octave-5th-3rd
        "rhythm": 0.5,                    # 8th notes
    },
    "alberti": {    # Alberti bass (Mozart style)
        "name": "阿尔贝蒂低音",
        "pattern": [0, 2, 1, 2],   # root-5th-3rd-5th
        "rhythm": 0.25,              # 16th notes
    },
}

CHORD_PATTERNS = {
    "":     [0, 4, 7],      # major
    "m":    [0, 3, 7],      # minor
    "7":    [0, 4, 7, 10],  # dominant 7
    "m7":   [0, 3, 7, 10],  # minor 7
    "maj7": [0, 4, 7, 11],  # major 7
    "dim":  [0, 3, 6],      # diminished
    "aug":  [0, 4, 8],      # augmented
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def extract_melody(midi: pretty_midi.PrettyMIDI, split_pitch: int = 60) -> tuple[list, list]:
    """Split MIDI notes into melody (top notes) and harmony (lower notes)."""
    all_notes = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            all_notes.append(note)

    # Group notes by onset time (within 50ms = simultaneous)
    all_notes.sort(key=lambda n: n.start)
    melody_notes = []
    harmony_notes = []

    i = 0
    while i < len(all_notes):
        # Find simultaneous group
        group = [all_notes[i]]
        j = i + 1
        while j < len(all_notes) and all_notes[j].start - group[0].start < 0.05:
            group.append(all_notes[j])
            j += 1

        # Top note → melody, rest → harmony
        group.sort(key=lambda n: n.pitch, reverse=True)
        melody_notes.append(group[0])
        harmony_notes.extend(group[1:])
        i = j

    return melody_notes, harmony_notes


def generate_accompaniment(
    chords: list[dict],
    style: str = "broken",
    bpm: float = 120.0,
    velocity: int = 60,
) -> list[pretty_midi.Note]:
    """Generate left-hand accompaniment notes based on chord progression and style."""
    if style not in STYLES:
        style = "broken"

    style_config = STYLES[style]
    pattern = style_config["pattern"]
    rhythm = style_config["rhythm"]
    beat_duration = 60.0 / bpm
    note_duration = beat_duration * rhythm

    acc_notes = []
    for chord_info in chords:
        chord_name = chord_info["chord"]
        start_time = chord_info["start"]
        end_time = chord_info["end"]

        # Parse chord: "C", "Am", "G7" etc.
        root_str = chord_name.rstrip("mM7ajdimusg#0123456789b")
        # Extract root note
        root_pc = _note_name_to_pc(root_str) if root_str else 0
        # Extract chord quality suffix
        suffix = chord_name[len(root_str):]

        # Get chord intervals
        intervals = CHORD_PATTERNS.get(suffix, CHORD_PATTERNS[""])

        # Build chord notes in octave 3 (C3-B3 = MIDI 48-59)
        base_octave = 3
        chord_midi = [root_pc + 12 * base_octave + interval for interval in intervals]
        # Keep in bass range (MIDI 36-60)
        chord_midi = [max(36, min(60, m)) for m in chord_midi]

        # Apply pattern
        t = start_time
        pattern_idx = 0
        while t < end_time:
            step = pattern[pattern_idx % len(pattern)]
            if step < len(chord_midi):
                midi_pitch = chord_midi[step]
                acc_notes.append(pretty_midi.Note(
                    velocity=velocity,
                    pitch=midi_pitch,
                    start=t,
                    end=min(t + note_duration * 0.9, end_time),
                ))
            t += note_duration
            pattern_idx += 1
            if t + note_duration > end_time:
                break

    return acc_notes


def arrange_piano(
    midi_path: str,
    output_path: str,
    style: str = "broken",
    difficulty: str = "medium",
    bpm: float = 120.0,
) -> str:
    """
    Full piano arrangement:
    1. Extract melody (right hand)
    2. Detect chords
    3. Generate accompaniment (left hand)
    4. Combine into piano MIDI
    """
    midi = pretty_midi.PrettyMIDI(midi_path)

    # Extract melody
    melody_notes, harmony_notes = extract_melody(midi)

    # Detect chords
    from app.models.chord_detect import detect_chords
    chords = detect_chords(midi_path)

    # Difficulty adjustments
    velocity_map = {
        "easy": 50,
        "medium": 65,
        "hard": 80,
    }
    acc_velocity = velocity_map.get(difficulty, 65)

    if difficulty == "easy":
        # Easier: block chords, slower
        style = "block"
    elif difficulty == "medium":
        style = "broken"
    elif difficulty == "hard":
        style = style  # Use selected style

    # Generate accompaniment
    acc_notes = generate_accompaniment(chords, style=style, bpm=bpm, velocity=acc_velocity)

    # Create output MIDI
    out_midi = pretty_midi.PrettyMIDI()
    # RH: melody
    rh_track = pretty_midi.Instrument(program=0, name="Right Hand")
    for n in melody_notes:
        rh_track.notes.append(pretty_midi.Note(
            velocity=n.velocity, pitch=n.pitch,
            start=n.start, end=n.end,
        ))
    out_midi.instruments.append(rh_track)

    # LH: accompaniment
    lh_track = pretty_midi.Instrument(program=0, name="Left Hand")
    for n in acc_notes:
        lh_track.notes.append(n)
    out_midi.instruments.append(lh_track)

    out_midi.write(output_path)
    return output_path


def _note_name_to_pc(name: str) -> int:
    """Convert note name to pitch class (C=0, C#=1, etc.)"""
    name = name.strip().upper()
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    if not name:
        return 0
    pc = base.get(name[0], 0)
    if len(name) > 1 and name[1] == "#":
        pc += 1
    elif len(name) > 1 and name[1] == "B":
        pc -= 1
    return pc % 12
