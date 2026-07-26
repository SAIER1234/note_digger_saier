# AutoDL GPU 快速上手 — 让 Note Digger 拥有专业级转录

## 为什么需要 GPU？

| 引擎 | 质量 | 需要 GPU |
|------|------|---------|
| Simple librosa | 30分 | ❌ |
| Basic Pitch | 70分 | ❌ |
| **Aria-AMT** | **90分** | ✅ |

Aria-AMT 是 2024 年最强开源钢琴转录模型，MAESTRO 基准 95%+ F1 准确率。

## 5 分钟部署

### Step 1: 注册 AutoDL

访问 https://www.autodl.com → 手机注册 → 实名认证（送 10-30 元体验金）

### Step 2: 充值 50 元

微信/支付宝 → 最低 50 元。跑一次转录 ≈ ¥0.15，够用几百次。

### Step 3: 开实例

控制台 → 容器实例 → 租用新实例：

- **GPU**: RTX 2080Ti (¥0.88/时) 或 RTX 3090 (¥1.48/时)
- **镜像**: PyTorch 2.3.0 + Python 3.11 + CUDA 12.1
- **数据盘**: 50GB（模型文件 446MB，够用）
- 创建 → 等 1 分钟开机

### Step 4: 一键部署

SSH 登录后运行：

```bash
# 上传部署脚本
# 方式1: 直接在 SSH 终端粘贴运行
bash <(curl -s https://raw.githubusercontent.com/.../cloud_gpu_setup.sh)

# 方式2: 手动执行
git clone https://github.com/EleutherAI/aria-amt.git
cd aria-amt && pip install -e .
mkdir -p /root/models
python -c "from huggingface_hub import hf_hub_download; hf_hub_download('AEmotionStudio/aria-amt-models', 'piano-medium-double-1.0.safetensors', local_dir='/root/models')"

# 启动转录服务
cd /root && python transcribe_server.py
# 服务监听在 http://你的实例IP:8000
```

### Step 5: 对接 Note Digger

在你的 `.env` 文件里加：

```
CLOUD_GPU_URL=http://你的AutoDL实例IP:8000
```

重启后端。现在选"自动"或"aria-amt"引擎 = 云端专业转录。

## 省钱技巧

- **用完就关机！** 关机不扣 GPU 费（只扣数据盘几毛/天）
- 设置「空闲 30 分钟自动关机」
- 充 50 元够测试几百次
- 真的要商用再包月（更便宜）

## 安全提醒

AutoDL 实例有公网 IP，建议：
```bash
# 设置防火墙只允许你的 IP 访问
ufw allow from 你的IP to any port 8000
```
