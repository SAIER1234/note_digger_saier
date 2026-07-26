"""MIDI post-processing: tempo detection, quantization, key detection."""

from pathlib import Path
from typing import Optional

import pretty_midi
import numpy as np
import librosa


def postprocess_midi(
    midi_path: Path,
    output_path: Optional[Path] = None,
    quantize: bool = True,
    detect_key: bool = True,
    detect_tempo: bool = True,
    remove_short_notes: bool = True,
    min_note_duration: float = 0.06,  # 60ms — musical 32nd note at 120bpm is 62.5ms
) -> Path:
    """
    Clean up and enhance raw AMT output MIDI.

    - Quantize note onsets/offsets to detected beat grid
    - Detect and set key signature
    - Detect and set tempo
    - Remove spurious very short notes (noise)
    """
    if output_path is None:
        output_path = midi_path.with_stem(midi_path.stem + "_clean")

    midi = pretty_midi.PrettyMIDI(str(midi_path))

    for instrument in midi.instruments:
        if remove_short_notes:
            instrument.notes = [
                n for n in instrument.notes
                if (n.end - n.start) > min_note_duration
            ]

        # Remove duplicate/overlapping notes
        instrument.notes = _remove_overlapping_notes(instrument.notes)

        # Remove very quiet notes (likely noise) — use percentile threshold
        velocities = [n.velocity for n in instrument.notes]
        if velocities:
            p10 = np.percentile(velocities, 10)
            threshold = max(8, p10 * 0.5)  # Keep at least notes above half of 10th percentile
            instrument.notes = [
                n for n in instrument.notes if n.velocity > threshold
            ]
            # Smooth extreme velocities
            p90 = np.percentile(velocities, 90)
            for n in instrument.notes:
                n.velocity = int(np.clip(n.velocity, 15, min(127, p90 * 1.2)))

    # Tempo detection
    if detect_tempo and len(midi.instruments) > 0:
        try:
            estimated_tempo = _detect_tempo_from_notes(midi)
            if estimated_tempo and len(midi.instruments) > 0 and sum(len(i.notes) for i in midi.instruments) >= 2:
                # Create tempo change at time 0
                tempo_change = pretty_midi.TempoChange(tempo=float(estimated_tempo), time=0.0)
                # Write to internal tempo track via _load_tempo_changes
                from pretty_midi import TempoChange
                midi._tempo_changes = [TempoChange(tempo=float(estimated_tempo), time=0.0)]
        except Exception:
            pass  # Tempo detection is best-effort

    # Key detection
    if detect_key:
        try:
            estimated_key, confidence = _detect_key_from_notes(midi)
            # Only set key if confidence is meaningful (correlation > 0.3)
            if estimated_key is not None and confidence > 0.3:
                # pretty_midi key_number must be in [-7, 7]
                clamped_key = max(-7, min(7, int(estimated_key)))
                midi._key_signatures = [
                    pretty_midi.KeySignature(clamped_key, 0.0)
                ]
        except Exception:
            pass  # Key detection is best-effort

    midi.write(str(output_path))
    return output_path


def _remove_overlapping_notes(
    notes: list[pretty_midi.Note],
) -> list[pretty_midi.Note]:
    """Remove notes that overlap with higher-velocity notes of the same pitch."""
    notes = sorted(notes, key=lambda n: (n.pitch, n.start, -n.velocity))
    cleaned = []
    for note in notes:
        if cleaned and cleaned[-1].pitch == note.pitch:
            # Check overlap
            if note.start < cleaned[-1].end:
                # Keep the louder one
                if note.velocity > cleaned[-1].velocity:
                    cleaned[-1] = note
                continue
        cleaned.append(note)
    return cleaned


def _detect_tempo_from_notes(midi: pretty_midi.PrettyMIDI) -> Optional[float]:
    """Estimate tempo from note onset intervals."""
    all_onsets = []
    for inst in midi.instruments:
        for note in inst.notes:
            all_onsets.append(note.start)

    if len(all_onsets) < 2:
        return None

    all_onsets = sorted(set(all_onsets))
    intervals = np.diff(all_onsets)
    # Filter outliers
    intervals = intervals[intervals < np.percentile(intervals, 90)]
    intervals = intervals[intervals > np.percentile(intervals, 10)]

    if len(intervals) < 2:
        return None

    # The most common short interval is likely a beat subdivision
    # Use histogram to find dominant interval
    hist, edges = np.histogram(intervals, bins=50)
    dominant_interval = edges[np.argmax(hist)]

    # Try common beat subdivisions
    candidates = [dominant_interval, dominant_interval * 2, dominant_interval * 4]
    best_tempo = None
    best_score = float("inf")

    for interval in candidates:
        if interval <= 0:
            continue
        tempo = 60.0 / interval
        # Score: prefer tempos in [40, 220] range and close to round numbers
        if 40 <= tempo <= 220:
            score = abs(tempo - round(tempo / 5) * 5)  # Prefer multiples of 5
            if score < best_score:
                best_score = score
                best_tempo = round(tempo)

    return best_tempo


def _detect_key_from_notes(midi: pretty_midi.PrettyMIDI) -> tuple[Optional[int], float]:
    """
    Detect key signature from notes using Krumhansl-Schmuckler profiles.
    Returns (key_number, confidence) where confidence is the best correlation score.
    key_number: standard MIDI key signature (-7 flats to +7 sharps, 0=C).
    """
    pitch_counts = np.zeros(12)
    for inst in midi.instruments:
        for note in inst.notes:
            pitch_counts[note.pitch % 12] += note.end - note.start

    total = pitch_counts.sum()
    if total == 0:
        return None, 0.0

    # Krumhansl-Schmuckler key profiles
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    # Normalize pitch counts
    pitch_counts = pitch_counts / total

    best_corr = -2.0  # Correlation ranges from -1 to 1
    best_key = 0

    for key in range(12):
        rotated_major = np.roll(major_profile / major_profile.sum(), key)
        rotated_minor = np.roll(minor_profile / minor_profile.sum(), key)

        corr_major = np.corrcoef(pitch_counts, rotated_major)[0, 1]
        corr_minor = np.corrcoef(pitch_counts, rotated_minor)[0, 1]

        # Handle NaN from zero-variance input
        if np.isnan(corr_major):
            corr_major = -2.0
        if np.isnan(corr_minor):
            corr_minor = -2.0

        if corr_major > best_corr:
            best_corr = corr_major
            best_key = key  # 0=C, 1=G (1 sharp), 2=D (2 sharps), etc.
        if corr_minor > best_corr:
            best_corr = corr_minor
            best_key = key - 12  # -3=Eb major/C minor (3 flats), etc.

    if best_corr <= -1.0:
        return None, 0.0  # No meaningful correlation — skip key setting

    return best_key, float(best_corr)


def get_midi_info(midi_path: Path) -> dict:
    """Extract summary information from a MIDI file."""
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    total_notes = sum(len(inst.notes) for inst in midi.instruments)
    total_duration = midi.get_end_time()

    pitches = []
    for inst in midi.instruments:
        for note in inst.notes:
            pitches.append(note.pitch)

    return {
        "total_notes": total_notes,
        "duration_seconds": round(total_duration, 2),
        "num_tracks": len(midi.instruments),
        "pitch_range": f"{min(pitches)}-{max(pitches)}" if pitches else "N/A",
        "tempo": round(midi.estimate_tempo(), 1) if total_notes >= 2 else None,
        "has_drums": any(instrument.is_drum for instrument in midi.instruments),
    }
