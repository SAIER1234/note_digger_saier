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
    """Check if cloud GPU is configured and reachable via SSH."""
    if not CLOUD_GPU_HOST:
        return False
    try:
        client = _get_ssh()
        stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=name --format=csv,noheader", timeout=10)
        return "3080" in stdout.read().decode() or "GeForce" in stdout.read().decode()
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

    # Run Aria-AMT
    work_dir = f"/tmp/note_digger_{audio_path.stem}"
    cmd = (
        f"mkdir -p {work_dir} && "
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
