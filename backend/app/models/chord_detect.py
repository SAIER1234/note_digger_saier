"""Chord detection from MIDI — CPU-friendly, template-based.

Groups notes into time windows and matches pitch class sets
against common chord templates. No deep learning deps.
"""

import numpy as np
import pretty_midi

# Chord templates: (chord_name, semitone_intervals_from_root)
CHORD_TEMPLATES = [
    ("", [0, 4, 7]),           # Major
    ("m", [0, 3, 7]),          # Minor
    ("7", [0, 4, 7, 10]),      # Dominant 7
    ("m7", [0, 3, 7, 10]),     # Minor 7
    ("maj7", [0, 4, 7, 11]),   # Major 7
    ("dim", [0, 3, 6]),        # Diminished
    ("aug", [0, 4, 8]),        # Augmented
    ("sus4", [0, 5, 7]),       # Sus4
    ("m7b5", [0, 3, 6, 10]),   # Half-diminished
    ("6", [0, 4, 7, 9]),       # Major 6
    ("m6", [0, 3, 7, 9]),      # Minor 6
]

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def detect_chords(midi_path: str, window_beats: float = 1.0, bpm: float = 120.0) -> list[dict]:
    """
    Detect chords from MIDI by time-window pitch class analysis.

    Returns list of {start, end, chord, confidence}.
    """
    midi = pretty_midi.PrettyMIDI(str(midi_path))

    # Collect all note events
    all_notes = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            all_notes.append((note.start, note.end, note.pitch))

    if not all_notes:
        return []

    # Sort by start time
    all_notes.sort()

    # Segment into windows
    window_sec = window_beats * 60.0 / bpm
    max_time = max(n.end for n in all_notes)
    num_windows = int(np.ceil(max_time / window_sec))

    chords = []
    for wi in range(num_windows):
        t_start = wi * window_sec
        t_end = t_start + window_sec

        # Find active notes in this window
        window_pitches = set()
        for start, end, pitch in all_notes:
            if start < t_end and end > t_start:
                window_pitches.add(pitch % 12)

        if len(window_pitches) < 3:
            continue

        # Match against templates
        best_chord, best_confidence = _match_chord(window_pitches)

        if best_confidence > 0.5:
            chords.append({
                "start": round(t_start, 2),
                "end": round(t_end, 2),
                "chord": best_chord,
                "confidence": round(best_confidence, 2),
            })

    # Merge consecutive identical chords
    return _merge_chords(chords)


def _match_chord(pitch_classes: set) -> tuple[str, float]:
    """Match a set of pitch classes against chord templates."""
    best_name = "?"
    best_score = 0.0
    pcs = sorted(pitch_classes)

    for root in range(12):
        for suffix, intervals in CHORD_TEMPLATES:
            expected = {(root + i) % 12 for i in intervals}
            match_count = len(pitch_classes & expected)
            extra_count = len(pitch_classes - expected)
            # Score: prefer higher match ratio, penalize extra notes
            if len(expected) > 0:
                score = match_count / len(expected) - extra_count * 0.2
                score = max(0, score)
                if score > best_score:
                    best_score = score
                    best_name = f"{NOTE_NAMES[root]}{suffix}"

    return best_name, best_score


def _merge_chords(chords: list[dict]) -> list[dict]:
    """Merge consecutive chords with the same name."""
    if not chords:
        return []
    merged = [chords[0]]
    for c in chords[1:]:
        if c["chord"] == merged[-1]["chord"]:
            merged[-1]["end"] = c["end"]
        else:
            merged.append(c)
    return merged


def format_chord_line(chords: list[dict]) -> str:
    """Format chords as a readable line: | C | Am | F | G |"""
    if not chords:
        return ""
    return " | ".join(c["chord"] for c in chords)
