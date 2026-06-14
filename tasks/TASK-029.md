---
id: TASK-029
title: 实现素材生成服务模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现素材生成服务，包括标题生成、摘要生成、缩略图生成。

# 验收标准 (Acceptance Criteria)
- [x] 独立 LLM 实例配置 - LLMInstance, LLMInstanceManager 支持独立配置
- [x] 标题候选生成 - TitleGenerator 支持多平台风格、emoji 选项
- [x] 摘要生成（首尾字幕摘取）- SummaryGenerator + SubtitleExtractor.extract_head_tail()
- [x] 视频截帧缩略图 - ThumbnailGenerator._extract_frame() 使用 FFmpeg
- [x] AI 绘图缩略图（可选）- ThumbnailGenerator._generate_ai_thumbnail() 支持 DALL-E
- [x] 进度上报 - execute() 方法按阶段上报进度

# 上下文 (Context)
- 参考 `docs/13-服务-素材生成服务设计.md`
- 目录：`backend/services/asset_gen.py`
