# Note Digger — 迭代日志

## Round 5 — 2026-07-27 [quality]
- **方向**: 转录质量 — chord/arranger 回归测试 + 三 bug 修复
- **bugfix**: chord_detect 存元组误用属性、arranger rstrip 洗掉升降号、MusicXML 编曲前生成
- **测试**: verify.py 增至 21 项，新增 chord detect + arranger 回归
- **下轮**: System（饥饿度0.90）或编曲自适应

## Round 4 — 2026-07-27 [ux]
- **方向**: 用户体验 — 移动端适配 + 反馈优化
- **完成**: 响应式排版、模型选择器自动换行、离线重试按钮、加载时间预估
- **下轮**: System（饥饿度0.60）或 Quality 自适应预设

## Round 3 — 2026-07-27 [arr]
- **方向**: 编曲质量 — 智能大谱表分离
- **完成**: 替换固定 C4 分割为方差最小化聚类算法
- **算法**: 同时发音(30ms内)归同一只手 + K-means 找最优分割点
- **验证**: MusicXML 成功输出双谱表，转录端到端通过
- **下轮**: UX（饥饿度最高）或 adaptive preset

## Round 2 — 2026-07-27 [quality]
- **方向**: 转录质量 — 参数网格搜索优化
- **完成**: 测试 14 组参数组合，找到最优 balanced preset
- **最优**: onset=0.6, frame=0.4, min_len=50ms → Avg F1 0.901 (+7.8%)
- **修复**: 快速音符 F1 0.118→0.984 (+86.6%)
- **代价**: 和弦/琶音精度略降 (1.0→0.83, -17%)
- **部署**: medium preset 更新 + 默认 quality 改为 medium
- **下轮**: 自适应预设（根据音频特征选择 high/medium）

## Round 1 — 2026-07-27 [quality]
- **方向**: 转录质量 — 建立评测基线
- **完成**: 6例合成基准数据(音阶/琶音/和弦/旋律低音/快速/弱力度) + 自动化评测脚本
- **基线**: Avg F1=0.823, Score=84.8
- **关键发现**: 快速音符(140bpm 16分) F1 仅 0.118 — min_note_length=100ms 太激进
- **下轮**: 网格搜索 Basic Pitch 参数，重点修复快速段落识别
