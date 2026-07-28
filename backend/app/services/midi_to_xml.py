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

    # Add dynamic markings from MIDI velocities
    _add_dynamic_markings(score)

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


def _add_dynamic_markings(score: m21.stream.Score) -> None:
    """Add dynamic markings (pp/p/mp/mf/f/ff) and crescendo/decrescendo
    hairpins based on MIDI note velocities.

    Reads velocities from the parsed score, computes per-measure average
    velocity, and inserts music21 Dynamic objects where the dynamic level
    changes. Adds crescendo/decrescendo hairpins for gradual transitions.
    """
    from music21 import dynamics, chord, note, stream

    # Velocity → dynamic mapping
    def velocity_to_dynamic(vel: float) -> tuple[str, float]:
        if vel < 30:
            return 'pp', vel
        elif vel < 45:
            return 'p', vel
        elif vel < 60:
            return 'mp', vel
        elif vel < 78:
            return 'mf', vel
        elif vel < 95:
            return 'f', vel
        else:
            return 'ff', vel

    for part in score.parts:
        measures = list(part.getElementsByClass(stream.Measure))
        if not measures:
            continue

        # Compute average velocity per measure
        measure_dynamics = []
        for m in measures:
            velocities = []
            for el in m.flatten().notes:
                if hasattr(el, 'volume') and hasattr(el.volume, 'velocity'):
                    velocities.append(el.volume.velocity)
            if velocities:
                avg_vel = sum(velocities) / len(velocities)
                dyn_name, _ = velocity_to_dynamic(avg_vel)
                measure_dynamics.append((m, avg_vel, dyn_name))
            else:
                # Measure with rests only — inherit previous dynamic
                if measure_dynamics:
                    measure_dynamics.append((m, measure_dynamics[-1][1], measure_dynamics[-1][2]))

        if not measure_dynamics:
            continue

        # Insert dynamic markings where level changes
        prev_dyn = None
        for i, (measure, avg_vel, dyn_name) in enumerate(measure_dynamics):
            if dyn_name != prev_dyn:
                try:
                    dyn = dynamics.Dynamic(dyn_name)
                    # Place at start of measure (before first note/rest)
                    measure.insert(0, dyn)
                except Exception:
                    pass
                prev_dyn = dyn_name

            # Check for crescendo/decrescendo across consecutive measures
            if i >= 2:
                v1 = measure_dynamics[i-2][1]
                v2 = measure_dynamics[i-1][1]
                v3 = measure_dynamics[i][1]
                # Detect sustained rise or fall (>10 velocity change over 2 measures)
                if v3 - v1 > 10 and v2 > v1:
                    try:
                        hairpin = dynamics.Crescendo()
                        # Place at end of first measure in the sequence
                        prev_measure = measure_dynamics[i-1][0]
                        prev_measure.insert(len(list(prev_measure.notesAndRests)), hairpin)
                    except Exception:
                        pass
                elif v1 - v3 > 10 and v2 < v1:
                    try:
                        hairpin = dynamics.Decrescendo()
                        prev_measure = measure_dynamics[i-1][0]
                        prev_measure.insert(len(list(prev_measure.notesAndRests)), hairpin)
                    except Exception:
                        pass


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
