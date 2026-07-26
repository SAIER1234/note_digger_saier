"""MIDI to MusicXML conversion using music21."""

from pathlib import Path

import music21 as m21


def midi_to_musicxml(midi_path: Path, output_path: Path | None = None, split_hands: bool = True) -> Path:
    """
    Convert a MIDI file to MusicXML format with piano grand-staff formatting.
    """
    if output_path is None:
        output_path = midi_path.with_suffix(".musicxml")

    # Use music21's built-in MIDI parsing — better measure detection
    score = m21.converter.parse(str(midi_path))

    # Format as readable piano score
    _format_as_piano_score(score)

    if split_hands and len(score.parts) == 1:
        _split_into_grand_staff(score)

    score.write("musicxml", fp=str(output_path))
    return output_path


def _split_into_grand_staff(score):
    """Split a single-staff score into grand staff (RH treble, LH bass)."""
    from music21 import stream, clef, instrument, note, chord as m21chord

    SPLIT_PITCH = 60  # C4

    try:
        original_part = score.parts[0]
    except IndexError:
        return

    # Collect notes
    rh_notes = []
    lh_notes = []
    for el in original_part.flatten().notesAndRests:
        if isinstance(el, (note.Note, m21chord.Chord)):
            pitches = [el.pitch.midi] if isinstance(el, note.Note) else [p.midi for p in el.pitches]
            avg = sum(pitches) / len(pitches)
            if avg >= SPLIT_PITCH:
                rh_notes.append(el)
            else:
                lh_notes.append(el)

    # If no split possible, keep as-is
    if not rh_notes or not lh_notes:
        return

    # Create RH part
    rh_part = stream.Part()
    rh_part.insert(0, instrument.Piano())
    rh_part.insert(0, clef.TrebleClef())
    for n in rh_notes:
        rh_part.append(n)

    # Create LH part
    lh_part = stream.Part()
    lh_part.insert(0, instrument.Piano())
    lh_part.insert(0, clef.BassClef())
    for n in lh_notes:
        lh_part.append(n)

    # Replace original parts
    score.remove(original_part)
    score.insert(0, rh_part)
    score.insert(1, lh_part)


def _format_as_piano_score(score: m21.stream.Score) -> None:
    """Format a score for piano grand staff display."""
    from music21 import instrument, clef, key, meter

    # Detect and set key signature
    try:
        detected_key = score.analyze("key")
        if detected_key:
            for part in score.parts:
                part.insert(0, detected_key)
    except Exception:
        pass  # Skip key detection if not enough notes

    # Ensure parts use piano instrument
    for part in score.parts:
        part.insert(0, instrument.Piano())

    # Try to split right/left hand based on pitch
    # (simplified; more sophisticated splitting could use ML)
    _assign_hands(score)


def _assign_hands(score: m21.stream.Score) -> None:
    """Simple hand assignment: split at middle C (C4 = MIDI 60)."""
    from music21 import clef

    for part in score.parts:
        # Check if this part already has a clef assignment
        existing_clefs = list(part.getElementsByClass(clef.Clef))
        if existing_clefs:
            continue  # Don't overwrite existing clefs

        # Get pitch range (handle Note and Chord)
        from music21 import chord
        pitches = []
        for n in part.flatten().notes:
            if isinstance(n, chord.Chord):
                pitches.extend(p.midi for p in n.pitches)
            else:
                pitches.append(n.pitch.midi)
        if not pitches:
            continue

        avg_pitch = sum(pitches) / len(pitches)
        if avg_pitch > 60:
            part.insert(0, clef.TrebleClef())
        else:
            part.insert(0, clef.BassClef())


def musicxml_to_pretty_string(musicxml_path: Path) -> str:
    """Load MusicXML and return a human-readable summary."""
    score = m21.converter.parse(str(musicxml_path))
    parts_info = []
    for i, part in enumerate(score.parts):
        notes = list(part.flatten().notes)
        from music21 import chord
        pitches = []
        for n in notes[:20]:
            if isinstance(n, chord.Chord):
                pitches.extend(str(p) for p in n.pitches)
            else:
                pitches.append(str(n.pitch))
        parts_info.append(
            f"Part {i+1}: {len(notes)} notes, "
            f"range {min(pitches)} - {max(pitches)}"
        )
    return "\n".join(parts_info)
