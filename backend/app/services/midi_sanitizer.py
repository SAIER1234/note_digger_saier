"""MIDI sanitizer — removes garbage notes that ruin sheet music and playback.

Must be called as FINAL step before MusicXML conversion and output.
Handles: ghost notes, infinite durations, zero velocities, overlaps.
"""

from pathlib import Path
import pretty_midi


def sanitize_midi(midi_path: Path, output_path: Path | None = None) -> Path:
    """Clean up a MIDI file for safe playback and sheet music rendering.

    Rules:
    - Remove notes shorter than 40ms (inaudible noise)
    - Cap notes longer than 16 seconds (prevent duplex-maxima)
    - Remove notes with velocity < 1
    - Remove duplicate overlapping notes (keep louder)
    - Remove notes outside piano range (MIDI 21-108)
    - Enforce minimum 10ms gap between same-pitch notes
    """
    if output_path is None:
        output_path = midi_path

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    removed = 0
    capped = 0

    for inst in midi.instruments:
        if inst.is_drum:
            continue

        new_notes = []
        for note in sorted(inst.notes, key=lambda n: (n.pitch, n.start)):
            dur = note.end - note.start

            # 1. Ghost note — too short
            if dur < 0.04:
                removed += 1
                continue

            # 2. Infinite note — cap it
            if dur > 16.0:
                note.end = note.start + 16.0
                capped += 1

            # 3. Dead note
            if note.velocity < 1:
                note.velocity = 64

            # 4. Out of piano range
            if note.pitch < 21 or note.pitch > 108:
                removed += 1
                continue

            # 5. Overlapping same pitch — keep louder, truncate earlier
            if new_notes and new_notes[-1].pitch == note.pitch:
                prev = new_notes[-1]
                if note.start < prev.end:
                    overlap = prev.end - note.start
                    prev_dur = prev.end - prev.start
                    if overlap > prev_dur * 0.5:
                        # Major overlap — keep louder
                        if note.velocity > prev.velocity:
                            new_notes[-1] = note
                        removed += 1
                        continue
                    else:
                        # Minor overlap — truncate, keep both with gap
                        prev.end = max(prev.start, note.start - 0.01)

            new_notes.append(note)

        inst.notes = new_notes

    # Write cleaned MIDI
    midi.write(str(output_path))

    return output_path
