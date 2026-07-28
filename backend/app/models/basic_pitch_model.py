"""Basic Pitch integration: Spotify's lightweight CPU audio-to-MIDI model.

Basic Pitch (Spotify, ISMIR 2022) — instrument-agnostic, polyphonic,
works on CPU, outputs MIDI with pitch bend detection.

This is the PRIMARY transcription engine for CPU-only deployments.
"""

import os
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf
import librosa


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
    "low": {     # Most sensitive — catches more notes, may have noise
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 58.0,
        "minimum_frequency": 32.7,       # C1
        "maximum_frequency": 4186.0,     # C8
    },
}


def analyze_audio_density(audio_path: Path) -> dict:
    """Pre-analyze audio to determine note density for adaptive preset selection.

    Uses onset detection + spectral analysis. Lightweight — runs in ~1s for
    a 30s audio clip at 22050Hz mono.

    Returns dict with onsets_per_second, duration, density classification.
    """
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    duration = len(y) / sr if sr > 0 else 0

    if duration < 0.5:
        return {"onsets_per_second": 0, "duration": duration, "density": "sparse"}

    # Onset detection — count note attacks
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr,
        units='frames',
        hop_length=512,
        backtrack=True,
    )
    onsets_per_second = len(onset_frames) / duration if duration > 0 else 0

    # Spectral centroid — higher = brighter timbre = more harmonic content
    spectral = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    centroid = float(librosa.feature.spectral_centroid(S=spectral, sr=sr).mean())

    # Density classification (tuned for piano — onsets are harder to detect
    # than percussive instruments, so thresholds are lower than typical)
    if onsets_per_second > 5:
        density = "fast"       # Rapid passages — need medium preset (50ms min note)
    elif onsets_per_second > 2:
        density = "normal"     # Moderate tempo — high preset works well
    else:
        density = "sparse"     # Very sparse — high preset, prioritize precision

    return {
        "onsets_per_second": round(onsets_per_second, 1),
        "duration": round(duration, 1),
        "spectral_centroid_hz": round(centroid, 0),
        "density": density,
    }


def select_quality_preset(audio_path: Path) -> str:
    """Select best quality preset based on audio characteristics.

    - fast (>5 onsets/s):    'medium' — lower threshold, shorter min note (50ms)
    - normal (2-5/s):        'high'   — balanced, good precision
    - sparse (<2/s):         'high'   — prioritize clean output over recall

    Falls back to 'high' on any analysis error.
    """
    try:
        info = analyze_audio_density(audio_path)
        if info["density"] == "fast":
            return "medium"
        return "high"
    except Exception:
        return "high"


def transcribe_basic_pitch(
    audio_path: Path,
    output_dir: Path,
    quality: str = "adaptive",
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
        quality: Preset: 'adaptive' (auto-select, default), 'high', 'medium', 'low'
        onset_threshold: Override — higher = fewer notes (0.3-0.9)
        frame_threshold: Override — higher = less noise (0.2-0.6)
        minimum_note_length: Override — min ms per note
        minimum_frequency: Override — min Hz
        maximum_frequency: Override — max Hz

    Returns:
        Path to output MIDI file
    """
    # Adaptive quality: analyze audio first, then pick preset
    if quality == "adaptive":
        quality = select_quality_preset(audio_path)

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
    """Remove likely noise from Basic Pitch output.

    Smart overlap handling:
    - Ghost notes (<60ms, <30 vel) → discard
    - Re-strikes (small overlap, decent velocity) → keep both with truncation
    - Duplicates (large overlap) → keep the louder one
    """
    for instrument in midi_data.instruments:
        if instrument.is_drum:
            instrument.notes = []
            continue

        filtered = []
        for note in sorted(instrument.notes, key=lambda n: (n.pitch, n.start)):
            duration = note.end - note.start

            # Ghost note: very short and quiet
            if duration < 0.06 and note.velocity < 30:
                continue
            # General quality filter
            if duration < min_duration or note.velocity < min_velocity:
                continue

            if filtered and filtered[-1].pitch == note.pitch:
                prev = filtered[-1]
                prev_dur = prev.end - prev.start
                overlap = prev.end - note.start
                overlap_ratio = overlap / prev_dur if prev_dur > 0 else 1.0

                if overlap_ratio < 0.35 and note.velocity >= 25:
                    # Re-strike in legato playing — keep both
                    prev.end = max(note.start - 0.005, prev.start)
                    if prev.end > prev.start:
                        filtered.append(note)
                    else:
                        filtered[-1] = note  # Truncation made zero-length
                    continue
                else:
                    # Duplicate — keep louder
                    if note.velocity > prev.velocity:
                        filtered[-1] = note
                    continue

            filtered.append(note)
        instrument.notes = filtered


def transcribe_basic_pitch_multitrack(
    audio_path: Path,
    output_dir: Path,
    **kwargs,
) -> Path:
    """Transcribe multi-instrument audio using Basic Pitch."""
    return transcribe_basic_pitch(audio_path, output_dir, **kwargs)
