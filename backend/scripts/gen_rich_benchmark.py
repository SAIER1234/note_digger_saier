"""Generate richer benchmark cases: pop ballad + jazz chords."""
import sys, numpy as np, soundfile as sf, pretty_midi
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from pathlib import Path

BENCHMARK = Path(__file__).resolve().parent.parent / "test_data" / "benchmark"
SR = 22050

def piano_note(pitch, duration, velocity=80):
    freq = 440.0 * (2 ** ((pitch - 69) / 12.0))
    t = np.arange(0, duration, 1/SR)
    audio = np.zeros_like(t)
    for amp, mult in [(1.0,1.0),(0.45,2.0),(0.22,3.0),(0.12,4.0),(0.06,5.0),(0.03,6.0)]:
        audio += amp * np.sin(2*np.pi*freq*mult*t)
    attack = int(0.008*SR); decay = int(0.04*SR); release = min(int(0.18*SR), len(t)//2)
    env = np.ones(len(t))
    if attack > 0: env[:attack] = np.linspace(0,1,attack)
    if decay > 0: env[attack:attack+decay] = np.linspace(1,0.7,decay)
    if release > 0: env[-release:] = np.linspace(0.7,0,release)
    return audio * env * (velocity/127.0) * 0.8

def make_case(name, notes, tempo=120):
    case_dir = BENCHMARK / name
    case_dir.mkdir(parents=True, exist_ok=True)
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano = pretty_midi.Instrument(program=0)
    for p, s, d, v in notes: piano.notes.append(pretty_midi.Note(velocity=v, pitch=p, start=s, end=s+d))
    midi.instruments.append(piano)
    midi.write(str(case_dir/'ground_truth.mid'))
    total_dur = max(s+d for _, s, d, _ in notes) + 0.5
    audio = np.zeros(int(SR*total_dur))
    for pitch, start, dur, vel in notes:
        na = piano_note(pitch, dur+0.1, vel)
        si = int(start*SR); ei = min(si+len(na), len(audio))
        audio[si:ei] += na[:ei-si]
    peak = abs(audio).max()
    if peak > 0: audio /= peak * 1.1
    sf.write(str(case_dir/'audio.wav'), audio, SR)
    return len(notes)

n9 = make_case("09_pop_ballad", [
    (60,0,1.8,80),(64,2,1.8,75),(67,4,1.8,85),(72,6,2.8,80),
    (48,0,2,60),(55,0,2,55),(43,2,2,58),(50,2,2,53),
    (53,4,2,60),(60,4,2,55),(48,6,3,62),(55,6,3,57),
], tempo=72)
print(f"09_pop_ballad: {n9} notes")

n10 = make_case("10_jazz_chords", [
    (50,0,3.5,65),(53,0,3.5,60),(57,0,3.5,60),(60,0,3.5,70),
    (48,4,3.5,65),(52,4,3.5,60),(55,4,3.5,60),(59,4,3.5,70),
    (48,8,4,70),(52,8,4,65),(55,8,4,65),(59,8,4,75),
], tempo=100)
print(f"10_jazz_chords: {n10} notes")
print("Done")
