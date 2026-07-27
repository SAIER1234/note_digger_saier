# Verification Checklist — Pre-Deploy Gate

**Rule: NEVER deploy to ECS before passing all checks.**

## Quick Start
```bash
# Must use bp311 conda env!
python scripts/verify.py
# Exit 0 = safe to deploy. Exit 1 = fix failures first.
```

## What It Tests

| # | Test | Catches |
|---|------|---------|
| 1 | All backend imports | Missing deps, circular imports, syntax errors |
| 2 | FastAPI health | App starts, routes registered |
| 3 | Auth register→login→me→activate | API path mismatch, DB errors, JWT issues |
| 4 | music21 MIDI→MusicXML | **MOST IMPORTANT**: API version changes, `score.remove()` bugs |
| 5 | Basic Pitch presets | Preset validation, medium preset min_len=50 |
| 6 | Evaluate F1 + playability | Scoring logic unchanged |
| 7 | Key detection | Valid range [-7,7], empty MIDI → None |
| 8 | `npm run build` | TypeScript errors, import issues, syntax |
| 9 | Route consistency | Frontend fetch paths match backend routes |

## Manual Checks (when applicable)

- [ ] **API signature change?** → Update frontend types in `lib/types.ts`
- [ ] **DB schema change?** → Migration script + test on copy of `note_digger.db`
- [ ] **New Python dependency?** → `pip install` in bp311 + add to requirements
- [ ] **Nginx config change?** → Test locally with `curl` against backend first
- [ ] **New frontend route?** → Test with `npm run dev` locally

## Common Pitfalls

1. **music21 API**: Always test against installed version (9.x on ECS). `score.remove()` works, `score.core` does NOT exist.
2. **Frontend auth paths**: MUST include `/api/v1` prefix. Nginx routes `/api/*` to backend only.
3. **Basic Pitch presets**: `min_note_length` in ms. 16th notes at 180bpm = 83ms. Keep below this.
4. **pretty_midi key_number**: Valid range is [-7, 7]. Clamp before passing to `KeySignature()`.
5. **ECS GitHub blocked**: Use `scp` not `git pull` for deployment.
6. **Port map**: autofarm=8000, backend=8001, frontend=3000, nginx=80.
