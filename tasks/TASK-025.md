---
id: TASK-025
title: 实现语音识别服务模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现语音识别服务，集成 Whisper 本地模型和在线大模型，生成 SRT 格式字幕。

# 验收标准 (Acceptance Criteria)
- [x] Whisper 模型加载与推理
- [x] 音频提取（FFmpeg）
- [x] SRT 字幕生成
- [x] 在线大模型调用（备选）
- [x] GPU 加速支持
- [x] 进度上报

# 上下文 (Context)
- 参考 `docs/09-服务-语音识别服务设计.md`
- 目录：`backend/services/asr.py`
