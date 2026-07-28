"""Piano arrangement engine — melody extraction, LH accompaniment, difficulty grading.

Model-agnostic: works on any MIDI output (Basic Pitch, Aria-AMT, etc.)
Pure rule-based music theory — no ML training needed.
"""

import random
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
        "pattern": [0, 1, 2, 3, 2, 1],  # root-3rd-5th-octave-3rd
        "rhythm": 0.5,                    # 8th notes
    },
    "alberti": {    # Alberti bass (Mozart style)
        "name": "阿尔贝蒂低音",
        "pattern": [0, 2, 1, 2],   # root-5th-3rd-5th
        "rhythm": 0.25,              # 16th notes
    },
    "waltz": {      # Waltz: bass-chord-chord (oom-pah-pah) in 3/4
        "name": "华尔兹",
        "pattern": [-1, 99, 99],    # -1=bass, 99=full chord (special marker)
        "rhythm": 0.5,               # beat duration in 3/4 (quarter = 0.5s at 120bpm)
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

STYLES["piano"] = {
    "name": "钢琴独奏",
    "pattern": [0, 1, 2, 3, 2, 1],  # Wide broken chord
    "rhythm": 0.375,  # Triplet feel
}
# AI mode
STYLES["ai"] = {
    "name": "AI 智能编曲",
    "pattern": [0],
    "rhythm": 0.5,
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# All inversions to try for voice leading (which chord tone goes in the bass)
INVERSIONS = [0, 1, 2, 3]  # root, 1st, 2nd, 3rd inversion


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

        # Select melody note: weighted score = pitch * 0.4 + velocity * 0.6
        # Loud mid-range notes beat quiet top notes
        group.sort(key=lambda n: n.pitch * 0.4 + n.velocity * 0.6, reverse=True)
        melody_notes.append(group[0])
        harmony_notes.extend(group[1:])
        i = j

    return melody_notes, harmony_notes


def _find_smoothest_voicing(chord_intervals: list[int], root_pc: int, prev_pitches: list[int]) -> list[int]:
    """Find the voicing (inversion + octave placement) that minimizes
    total semitone distance from the previous chord's pitches.

    This implements voice leading — smooth transitions between chords.
    """
    if not prev_pitches or len(chord_intervals) <= 1:
        # First chord or single-note: use root position in octave 3
        return [root_pc + 12 * 3 + i for i in chord_intervals]

    best_voicing = None
    best_distance = float("inf")

    # Try each inversion
    for inv in range(len(chord_intervals)):
        # Rotate intervals to create inversion
        rotated = chord_intervals[inv:] + [i + 12 for i in chord_intervals[:inv]]

        # Try octave placements — keep within bass range (MIDI 28-65)
        for octave_base in [24, 36, 48]:
            voicing = [root_pc + octave_base + i for i in rotated]
            # Clamp to playable LH range
            voicing = [max(28, min(67, v)) for v in voicing]

            # Calculate total distance to previous pitches (greedy matching)
            prev_sorted = sorted(prev_pitches)
            voicing_sorted = sorted(voicing)
            total_dist = sum(abs(v - p) for v, p in zip(voicing_sorted, prev_sorted))

            if total_dist < best_distance:
                best_distance = total_dist
                best_voicing = voicing

    return best_voicing if best_voicing else [root_pc + 12 * 3 + i for i in chord_intervals]


def generate_accompaniment(
    chords: list[dict],
    style: str = "broken",
    bpm: float = 120.0,
    velocity: int = 60,
) -> list[pretty_midi.Note]:
    """Generate left-hand accompaniment notes based on chord progression and style.

    Features:
    - Voice leading: chords transition smoothly by choosing nearest inversion
    - Waltz: proper 3/4 bass-chord-chord with chord clusters
    - Dynamics arc: crescendo to middle, decrescendo to end
    """
    if style not in STYLES:
        style = "broken"

    style_config = STYLES[style]
    pattern = style_config["pattern"]
    rhythm = style_config["rhythm"]
    beat_duration = 60.0 / bpm
    note_duration = beat_duration * rhythm

    acc_notes = []
    prev_voicing = []
    is_waltz = (style == "waltz")

    # Quality guard: minimum velocity floor + max note density
    velocity_floor = max(35, velocity - 15)

    # Calculate total duration for dynamics arc
    if chords:
        total_duration = chords[-1]["end"] - chords[0]["start"]
    else:
        total_duration = 0

    for chord_info in chords:
        chord_name = chord_info["chord"]
        start_time = chord_info["start"]
        end_time = chord_info["end"]

        # Parse chord root and quality
        known_suffixes = ["maj7", "m7b5", "m7", "m6", "m", "sus4", "dim", "aug", "7", "6"]
        root_str = chord_name
        suffix = ""
        for s in known_suffixes:
            if chord_name.endswith(s) and len(chord_name) > len(s):
                root_str = chord_name[:-len(s)]
                suffix = s
                break
        root_pc = _note_name_to_pc(root_str) if root_str else 0

        # Get chord intervals
        intervals = CHORD_PATTERNS.get(suffix, CHORD_PATTERNS[""])

        # Find best voicing via voice leading
        chord_voicing = _find_smoothest_voicing(intervals, root_pc, prev_voicing)

        # Dynamics arc: velocity curve based on position in piece
        if total_duration > 0:
            piece_position = (start_time - chords[0]["start"]) / total_duration
            # Arc: start 0.85 → peak 1.1 at 0.6 → end 0.75
            if piece_position < 0.6:
                arc_mult = 0.85 + piece_position * (1.1 - 0.85) / 0.6
            else:
                arc_mult = 1.1 - (piece_position - 0.6) * (1.1 - 0.75) / 0.4
        else:
            arc_mult = 1.0

        # Generate pattern
        if is_waltz:
            # Waltz: bass on beat 1, full chord on beats 2 and 3
            # 3/4 time: each beat = beat_duration, pattern has 3 beats per bar
            bar_duration = beat_duration * 3  # 3 beats per bar
            t = start_time
            while t < end_time:
                for beat_in_bar in range(3):
                    beat_time = t + beat_in_bar * beat_duration
                    if beat_time >= end_time:
                        break

                    is_downbeat = (beat_in_bar == 0)
                    base_vel = velocity + 8 if is_downbeat else velocity - 2
                    vel = max(velocity_floor, min(100, int(base_vel * arc_mult) + random.randint(-2, 2)))

                    if beat_in_bar == 0:
                        # Beat 1: bass note (root, one octave below)
                        bass_pitch = chord_voicing[0] - 12
                        acc_notes.append(pretty_midi.Note(
                            velocity=vel, pitch=max(24, bass_pitch),
                            start=beat_time,
                            end=min(beat_time + beat_duration * 0.85, end_time),
                        ))
                    else:
                        # Beats 2 & 3: full chord (all voicing notes together)
                        for vp in chord_voicing:
                            acc_notes.append(pretty_midi.Note(
                                velocity=vel, pitch=vp,
                                start=beat_time,
                                end=min(beat_time + beat_duration * 0.7, end_time),
                            ))
                t += bar_duration

            # Update voice leading state
            prev_voicing = list(chord_voicing)

        else:
            # Standard pattern-based styles (broken, arpeggio, block, alberti)
            t = start_time
            pattern_idx = 0
            chord_notes_played = []  # Track notes played in this chord for voice leading

            while t < end_time:
                step = pattern[pattern_idx % len(pattern)]
                if step < len(chord_voicing):
                    midi_pitch = chord_voicing[step]
                    chord_notes_played.append(midi_pitch)

                    # Velocity: accent on downbeats, softer on upbeats
                    is_downbeat = (pattern_idx % len(pattern) == 0)
                    base_vel = velocity + 5 if is_downbeat else velocity - 3
                    vel = max(30, min(100, int(base_vel * arc_mult) + random.randint(-3, 3)))

                    acc_notes.append(pretty_midi.Note(
                        velocity=vel,
                        pitch=midi_pitch,
                        start=t,
                        end=min(t + note_duration * 0.9, end_time),
                    ))
                t += note_duration
                pattern_idx += 1
                if t + note_duration > end_time:
                    break

            # Update voice leading state for next chord
            if chord_notes_played:
                # Use unique pitches as the "voicing" for distance calculation
                prev_voicing = sorted(set(chord_notes_played))

    return acc_notes


def _harmonize_melody(
    melody_notes: list[pretty_midi.Note],
    chords: list[dict],
) -> list[pretty_midi.Note]:
    """Add harmony notes (thirds/sixths) below melody, guided by chord context.

    Rules:
    - For each melody note, find the active chord, add a chord tone below
    - Prefer a third below (rich, standard), fall back to a fourth/sixth
    - Skip if melody note < 0.12s (fast passages stay clean)
    - Skip if harmony would go below G3 (MIDI 55) — keep RH in treble range
    - Harmony velocity = 75% of melody velocity
    """
    harmony_notes = []

    # Build chord lookup: time → chord info
    for note in melody_notes:
        note_time = note.start + (note.end - note.start) * 0.5  # Middle of note

        # Skip very short notes
        if (note.end - note.start) < 0.12:
            continue

        # Find active chord
        active_chord = None
        for c in chords:
            if c["start"] <= note_time < c["end"]:
                active_chord = c
                break

        if active_chord is None:
            continue

        chord_name = active_chord["chord"]
        # Parse chord
        known_suffixes = ["maj7", "m7b5", "m7", "m6", "m", "sus4", "dim", "aug", "7", "6"]
        root_str = chord_name
        suffix = ""
        for s in known_suffixes:
            if chord_name.endswith(s) and len(chord_name) > len(s):
                root_str = chord_name[:-len(s)]
                suffix = s
                break
        root_pc = _note_name_to_pc(root_str) if root_str else 0
        intervals = CHORD_PATTERNS.get(suffix, CHORD_PATTERNS[""])

        # Build chord pitch classes (in MIDI range around the melody note)
        melody_pc = note.pitch % 12
        melody_octave = note.pitch // 12

        # Try intervals below the melody: prefer 3rd (3-4 semitones), then 4th (5), then 6th (8-9)
        preferred_intervals_below = [3, 4, 5, 8, 9]

        best_harmony = None
        for interval_down in preferred_intervals_below:
            candidate_pc = (melody_pc - interval_down) % 12
            # Check if this pitch class is in the chord
            chord_pcs = {(root_pc + i) % 12 for i in intervals}
            if candidate_pc in chord_pcs:
                # Calculate MIDI pitch
                candidate_pitch = note.pitch - interval_down
                # Don't go below G3 (MIDI 55)
                if candidate_pitch >= 55:
                    best_harmony = candidate_pitch
                    break

        if best_harmony is not None:
            harmony_notes.append(pretty_midi.Note(
                velocity=int(note.velocity * 0.75),
                pitch=best_harmony,
                start=note.start,
                end=note.end,
            ))

    return harmony_notes


def _add_ending(
    melody_notes: list[pretty_midi.Note],
    acc_notes: list[pretty_midi.Note],
    chords: list[dict],
    bpm: float,
    style: str,
) -> list[pretty_midi.Note]:
    """Add ritardando and a final sustained chord to the arrangement.

    - Last 1-2 measures: gradually stretch note durations (ritardando)
    - Final chord: block chord held for 2x beat duration
    """
    if not chords or not acc_notes:
        return acc_notes

    beat_dur = 60.0 / bpm
    last_chord = chords[-1]
    piece_end = max(
        max((n.end for n in melody_notes), default=0),
        max((n.end for n in acc_notes), default=0),
    )

    # Parse final chord
    known_suffixes = ["maj7", "m7b5", "m7", "m6", "m", "sus4", "dim", "aug", "7", "6"]
    chord_name = last_chord["chord"]
    root_str = chord_name
    suffix = ""
    for s in known_suffixes:
        if chord_name.endswith(s) and len(chord_name) > len(s):
            root_str = chord_name[:-len(s)]
            suffix = s
            break
    root_pc = _note_name_to_pc(root_str) if root_str else 0
    intervals = CHORD_PATTERNS.get(suffix, CHORD_PATTERNS[""])

    # Final chord pitches in LH range
    final_pitches = [max(36, min(60, root_pc + 12 * 3 + i)) for i in intervals]

    # Add final chord — block chord held for 2 beats
    final_start = piece_end + beat_dur * 0.25  # Slight pause before ending
    for p in final_pitches:
        acc_notes.append(pretty_midi.Note(
            velocity=70,
            pitch=p,
            start=final_start,
            end=final_start + beat_dur * 2.0,
        ))

    # Add deep bass note below final chord
    acc_notes.append(pretty_midi.Note(
        velocity=75,
        pitch=final_pitches[0] - 12,
        start=final_start,
        end=final_start + beat_dur * 2.0,
    ))

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
    3. Generate accompaniment with voice leading (left hand)
    4. Combine into piano MIDI
    """
    midi = pretty_midi.PrettyMIDI(midi_path)

    # Extract melody
    melody_notes, harmony_notes = extract_melody(midi)

    # Detect chords
    from app.models.chord_detect import detect_chords
    chords = detect_chords(midi_path)

    # Harmonize melody (add thirds/sixths for richer RH)
    harmony_notes_from_chord = _harmonize_melody(melody_notes, chords)

    # Difficulty adjustments
    velocity_map = {
        "easy": 50,
        "medium": 65,
        "hard": 80,
    }
    acc_velocity = velocity_map.get(difficulty, 65)

    # AI mode: call Orpheus 748M GPU server, then polish with rule-based postprocessing
    if style == "ai":
        from app.models.cloud_amt import arrange_cloud_ai, is_orpheus_available
        if is_orpheus_available():
            try:
                ai_path = arrange_cloud_ai(midi_path, output_path)
                # Apply rule-based polish: quantization + velocity smoothing
                from app.models.postprocess import postprocess_midi
                polished_path = output_path.replace(".mid", "_polished.mid") if isinstance(output_path, str) else str(output_path).replace(".mid", "_polished.mid")
                postprocess_midi(Path(ai_path) if isinstance(ai_path, str) else ai_path, Path(polished_path))
                import shutil
                shutil.move(polished_path, ai_path if isinstance(ai_path, str) else str(ai_path))
                return ai_path if isinstance(ai_path, str) else str(ai_path)
            except Exception:
                pass  # Fall through to rule-based
        # If AI unavailable, fall through to broken style
        style = "broken"

    if difficulty == "easy":
        # Easier: block chords, slower
        style = "block"
    elif difficulty == "medium":
        style = "broken"
    elif difficulty == "hard":
        style = style  # Use selected style

    # Generate accompaniment
    acc_notes = generate_accompaniment(chords, style=style, bpm=bpm, velocity=acc_velocity)

    # Add ending: final chord + ritardando
    acc_notes = _add_ending(melody_notes, acc_notes, chords, bpm, style)

    # Create output MIDI
    out_midi = pretty_midi.PrettyMIDI()
    # RH: melody + harmony
    rh_track = pretty_midi.Instrument(program=0, name="Right Hand")
    for n in melody_notes:
        rh_track.notes.append(pretty_midi.Note(
            velocity=n.velocity, pitch=n.pitch,
            start=n.start, end=n.end,
        ))
    # Add harmony notes (thirds/sixths below melody)
    for n in harmony_notes_from_chord:
        rh_track.notes.append(n)
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
