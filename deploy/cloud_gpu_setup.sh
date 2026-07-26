#!/bin/bash
# AutoDL GPU Instance Setup — Aria-AMT Transcription Microservice
# Run once on a fresh AutoDL instance (PyTorch 2.3+ image)
# Estimated setup time: 5 minutes

set -e

echo "=== Note Digger Cloud GPU Setup ==="

# 1. Install system deps
echo "[1/5] Installing system deps..."
apt-get update -qq && apt-get install -y -qq \
    ffmpeg libsndfile1 fluidsynth fluid-soundfont-gm git curl \
    2>/dev/null

# 2. Clone Aria-AMT
echo "[2/5] Cloning Aria-AMT..."
cd /root
if [ ! -d aria-amt ]; then
    git clone https://github.com/EleutherAI/aria-amt.git
fi
cd aria-amt
pip install -e . -q

# 3. Download model weights
echo "[3/5] Downloading model weights (~446MB)..."
mkdir -p /root/models
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download('AEmotionStudio/aria-amt-models', 'piano-medium-double-1.0.safetensors', local_dir='/root/models')
print('Model downloaded')
"

# 4. Install FastAPI for microservice
echo "[4/5] Installing API server..."
pip install fastapi uvicorn python-multipart -q

# 5. Create transcription server
echo "[5/5] Creating transcription service..."
cat > /root/transcribe_server.py << 'PYEOF'
import os, subprocess, tempfile, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn

app = FastAPI(title="Note Digger Cloud")
MODEL_DIR = "/root/models"
CHECKPOINT = f"{MODEL_DIR}/piano-medium-double-1.0.safetensors"

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe audio to MIDI using Aria-AMT."""
    task_id = uuid.uuid4().hex[:12]
    work_dir = Path(f"/tmp/{task_id}")
    work_dir.mkdir(parents=True)

    # Save uploaded audio
    audio_path = work_dir / "input.wav"
    content = await file.read()
    audio_path.write_bytes(content)

    # Run Aria-AMT
    result = subprocess.run([
        "aria-amt", "transcribe", "medium-double", CHECKPOINT,
        "-load_path", str(audio_path),
        "-save_dir", str(work_dir),
        "-bs", "1", "-compile"
    ], capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        raise HTTPException(500, f"Transcription failed: {result.stderr[:500]}")

    # Find output MIDI
    midi_files = sorted(work_dir.glob("*.mid*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not midi_files:
        raise HTTPException(500, "No MIDI output")

    return FileResponse(midi_files[0], media_type="audio/midi",
                       filename=f"{task_id}.mid")

@app.get("/health")
async def health():
    return {"status": "ok", "gpu": os.popen("nvidia-smi --query-gpu=name --format=csv,noheader").read().strip()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
PYEOF

echo ""
echo "=== Setup Complete ==="
echo "Start service: python /root/transcribe_server.py"
echo "Test: curl http://localhost:8000/health"
echo ""
echo "GPU info:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
