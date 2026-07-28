# Note Digger — GPU 转录服务 完整部署指南 v2

> **目标**：在 AutoDL 云 GPU 上部署 Aria-AMT，ECS 通过 HTTP 调用，实现高质量钢琴扒谱。
> **耗时**：30-45 分钟（一次性）
> **费用**：约 5-8 元（测试用）
> **难度**：会复制粘贴终端命令即可

---

## 一、配置要求

### 1.1 GPU 服务器（AutoDL）

| 项目 | 最低要求 | 推荐配置 | 为什么 |
|------|---------|---------|--------|
| GPU | RTX 3060 (12GB) | **RTX A4000 (16GB)** | A4000 性价比最高，16GB 够跑 medium-double 模型 |
| 显存 | ≥ 12GB | ≥ 16GB | 模型权重 ~2GB，推理中间激活 ~6-8GB |
| 内存 | ≥ 8GB | **16GB** | 音频预处理 + Python 开销 |
| CPU | 4 核 | 8 核 | torch.compile 首次编译需要 CPU |
| 系统盘 | 30GB | 50GB | 模型 + 依赖 ~5GB，日志 + 临时文件 |
| 操作系统 | Ubuntu 20.04+ | Ubuntu 22.04 | CUDA 兼容性最好 |
| Python | **3.11.x（硬性要求）** | 3.11.8+ | Aria-AMT 只支持 3.11 |
| CUDA | ≥ 11.8 | **12.1** | PyTorch 2.1 推荐 |
| PyTorch | ≥ 2.0 | **2.1.0** | 与 torchaudio 2.1.0 配套 |
| torchaudio | **≤ 2.5（硬性要求）** | **2.1.0** | ≥ 2.6 删除了 io 子模块，Aria-AMT import 会炸 |
| 网络 | 能访问 HuggingFace | 国内需 HF 镜像 | 下载模型权重用 |

### 1.2 ECS 服务器（已有）

| 项目 | 当前状态 | 需要改动 |
|------|---------|---------|
| 内存 | 7.1GB，可用 ~5.4GB | 无需改动 |
| Python | 3.11（venv） | 无需改动 |
| 网络 | 能访问外网 | 需确认能连通 AutoDL 公网 IP:8000 |
| 磁盘 | 25GB 可用 | 无需改动 |

### 1.3 端口与网络

```
你的电脑 ──SSH:22──→ AutoDL GPU (公网IP:xxxxx)
                          │
                          ├── :8000 HTTP API (aria_server.py)
                          │
ECS 112.124.56.83 ──HTTP──┘  POST /transcribe
```

| 端口 | 用途 | 方向 |
|------|------|------|
| 22 | SSH 管理 AutoDL | 你的电脑 → AutoDL |
| 8000 | Aria-AMT API | ECS → AutoDL |
| 35100 | AutoDL SSH 端口映射 | 你的电脑 → AutoDL |

---

## 二、AutoDL 操作（在浏览器里）

### 步骤 1：注册

1. 打开浏览器，访问 **https://www.autodl.com**
2. 点右上角「注册」，用手机号注册
3. 注册后点右上角「充值」
4. 充值金额填 **10 元**，支付宝/微信扫码
5. 看到余额变成 10 元 → ✅ 下一步

### 步骤 2：创建 GPU 实例

1. 左侧菜单点「容器实例」
2. 点橙色按钮「租用新实例」
3. 你会看到一个表单，**逐项按下面选择**：

```
┌─────────────────────────────────────────┐
│ 计费方式：  ○ 包月  ● 按量计费          │
│                                          │
│ GPU 型号：  下拉选「RTX A4000」           │
│             如果 A4000 缺货，选「RTX 3090」│
│                                          │
│ 显卡数量：  1 卡                          │
│                                          │
│ CPU：       选 8 核的那个                 │
│                                          │
│ 内存：      选 16GB 的那个                │
│                                          │
│ 数据盘：    默认 50GB，不用改              │
│                                          │
│ 镜像：      在搜索框输入 "3.11"           │
│             选「PyTorch 2.1.0 Python 3.11 │
│                  CUDA 12.1 Ubuntu 22.04」 │
│             （一定要 Python 3.11！）       │
└─────────────────────────────────────────┘
```

4. 点底部「立即创建」
5. 等 1-2 分钟，状态从「创建中」→「运行中」→ ✅

### 步骤 3：查看实例信息

1. 在「容器实例」列表里找到你的实例
2. 记下以下信息（**后面会反复用到**）：

| 信息 | 在哪里看 | 示例值 |
|------|---------|--------|
| 公网 IP | 列表里直接显示 | `123.45.67.89` |
| SSH 端口 | 列表里「SSH」列 | `35100` |
| 登录密码 | 点「更多」→「修改密码」 | `aBc123456` |

3. 完整的 SSH 命令是：
   ```bash
   ssh -p 35100 root@123.45.67.89
   ```

---

## 三、AutoDL 操作（在终端里）

> 以下所有命令在 **Windows Terminal** 或 **Git Bash** 里执行。
> 每一条命令建议**整行复制粘贴**，避免手打出错。

### 步骤 4：SSH 连接

打开终端，输入（替换成你的 IP 和端口）：

```bash
ssh -p 35100 root@123.45.67.89
```

首次连接会问 `Are you sure you want to continue connecting?`，输入 `yes` 回车。
密码输入时不显示字符，粘贴后直接回车。

进去后你应该看到：
```
Welcome to Ubuntu 22.04.x LTS
root@container-xxxx:~#
```

### 步骤 5：验证环境

逐条执行，确认输出符合预期：

```bash
# 1. 确认 GPU
nvidia-smi
```
**预期输出**：表格显示 RTX A4000，Driver Version, CUDA Version: 12.1

```bash
# 2. 确认 Python 版本
python --version
```
**预期输出**：`Python 3.11.x`

```bash
# 3. 确认 CUDA
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```
**预期输出**：`CUDA: True`

> 如果任何一项不符合预期，**不要继续**。回到 AutoDL 控制台，释放这个实例，重新选镜像创建。

### 步骤 6：降级 torchaudio ⚠️ 最关键一步

```bash
# 先看当前版本
python -c "import torchaudio; print(torchaudio.__version__)"
```

如果显示 `2.6.0` 或更高 → **必须降级**。如果显示 `2.1.0` 或 `2.4.0` → 跳过此步。

```bash
# 降级
pip uninstall torchaudio -y
pip install torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121
```

**验证**（这步必须通过，否则后面全白做）：
```bash
python -c "
import torch
import torchaudio
print('torch:', torch.__version__)
print('torchaudio:', torchaudio.__version__)
from torchaudio.io import StreamReader
print('StreamReader OK')
"
```
**预期输出**：最后一行是 `StreamReader OK`。如果不是，重新执行降级命令。

### 步骤 7：安装依赖

```bash
# 系统工具
apt-get update && apt-get install -y git wget

# Python 包（一行安装，约 2-3 分钟）
pip install soundfile librosa pretty_midi fastapi uvicorn python-multipart

# 如果 pip 下载太慢，先换清华源：
# pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 步骤 8：克隆并安装 Aria-AMT

```bash
cd /root
git clone https://github.com/EleutherAI/aria-amt.git
cd aria-amt
pip install -e .
```

**验证**：
```bash
which aria-amt
```
**预期输出**：`/usr/local/bin/aria-amt` 或 `/root/miniconda3/bin/aria-amt`

### 步骤 9：下载模型权重

```bash
mkdir -p /root/aria_amt_checkpoints
cd /root/aria_amt_checkpoints

# 下载（约 2.2GB，需要 2-5 分钟）
wget -O piano-medium-double-1.0.safetensors \
  "https://huggingface.co/AEmotionStudio/aria-amt-models/resolve/main/piano-medium-double-1.0.safetensors"
```

> **如果下载失败或太慢**，用国内镜像：
> ```bash
> wget -O piano-medium-double-1.0.safetensors \
>   "https://hf-mirror.com/AEmotionStudio/aria-amt-models/resolve/main/piano-medium-double-1.0.safetensors"
> ```

**验证**：
```bash
ls -lh /root/aria_amt_checkpoints/
```
**预期输出**：一个约 2.2GB 的 `.safetensors` 文件。

### 步骤 10：冒烟测试

生成测试音频并跑转录：

```bash
# 生成一段 C 大三和弦音频
python -c "
import soundfile as sf
import numpy as np
sr = 16000
t = np.linspace(0, 3, sr*3)
audio = (np.sin(2*np.pi*523*t)*0.5 + np.sin(2*np.pi*659*t)*0.3 + np.sin(2*np.pi*784*t)*0.2).astype(np.float32)
sf.write('/tmp/test.wav', audio, sr)
print('Test audio created')
"

# 转录（首次运行需要 torch.compile，约 30-60 秒）
aria-amt transcribe \
    medium-double \
    /root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors \
    -load_path /tmp/test.wav \
    -save_dir /tmp/test_out \
    -bs 1 \
    -compile

# 检查输出
ls -la /tmp/test_out/
```

**预期输出**：`/tmp/test_out/` 下有一个 `.mid` 文件。

> 如果这里报错，回头看步骤 6——99% 是 torchaudio 版本问题。

---

## 四、部署 HTTP API 服务

### 步骤 11：创建服务文件

在 AutoDL 终端里执行以下整段（一次性粘贴）：

```bash
cat > /root/aria_server.py << 'ENDOFFILE'
"""Aria-AMT HTTP API server — ECS calls this to transcribe audio on GPU."""
import os, sys, json, subprocess, tempfile, shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn

# ⚠️ CRITICAL: CUDA requires spawn, not fork (Linux default)
import multiprocessing
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

CHECKPOINT = Path("/root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors")

app = FastAPI(title="Aria-AMT GPU Service")


@app.get("/health")
async def health():
    import torch
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.total",
         "--format=csv,noheader"],
        capture_output=True, text=True
    )
    return {
        "status": "healthy",
        "gpu": gpu.stdout.strip(),
        "checkpoint": CHECKPOINT.exists(),
        "cuda": torch.cuda.is_available(),
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    tmp_dir = Path(tempfile.mkdtemp(dir="/tmp"))
    audio_path = tmp_dir / f"input{suffix}"
    content = await file.read()
    audio_path.write_bytes(content)

    out_dir = tmp_dir / "out"
    out_dir.mkdir()

    try:
        cmd = [
            "aria-amt", "transcribe",
            "medium-double",
            str(CHECKPOINT),
            "-load_path", str(audio_path),
            "-save_dir", str(out_dir),
            "-bs", "1",
            "-compile",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr[:500])

        midi_files = sorted(out_dir.glob("*.mid*"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if not midi_files:
            raise HTTPException(status_code=500, detail="No MIDI output")

        import pretty_midi
        midi = pretty_midi.PrettyMIDI(str(midi_files[0]))
        notes = []
        for inst in midi.instruments:
            for note in inst.notes:
                notes.append({
                    "pitch": int(note.pitch),
                    "onset": round(float(note.start), 4),
                    "offset": round(float(note.end), 4),
                    "velocity": int(note.velocity),
                })

        return {
            "status": "completed",
            "notes": notes,
            "num_notes": len(notes),
            "midi_hex": midi_files[0].read_bytes().hex(),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
ENDOFFILE

echo "✅ aria_server.py created"
```

### 步骤 12：启动服务

```bash
cd /root
nohup python aria_server.py > /root/aria_server.log 2>&1 &

# 等模型加载（首次有 torch.compile 预热，约 30 秒）
echo "Waiting for model to load..."
sleep 30

# 检查是否启动成功
curl -s http://localhost:8000/health | python3 -m json.tool
```

**预期输出**：
```json
{
    "status": "healthy",
    "gpu": "NVIDIA RTX A4000, 0 MiB / 15360 MiB",
    "checkpoint": true,
    "cuda": true
}
```

> 如果返回 `curl: (7) Failed to connect`，说明服务还没起来。再等 15 秒重试。
> 如果返回错误，看日志：`tail -50 /root/aria_server.log`

### 步骤 13：端到端测试

```bash
# 用之前的测试音频
curl -s -X POST http://localhost:8000/transcribe \
  -F "file=@/tmp/test.wav" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'status={d[\"status\"]} notes={d[\"num_notes\"]}')"
```

**预期输出**：`status=completed notes=3`（或类似数字）

---

## 五、配置 AutoDL 端口映射 ⚠️ 容易漏

### 步骤 14：开放 8000 端口

AutoDL 默认只开 SSH 端口，8000 需要手动映射。

1. AutoDL 控制台 → 容器实例 → 你的实例
2. 点右侧「更多」→「端口映射」
3. 点「添加端口映射」
4. 填写：

```
容器端口：8000
协议：    HTTP
```

5. 点确定。你会看到一行新增的映射，AutoDL 会分配一个**外部端口号**（比如 `46000`）。

6. 记下完整的外部访问地址。AutoDL 会显示类似：
   ```
   http://123.45.67.89:46000
   ```
   这就是 ECS 要调用的 GPU 服务地址。

### 步骤 15：验证外网可访问

从**你的电脑**（不是 AutoDL SSH 里）执行：

```bash
curl http://123.45.67.89:46000/health
```

**预期输出**：JSON 格式的健康检查响应。

> 如果连不上，检查：
> 1. 端口映射是否添加成功
> 2. 外部端口是不是你填的那个
> 3. API 服务是否在运行（SSH 进去 `ps aux | grep aria_server`）

---

## 六、ECS 集成

### 步骤 16：SSH 到 ECS

```bash
ssh root@112.124.56.83
# 密码：LYXlyx20060605!
```

### 步骤 17：更新 cloud_amt.py 支持 HTTP 模式

我们现有的 `cloud_amt.py` 只支持 SSH/SFTP。加一个 HTTP 模式的函数：

```bash
cd /opt/note_digger_saier/backend
```

编辑 `app/models/cloud_amt.py`，在文件**末尾**追加以下代码：

```python
# --- HTTP mode for AutoDL (simpler than SSH, no paramiko needed) ---

CLOUD_HTTP_URL = os.getenv("CLOUD_GPU_HTTP_URL", "")


def is_cloud_http_available() -> bool:
    """Check if cloud GPU is reachable via HTTP."""
    if not CLOUD_HTTP_URL:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{CLOUD_HTTP_URL.rstrip('/')}/health",
            headers={"User-Agent": "NoteDigger/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def transcribe_cloud_http(audio_path: Path, output_dir: Path) -> Path:
    """Transcribe via HTTP to AutoDL GPU server."""
    import urllib.request
    import urllib.error

    url = CLOUD_HTTP_URL.rstrip('/') + "/transcribe"

    # Read audio
    with open(audio_path, 'rb') as f:
        audio_data = f.read()

    # Build multipart request
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
            import json as _json
            result = _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GPU server error: {e.read().decode()[:300]}")
    except Exception as e:
        raise RuntimeError(f"GPU request failed: {e}")

    if result.get("status") != "completed":
        raise RuntimeError(f"Transcription failed: {result}")

    # Decode MIDI from hex
    midi_bytes = bytes.fromhex(result["midi_hex"])
    output_path = output_dir / f"{audio_path.stem}_aria.mid"
    output_path.write_bytes(midi_bytes)

    return output_path
```

### 步骤 18：更新 is_cloud_available 函数

找到 `cloud_amt.py` 中已有的 `is_cloud_available()` 函数（约第 42 行），在 `return False` **前面**加一行 HTTP 检查：

```python
def is_cloud_available() -> bool:
    if not CLOUD_GPU_HOST:
        return False
    # Try HTTP first (AutoDL), then SSH (legacy seetacloud)
    if CLOUD_HTTP_URL:
        return is_cloud_http_available()
    # ... 后面保持原有 SSH 检查代码不变 ...
```

> 实际上，更简单的方法是把整个 `is_cloud_available` 改成：
> ```python
> def is_cloud_available() -> bool:
>     if CLOUD_HTTP_URL:
>         return is_cloud_http_available()
>     if CLOUD_GPU_HOST:
>         try:
>             # ... 原有 SSH 逻辑 ...
>         except:
>             return False
>     return False
> ```

### 步骤 19：更新转录管线

编辑 `app/tasks/transcription.py`，找到转录逻辑（约第 55 行），在 auto 模式中加入 HTTP 优先：

```python
# 原来的 auto 分支大约是这样：
else:
    if is_cloud_available():
        raw_midi_path = transcribe_cloud(processed_path, output_dir)
    else:
        raw_midi_path = transcribe_basic_pitch(processed_path, output_dir, quality="adaptive")
```

改为：

```python
else:
    from app.models.cloud_amt import is_cloud_http_available, transcribe_cloud_http
    if is_cloud_http_available():
        raw_midi_path = transcribe_cloud_http(processed_path, output_dir)
    elif is_cloud_available():
        raw_midi_path = transcribe_cloud(processed_path, output_dir)
    else:
        raw_midi_path = transcribe_basic_pitch(processed_path, output_dir, quality="adaptive")
```

同样修改 `basic-pitch` 和 `aria-amt` 分支中的逻辑。

### 步骤 20：配置环境变量

```bash
# 在 ECS 上
cd /opt/note_digger_saier/backend

# 把 <外部地址> 替换成步骤 14 里 AutoDL 给你的地址
echo 'CLOUD_GPU_HTTP_URL=http://123.45.67.89:46000' >> .env

# 确认写入
cat .env | grep CLOUD
```

### 步骤 21：重启并测试

```bash
systemctl restart note-digger-backend
sleep 3

# 测试健康检查
curl -s http://localhost:8001/api/v1/health

# 测试上传 + 转录（用 Aria-AMT）
curl -s -X POST http://localhost:8001/api/v1/transcribe/file \
  -F "file=@/opt/note_digger_saier/backend/test_data/benchmark/09_pop_ballad/audio.wav" \
  -F "model=aria-amt" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'task_id={d[\"task_id\"]}')"

# 等 60 秒后查结果
sleep 60
curl -s http://localhost:8001/api/v1/transcribe/<task_id> | python3 -m json.tool | head -10
```

---

## 七、验证清单

完成部署后，逐项检查：

- [ ] AutoDL 实例状态：运行中
- [ ] `nvidia-smi` 能看到 GPU
- [ ] `python --version` = 3.11.x
- [ ] `torchaudio.__version__` ≤ 2.5，`StreamReader` 能 import
- [ ] 模型权重文件存在且 > 2GB
- [ ] 冒烟测试通过（`/tmp/test_out/` 有 .mid 文件）
- [ ] `aria_server.py` 在后台运行（`ps aux | grep aria_server`）
- [ ] `curl localhost:8000/health` 返回 200
- [ ] AutoDL 端口映射已添加
- [ ] `curl <外部地址>/health` 从你的电脑访问成功
- [ ] ECS `.env` 中 `CLOUD_GPU_HTTP_URL` 已设置
- [ ] ECS 后端重启后健康检查正常
- [ ] ECS 上传音频 → aria-amt 模型 → 转录成功

---

## 八、日常使用

### 开机
1. AutoDL 控制台 → 实例 → **开机**（约 1 分钟）
2. SSH 进去 → `nohup python /root/aria_server.py > /root/aria_server.log 2>&1 &`
3. 等 30 秒 → `curl localhost:8000/health` 确认
4. 正常使用 Note Digger，选择 Aria-AMT 模型

### 关机
1. AutoDL 控制台 → 实例 → **关机**（不要点释放！）
2. 关机后只收数据盘存储费（约 0.1 元/天）

### 释放（如果以后不再用）
1. AutoDL 控制台 → 实例 → **释放**
2. 所有数据将被删除，下次需要从步骤 2 重新来

---

## 九、故障排查

| 症状 | 诊断命令 | 常见原因 | 解决 |
|------|---------|---------|------|
| `StreamReader` import 失败 | `python -c "from torchaudio.io import StreamReader"` | torchaudio ≥ 2.6 | 回到步骤 6 降级 |
| `aria-amt: command not found` | `which aria-amt` | 没装或 PATH 问题 | `cd /root/aria-amt && pip install -e .` |
| CUDA out of memory | `nvidia-smi` | 显存不够或 batch 太大 | 确认 `-bs 1`，关掉其他进程 |
| 权重下载失败 | `ls -lh /root/aria_amt_checkpoints/` | 网络问题 | 用 HF 镜像（步骤 9 的备用命令） |
| AutoDL 连不上 | `ssh -vvv -p xxx root@xxx` | 实例未启动或端口映射问题 | 等 3 分钟重试，刷新控制台 |
| GPU 服务连不上 | `curl <外部地址>/health` | 端口映射或防火墙 | 回到步骤 14-15 检查端口映射 |
| 转录返回 500 | `tail -100 /root/aria_server.log` | 模型加载失败或音频格式问题 | 确认模型权重存在，音频 16kHz mono |
| 转录超时 | `systemctl status note-digger-backend` | 音频太长或 GPU 太慢 | 默认超时 300 秒，长音频需增加 |

---

## 十、费用明细

| 操作 | 时长 | GPU 费 | 存储费 | 合计 |
|------|------|--------|--------|------|
| 初次部署 | ~40 分钟 | ~1.3 元 | 0 | ~1.3 元 |
| 开发测试 | 2 小时 | ~4 元 | ~0.1 元 | ~4.1 元 |
| 单次转录 | ~45 秒 | ~0.025 元 | 0 | ~0.025 元 |
| 闲置（关机） | 一天 | 0 | ~0.1 元 | ~0.1 元/天 |
| 闲置（运行中） | 一天 | ~48 元 | ~0.1 元 | ~48 元/天 ⚠️ |

**务必用完关机！**
