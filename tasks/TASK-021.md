---
id: TASK-021
title: 实现队列管理器模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现基于 SQLite 的持久化任务队列，支持任务入队、出队、状态管理、优先级控制。

# 验收标准 (Acceptance Criteria)
- [x] 任务队列表设计
- [x] 任务入队/出队操作
- [x] 任务状态流转（pending/running/completed/failed）
- [x] 优先级支持（插队/排队）
- [x] 按任务类型隔离队列

# 上下文 (Context)
- 参考 `docs/04-调度-队列管理器设计.md`
- 目录：`backend/workers/queue.py`
