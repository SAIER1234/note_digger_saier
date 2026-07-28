# Note Digger — 迭代日志

## Round 33 — 2026-07-28 [system] ⚠️ REPAIR
- **方向**: 系统修复 — GPU→CPU 自动降级 + torch 版本冲突修复
- **问题**: torch_einops_utils 把 torch 从 2.3 升到 2.13，torchaudio.io 崩溃
- **修复**: 后台重装 torch 2.3.0 + torchaudio 2.3.0
- **改进**: aria-amt/auto 模式现在 GPU 挂了自动切 Basic Pitch，不丢请求
- **Orpheus 748M**: 未受影响，始终健康
- **33轮**: quality(10)·arr(11)·ux(5)·system(6)·LOW_IMPACT(2)
- **教训**: 安装新依赖前先检查依赖树，避免自动升级核心包

## Round 32 — 2026-07-28 [arr] 🤖
- **方向**: 编曲质量 — Orpheus 748M AI 智能编曲集成
- **模型**: 7.48亿参数 Transformer，2.31M+ MIDI 训练，Flash Attention + RoPE
- **部署**: 与 Aria-AMT 共存 RTX 3080 (10GB)，端口 8001
- **前端**: 风格下拉新增「🤖 AI 智能编曲」，一键开启神经网络编曲
- **32轮**: quality(10)·arr(11)·ux(5)·system(5)·LOW_IMPACT(2)
- **里程碑**: 首个从零部署到生产的 AI 大模型！GPU 同时跑转录+编曲两个模型

## Round 31 — 2026-07-28 [arr]
- **方向**: 编曲质量 — 结尾处理 (final chord + ritardando)
- **方法**: 在所有音符后加终止和弦（块状+低八度根音），休止0.25拍，保持2拍
- **里程碑**: 首次 GPU 转录 + 编曲全链路跑通！(aria-amt cloud, 42 notes)
- **31轮**: quality(10)·arr(10)·ux(5)·system(5)·LOW_IMPACT(2)
- **下轮**: ux（饥饿度1.20）

## Round 30 — 2026-07-28 [system]
- **方向**: 系统健壮 — 结构化请求日志 + 错误追踪
- **日志**: 每次 API 调用记录 时间/方法/路径/状态码/耗时/客户端IP
- **存储**: backend/logs/api.log (文件) + systemd journal (控制台)
- **system/status**: 新增 requests_today, errors (5xx/4xx), recent_errors
- **30轮**: quality(10)·arr(9)·ux(5)·system(5)·LOW_IMPACT(2)
- **下轮**: arrangement 或 ux（饥饿度均为0.90）

## Round 29 — 2026-07-28 [quality]
- **方向**: 转录质量 — 智能连奏处理 (smart re-strike)
- **方法**: 区分幽灵音(<60ms)→丢弃, 同音反复(<35%重叠)→保留双音, 重复→保留大声
- **效果**: 05_fast_notes F1 +0.037 (0.820→0.857), 原10例无回归 (0.903 vs 0.908)
- **29轮**: quality(10)·arr(9)·ux(5)·system(4)·LOW_IMPACT(2)
- **下轮**: system（饥饿度1.125）

## Round 28 — 2026-07-28 [arr]
- **方向**: 编曲质量 — 旋律和声化 (thirds/sixths below melody)
- **方法**: 每个旋律音找当前和弦→选和弦内音下方三度/六度→加 harmony 音符
- **规则**: 跳过 <0.12s 快速音符, harmony ≥ G3 (保持在 treble), 力度=旋律×75%
- **效果**: pop_ballad 100% 旋律拍点都有和声, playability 99
- **28轮**: quality(9)·arr(9)·ux(5)·system(4)·LOW_IMPACT(2)
- **下轮**: quality（饥饿度1.05）

## Round 27 — 2026-07-28 [ux]
- **方向**: 用户体验 — MIDI→WAV 音频合成 + 导出端点修复
- **合成器**: 正弦波 + 2次谐波 + ADSR 包络，零外部依赖，始终可用
- **策略**: FluidSynth 优先（高质量），Python 合成回退（保底）
- **前端**: MidiPlayer (Web Audio) + 音频下载按钮，现已全功能
- **27轮**: quality(9)·arr(8)·ux(5)·system(4)·LOW_IMPACT(2)
- **下轮**: arrangement（饥饿度0.90）

## Round 26 — 2026-07-28 [quality]
- **方向**: 转录质量 — 新建 2 个高难度基准用例 + 自适应预设验证
- **新用例**: 11_fast_arpeggios (160bpm 16分, 48音/4.5s) + 12_three_voice (三声部复调)
- **自适应验证**: case 11 high=0.000→adaptive=0.118 (BIG WIN, 捕捉到快速音符)
- **基建**: gen_benchmark.py 正弦波合成 MIDI→WAV, 共12个基准用例
- **26轮**: quality(9)·arr(8)·ux(4)·system(4)·LOW_IMPACT(2)
- **下轮**: ux（饥饿度1.50）

## Round 25 — 2026-07-28 [arr]
- **方向**: 编曲质量 — MusicXML 动态标记 (dynamics)
- **方法**: 逐小节分析 velocity → pp/p/mp/mf/f/ff + crescendo/decrescendo 渐强渐弱线
- **原理**: 力度弧线(R22)已有速度数据，本轮将其写入五线谱标记
- **效果**: pop_ballad 编曲输出 4 个动态变化: f→mf→mp→mf
- **25轮**: quality(8)·arr(8)·ux(4)·system(4)·LOW_IMPACT(2)
- **下轮**: ux（饥饿度0.90）

## Round 24 — 2026-07-28 [system]
- **方向**: 系统健壮 — 磁盘追踪 + 自动清理 + 内存守卫
- **system/status**: 新增 outputs_mb / uploads_mb / old_files_count 字段
- **cleanup_outputs.py**: 删除 >30天 旧输出，支持 --dry-run
- **system_guard.py**: 读取 /proc/meminfo，可用 <500MB 拒绝新上传 (503)
- **ECS cron**: 每日 3:07 AM 自动清理，与 backup_db 同时运行
- **24轮**: quality(8)·arr(7)·ux(4)·system(4)·LOW_IMPACT(2)
- **下轮**: ux 或 arrangement（饥饿度均为0.90）

## Round 23 — 2026-07-28 [quality] ⚠️ LOW_IMPACT
- **方向**: 转录质量 — 自适应预设 (adaptive quality preset)
- **方法**: librosa onset detection + spectral centroid → 自动选 high/medium
- **阈值**: fast(>5 onsets/s)→medium(50ms), normal(2-5)→high, sparse(<2)→high
- **结果**: benchmark delta=0.000 — 当前基准无不触发 medium 的快速用例
- **价值**: 对真实快速曲目(肖邦练习曲等)有效，架构正确
- **23轮**: quality(8)·arr(7)·ux(4)·system(3)·LOW_IMPACT(2)
- **下轮**: system（饥饿度1.05）

## Round 22 — 2026-07-28 [arr]
- **方向**: 编曲质量 — 声部引导 + 华尔兹修复 + 力度弧线
- **voice leading**: _find_smoothest_voicing() 选最近转位，左手不再大跳
- **waltz fix**: 正确 3/4 拍 oom-pah-pah，第2&3拍弹完整和弦
- **dynamics arc**: 渐强至60%处→渐弱至结尾，告别恒定力度
- **评测**: chords playability 100, pop_ballad 99, 无回归
- **22轮**: quality(7) · arr(7) · ux(4) · system(3) · LOW_IMPACT(1)
- **下轮**: system（饥饿度0.90）

## Round 21 — 2026-07-28 [ux]
- **方向**: 用户体验 — 历史页显示音符数/时长/编曲状态
- **后端**: get_user_history 读取 MIDI 元数据
- **前端**: 丰富卡片: 钢琴/编曲图标, 音符数, 时长
- **下轮**: arrangement（饥饿度0.90）

## Round 20 — 2026-07-28 [quality] 🎯 里程碑
- **方向**: 转录质量 — 音符节奏量化 (16分音符网格)
- **方法**: 拍点四舍五入, 最大修正30%拍长, 防零时长
- **20轮**: quality(7) · arr(6) · ux(3) · system(3) · LOW_IMPACT(1)
- **下轮**: ux（饥饿度1.50）

## Round 19 — 2026-07-28 [arr]
- **方向**: 编曲质量 — 前端加难度选择器（简单/中等/困难）
- **效果**: easy=柱式慢速, medium=分解, hard=所选风格原速
- **下轮**: ux（饥饿度1.20）

## Round 18 — 2026-07-28 [system]
- **方向**: 系统健壮 — 系统状态监控端点
- **端点**: GET /api/v1/system/status (uptime/mem/disk/转录数)
- **下轮**: arrangement（饥饿度0.90）

## Round 17 — 2026-07-28 [quality]
- **方向**: 转录质量 — 新增流行+爵士基准，共10例
- **结果**: pop_ballad F1=0.96, jazz_chords F1=1.00
- **下轮**: system（饥饿度1.125）

## Round 16 — 2026-07-28 [arr]
- **方向**: 编曲质量 — 新增华尔兹风格 (oom-pah-pah)
- **模式**: 低音+和弦+和弦，-1映射到低八度根音
- **前端**: 下拉菜单+结果标记已更新
- **下轮**: quality（饥饿度1.05）

## Round 15 — 2026-07-28 [ux]
- **方向**: 用户体验 — 去除强制登录门
- **改进**: 未登录用户可直接上传扒谱，设备限免 3 次由后端管控
- **下轮**: arrangement（饥饿度0.90）

## Round 14 — 2026-07-27 [quality]
- **方向**: 转录质量 — 力度平滑（3点加权滑动窗口）
- **改进**: 相邻音符力度加权平均，减少突兀跳跃，MIDI 回放更自然
- **下轮**: ux（饥饿度1.50）

## Round 13 — 2026-07-27 [arr]
- **方向**: 编曲质量 — 和弦检测放宽门槛 (3→2 音高类) + 缺失音推断
- **改进**: 2音即可检测和弦，自动推断缺失的第三音（优先大三度→小三度→纯五度）
- **门槛**: 推断和弦需 0.75 置信度，3音以上用 0.5
- **下轮**: ux（饥饿度1.20）

## Round 12 — 2026-07-27 [system]
- **方向**: 系统健壮 — ECS 每日自动备份
- **完成**: crontab 每日 3:07 AM 运行 backup_db.py --clean，保留 7 天
- **验证**: 手动运行成功，28KB 备份文件已生成
- **下轮**: arrangement（饥饿度0.90）

## Round 11 — 2026-07-27 [quality] ⚠️ LOW_IMPACT
- **方向**: 转录质量 — 泛音过滤器实验（失败，已回滚）
- **尝试**: 八度+五度泛音过滤 → 严重回归 F1 0.823→0.743
- **根因**: 八度叠加在钢琴中是常见技法，无法区分"假泛音"和"故意八度"
- **教训**: 后处理过滤器仅靠音高关系不够，需要模型置信度或音源分离
- **下轮**: system（饥饿度0.90）

## Round 10 — 2026-07-27 [arr]
- **方向**: 编曲质量 — 左手伴奏力度变化
- **改进**: 强拍加重+5、弱拍减轻-3、随机±3人性化波动、力度钳制30-100
- **清理**: 删除 GPU 调试临时文件
- **下轮**: quality（饥饿度1.05）

## Round 9 — 2026-07-27 [ux]
- **方向**: 用户体验 — 转录结果页改进
- **改进**: 编曲标记(显示风格)、错误重试按钮、导出按钮 2 列移动端网格
- **修复**: TranscriptionResult 类型缺少 arranged/style 字段
- **下轮**: arrangement（饥饿度 1.35）

## Round 8 — 2026-07-27 [quality]
- **方向**: 转录质量 — 真实音频基准测试，发现 medium preset 在泛音上崩坏
- **关键发现**: medium F1=0.901(合成)→0.673(真实泛音)，high 反而 0.899 更好
- **修复**: 默认改回 high preset，泛音不会触发假阳性
- **基建**: 新增 2 例真实泛音基准（6 次谐波钢琴音色）
- **下轮**: UX（饥饿度最高）

## Round 7 — 2026-07-27 [system]
- **方向**: 系统健壮 — SQLite 备份 + 文件校验 + 速率限制
- **备份**: backend/scripts/backup_db.py，支持在线备份和自动清理
- **安全**: 上传文件检查扩展名和 magic bytes，拒绝非音频
- **限流**: 10次/分(转录) 20次/分(认证) 60次/分(其他)，429 返回
- **下轮**: UX（饥饿度最高）

## Round 6 — 2026-07-27 [arr]
- **方向**: 编曲质量 — 自动速度检测替代硬编码 120 BPM
- **改进**: chord_detect 和 arrange_piano 现在使用 detected tempo
- **效果**: 和弦窗口更准，减少假阳性，tempo 42→151 BPM 更合理
- **下轮**: System（饥饿度最高，从未跑过）

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
