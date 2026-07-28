"""Cloud GPU transcription — SSHes into GPU server for Aria-AMT.

No HTTP port needed. Uses SSH/SFTP for file transfer + command execution.
"""

import os
from pathlib import Path

# SSH config (env vars with hardcoded defaults for seetacloud instance)
CLOUD_GPU_HOST = os.getenv("CLOUD_GPU_HOST") or "connect.bjb2.seetacloud.com"
CLOUD_GPU_PORT = int(os.getenv("CLOUD_GPU_PORT") or "50716")
CLOUD_GPU_USER = os.getenv("CLOUD_GPU_USER") or "root"
CLOUD_GPU_PASSWORD = os.getenv("CLOUD_GPU_PASSWORD") or ""
CLOUD_GPU_CHECKPOINT = os.getenv("CLOUD_GPU_CHECKPOINT") or "/root/models/piano-medium-double-1.0.safetensors"
CLOUD_GPU_PYTHON = os.getenv("CLOUD_GPU_PYTHON") or "/root/miniconda3/bin/python"

_ssh_client = None


def _get_ssh():
    """Get or create SSH connection (connection pooling)."""
    global _ssh_client
    if _ssh_client is not None:
        try:
            _ssh_client.exec_command("echo ping", timeout=5)
            return _ssh_client
        except Exception:
            _ssh_client = None

    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        CLOUD_GPU_HOST, port=CLOUD_GPU_PORT,
        username=CLOUD_GPU_USER, password=CLOUD_GPU_PASSWORD,
        timeout=15,
    )
    _ssh_client = client
    return client


def is_cloud_available() -> bool:
    """Check if cloud GPU is reachable (HTTP first, then SSH)."""
    # AutoDL / HTTP mode (preferred)
    if CLOUD_HTTP_URL:
        return is_cloud_http_available()
    # Legacy SSH mode (seetacloud etc.)
    if not CLOUD_GPU_HOST:
        return False
    try:
        client = _get_ssh()
        stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=name --format=csv,noheader", timeout=10)
        output = stdout.read().decode()
        return "3080" in output or "GeForce" in output or "RTX" in output or "A4000" in output
    except Exception:
        return False


def transcribe_cloud(audio_path: Path, output_dir: Path, timeout: int = 180) -> Path:
    """
    SSH into GPU server, upload audio, run Aria-AMT, download MIDI.
    """
    if not CLOUD_GPU_HOST:
        raise RuntimeError("CLOUD_GPU_HOST not set. Configure cloud GPU SSH credentials.")

    client = _get_ssh()

    # Upload audio via SFTP
    remote_audio = "/tmp/note_digger_input.wav"
    sftp = client.open_sftp()
    sftp.put(str(audio_path), remote_audio)
    sftp.close()

    # Run Aria-AMT (must source conda env for CLI path)
    work_dir = f"/tmp/note_digger_{audio_path.stem}"
    cmd = (
        f"mkdir -p {work_dir} && "
        f"source /root/miniconda3/bin/activate aria && "
        f"aria-amt transcribe medium-double {CLOUD_GPU_CHECKPOINT} "
        f"-load_path {remote_audio} -save_dir {work_dir} -bs 1 -compile"
    )
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()

    if "Error" in err or "Traceback" in err:
        raise RuntimeError(f"Aria-AMT failed: {err[-500:]}")

    # Find and download MIDI
    stdin, stdout, stderr = client.exec_command(f"ls -t {work_dir}/*.mid* 2>/dev/null | head -1", timeout=10)
    remote_midi = stdout.read().decode().strip()
    if not remote_midi:
        raise RuntimeError(f"No MIDI output found in {work_dir}. Output: {out[-200:]}")

    output_path = output_dir / f"{audio_path.stem}_aria.mid"
    sftp = client.open_sftp()
    sftp.get(remote_midi, str(output_path))
    sftp.close()

    # Cleanup remote temp files
    client.exec_command(f"rm -rf {work_dir} {remote_audio}", timeout=5)

    return output_path


# --- HTTP mode for AutoDL / any GPU server running aria_server.py ---

CLOUD_HTTP_URL = os.getenv("CLOUD_GPU_HTTP_URL", "")


def is_cloud_http_available() -> bool:
    """Check if cloud GPU is reachable via HTTP (AutoDL mode)."""
    if not CLOUD_HTTP_URL:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{CLOUD_HTTP_URL.rstrip('/')}/health",
            headers={"User-Agent": "NoteDigger/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def transcribe_cloud_http(audio_path: Path, output_dir: Path) -> Path:
    """Transcribe via HTTP POST to GPU server running aria_server.py."""
    import urllib.request
    import urllib.error
    import json as _json

    url = CLOUD_HTTP_URL.rstrip("/") + "/transcribe"

    with open(audio_path, "rb") as f:
        audio_data = f.read()

    boundary = "----NoteDiggerBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + audio_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "NoteDigger/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise RuntimeError(f"GPU server error {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"GPU HTTP request failed: {e}")

    if result.get("status") != "completed":
        raise RuntimeError(f"Transcription failed: {result.get('detail', str(result)[:200])}")

    midi_bytes = bytes.fromhex(result["midi_hex"])
    output_path = output_dir / f"{audio_path.stem}_aria.mid"
    output_path.write_bytes(midi_bytes)

    return output_path


# --- Orpheus AI Arrangement ---

def arrange_cloud_ai(midi_path: Path, output_path: Path, timeout: int = 120) -> Path:
    """Send MIDI to Orpheus 748M GPU server for AI arrangement."""
    client = _get_ssh()

    remote_midi = "/tmp/orpheus_input.mid"
    sftp = client.open_sftp()
    sftp.put(str(midi_path), remote_midi)
    sftp.close()

    # Call Orpheus server on GPU (port 8001)
    cmd = (
        f"curl -s -X POST http://localhost:8001/arrange "
        f"-F 'file=@{remote_midi}' "
        f"--max-time {timeout}"
    )
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout + 10)
    result = stdout.read().decode()

    try:
        import json as _json
        data = _json.loads(result)
    except Exception:
        raise RuntimeError(f"Orpheus returned invalid JSON: {result[:200]}")

    if data.get("status") != "completed":
        raise RuntimeError(f"Orpheus arrangement failed: {data}")

    # Decode MIDI from hex
    midi_bytes = bytes.fromhex(data["midi_hex"])
    output_path.write_bytes(midi_bytes)

    # Cleanup
    client.exec_command(f"rm -f {remote_midi}", timeout=5)

    return output_path


def is_orpheus_available() -> bool:
    """Check if Orpheus AI arrangement server is reachable."""
    try:
        client = _get_ssh()
        stdin, stdout, stderr = client.exec_command(
            "curl -s http://localhost:8001/health", timeout=10
        )
        result = stdout.read().decode()
        return '"status":"healthy"' in result
    except Exception:
        return False


def get_cloud_gpu_info() -> dict:
    """Get cloud GPU instance info."""
    if not CLOUD_GPU_HOST:
        return {"available": False, "reason": "CLOUD_GPU_HOST not set"}
    try:
        client = _get_ssh()
        stdin, stdout, stderr = client.exec_command(
            "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader", timeout=10
        )
        gpu_info = stdout.read().decode().strip()
        return {"available": True, "gpu": gpu_info, "host": CLOUD_GPU_HOST}
    except Exception as e:
        return {"available": False, "reason": str(e)}
