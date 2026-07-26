"""Simple CPU AMT using librosa — pitch detection + onset detection → MIDI.

Pure CPU, no GPU, no deep learning deps. Uses:
- librosa pYIN for pitch tracking
- librosa onset detection for note boundaries
- pretty_midi for MIDI generation

This is a lightweight fallback when Aria-AMT (needs GPU) and
Basic Pitch (needs compatible TF) are unavailable.
"""

from pathlib import Path

import numpy as np
import librosa
import pretty_midi


def transcribe_simple(
    audio_path: Path,
    output_dir: Path,
    sr: int = 22050,
    hop_length: int = 512,
    fmin: float = 32.7,  # C1
    fmax: float = 2093.0,  # C7
    onset_sensitivity: float = 0.5,
) -> Path:
    """
    Transcribe audio using librosa pYIN pitch tracking.

    Process:
    1. Load audio
    2. Detect onsets (note starts)
    3. Track pitch between onsets using pYIN
    4. Build MIDI from detected notes
    """
    # Load audio
    y, sr_in = librosa.load(str(audio_path), sr=sr, mono=True)
    duration = len(y) / sr

    # ---- Harmonic-percussive separation (clean up piano) ----
    y_harmonic, _ = librosa.effects.hpss(y)

    # ---- Onset detection ----
    onset_frames = librosa.onset.onset_detect(
        y=y_harmonic,
        sr=sr,
        hop_length=hop_length,
        backtrack=True,
        units="frames",
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
    onset_times = list(onset_times) + [duration]  # Add end boundary

    # ---- Pitch tracking with pYIN ----
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y_harmonic,
        fmin=fmin,
        fmax=fmax,
        sr=sr,
        hop_length=hop_length,
        fill_na=0.0,
    )

    # ---- Convert frames to time grid ----
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)

    # ---- Build MIDI ----
    midi = pretty_midi.PrettyMIDI()
    piano = pretty_midi.Instrument(program=0, name="Piano")

    current_note = None
    for i, onset_time in enumerate(onset_times[:-1]):
        next_onset_time = onset_times[i + 1]

        # Find frames in this segment
        seg_mask = (times >= onset_time) & (times < next_onset_time)
        seg_f0 = f0[seg_mask]
        seg_times = times[seg_mask]
        seg_voiced = voiced_flag[seg_mask]

        if len(seg_f0) == 0:
            continue

        # Use median pitch of voiced frames
        voiced_f0 = seg_f0[seg_voiced]
        if len(voiced_f0) == 0:
            continue

        median_pitch = np.median(voiced_f0)
        midi_note = int(round(librosa.hz_to_midi(median_pitch)))

        # Clamp to valid MIDI range
        if midi_note < 21 or midi_note > 108:
            continue

        # Estimate velocity from voiced probability
        mean_prob = np.mean(voiced_prob[seg_mask]) if len(seg_mask) > 0 else 0.5
        velocity = int(np.clip(mean_prob * 127, 30, 120))

        note_start = onset_time
        note_end = min(next_onset_time, note_start + 2.0)  # Max 2 second notes

        piano.notes.append(
            pretty_midi.Note(
                velocity=velocity,
                pitch=midi_note,
                start=note_start,
                end=note_end,
            )
        )

    midi.instruments.append(piano)

    # Save
    output_path = output_dir / f"{audio_path.stem}_simple.mid"
    midi.write(str(output_path))

    return output_path
