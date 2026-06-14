# TASK-084: 视频级 Workflow、Session、Trace 数据模型设计与实现

## 任务信息

- **优先级**: 高
- **状态**: Todo
- **负责人**: 待分配
- **创建时间**: 2026-06-14
- **预计工时**: 8小时
- **来源**: 视频级 Agent 工作流架构改造方案

## 任务描述

为每个视频建立独立 Workflow、Agent Session、Trace 索引与 Workflow Node 状态模型。批量处理本质上是一组单视频 Workflow 的队列。

## 需求

1. 新增 Workflow 模型，绑定单个 `video_id`。
2. 新增 WorkflowNode 模型，记录每个步骤状态、task_id、attempt、参数摘要。
3. 新增 VideoAgentSession 模型，保存视频级对话会话、全局限制和当前活动节点。
4. 新增 VideoTrace 模型或文件索引，指向该视频的 trace 文件与 final review。
5. 提供 Repository 与基础查询方法。

## 验收标准

- [ ] 新增 ORM 模型并能自动建表
- [ ] 一个视频可创建一个 active Workflow 和 Agent Session
- [ ] WorkflowNode 可关联现有 Task
- [ ] 能按 video_id 查询 Workflow、Session、Nodes、Trace
- [ ] 不破坏现有 Task / Video 数据结构

## 相关文件

- `backend/core/models.py`
- `backend/core/repositories.py`
- `backend/core/database.py`
- `docs/02-核心-数据库管理器设计.md`

## 依赖任务

- TASK-083

