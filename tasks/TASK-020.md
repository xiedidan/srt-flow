---
id: TASK-020
title: 实现日志管理器模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现日志管理器模块，支持统一日志记录、按任务分流日志文件、结构化日志输出。

# 验收标准 (Acceptance Criteria)
- [x] 统一日志格式配置 ([时间戳] [级别] [模块] [任务ID] - 消息)
- [x] 按任务 ID 分流日志到独立文件 (TaskContext + TaskFileHandler)
- [x] 日志级别动态配置 (set_log_level)
- [x] 控制台和文件双输出 (app.log + console)
- [x] 日志轮转配置 (RotatingFileHandler, 10MB, 5 backups)

# 上下文 (Context)
- 参考 `docs/03-核心-日志管理器设计.md`
- 目录：`backend/core/logger.py`
