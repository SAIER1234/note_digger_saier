"""Generate synthetic benchmark test data for piano transcription evaluation.

Creates MIDI files with known ground truth → synthesizes audio →
ready for benchmark evaluation.

Usage:
  python scripts/generate_benchmark.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pretty_midi
import soundfile as sf


BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "test_data" / "benchmark"
SAMPLE_RATE = 22050

# Musical constants
C4 = 60  # MIDI pitch for middle C


def create_midi(filename: str, notes: list[tuple[int, float, float, int]],
                tempo: float = 120.0) -> Path:
    """Create a MIDI file with given notes.

    Args:
        filename: output filename (without extension)
        notes: list of (pitch, start_time, duration, velocity) tuples
        tempo: BPM

    Returns path to created MIDI file.
    """
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano

    for pitch, start, duration, velocity in notes:
        note = pretty_midi.Note(
            velocity=velocity,
            pitch=pitch,
            start=start,
            end=start + duration,
        )
        piano.notes.append(note)

    midi.instruments.append(piano)

    out_dir = BENCHMARK_DIR / filename
    out_dir.mkdir(parents=True, exist_ok=True)
    midi_path = out_dir / "ground_truth.mid"
    midi.write(str(midi_path))
    return midi_path


def synthesize_audio(midi_path: Path) -> Path:
    """Synthesize audio from MIDI using simple sine waves (no external deps needed).

    Returns path to WAV file.
    """
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    duration = midi.get_end_time() + 0.5  # 0.5s padding
    audio = np.zeros(int(SAMPLE_RATE * duration))

    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            t = np.arange(
                int(note.start * SAMPLE_RATE),
                int(note.end * SAMPLE_RATE),
            ) / SAMPLE_RATE
            freq = 440.0 * (2 ** ((note.pitch - 69) / 12.0))
            # ADSR envelope
            env = _adsr_envelope(len(t), SAMPLE_RATE)
            sine = np.sin(2 * np.pi * freq * (t - note.start)) * env
            # Apply velocity
            sine *= note.velocity / 127.0 * 0.6
            # Add harmonics for richer sound
            sine += 0.3 * np.sin(2 * np.pi * freq * 2 * (t - note.start)) * env
            sine += 0.1 * np.sin(2 * np.pi * freq * 3 * (t - note.start)) * env

            start_idx = int(note.start * SAMPLE_RATE)
            audio[start_idx:start_idx + len(sine)] += sine

    # Normalize
    peak = np.abs(audio).max()
    if peak > 0:
        audio /= peak * 1.1

    wav_path = midi_path.parent / "audio.wav"
    sf.write(str(wav_path), audio, SAMPLE_RATE)
    return wav_path


def _adsr_envelope(n: int, sr: int) -> np.ndarray:
    """Simple ADSR envelope for piano-like sound."""
    env = np.ones(n)
    attack = min(int(0.01 * sr), n // 4)
    decay = min(int(0.05 * sr), n // 4)
    release = min(int(0.15 * sr), n // 2)
    sustain_level = 0.7

    env[:attack] = np.linspace(0, 1, attack)
    if decay > 0:
        env[attack:attack + decay] = np.linspace(1, sustain_level, decay)
    env[attack + decay:] = sustain_level
    if release > 0:
        env[-release:] = np.linspace(sustain_level, 0, release)

    return env


# ── Benchmark Cases ──

def case_c_major_scale():
    """Simple C major scale, one octave."""
    notes = []
    pitches = [C4, C4+2, C4+4, C4+5, C4+7, C4+9, C4+11, C4+12]
    for i, p in enumerate(pitches):
        notes.append((p, i * 0.5, 0.45, 80))
    midi_path = create_midi("01_c_major_scale", notes, tempo=120)
    synthesize_audio(midi_path)
    print(f"  ✓ 01_c_major_scale ({len(notes)} notes)")


def case_arpeggio():
    """C major arpeggio with overlapping notes."""
    notes = [
        (C4, 0.0, 1.5, 75),
        (C4+4, 0.5, 1.5, 75),
        (C4+7, 1.0, 1.5, 75),
        (C4+12, 1.5, 1.5, 75),
        (C4+7, 2.0, 1.5, 70),
        (C4+4, 2.5, 1.5, 70),
        (C4, 3.0, 2.0, 65),
    ]
    midi_path = create_midi("02_arpeggio", notes, tempo=100)
    synthesize_audio(midi_path)
    print(f"  ✓ 02_arpeggio ({len(notes)} notes)")


def case_chords():
    """Chord progression: C - Am - F - G."""
    chords = [
        [(C4, 0.0, 2.0, 85), (C4+4, 0.0, 2.0, 80), (C4+7, 0.0, 2.0, 80)],
        [(C4-3, 2.0, 2.0, 80), (C4, 2.0, 2.0, 75), (C4+4, 2.0, 2.0, 75)],
        [(C4-7, 4.0, 2.0, 80), (C4, 4.0, 2.0, 75), (C4+5, 4.0, 2.0, 75)],
        [(C4-5, 6.0, 2.0, 85), (C4+2, 6.0, 2.0, 80), (C4+7, 6.0, 2.0, 80)],
    ]
    all_notes = []
    for chord in chords:
        all_notes.extend(chord)
    midi_path = create_midi("03_chords", all_notes, tempo=90)
    synthesize_audio(midi_path)
    print(f"  ✓ 03_chords ({len(all_notes)} notes)")


def case_melody_bass():
    """Simple melody with bass accompaniment."""
    melody = [(C4+12, i*0.5, 0.4, 85) for i in range(8)]
    bass = [(C4, i*1.0, 0.8, 70) for i in range(4)]
    all_notes = melody + bass
    midi_path = create_midi("04_melody_bass", all_notes, tempo=120)
    synthesize_audio(midi_path)
    print(f"  ✓ 04_melody_bass ({len(all_notes)} notes)")


def case_fast_notes():
    """Rapid 16th notes at 140 BPM."""
    notes = []
    pattern = [C4, C4+2, C4+4, C4+5, C4+7, C4+5, C4+4, C4+2]
    for i, p in enumerate(pattern * 4):  # 32 notes
        notes.append((p, i * 0.12, 0.1, 75))
    midi_path = create_midi("05_fast_notes", notes, tempo=140)
    synthesize_audio(midi_path)
    print(f"  ✓ 05_fast_notes ({len(notes)} notes)")


def case_low_dynamics():
    """Soft, slow piece — tests velocity sensitivity."""
    notes = []
    for i in range(6):
        notes.append((C4+2 + i*2, i * 1.0, 0.9, 30 + i*5))
    midi_path = create_midi("06_low_dynamics", notes, tempo=60)
    synthesize_audio(midi_path)
    print(f"  ✓ 06_low_dynamics ({len(notes)} notes)")


# ── Main ──

def main():
    print("Generating benchmark test data...")
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    case_c_major_scale()
    case_arpeggio()
    case_chords()
    case_melody_bass()
    case_fast_notes()
    case_low_dynamics()
    print(f"\nDone! {len(list(BENCHMARK_DIR.iterdir()))} cases in {BENCHMARK_DIR}")


if __name__ == "__main__":
    main()
