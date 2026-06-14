---
id: TASK-026
title: 实现翻译服务模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现字幕翻译服务，封装多种 LLM API，支持批次处理和故障转移。

# 验收标准 (Acceptance Criteria)
- [x] SRT 字幕解析与生成
- [x] LLM API 封装（DeepSeek/Gemini/OpenAI）
- [x] 多实例配置与故障转移
- [x] 批次处理逻辑
- [x] 翻译结果解析
- [x] 进度上报（基于批次）

# 上下文 (Context)
- 参考 `docs/10-服务-翻译服务设计.md`
- 目录：`backend/services/translator.py`
