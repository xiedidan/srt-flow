---
id: TASK-061
title: 任务调度器逻辑梳理
status: Done
assignee: Kiro
priority: Medium
---

# 任务描述
梳理任务调度器的逻辑，解决目前任务调度只能同时处理一个任务、不同种类任务不能并行的问题。

# 验收标准 (Acceptance Criteria)
- [x] 分析当前任务调度器的实现逻辑
- [x] 确认是否支持不同类型任务并行（流水线模式）
- [x] 如不支持，修改调度器实现并行处理
- [x] 确保每种任务类型最多1个并发
- [x] 更新相关文档说明调度逻辑

# 上下文 (Context)
- 来源：需求日记
- 相关文档：`docs/06-调度-调度器设计.md`
- 项目规则中提到：每种任务类型最多1个并发，不同类型可并行（流水线）

# 实现方案

## 问题分析
原有实现在 `main.py` 的 `worker_loop` 中使用单一循环顺序处理所有任务类型，每次循环只处理一个任务后就 break，导致不同类型任务无法并行。

## 解决方案
将单一 `worker_loop` 重构为多个并行的 `process_task_type` 协程：
- 每种任务类型有独立的 worker 协程
- 使用 `asyncio.create_task` 并行启动所有 worker
- 使用 `running_tasks` 字典 + `asyncio.Lock` 确保每种类型最多1个并发
- 保留所有原有的预处理和后处理逻辑

## 关键改动
1. 新增 `running_tasks: Dict[TaskType, bool]` 跟踪每种类型的运行状态
2. 新增 `running_tasks_lock` 确保并发安全
3. 将 `worker_loop` 拆分为 `process_task_type(task_type, service)` 函数
4. 启动时为每种任务类型创建独立的 asyncio task
5. 关闭时取消所有 worker tasks
