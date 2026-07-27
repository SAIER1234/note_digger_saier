"""Basic Pitch integration: Spotify's lightweight CPU audio-to-MIDI model.

Basic Pitch (Spotify, ISMIR 2022) — instrument-agnostic, polyphonic,
works on CPU, outputs MIDI with pitch bend detection.

This is the PRIMARY transcription engine for CPU-only deployments.
Aria-AMT is used when GPU (CUDA) is available.
"""

import os
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf


# Piano-optimized quality presets (tuned via benchmark grid search, Round 2)
QUALITY_PRESETS = {
    "high": {   # Cleanest — fewer notes, almost no noise
        "onset_threshold": 0.7,
        "frame_threshold": 0.5,
        "minimum_note_length": 100.0,  # ms
        "minimum_frequency": 55.0,      # A1
        "maximum_frequency": 3520.0,    # A7
    },
    "medium": {  # Balanced — best avg F1 (0.901 vs 0.823 baseline)
        "onset_threshold": 0.6,
        "frame_threshold": 0.4,
        "minimum_note_length": 50.0,   # Catches 16th notes up to 180bpm
        "minimum_frequency": 55.0,
        "maximum_frequency": 3520.0,
    },
    "low": {     # More sensitive — catches more notes, may have noise
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 58.0,
        "minimum_frequency": 32.7,       # C1
        "maximum_frequency": 4186.0,     # C8
    },
}


def transcribe_basic_pitch(
    audio_path: Path,
    output_dir: Path,
    quality: str = "high",
    onset_threshold: float | None = None,
    frame_threshold: float | None = None,
    minimum_note_length: float | None = None,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
) -> Path:
    """
    Transcribe audio to MIDI using Basic Pitch (Spotify).

    Args:
        audio_path: Path to preprocessed audio
        output_dir: Output directory
        quality: Preset: 'high' (cleanest), 'medium' (balanced), 'low' (most notes)
        onset_threshold: Override — higher = fewer notes (0.3-0.9)
        frame_threshold: Override — higher = less noise (0.2-0.6)
        minimum_note_length: Override — min ms per note
        minimum_frequency: Override — min Hz
        maximum_frequency: Override — max Hz

    Returns:
        Path to output MIDI file
    """
    # Apply quality preset, allow overrides
    preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])
    onset = onset_threshold if onset_threshold is not None else preset["onset_threshold"]
    frame = frame_threshold if frame_threshold is not None else preset["frame_threshold"]
    min_len = minimum_note_length if minimum_note_length is not None else preset["minimum_note_length"]
    min_freq = minimum_frequency if minimum_frequency is not None else preset["minimum_frequency"]
    max_freq = maximum_frequency if maximum_frequency is not None else preset["maximum_frequency"]
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    model_output, midi_data, note_events = predict(
        str(audio_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset,
        frame_threshold=frame,
        minimum_note_length=min_len,
        minimum_frequency=min_freq,
        maximum_frequency=max_freq,
        melodia_trick=True,  # Better piano transcription
    )

    # Post-filter: remove very short/quiet notes and near-duplicates
    _clean_midi_notes(midi_data)

    output_path = output_dir / f"{audio_path.stem}_basicpitch.mid"
    midi_data.write(str(output_path))

    return output_path


def _clean_midi_notes(midi_data, min_duration: float = 0.07, min_velocity: int = 15):
    """Remove likely noise from Basic Pitch output."""
    for instrument in midi_data.instruments:
        if instrument.is_drum:
            instrument.notes = []
            continue

        filtered = []
        for note in sorted(instrument.notes, key=lambda n: (n.pitch, n.start)):
            duration = note.end - note.start
            if duration < min_duration or note.velocity < min_velocity:
                continue
            if filtered and filtered[-1].pitch == note.pitch:
                if note.start < filtered[-1].end:
                    if note.velocity > filtered[-1].velocity:
                        filtered[-1] = note
                    continue
            filtered.append(note)
        instrument.notes = filtered


def transcribe_basic_pitch_multitrack(
    audio_path: Path,
    output_dir: Path,
    **kwargs,
) -> Path:
    """
    Transcribe multi-instrument audio using Basic Pitch.
    Handles polyphonic audio reasonably well.
    """
    # Basic Pitch is instrument-agnostic, so we pass through directly
    return transcribe_basic_pitch(audio_path, output_dir, **kwargs)
