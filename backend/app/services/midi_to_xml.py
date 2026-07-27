"""MIDI to MusicXML conversion using music21."""

from pathlib import Path

import music21 as m21


def midi_to_musicxml(midi_path: Path, output_path: Path | None = None, split_hands: bool = True) -> Path:
    """Convert a MIDI file to MusicXML format with piano grand-staff formatting."""
    if output_path is None:
        output_path = midi_path.with_suffix(".musicxml")

    score = m21.converter.parse(str(midi_path))

    # Format as readable piano score
    _format_as_piano_score(score)

    if split_hands and len(score.parts) == 1:
        _split_into_grand_staff(score)

    score.write("musicxml", fp=str(output_path))
    return output_path


def _split_into_grand_staff(score):
    """Split a single-staff score into piano grand staff (RH treble, LH bass).

    Uses a smart split: simultaneous notes stay together, split point
    chosen to minimize within-hand pitch variance.
    """
    from music21 import stream, clef, instrument, note, chord as m21chord
    import statistics

    try:
        original_part = score.parts[0]
    except IndexError:
        return

    # Collect notes
    notes_only = []
    for el in original_part.flatten().notesAndRests:
        if isinstance(el, (note.Note, m21chord.Chord)):
            notes_only.append(el)

    if len(notes_only) < 2:
        return

    # Find optimal split point
    def _pitch(el):
        if isinstance(el, note.Note):
            return el.pitch.midi
        return sum(p.midi for p in el.pitches) / len(el.pitches)

    all_pitches = sorted([_pitch(el) for el in notes_only])

    best_split = 60  # Default C4
    best_score = float('inf')
    for candidate in range(48, 73):
        below = [p for p in all_pitches if p < candidate]
        above = [p for p in all_pitches if p >= candidate]
        if len(below) < 2 or len(above) < 2:
            continue
        var_below = statistics.variance(below)
        var_above = statistics.variance(above)
        sc = var_below * len(below) + var_above * len(above)
        if sc < best_score:
            best_score = sc
            best_split = candidate

    # Group simultaneous notes (within 30ms) into the same hand
    EPSILON = 0.03
    assignments = {}
    for el in notes_only:
        onset = float(el.offset)
        cluster_pitches = [_pitch(el)]
        for other in notes_only:
            if other is el:
                continue
            if abs(onset - float(other.offset)) < EPSILON:
                cluster_pitches.append(_pitch(other))
        cluster_avg = sum(cluster_pitches) / len(cluster_pitches)
        assignments[id(el)] = 'rh' if cluster_avg >= best_split else 'lh'

    has_rh = any(v == 'rh' for v in assignments.values())
    has_lh = any(v == 'lh' for v in assignments.values())
    if not has_rh or not has_lh:
        return

    # Build new parts with measure structure preserved
    rh_part = stream.Part()
    rh_part.insert(0, instrument.Piano())
    rh_part.insert(0, clef.TrebleClef())

    lh_part = stream.Part()
    lh_part.insert(0, instrument.Piano())
    lh_part.insert(0, clef.BassClef())

    for m in original_part.getElementsByClass(stream.Measure):
        rh_measure = stream.Measure(number=m.number)
        lh_measure = stream.Measure(number=m.number)

        ts = m.getTimeSignatures()
        if ts:
            rh_measure.timeSignature = ts[0]
            lh_measure.timeSignature = ts[0]

        for el in m.notesAndRests:
            if id(el) in assignments:
                if assignments[id(el)] == 'rh':
                    rh_measure.append(el)
                else:
                    lh_measure.append(el)
            elif isinstance(el, note.Rest):
                rh_measure.append(el)

        if len(rh_measure.notesAndRests) > 0:
            rh_part.append(rh_measure)
        if len(lh_measure.notesAndRests) > 0:
            lh_part.append(lh_measure)

    # Rebuild score — remove old part, insert new ones
    score.remove(original_part)
    score.insert(0, rh_part)
    score.insert(1, lh_part)


def _format_as_piano_score(score: m21.stream.Score) -> None:
    """Format a score for piano grand staff display."""
    from music21 import instrument, clef

    # Detect and set key signature
    try:
        detected_key = score.analyze("key")
        if detected_key:
            for part in score.parts:
                part.insert(0, detected_key)
    except Exception:
        pass

    # Ensure parts use piano instrument
    for part in score.parts:
        part.insert(0, instrument.Piano())

    # Simple hand/clef assignment
    _assign_hands(score)


def _assign_hands(score: m21.stream.Score) -> None:
    """Assign treble/bass clef based on average pitch."""
    from music21 import clef, chord

    for part in score.parts:
        existing = list(part.getElementsByClass(clef.Clef))
        if existing:
            continue

        pitches = []
        for n in part.flatten().notes:
            if isinstance(n, chord.Chord):
                pitches.extend(p.midi for p in n.pitches)
            else:
                pitches.append(n.pitch.midi)
        if pitches:
            avg = sum(pitches) / len(pitches)
            part.insert(0, clef.TrebleClef() if avg > 60 else clef.BassClef())


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
