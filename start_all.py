"""One-click launcher: kills old, starts backend + frontend, tests cloud GPU."""
import subprocess, ctypes, os, time, urllib.request, json, shutil, sys

BACKEND_DIR = r"d:\GitWarehouse\note_digger_saier\backend"
FRONTEND_DIR = r"d:\GitWarehouse\note_digger_saier\frontend"
PYTHON = r"D:\Software\anaconda3\envs\bp311\python.exe"
BACKEND_PORT = 8009
FRONTEND_PORT = 5000

# 1. Kill ALL old processes
print("=== Cleaning ports ===")
for _ in range(2):
    r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    for line in r.stdout.split('\n'):
        for port in [str(BACKEND_PORT), str(FRONTEND_PORT), '8000', '3000']:
            if f':{port}' in line and 'LISTENING' in line:
                pid = int(line.strip().split()[-1])
                try:
                    ctypes.windll.kernel32.OpenProcess(1, False, pid)
                    ctypes.windll.kernel32.TerminateProcess(pid, 0)
                    print(f"  Killed PID {pid} on port {port}")
                except:
                    pass
    time.sleep(1)

# Clean Next.js lock
lock = os.path.join(FRONTEND_DIR, ".next", "dev")
if os.path.exists(lock):
    shutil.rmtree(lock, ignore_errors=True)

time.sleep(2)
print("  Ports clean")

# 2. Start backend
print(f"\n=== Starting backend on :{BACKEND_PORT} ===")
os.chdir(BACKEND_DIR)
backend = subprocess.Popen(
    [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
    cwd=BACKEND_DIR,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(4)

# Verify backend
try:
    r = urllib.request.urlopen(f"http://localhost:{BACKEND_PORT}/", timeout=5)
    print(f"  Backend: {json.loads(r.read())['status']}")
except Exception as e:
    print(f"  Backend FAILED: {e}")
    sys.exit(1)

# 3. Start frontend
print(f"\n=== Starting frontend on :{FRONTEND_PORT} ===")
os.chdir(FRONTEND_DIR)
frontend = subprocess.Popen(
    [r"D:\npm.cmd", "run", "dev", "--", "-p", str(FRONTEND_PORT)],
    cwd=FRONTEND_DIR,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

# Wait for Next.js to compile
print("  Waiting for Next.js Turbopack...")
for i in range(15):
    time.sleep(3)
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{FRONTEND_PORT}/", timeout=5)
        if r.status == 200:
            print(f"  Frontend: HTTP 200 ({(i+1)*3}s)")
            break
    except:
        if i % 3 == 2:
            print(f"  Still compiling... ({(i+1)*3}s)")

# 4. Test cloud GPU
print(f"\n=== Testing Cloud GPU (Aria-AMT) ===")
test_wav = r"d:\GitWarehouse\note_digger_saier\test_piano.wav"
with open(test_wav, "rb") as f:
    wav = f.read()

boundary = "----CloudTest"
body = (
    b"--" + boundary.encode() + b"\r\n"
    b'Content-Disposition: form-data; name="file"; filename="test.wav"\r\n'
    b"Content-Type: audio/wav\r\n\r\n"
    + wav + b"\r\n"
    b"--" + boundary.encode() + b"\r\n"
    b'Content-Disposition: form-data; name="model"\r\n\r\n'
    b"aria-amt\r\n"
    b"--" + boundary.encode() + b"--\r\n"
)

req = urllib.request.Request(
    f"http://localhost:{BACKEND_PORT}/api/v1/transcribe/file",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)

t0 = time.time()
resp = urllib.request.urlopen(req, timeout=15)
init = json.loads(resp.read())
task_id = init["task_id"]
print(f"  Task {task_id} | {init['status']}")

for i in range(30):
    time.sleep(5)
    r = urllib.request.urlopen(
        f"http://localhost:{BACKEND_PORT}/api/v1/transcribe/{task_id}", timeout=5
    )
    d = json.loads(r.read())
    pct = d.get("percent", 0)
    stage = d.get("stage", "")
    st = d["status"]
    elapsed = time.time() - t0
    print(f"  [{elapsed:.0f}s] {pct}% {stage} ({st})")
    if st == "completed":
        print(f"\n  *** CLOUD GPU SUCCESS! ***")
        print(f"  Engine: {d.get('engine', '?')}")
        print(f"  MIDI: http://localhost:{BACKEND_PORT}{d.get('midi_url', '')}")
        break
    if st == "failed":
        err = d.get("error", "")[:300]
        print(f"\n  FAILED: {err}")
        if "Aria-AMT not installed" in err:
            print("  >> Cloud NOT reached — falling back to local")
        elif "paramiko" in err.lower() or "ssh" in err.lower():
            print("  >> SSH connection issue")
        elif "queued" in st:
            print("  >> Task stuck in queue — not in DEV_MODE?")
        break

print(f"\n=== Done ===")
print(f"Frontend: http://localhost:{FRONTEND_PORT}")
print(f"Backend:  http://localhost:{BACKEND_PORT}")
print(f"Press Ctrl+C to stop servers")
sys.stdout.flush()

# Keep running
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down...")
    backend.terminate()
    frontend.terminate()
