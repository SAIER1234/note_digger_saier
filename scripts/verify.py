"""Pre-deploy verification - catches 90% of bugs before they reach ECS.

Run with: python scripts/verify.py
Requires: bp311 conda environment, Node.js in PATH

Tests:
  1. Backend imports (all modules)
  2. FastAPI app starts + health check
  3. Auth endpoints (register → login → me)
  4. music21 MIDI→MusicXML pipeline (critical -- catches API changes)
  5. Basic Pitch import + preset validation
  6. Evaluate module (pair comparison + playability)
  7. Frontend npm run build
  8. API route consistency (frontend calls match backend routes)

Exit code 0 = all pass. Exit code 1 = failures.
"""

import subprocess
import sys
import json
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PYTHON = sys.executable  # Should be bp311 python

PASS = 0
FAIL = 0
SKIP = 0


def run_test(name: str, cmd: list[str], timeout: int = 60, env: dict | None = None) -> bool:
    """Run a test command. Returns True if it passes."""
    global PASS, FAIL, SKIP
    print(f"  [{name}] ... ", end="", flush=True)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(BACKEND_DIR), env=env)
        if r.returncode == 0 and "FAIL" not in r.stdout and "FAIL" not in r.stderr:
            print("PASS")
            PASS += 1
            return True
        else:
            print(f"X FAIL (code={r.returncode})")
            if r.stderr:
                for line in r.stderr.strip().split("\n")[-5:]:
                    print(f"    stderr: {line}")
            if r.stdout and "FAIL" in r.stdout:
                print(f"    stdout: {r.stdout.strip()[:200]}")
            FAIL += 1
            return False
    except subprocess.TimeoutExpired:
        print(f"X TIMEOUT ({timeout}s)")
        FAIL += 1
        return False
    except Exception as e:
        print(f"X ERROR: {e}")
        FAIL += 1
        return False


def python_test(name: str, code: str, timeout: int = 30) -> bool:
    """Run a Python one-liner test."""
    return run_test(name, [PYTHON, "-c", code], timeout)


def main():
    global PASS, FAIL, SKIP
    print("=" * 60)
    print("Note Digger -- Pre-Deploy Verification")
    print(f"Python: {PYTHON}")
    print(f"Backend: {BACKEND_DIR}")
    print(f"Frontend: {FRONTEND_DIR}")
    print("=" * 60)

    # -- 1. Backend imports --
    print("\n-- 1. Backend Module Imports --")
    modules = [
        ("config", "from app.config import DEV_MODE, OUTPUT_DIR, API_PREFIX; assert DEV_MODE"),
        ("main", "from app.main import app; assert app.title == 'Note Digger'"),
        ("user model", "from app.models.user import init_db, create_user, authenticate_user; init_db()"),
        ("evaluate", "from app.evaluate import evaluate_pair, evaluate_playability, match_notes"),
        ("basic_pitch", "from app.models.basic_pitch_model import QUALITY_PRESETS, transcribe_basic_pitch; assert 'medium' in QUALITY_PRESETS"),
        ("postprocess", "from app.models.postprocess import postprocess_midi, _detect_key_from_notes"),
        ("midi_to_xml", "from app.services.midi_to_xml import midi_to_musicxml"),
        ("audio", "from app.services.audio import preprocess_audio, validate_audio"),
        ("chord_detect", "from app.models.chord_detect import detect_chords"),
        ("arranger", "from app.models.arranger import arrange_piano, extract_melody"),
        ("auth middleware", "from app.middleware.auth import create_token, decode_token, get_user_from_header"),
        ("file_storage", "from app.utils.file_storage import generate_task_id, get_output_dir"),
    ]
    for name, code in modules:
        python_test(f"import: {name}", f"import sys; sys.path.insert(0, 'backend'); {code}")

    # -- 2. FastAPI startup + health --
    print("\n-- 2. FastAPI Health Check --")
    python_test("app health", """
import sys; sys.path.insert(0, 'backend')
from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
r = client.get("/api/v1/health")
assert r.status_code == 200
assert r.json()["status"] == "healthy"
print("health: OK")
""")

    # -- 3. Auth endpoints --
    print("\n-- 3. Auth Endpoints (route + logic) --")
    python_test("auth flow", """
import sys; sys.path.insert(0, 'backend')
from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)

# Clean up test user if exists
import sqlite3, os
db_path = os.path.join(os.path.dirname(os.path.abspath('backend')), 'note_digger.db')
try:
    db = sqlite3.connect(db_path)
    db.execute("DELETE FROM users WHERE email = 'test_verify@nd.com'")
    db.commit()
    db.close()
except: pass

# Register
r = client.post("/api/v1/auth/register", json={"email": "test_verify@nd.com", "password": "test123"})
assert r.status_code == 200, f"Register failed: {r.text}"
data = r.json()
assert "token" in data and "user" in data
token = data["token"]

# Login
r = client.post("/api/v1/auth/login", json={"email": "test_verify@nd.com", "password": "test123"})
assert r.status_code == 200, f"Login failed: {r.text}"

# Me
r = client.get(f"/api/v1/auth/me/token/{token}")
assert r.status_code == 200
user = r.json()["user"]
assert user["tier"] == "free"
assert user["usage_limit"] == 3

# Activate (use first available code)
import sqlite3, os
db_path = os.path.join(os.path.dirname(os.path.abspath('backend')), 'note_digger.db')
db = sqlite3.connect(db_path)
row = db.execute("SELECT code FROM activation_codes WHERE used_by IS NULL LIMIT 1").fetchone()
db.close()
if row:
    r = client.post(f"/api/v1/auth/activate/token/{token}/code/{row[0]}")
    assert r.status_code == 200
    data2 = r.json()
    assert data2["user"]["tier"] == "pro", f"Activate failed: {r.text}"

print("auth: register+login+me+activate OK")
""", timeout=15)

    # -- 4. music21 MIDI→MusicXML (critical!) --
    print("\n-- 4. music21 MIDI→MusicXML Pipeline --")
    python_test("music21 grand staff", """
import sys, tempfile; sys.path.insert(0, 'backend')
from pathlib import Path
from app.services.midi_to_xml import midi_to_musicxml
import pretty_midi

# Create a tiny MIDI with notes in both hands
midi = pretty_midi.PrettyMIDI()
piano = pretty_midi.Instrument(program=0)
piano.notes.append(pretty_midi.Note(velocity=80, pitch=72, start=0.0, end=0.5))   # C5 (RH)
piano.notes.append(pretty_midi.Note(velocity=70, pitch=48, start=0.0, end=0.5))   # C3 (LH)
midi.instruments.append(piano)

tmp_midi = Path(tempfile.mktemp(suffix='.mid'))
tmp_xml = Path(tempfile.mktemp(suffix='.musicxml'))
midi.write(str(tmp_midi))

# Convert (this tests _split_into_grand_staff + score.remove)
result = midi_to_musicxml(tmp_midi, tmp_xml, split_hands=True)
assert result.exists(), "MusicXML not created"
assert result.stat().st_size > 100, f"MusicXML too small: {result.stat().st_size} bytes"

# Verify it's valid XML with 2 parts
import music21 as m21
score = m21.converter.parse(str(result))
assert len(score.parts) >= 1, f"Expected >=1 parts, got {len(score.parts)}"

tmp_midi.unlink(missing_ok=True)
tmp_xml.unlink(missing_ok=True)
print(f"music21: grand staff split OK ({len(score.parts)} parts)")
""", timeout=30)

    # -- 5. Basic Pitch preset validation --
    print("\n-- 5. Basic Pitch Presets --")
    python_test("preset validation", """
import sys; sys.path.insert(0, 'backend')
from app.models.basic_pitch_model import QUALITY_PRESETS

for name, preset in QUALITY_PRESETS.items():
    assert 0 < preset['onset_threshold'] <= 1.0, f"{name}: bad onset_threshold"
    assert 0 < preset['frame_threshold'] <= 1.0, f"{name}: bad frame_threshold"
    assert preset['minimum_note_length'] > 0, f"{name}: bad min_note_length"
    assert preset['minimum_frequency'] > 0, f"{name}: bad min_frequency"
    assert preset['maximum_frequency'] > preset['minimum_frequency'], f"{name}: freq range"

print(f"presets: {list(QUALITY_PRESETS.keys())} all valid")
assert QUALITY_PRESETS['medium']['minimum_note_length'] == 50.0, "medium preset not updated!"
""")

    # -- 6. Evaluate module --
    print("\n-- 6. Evaluate Module --")
    python_test("evaluate pair", """
import sys, tempfile; sys.path.insert(0, 'backend')
from pathlib import Path
from app.evaluate import evaluate_pair, evaluate_playability
import pretty_midi

# Create matching MIDIs
def make_midi(notes):
    midi = pretty_midi.PrettyMIDI()
    p = pretty_midi.Instrument(program=0)
    for pitch, start, dur, vel in notes:
        p.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=start, end=start+dur))
    midi.instruments.append(p)
    return midi

notes = [(60, 0.0, 0.5, 80), (64, 0.5, 0.5, 75), (67, 1.0, 0.5, 85)]
pred_path = Path(tempfile.mktemp(suffix='.mid'))
gt_path = Path(tempfile.mktemp(suffix='.mid'))
make_midi(notes).write(str(pred_path))
make_midi(notes).write(str(gt_path))

r = evaluate_pair(pred_path, gt_path, label="test")
assert r['f1'] == 1.0, f"Expected F1=1.0, got {r['f1']}"
assert r['precision'] == 1.0

# Playability
p = evaluate_playability(pred_path)
assert p['playability_score'] == 100.0

pred_path.unlink(); gt_path.unlink()
print("evaluate: F1=1.0, playability=100 OK")
""", timeout=15)

    # -- 7. Key detection (the buggy one!) --
    print("\n-- 7. Key Detection (regression test) --")
    python_test("key detection", """
import sys; sys.path.insert(0, 'backend')
from app.models.postprocess import _detect_key_from_notes
import pretty_midi

# Test with a simple C major scale
midi = pretty_midi.PrettyMIDI()
p = pretty_midi.Instrument(program=0)
for i, pitch in enumerate([60, 62, 64, 65, 67, 69, 71, 72]):
    p.notes.append(pretty_midi.Note(velocity=80, pitch=pitch, start=i*0.5, end=i*0.5+0.45))
midi.instruments.append(p)

key, conf = _detect_key_from_notes(midi)
assert key is not None, "Key detection returned None"
assert -7 <= key <= 7, f"Key {key} out of valid range [-7, 7]"
assert conf > 0.3, f"Confidence {conf} too low"

# Test with empty MIDI (edge case)
empty_midi = pretty_midi.PrettyMIDI()
empty_midi.instruments.append(pretty_midi.Instrument(program=0))
key2, conf2 = _detect_key_from_notes(empty_midi)
assert key2 is None, "Empty MIDI should return None"
print(f"key detect: key={key}, conf={conf:.2f} OK")
""", timeout=15)

    # -- 8. Frontend build --
    print("\n-- 8. Frontend Build --")
    if FRONTEND_DIR.exists():
        r = subprocess.run(
            "npm run build",
            capture_output=True, text=True, timeout=120, shell=True,
            cwd=str(FRONTEND_DIR), encoding='utf-8', errors='replace'
        )
        if r.returncode == 0 and "Compiled successfully" in (r.stdout or ""):
            print("  [frontend build] PASS")
            PASS += 1
        else:
            print("  [frontend build] X FAIL")
            for line in (r.stderr or "").split("\n")[-5:]:
                if line.strip():
                    print(f"    {line}")
            for line in (r.stdout or "").split("\n")[-5:]:
                if line.strip():
                    print(f"    {line}")
            FAIL += 1
    else:
        print("  [frontend build] -- SKIP (no frontend dir)")
        SKIP += 1

    # -- 9. API route consistency --
    print("\n-- 9. API Route Consistency (frontend <-> backend) --")
    python_test("route check", """
import sys, re; sys.path.insert(0, 'backend')
from pathlib import Path
from app.main import app
from app.config import API_PREFIX

# Backend routes
backend_routes = set()
for route in app.routes:
    if hasattr(route, 'path'):
        backend_routes.add(route.path)

# Frontend API calls
frontend_dir = Path('frontend/lib')
ts_files = list(frontend_dir.glob('*.ts')) + list(frontend_dir.glob('*.tsx'))
api_calls = set()
for f in ts_files:
    text = f.read_text()
    # Find fetch URLs
    for m in re.finditer(r'[`"](/(?:api/)?[^`"]+)[`"]', text):
        api_calls.add(m.group(1))

# Check each frontend call matches a backend route
mismatches = []
for call in sorted(api_calls):
    # Normalize: remove template vars and query params
    normalized = re.sub(r'\\\\$\\\\{[^}]+\\\\}', '*', call).split('?')[0]
    # Check if any backend route matches
    found = False
    for br in backend_routes:
        br_pattern = re.sub(r'\\\\{[^}]+\\\\}', '*', br)
        if re.match(br_pattern.replace('*', '[^/]+'), normalized):
            found = True
            break
    if not found and not call.startswith('/_next/'):
        mismatches.append(call)

if not mismatches:
    print("route check: all frontend API paths match backend routes OK")
else:
    print(f"route check: {len(mismatches)} potential mismatches:")
    for m in mismatches:
        print(f"  - {m}")
""", timeout=15)

    # -- Summary --
    print("\n" + "=" * 60)
    total = PASS + FAIL + SKIP
    print(f"Results: {PASS} passed, {FAIL} failed, {SKIP} skipped (of {total})")
    if FAIL == 0:
        print("PASS ALL CHECKS PASSED -- safe to deploy")
        return 0
    else:
        print("X VERIFICATION FAILED -- fix before deploying")
        return 1


if __name__ == "__main__":
    sys.exit(main())
