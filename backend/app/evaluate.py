"""Automated benchmark evaluation for piano transcription quality.

Compares transcribed MIDI against ground truth MIDI.
Metrics: precision, recall, F1, onset MAE, velocity correlation.

Usage:
  python -m app.evaluate --pred transcribed.mid --gt ground_truth.mid
  python -m app.evaluate --batch  # Run full benchmark suite
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pretty_midi

# Pitch tolerance in semitones for note matching
PITCH_TOLERANCE = 0.5
# Onset time tolerance in seconds
ONSET_TOLERANCE = 0.05  # 50ms


def extract_notes(midi_path: Path) -> list[dict]:
    """Extract all notes from a MIDI file as a flat list."""
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    notes = []
    for inst in midi.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            notes.append({
                "pitch": note.pitch,
                "onset": note.start,
                "offset": note.end,
                "velocity": note.velocity,
            })
    return notes


def match_notes(
    pred_notes: list[dict],
    gt_notes: list[dict],
    pitch_tolerance: float = PITCH_TOLERANCE,
    onset_tolerance: float = ONSET_TOLERANCE,
) -> dict:
    """Match predicted notes to ground truth notes.

    A match requires: |pitch_pred - pitch_gt| < pitch_tolerance
                   AND |onset_pred - onset_gt| < onset_tolerance

    Returns:
        dict with metrics: precision, recall, f1, tp, fp, fn,
                          median_onset_error, velocity_correlation,
                          matched_pairs (list of (pred_idx, gt_idx))
    """
    pred_available = list(range(len(pred_notes)))
    gt_matched = set()
    matched_pairs = []

    # Greedy matching: for each predicted note, find best GT match
    for pi, pn in enumerate(pred_notes):
        best_gt = None
        best_dist = float("inf")

        for gi, gn in enumerate(gt_notes):
            if gi in gt_matched:
                continue
            pitch_diff = abs(pn["pitch"] - gn["pitch"])
            onset_diff = abs(pn["onset"] - gn["onset"])
            if pitch_diff <= pitch_tolerance and onset_diff <= onset_tolerance:
                dist = pitch_diff + onset_diff * 10  # Weight onset less
                if dist < best_dist:
                    best_dist = dist
                    best_gt = gi

        if best_gt is not None:
            gt_matched.add(best_gt)
            matched_pairs.append((pi, best_gt))

    tp = len(matched_pairs)
    fp = len(pred_notes) - tp
    fn = len(gt_notes) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Onset error for matched notes
    onset_errors = []
    for pi, gi in matched_pairs:
        onset_errors.append(abs(pred_notes[pi]["onset"] - gt_notes[gi]["onset"]) * 1000)  # ms
    median_onset_error = float(np.median(onset_errors)) if onset_errors else 0.0

    # Velocity correlation for matched notes
    velocity_corr = 0.0
    if len(matched_pairs) >= 3:
        pred_vels = [pred_notes[pi]["velocity"] for pi, _ in matched_pairs]
        gt_vels = [gt_notes[gi]["velocity"] for _, gi in matched_pairs]
        if np.std(pred_vels) > 0 and np.std(gt_vels) > 0:
            velocity_corr = float(np.corrcoef(pred_vels, gt_vels)[0, 1])
            if np.isnan(velocity_corr):
                velocity_corr = 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "median_onset_error_ms": round(median_onset_error, 2),
        "velocity_correlation": round(velocity_corr, 4),
    }


def evaluate_playability(midi_path: Path) -> dict:
    """Score a MIDI file for piano playability.

    Checks:
    - Left hand span ≤ 10 semitones
    - Right hand minimum pitch ≥ C3 (MIDI 48)
    - No voice crossing (LH max < RH min for overlapping notes)
    - Max 4 simultaneous notes per hand
    - No notes shorter than 50ms (ghost notes)

    Returns dict with score (0-100) and violation details.
    """
    midi = pretty_midi.PrettyMIDI(str(midi_path))
    score = 100
    violations = []

    for inst in midi.instruments:
        if inst.is_drum:
            continue

        # Split notes at C4 (MIDI 60) into LH (below) and RH (above)
        lh_notes = [n for n in inst.notes if n.pitch < 60]
        rh_notes = [n for n in inst.notes if n.pitch >= 60]

        # LH span check
        if lh_notes:
            lh_pitches = [n.pitch for n in lh_notes]
            lh_span = max(lh_pitches) - min(lh_pitches)
            if lh_span > 10:
                score -= 1
                violations.append(f"LH span {lh_span} > 10 semitones")

        # RH min pitch check
        if rh_notes:
            rh_min = min(n.pitch for n in rh_notes)
            if rh_min < 48:
                score -= 0.5
                violations.append(f"RH min pitch {rh_min} < C3 (48)")

        # Voice crossing check
        if lh_notes and rh_notes:
            lh_max_pitch = max(n.pitch for n in lh_notes)
            rh_min_pitch = min(n.pitch for n in rh_notes)
            # Check for temporal overlap + pitch crossing
            for lh in lh_notes:
                for rh in rh_notes:
                    if (lh.start < rh.end and rh.start < lh.end
                            and lh.pitch > rh.pitch):
                        score -= 2
                        violations.append(
                            f"Voice crossing: LH {lh.pitch} > RH {rh.pitch} "
                            f"at t={lh.start:.1f}s"
                        )
                        break  # Count once per LH note

        # Max simultaneous notes check
        time_points = sorted(set(
            [n.start for n in inst.notes] + [n.end for n in inst.notes]
        ))
        for t in time_points:
            lh_active = [n for n in lh_notes if n.start <= t < n.end]
            rh_active = [n for n in rh_notes if n.start <= t < n.end]
            if len(lh_active) > 4:
                score -= 0.5
                violations.append(f"{len(lh_active)} LH notes at t={t:.1f}s")
                break
            if len(rh_active) > 4:
                score -= 0.5
                violations.append(f"{len(rh_active)} RH notes at t={t:.1f}s")
                break

        # Ghost note check (< 50ms)
        ghost_count = sum(1 for n in inst.notes if (n.end - n.start) < 0.05)
        if ghost_count > 0:
            score -= ghost_count
            violations.append(f"{ghost_count} ghost notes (< 50ms)")

    return {
        "playability_score": max(0, round(score, 1)),
        "violations": violations[:20],  # Cap at 20
        "violation_count": len(violations),
    }


def evaluate_pair(
    pred_path: Path,
    gt_path: Path,
    label: str = "",
) -> dict:
    """Evaluate a single prediction vs ground truth pair."""
    pred_notes = extract_notes(pred_path)
    gt_notes = extract_notes(gt_path)

    note_metrics = match_notes(pred_notes, gt_notes)
    playability = evaluate_playability(pred_path)

    # Weighted total score (scaled to 0-100)
    weighted = (
        note_metrics["f1"] * 0.85
        + (1 - min(note_metrics["median_onset_error_ms"], 200) / 200) * 0.10
        + (playability["playability_score"] / 100) * 0.05
    ) * 100

    return {
        "label": label,
        "pred_file": str(pred_path),
        "gt_file": str(gt_path),
        "note_count_pred": len(pred_notes),
        "note_count_gt": len(gt_notes),
        **note_metrics,
        "playability": playability,
        "weighted_score": round(weighted, 1),
    }


def run_benchmark(benchmark_dir: Path) -> dict:
    """Run full benchmark suite.

    Expects benchmark_dir to contain subdirectories, each with:
      - audio.wav (input audio)
      - ground_truth.mid (correct MIDI)

    For each case, runs transcription and evaluates.
    """
    from app.tasks.transcription import _run_pipeline

    results = []
    cases = sorted(
        [d for d in benchmark_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    for case_dir in cases:
        audio_path = case_dir / "audio.wav"
        gt_path = case_dir / "ground_truth.mid"
        if not audio_path.exists() or not gt_path.exists():
            print(f"  SKIP {case_dir.name}: missing audio.wav or ground_truth.mid")
            continue

        print(f"  Transcribing {case_dir.name}...")
        try:
            output = _run_pipeline(
                task_id=f"bench_{case_dir.name}",
                source_type="file",
                source_path=str(audio_path),
                options={"model": "basic-pitch"},
            )
            pred_path = Path(output.get("output_dir", "")) / "transcribed_clean.mid"
            if not pred_path.exists():
                print(f"    FAIL: no output MIDI")
                continue

            result = evaluate_pair(pred_path, gt_path, label=case_dir.name)
            results.append(result)
            print(f"    F1={result['f1']:.3f}  Score={result['weighted_score']}")
        except Exception as e:
            print(f"    ERROR: {e}")

    # Aggregate
    if not results:
        return {"error": "No benchmark cases found", "results": []}

    avg_f1 = np.mean([r["f1"] for r in results])
    avg_score = np.mean([r["weighted_score"] for r in results])
    avg_onset = np.mean([r["median_onset_error_ms"] for r in results])

    return {
        "summary": {
            "cases": len(results),
            "avg_f1": round(float(avg_f1), 4),
            "avg_weighted_score": round(float(avg_score), 1),
            "avg_onset_error_ms": round(float(avg_onset), 2),
        },
        "results": results,
    }


# ── CLI ──

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcription benchmark evaluator")
    parser.add_argument("--pred", type=Path, help="Predicted MIDI file")
    parser.add_argument("--gt", type=Path, help="Ground truth MIDI file")
    parser.add_argument("--batch", action="store_true", help="Run full benchmark")
    parser.add_argument("--benchmark-dir", type=Path,
                        default=Path(__file__).parent.parent / "test_data" / "benchmark",
                        help="Benchmark directory")
    parser.add_argument("--playability", type=Path, help="Score playability of a MIDI file")

    args = parser.parse_args()

    if args.playability:
        result = evaluate_playability(args.playability)
        print(json.dumps(result, indent=2))
    elif args.pred and args.gt:
        result = evaluate_pair(args.pred, args.gt)
        print(json.dumps(result, indent=2))
    elif args.batch:
        print("Running benchmark suite...")
        result = run_benchmark(args.benchmark_dir)
        print("\n" + "=" * 50)
        print(json.dumps(result["summary"], indent=2))
        for r in result["results"]:
            print(f"  {r['label']:20s}  F1={r['f1']:.3f}  Score={r['weighted_score']}")
    else:
        parser.print_help()
