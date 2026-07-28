"""Generate challenging benchmark cases for quality testing.

Creates synthetic audio (sine wave) from MIDI, stored alongside
ground truth MIDI. Tests the adaptive preset (R23).

Usage:
  python scripts/gen_benchmark.py          # Generate all new cases
  python scripts/gen_benchmark.py --list   # List existing cases
"""

import argparse
import struct
import wave
from pathlib import Path
import numpy as np
import pretty_midi

BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "test_data" / "benchmark"
SAMPLE_RATE = 22050


def midi_to_sine_wav(midi_path: Path, wav_path: Path, sr: int = SAMPLE_RATE):
    """Render MIDI to audio using sine waves (pure tone synthesis).
    Simple but sufficient for benchmark testing — no external deps.
    """
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    duration = midi.get_end_time() + 0.5
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
            # Envelope: quick attack, sustain, quick release
            env = np.ones_like(t)
            attack = min(int(0.01 * sr), len(t) // 4)
            release = min(int(0.03 * sr), len(t) // 4)
            if attack > 0:
                env[:attack] = np.linspace(0, 1, attack)
            if release > 0:
                env[-release:] = np.linspace(1, 0, release)

            sine = np.sin(2 * np.pi * freq * t, dtype=np.float32)
            velocity_factor = note.velocity / 127.0
            audio[start_sample:end_sample] += sine * env * velocity_factor * 0.3

    # Normalize
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.9

    # Write WAV
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(str(wav_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())


def gen_case_11_fast_arpeggios():
    """Fast arpeggio runs at 160bpm — tests adaptive preset triggering medium quality."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=160)
    inst = pretty_midi.Instrument(program=0, name="Piano")

    # C major arpeggio: C4-E4-G4-C5-E5-G5-C6-G5-E5-C5-G4-E4 (repeat)
    pattern = [60, 64, 67, 72, 76, 79, 84, 79, 76, 72, 67, 64]
    bpm = 160
    beat_dur = 60.0 / bpm  # 0.375s per beat
    note_dur = beat_dur / 4  # 16th notes = 0.09375s (~94ms)

    t = 0.0
    for _ in range(4):  # 4 repetitions
        for pitch in pattern:
            inst.notes.append(pretty_midi.Note(
                velocity=80, pitch=pitch,
                start=t, end=t + note_dur * 0.85,
            ))
            t += note_dur

    midi.instruments.append(inst)

    case_dir = BENCHMARK_DIR / "11_fast_arpeggios"
    case_dir.mkdir(parents=True, exist_ok=True)
    midi_path = case_dir / "ground_truth.mid"
    wav_path = case_dir / "audio.wav"
    midi.write(str(midi_path))
    midi_to_sine_wav(midi_path, wav_path)
    print(f"11_fast_arpeggios: {len(pattern)*4} notes, {t:.1f}s, {bpm}bpm 16ths")


def gen_case_12_three_voice():
    """Three-voice counterpoint — tests polyphonic melody extraction."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=100)
    inst = pretty_midi.Instrument(program=0, name="Piano")

    bpm = 100
    beat_dur = 60.0 / bpm

    # Voice 1 (soprano): melody
    soprano = [72, 74, 76, 77, 79, 77, 76, 74, 72, 71, 72, 0]  # 0=rest
    # Voice 2 (alto): harmony
    alto    = [64, 65, 67, 65, 67, 65, 64, 62, 60, 60, 60, 0]
    # Voice 3 (bass): bass line
    bass    = [48, 45, 43, 41, 43, 48, 47, 45, 48, 43, 48, 0]

    t = 0.0
    note_len = beat_dur * 0.85
    for s, a, b in zip(soprano, alto, bass):
        if s > 0:
            inst.notes.append(pretty_midi.Note(velocity=85, pitch=s, start=t, end=t + note_len))
        if a > 0:
            inst.notes.append(pretty_midi.Note(velocity=70, pitch=a, start=t, end=t + note_len))
        if b > 0:
            inst.notes.append(pretty_midi.Note(velocity=65, pitch=b, start=t, end=t + note_len))
        t += beat_dur

    midi.instruments.append(inst)

    case_dir = BENCHMARK_DIR / "12_three_voice"
    case_dir.mkdir(parents=True, exist_ok=True)
    midi_path = case_dir / "ground_truth.mid"
    wav_path = case_dir / "audio.wav"
    midi.write(str(midi_path))
    midi_to_sine_wav(midi_path, wav_path)
    note_count = sum(1 for n in inst.notes)
    print(f"12_three_voice: {note_count} notes, {t:.1f}s, {bpm}bpm 3-voice")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate benchmark cases")
    parser.add_argument("--list", action="store_true", help="List existing cases")
    args = parser.parse_args()

    if args.list:
        for d in sorted(BENCHMARK_DIR.iterdir()):
            if d.is_dir():
                gt = d / "ground_truth.mid"
                audio = d / "audio.wav"
                print(f"{d.name}: gt={gt.exists()} audio={audio.exists()}")
    else:
        BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        gen_case_11_fast_arpeggios()
        gen_case_12_three_voice()
        print("\nDone. Run benchmark to test new cases.")
