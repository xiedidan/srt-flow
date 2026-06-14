---
id: TASK-028
title: 实现视频合成服务模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现视频合成服务，封装 FFmpeg 命令，支持字幕烧录和音轨替换。

# 验收标准 (Acceptance Criteria)
- [x] FFmpeg 命令封装
- [x] 字幕烧录（单字幕/双字幕）
- [x] 字幕样式配置
- [x] 样式预设管理
- [x] 硬件加速支持
- [x] 进度解析与上报

# 上下文 (Context)
- 参考 `docs/12-服务-视频合成服务设计.md`
- 目录：`backend/services/synthesizer.py`
