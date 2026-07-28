"""MIDI to audio synthesis — pure Python, zero external dependencies.

Uses sine wave synthesis with ADSR envelope. Lightweight alternative
to FluidSynth — always works, good enough for preview playback.
"""

import struct
import wave
from pathlib import Path

import numpy as np
import pretty_midi

SAMPLE_RATE = 22050  # Good enough for preview, keeps files small


def midi_to_wav(midi_path: Path, output_path: Path | None = None, sr: int = SAMPLE_RATE) -> Path:
    """Render MIDI to WAV using sine wave synthesis.

    Args:
        midi_path: Path to input MIDI file
        output_path: Output WAV path (default: midi_path with .wav extension)
        sr: Sample rate (default 22050)

    Returns:
        Path to generated WAV file
    """
    if output_path is None:
        output_path = midi_path.with_suffix(".wav")

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    duration = midi.get_end_time() + 0.5  # Small tail for reverb
    total_samples = int(duration * sr)
    audio = np.zeros(total_samples, dtype=np.float32)

    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            freq = 440.0 * (2 ** ((note.pitch - 69) / 12.0))
            start_sample = int(note.start * sr)
            end_sample = min(int(note.end * sr), total_samples)
            if end_sample <= start_sample:
                continue

            t = np.arange(end_sample - start_sample, dtype=np.float32) / sr

            # ADSR envelope
            env = np.ones_like(t)
            n = len(t)
            attack = min(int(0.015 * sr), n // 4)
            decay = min(int(0.05 * sr), n // 6)
            release = min(int(0.08 * sr), n // 3)

            if attack > 0:
                env[:attack] = np.linspace(0, 1, attack)
            if release > 0:
                env[-release:] = np.linspace(1, 0, release)
            if decay > 0 and n > attack + release:
                sustain_start = attack
                sustain_end = n - release
                decay_len = min(decay, sustain_end - sustain_start)
                if decay_len > 0:
                    sustain_level = 0.7
                    env[sustain_start:sustain_start + decay_len] = np.linspace(1, sustain_level, decay_len)
                    env[sustain_start + decay_len:sustain_end] = sustain_level

            # Piano-like tone: fundamental + 2 harmonics
            sine = (
                np.sin(2 * np.pi * freq * t) * 0.7 +
                np.sin(2 * np.pi * freq * 2 * t) * 0.2 +
                np.sin(2 * np.pi * freq * 3 * t) * 0.1
            ).astype(np.float32)

            velocity_factor = note.velocity / 127.0
            audio[start_sample:end_sample] += sine * env * velocity_factor * 0.25

    # Normalize and prevent clipping
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.85

    # Write WAV
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(output_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())

    return output_path
