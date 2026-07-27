# CLAUDE.md — Note Digger

## 铁律：先验后布

**每次改代码后，必须先本地跑 `python scripts/verify.py`，20 项全通过才能部署到 ECS。**

理由：过去 100% 的 bug 都是写完直接推 ECS 导致的。验证脚本 90 秒跑完，能拦住 import 错误、API 路径不匹配、music21 版本不兼容、前端编译失败。

部署流程：
1. 写代码
2. `python scripts/verify.py`（必须 20/20 通过）
3. `git commit -m "[direction] ..."` + `git push`
4. `scp` 改动文件到 ECS + `systemctl restart` 受影响服务
5. `curl http://112.124.56.83/api/v1/health` 确认存活

详细的陷阱和检查清单见 [VERIFICATION.md](VERIFICATION.md)。

## 已知陷阱

1. **music21**: `score.remove(part)` 能用，`score.core` 不存在。MIDI 解析格式因版本而异。
2. **Frontend API 路径**: Nginx 只代理 `/api/*` 到后端。所以 auth.ts 必须用 `/api/v1/auth/...` 不 是 `/auth/...`。
3. **Basic Pitch**: `min_note_length` 单位是 ms。16分音符在 180bpm = 83ms，所以 medium preset 用 50ms。
4. **pretty_midi**: `KeySignature(key_number, time)` 的 key_number 必须 ∈ [-7, 7]。
5. **ECS GitHub 被墙**: 不能用 `git pull`，用 `scp`。
6. **Windows 编码**: 输出用 ASCII，`python scripts/verify.py` 前设 `PYTHONIOENCODING=utf-8`。

## 项目概述

AI 自动钢琴扒谱 Web 应用。专注钢琴独奏→五线谱。

- GitHub: SAIER1234/note_digger_saier
- ECS: 112.124.56.83 (阿里云 7.1GB, Ubuntu), autofarm 占 8000
- 预算: <100元/月

## 架构

| 组件 | 端口 | 技术 |
|------|------|------|
| Frontend | :3000 (ECS) / :5050 (本地) | Next.js 16 + TailwindCSS |
| Backend API | :8001 (ECS) / :8002 (本地) | FastAPI + uvicorn |
| Nginx | :80 | 反代 `/`→:3000, `/api/`→:8001 |
| DB | SQLite | note_digger.db |
| Loop | CronCreate | 每小时 :57, LOOP_STATE.json |

## 转录引擎

| 引擎 | 质量 | 环境 | 状态 |
|------|------|------|------|
| Basic Pitch (medium) | F1=0.901 | CPU | 已部署 |
| Aria-AMT | 90分(估计) | GPU | 未部署 |
| Simple (librosa) | 30分 | CPU | 备用 |

Pipeline: 上传→预处理(16kHz mono)→转录→后处理→MIDI→music21→MusicXML→OSMD渲染

## 基准评测

- 6 例合成测试数据: `backend/test_data/benchmark/`
- 评测: `backend/app/evaluate.py` (F1/编曲分)
- 指标: `metrics/round_NNN.json`

## Loop 状态

- 方向轮转: 质量(35%)→编曲(30%)→UX(20%)→系统(15%)
- 状态文件: [LOOP_STATE.json](LOOP_STATE.json), [CHANGELOG.md](CHANGELOG.md)
- 停止条件: REGRESSION/宕机/4轮无进展/内存<300MB/磁盘<5GB
