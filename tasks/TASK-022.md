---
id: TASK-022
title: 实现工作进程与调度器模块
status: Review
assignee: Kiro
priority: High
---

# 任务描述
实现工作进程和调度器，负责从队列消费任务、分发执行、并发控制、时段控制、进度上报。

# 验收标准 (Acceptance Criteria)
- [x] 工作进程主循环实现
- [x] 任务分发到具体服务
- [x] 并发控制（每类型最多1个并发）
- [x] 任务时段检查
- [x] 进度回调机制
- [x] 错误处理与自动调度下一任务

# 上下文 (Context)
- 参考 `docs/05-调度-工作进程设计.md`
- 参考 `docs/06-调度-调度器设计.md`
- 目录：`backend/workers/`
