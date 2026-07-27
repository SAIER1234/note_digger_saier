# CLAUDE.md — Note Digger

## 项目概述
AI 自动钢琴扒谱 Web 应用。Phase 1 专注钢琴独奏转录，后续加多乐器。

## 用户信息
- GitHub: SAIER1234
- 服务器: 阿里云 ECS 2G8核（与 autofarm 共用）
- 预算: 尽量省钱（<100元/月）

## 架构决策
1. **Aria-AMT** (SOTA 钢琴转录) 优于 Basic Pitch/MT3/Transkun
2. **FastAPI + Celery** 而非 Node.js（AI 生态全在 Python）
3. **MusicXML** 作为中间格式（MIDI→谱面的桥梁）
4. **CPU 优先**，Aria-AMT 需 GPU（AutoDL RTX 2080Ti ¥0.88/h）

## 三级转录引擎
| 引擎 | 质量 | 环境 |
|------|------|------|
| Aria-AMT | 90分 | GPU (CUDA) |
| Basic Pitch | 70分 | CPU (TensorFlow) |
| Simple librosa | 30分 | CPU (零依赖) |

## 运行方式
- 本地: backend bp311 conda env port 8002, frontend Next.js dev port 5050
- ECS: backend venv port 8001, frontend Next.js production port 3000, Nginx :80
- Pipeline: 上传→预处理→转录→MIDI→MusicXML→OSMD渲染
- 评测: 6 例基准数据, evaluate.py 算 F1/编曲分

## 部署
- ECS 112.124.56.83 (阿里云 7.1GB), autofarm 占 8000
- **GitHub 在 ECS 上被墙**，部署用 scp 传文件，不要 git pull
- Systemd: note-digger-backend (8001) + note-digger-frontend (3000) + nginx
- Loop: CronCreate 每小时 :57, LOOP_STATE.json 持久化
