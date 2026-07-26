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
- 后端: bp311 conda env, uvicorn port 8002
- 前端: Next.js dev port 5050
- Pipeline: 上传→预处理→转录→MIDI→MusicXML→OSMD渲染

## 部署目标
- 同一台 ECS（阿里云 2G8核）
- Nginx + FastAPI(1 worker) + Next.js production
- 转录任务 → 云端 GPU（AutoDL）
- 无 Redis（内存不够，用内存队列）
