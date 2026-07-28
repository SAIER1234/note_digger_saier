# Aria-AMT GPU 转录服务 — 傻瓜级部署指南

> 去年在 seetacloud 失败过两次。原因：torchaudio 版本冲突、CUDA 多进程上下文错误。
> 这次所有坑都标注了 `⚠️ 上次炸在这里`。

---

## 0. 准备工作（你的电脑上）

需要：浏览器 + SSH 客户端（Windows Terminal / Git Bash）+ **30 分钟 + 约 5 元**

---

## 第一步：AutoDL 注册 + 创建实例

### 1.1 注册充值
1. 打开 https://www.autodl.com ，手机号注册
2. 右上角「充值」，充 **10 元**（A4000 约 2 元/时，够用）

### 1.2 创建实例
点「容器实例」→「租用新实例」：

| 选项 | 选什么 |
|------|--------|
| 计费方式 | **按量计费** |
| GPU | **RTX A4000**（16GB 显存，最便宜够用） |
| 内存 | 选 **16GB** 那个 |
| 数据盘 | 默认 50GB |

**镜像（最重要！）** 搜索框输入 `3.11`，选：
```
PyTorch 2.1.0 + Python 3.11 + CUDA 12.1
```
> `Python 3.11` 是硬性要求。如果没有 3.11 镜像，选 `Python 3.10 (Ubuntu)`，后面手动创建 conda 环境。

点「立即创建」，等 1-2 分钟。

---

## 第二步：连接实例

AutoDL 控制台 → 容器实例 → 复制 SSH 命令（类似 `ssh -p 12345 root@xx.xx.xx.xx`）

打开终端：
```bash
ssh -p <端口> root@<IP>
# 密码在 AutoDL 实例详情页
```

进去后验证：
```bash
nvidia-smi                     # 确认 GPU 可见
python --version               # 必须是 3.11.x
pip --version
```

---

## 第三步：安装 Aria-AMT

> ⚠️ 上次在 seetacloud 炸在这里——torchaudio 太新导致 `from torchaudio.io import StreamReader` 失败

### 3.1 安装系统依赖
```bash
apt-get update && apt-get install -y git wget
```

### 3.2 降级 torchaudio ⚠️ 关键！
```bash
# 为什么：torchaudio ≥ 2.6 删除了 .io 子模块，Aria-AMT 需要它
pip uninstall torchaudio -y
pip install torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121

# 验证
python -c "
import torch, torchaudio
print('torch:', torch.__version__)
print('torchaudio:', torchaudio.__version__)
print('CUDA:', torch.cuda.is_available())
from torchaudio.io import StreamReader
print('StreamReader OK ✅')
"
```

### 3.3 安装其他依赖
```bash
pip install soundfile librosa pretty_midi fastapi uvicorn python-multipart
```

### 3.4 克隆并安装 Aria-AMT
```bash
cd /root
git clone https://github.com/EleutherAI/aria-amt.git
cd aria-amt
pip install -e .
```

### 3.5 下载预训练权重
```bash
# Aria-AMT 官方权重（我们现有代码用的就是这个）
mkdir -p /root/aria_amt_checkpoints
wget -O /root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors \
  "https://huggingface.co/AEmotionStudio/aria-amt-models/resolve/main/piano-medium-double-1.0.safetensors"
```
> 如果下载慢，用 HF 镜像：
> ```bash
> wget -O /root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors \
>   "https://hf-mirror.com/AEmotionStudio/aria-amt-models/resolve/main/piano-medium-double-1.0.safetensors"
> ```

### 3.6 测试转录（验证一切正常）
```bash
# 生成一段测试音频
python -c "
import soundfile as sf, numpy as np
sr = 16000
t = np.linspace(0, 5, sr*5)
audio = (np.sin(2*np.pi*440*t)*0.5 + np.sin(2*np.pi*554*t)*0.3 + np.sin(2*np.pi*659*t)*0.2).astype(np.float32)
sf.write('/tmp/test_piano.wav', audio, sr)
"

# 跑转录 ⚡
aria-amt transcribe \
    medium-double \
    /root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors \
    -load_path /tmp/test_piano.wav \
    -save_dir /tmp/aria_test_out \
    -bs 1 \
    -compile

# 检查输出
ls -la /tmp/aria_test_out/
# 应该有一个 .mid 文件
```

看到 `.mid` 文件就成功了 ✅！

---

## 第四步：部署为 API 服务

### 4.1 创建 API 服务器

```bash
cat > /root/aria_server.py << 'ENDOFFILE'
"""Aria-AMT transcription server — wraps CLI as HTTP API."""
import os, sys, json, subprocess, tempfile, shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import uvicorn

# ⚠️ 上次炸在这里：Linux fork 模式与 CUDA 不兼容，必须用 spawn
import multiprocessing
try:
    multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # Already set

CHECKPOINT = Path("/root/aria_amt_checkpoints/piano-medium-double-1.0.safetensors")
MODEL_NAME = "medium-double"
SAVE_DIR = Path("/root/aria_outputs")
SAVE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Aria-AMT GPU Service")


@app.get("/health")
async def health():
    gpu_info = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True
    )
    return {
        "status": "healthy",
        "gpu": gpu_info.stdout.strip(),
        "checkpoint_exists": CHECKPOINT.exists(),
    }


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcribe audio → MIDI using Aria-AMT CLI."""
    # 保存上传文件
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    tmp_dir = Path(tempfile.mkdtemp(dir="/tmp"))
    audio_path = tmp_dir / f"input{suffix}"
    content = await file.read()
    audio_path.write_bytes(content)

    out_dir = tmp_dir / "output"
    out_dir.mkdir()

    try:
        # 跑 CLI
        cmd = [
            "aria-amt", "transcribe",
            MODEL_NAME,
            str(CHECKPOINT),
            "-load_path", str(audio_path),
            "-save_dir", str(out_dir),
            "-bs", "1",
            "-compile",        # torch.compile 加速
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {result.stderr[:500]}"
            )

        # 找输出的 MIDI
        midi_files = sorted(out_dir.glob("*.mid*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not midi_files:
            raise HTTPException(status_code=500, detail="No MIDI output generated")

        # 读 MIDI 解析音符
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
            "midi_bytes_hex": midi_files[0].read_bytes().hex(),
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Transcription timed out (5 min max)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Aria-AMT server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
ENDOFFILE

echo "Server file created at /root/aria_server.py"
```

### 4.2 启动服务（后台运行）

```bash
cd /root
nohup python aria_server.py > /root/aria_server.log 2>&1 &

# 等 15 秒让模型预热加载
sleep 15

# 测试健康检查
curl http://localhost:8000/health
```

应该看到包含 GPU 信息的 JSON 响应。

### 4.3 测试端到端转录

```bash
# 用 test_piano.wav 测试（如果本地有就 scp 到 AutoDL，否则用之前生成的）
curl -X POST http://localhost:8000/transcribe \
  -F "file=@/tmp/test_piano.wav" \
  | python3 -m json.tool | head -30
```

应该看到 notes 列表。

---

## 第五步：从 ECS 调用

### 5.1 获取 AutoDL 公网 IP
AutoDL 控制台 → 实例详情 → 复制公网 IP（不是 SSH 端口后面的那个，是 IP 地址）

### 5.2 在 ECS 上测试
```bash
ssh root@112.124.56.83
curl http://<AutoDL公网IP>:8000/health
```

> 如果连不上：
> 1. AutoDL 控制台 → 实例 → 更多 → 端口映射 → 确认 8000 端口已映射
> 2. 或者在 AutoDL 用 `ufw allow 8000` 开放防火墙

### 5.3 集成到 Note Digger
ECS 上编辑后端配置，添加 GPU 服务地址：
```bash
# 在 ECS 的 .env 中加一行
echo "ARIA_AMT_CLOUD_URL=http://<AutoDL公网IP>:8000/transcribe" >> /opt/note_digger_saier/backend/.env
```

后端代码中的 `cloud_amt.py` 已经支持远程调用，只需配好 URL 即可。

---

## 第六步：用完关机！

**AutoDL 按量计费，不关机会一直扣钱！**

- 控制台 → 容器实例 → **关机**（不丢数据，下次开机文件都在）
- 关机后每天 ~0.1 元数据盘费
- 如果彻底不需要 → **释放**（全删，下次需重来）

---

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| `from torchaudio.io import StreamReader` 报错 | torchaudio 太新 | `pip install torchaudio==2.1.0` |
| CUDA out of memory | 显存不足 | 换更大 GPU 或加 `-bs 1` |
| HFace 下载超时 | 国内网络 | `export HF_ENDPOINT=https://hf-mirror.com` |
| pip 太慢 | 国内网络 | `pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple` |
| SSH 连不上 | 实例未完全启动 | 等 3 分钟，刷新页面 |
| 端口不通 | AutoDL 防火墙 | 控制台 → 端口映射，添加 8000 |

---

## 成本

| 项目 | 价格 |
|------|------|
| A4000 按量 | ~2 元/h |
| 数据盘 50GB | ~0.1 元/天 |
| 网费 | ~0.1 元/次转录 |
| **开发测试 2h** | **≈ 5 元** |

**建议**：只在需要转录时开机，平时关机。一次典型转录约 30-60 秒 GPU 时间（含模型加载 ~10s）。
