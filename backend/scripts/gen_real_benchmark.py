"""Generate benchmark cases with realistic piano harmonics."""
import numpy as np
import soundfile as sf
from pathlib import Path

BENCHMARK = Path(__file__).resolve().parent.parent / "test_data" / "benchmark"
SR = 22050


def piano_note(pitch, duration, velocity=80):
    """Synthesize a note with 6-harmonic piano-like timbre."""
    freq = 440.0 * (2 ** ((pitch - 69) / 12.0))
    t = np.arange(0, duration, 1 / SR)
    audio = np.zeros_like(t)
    harmonics = [
        (1.0, 1.0), (0.5, 2.0), (0.25, 3.0),
        (0.15, 4.0), (0.08, 5.0), (0.04, 6.0),
    ]
    for amp, mult in harmonics:
        audio += amp * np.sin(2 * np.pi * freq * mult * t)
    # ADSR
    attack = int(0.01 * SR)
    decay = int(0.05 * SR)
    release = min(int(0.2 * SR), len(t) // 2)
    env = np.ones(len(t))
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack)
    if decay > 0:
        env[attack:attack + decay] = np.linspace(1, 0.7, decay)
    if release > 0:
        env[-release:] = np.linspace(0.7, 0, release)
    audio *= env * (velocity / 127.0) * 0.8
    return audio


def make_case(name, notes, tempo=120):
    """Create benchmark case with ground truth MIDI and harmonic audio."""
    import pretty_midi
    case_dir = BENCHMARK / name
    case_dir.mkdir(parents=True, exist_ok=True)

    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano = pretty_midi.Instrument(program=0)
    for pitch, start, dur, vel in notes:
        piano.notes.append(pretty_midi.Note(
            velocity=vel, pitch=pitch, start=start, end=start + dur
        ))
    midi.instruments.append(piano)
    midi.write(str(case_dir / "ground_truth.mid"))

    total_dur = max(start + dur for _, start, dur, _ in notes) + 0.5
    audio = np.zeros(int(SR * total_dur))
    for pitch, start, dur, vel in notes:
        note_audio = piano_note(pitch, dur + 0.1, vel)
        start_idx = int(start * SR)
        end_idx = min(start_idx + len(note_audio), len(audio))
        audio[start_idx:end_idx] += note_audio[:end_idx - start_idx]

    peak = abs(audio).max()
    if peak > 0:
        audio /= peak * 1.1
    sf.write(str(case_dir / "audio.wav"), audio, SR)
    return len(notes)


# Case 7: Melody with harmonics
n7 = make_case("07_real_melody", [
    (60, 0.0, 0.9, 80), (64, 1.0, 0.9, 75), (67, 2.0, 0.9, 85),
    (72, 3.0, 1.9, 80), (71, 5.0, 0.9, 70), (69, 6.0, 0.9, 75),
    (67, 7.0, 1.9, 80),
], tempo=100)
print(f"07_real_melody: {n7} notes")

# Case 8: Chord progression with harmonics
n8 = make_case("08_real_chord", [
    # C major
    (48, 0.0, 4.0, 70), (52, 0.0, 4.0, 65), (55, 0.0, 4.0, 65),
    (60, 0.0, 4.0, 75), (64, 0.0, 4.0, 70), (67, 0.0, 4.0, 70),
    # G major
    (43, 4.0, 4.0, 65), (47, 4.0, 4.0, 60), (50, 4.0, 4.0, 60),
    (55, 4.0, 4.0, 70), (59, 4.0, 4.0, 65), (62, 4.0, 4.0, 65),
], tempo=80)
print(f"08_real_chord: {n8} notes")

print("Done")
